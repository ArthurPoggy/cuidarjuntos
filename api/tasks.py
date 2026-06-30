import logging
from datetime import timedelta

from celery import shared_task
from django.db.models import Count, Q
from django.utils import timezone

from care.models import CareRecord, GroupMembership

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def notify_upcoming_records(self):
    """Busca registros PENDING nos próximos 30min e envia push ao responsável.

    Idempotente: cada registro só gera notificação uma vez. Antes de enviar,
    o registro é "reivindicado" com um UPDATE atômico condicional
    (`notified_at IS NULL` -> `notified_at = now`); se outra instância já o
    reivindicou, esta execução o pula — evitando push duplicado mesmo com
    múltiplos workers/beats concorrentes. Em qualquer falha de entrega
    (exceção, `failed > 0`, ou nenhum push entregue por ausência de token) o
    `notified_at` é revertido para `NULL`, de modo que o registro volta a ser
    elegível num próximo beat (dentro da janela) em vez de ficar marcado como
    notificado sem nunca ter sido entregue.
    """
    now_local = timezone.localtime(timezone.now())
    today = now_local.date()
    in_30min = now_local + timedelta(minutes=30)

    if in_30min.date() == today:
        records_qs = CareRecord.objects.filter(
            status=CareRecord.Status.PENDING,
            notified_at__isnull=True,
            date=today,
            time__gt=now_local.time(),
            time__lte=in_30min.time(),
        ).select_related("patient__care_group", "assigned_to")
    else:
        # Janela cruza meia-noite
        tomorrow = today + timedelta(days=1)
        records_qs = CareRecord.objects.filter(
            status=CareRecord.Status.PENDING,
            notified_at__isnull=True,
        ).filter(
            Q(date=today, time__gt=now_local.time()) |
            Q(date=tomorrow, time__lte=in_30min.time())
        ).select_related("patient__care_group", "assigned_to")

    if not records_qs.exists():
        logger.info("notify_upcoming_records: nenhum registro pendente na janela.")
        return

    from api.services.push import send_push

    for record in records_qs:
        try:
            group = record.patient.care_group
        except Exception:
            logger.warning(
                "notify_upcoming_records: registro %d sem grupo de cuidado, pulando.",
                record.id,
            )
            continue

        if record.assigned_to_id:
            user_ids = [record.assigned_to_id]
        else:
            user_ids = list(
                GroupMembership.objects.filter(group=group)
                .values_list("user_id", flat=True)
            )

        if not user_ids:
            logger.debug(
                "notify_upcoming_records: grupo %d sem membros, pulando registro %d.",
                group.id, record.id,
            )
            continue

        record_time = record.time.strftime("%H:%M")
        title = "Lembrete de Cuidado"
        # Corpo genérico: sem detalhes sensíveis (tipo/medicação) que possam
        # aparecer na tela de bloqueio fora do app autenticado. Os detalhes
        # seguem em `data` para o app buscar após autenticação.
        body = f"Você tem um cuidado agendado às {record_time}."

        # Claim atômico: só prossegue quem conseguir transicionar notified_at
        # de NULL para "agora". Se rowcount == 0, outra instância já
        # reivindicou o registro neste intervalo -> pulamos para evitar
        # notificação duplicada.
        claimed_at = timezone.now()
        claimed = CareRecord.objects.filter(
            id=record.id, notified_at__isnull=True
        ).update(notified_at=claimed_at)
        if not claimed:
            logger.debug(
                "notify_upcoming_records: registro %d já reivindicado por outra "
                "instância, pulando.",
                record.id,
            )
            continue

        def _release_claim():
            """Reverte o claim para que o registro volte a ser elegível."""
            CareRecord.objects.filter(
                id=record.id, notified_at=claimed_at
            ).update(notified_at=None)

        try:
            summary = send_push(
                user_ids=user_ids,
                title=title,
                body=body,
                data={"screen": "RecordDetail", "id": record.id},
            )
        except Exception as exc:
            _release_claim()
            logger.exception(
                "notify_upcoming_records: falha ao enviar notificação para registro %d.",
                record.id,
            )
            raise self.retry(exc=exc)

        # send_push captura falhas de rede/Expo e devolve um resumo em vez de
        # propagar exceção. Tratamos failed > 0 como entrega malsucedida.
        summary = summary or {}
        failed = summary.get("failed", 0)
        sent = summary.get("sent", 0)

        if failed:
            _release_claim()
            logger.warning(
                "notify_upcoming_records: %d falha(s) de entrega no registro %d; "
                "agendando retry.",
                failed,
                record.id,
            )
            raise self.retry(
                exc=RuntimeError(f"{failed} push(es) falharam no registro {record.id}")
            )

        if not sent:
            # Nenhum push entregue (ex.: destinatário sem token ativo). Não
            # houve entrega, então liberamos o claim para que o registro
            # continue elegível caso um token apareça dentro da janela, em vez
            # de marcá-lo como notificado permanentemente.
            _release_claim()
            logger.info(
                "notify_upcoming_records: nenhum token ativo para o registro %d; "
                "claim liberado.",
                record.id,
            )
            continue

        logger.info(
            "notify_upcoming_records: notificação enviada para %d usuário(s) "
            "(registro %d).",
            sent,
            record.id,
        )


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def notify_weekly_summary(self):
    """Envia resumo semanal de cuidados para todos os membros de cada grupo.

    Projetada para rodar toda segunda-feira às 09h00 via CELERY_BEAT_SCHEDULE.
    Cobre os 7 dias anteriores (seg–dom da semana passada).

    Idempotência + concorrência: cada grupo é "reivindicado" criando o
    WeeklySummaryLog (UniqueConstraint group+week_start) ANTES do envio. Só a
    instância que cria o log prossegue; concorrentes recebem created=False e
    pulam. Se o envio falhar totalmente (exceção ou nenhum push entregue), o
    log é removido para o grupo voltar a ser elegível num próximo retry. Em
    entrega parcial (sent > 0 e failed > 0) o log é mantido e o envio NÃO é
    refeito, para não notificar novamente quem já recebeu.
    """
    from care.models import CareGroup, WeeklySummaryLog
    from api.services.push import send_push

    today = timezone.localdate()
    week_start = today - timedelta(days=7)
    week_end = today - timedelta(days=1)

    groups = list(CareGroup.objects.select_related("patient").all())

    if not groups:
        logger.info("notify_weekly_summary: nenhum grupo encontrado.")
        return

    group_ids = [g.id for g in groups]
    patient_ids = [g.patient_id for g in groups]

    # Contagens done/missed por paciente — uma única query agregada.
    counts_by_patient = {
        row["patient_id"]: (row["done"], row["missed"])
        for row in (
            CareRecord.objects
            .filter(patient_id__in=patient_ids, date__range=(week_start, week_end))
            .values("patient_id")
            .annotate(
                done=Count("id", filter=Q(status=CareRecord.Status.DONE)),
                missed=Count("id", filter=Q(status=CareRecord.Status.MISSED)),
            )
        )
    }

    # Membros por grupo — uma única query.
    members_by_group = {}
    for gid, uid in (
        GroupMembership.objects.filter(group_id__in=group_ids)
        .values_list("group_id", "user_id")
    ):
        members_by_group.setdefault(gid, []).append(uid)

    # Grupos já notificados nesta semana — fast-path para evitar get_or_create
    # desnecessário; o claim autoritativo é o get_or_create abaixo.
    already_notified = set(
        WeeklySummaryLog.objects
        .filter(group_id__in=group_ids, week_start=week_start)
        .values_list("group_id", flat=True)
    )

    for group in groups:
        if group.id in already_notified:
            logger.debug(
                "notify_weekly_summary: grupo %s já notificado na semana %s, pulando.",
                group.pk, week_start,
            )
            continue

        done_count, missed_count = counts_by_patient.get(group.patient_id, (0, 0))

        if done_count == 0 and missed_count == 0:
            logger.debug(
                "notify_weekly_summary: grupo %s sem atividade na semana, pulando.",
                group.pk,
            )
            continue

        user_ids = members_by_group.get(group.id, [])

        if not user_ids:
            logger.debug(
                "notify_weekly_summary: grupo %s sem membros, pulando.", group.pk
            )
            continue

        body = (
            f"{done_count} realizado{'s' if done_count != 1 else ''}, "
            f"{missed_count} não realizado{'s' if missed_count != 1 else ''} "
            f"na última semana."
        )

        # Claim atômico: cria o log ANTES do envio. get_or_create depende da
        # UniqueConstraint(group, week_start); concorrentes recebem
        # created=False e não reenviam.
        log, created = WeeklySummaryLog.objects.get_or_create(
            group=group, week_start=week_start
        )
        if not created:
            logger.debug(
                "notify_weekly_summary: grupo %s já reivindicado por outra "
                "instância na semana %s, pulando.",
                group.pk, week_start,
            )
            continue

        def _release_claim():
            """Remove o log para o grupo voltar a ser elegível num retry."""
            WeeklySummaryLog.objects.filter(pk=log.pk).delete()

        try:
            summary = send_push(
                user_ids=user_ids,
                title="Resumo semanal de cuidados",
                body=body,
                data={"screen": "Dashboard"},
            )
        except Exception as exc:
            _release_claim()
            logger.exception(
                "notify_weekly_summary: falha ao enviar push para grupo %s.", group.pk
            )
            raise self.retry(exc=exc)

        summary = summary or {}
        failed = summary.get("failed", 0)
        sent = summary.get("sent", 0)

        if not sent:
            # Nenhum push entregue: ou não há tokens ativos, ou todos falharam.
            # Liberamos o claim. Só agendamos retry se houve falha de fato
            # (failed > 0); ausência de token não justifica retry.
            _release_claim()
            if failed:
                logger.warning(
                    "notify_weekly_summary: 0 entregues e %d falha(s) no grupo %s; "
                    "agendando retry.",
                    failed, group.pk,
                )
                raise self.retry(
                    exc=RuntimeError(f"{failed} push(es) falharam no grupo {group.pk}")
                )
            logger.info(
                "notify_weekly_summary: grupo %s sem token ativo; claim liberado.",
                group.pk,
            )
            continue

        # sent > 0: mantemos o log (idempotência). Em entrega parcial NÃO
        # refazemos o envio, para não notificar de novo quem já recebeu — o
        # retry do lote inteiro reenviaria para todos.
        if failed:
            logger.warning(
                "notify_weekly_summary: entrega parcial no grupo %s "
                "(sent=%d, failed=%d); log mantido, sem retry.",
                group.pk, sent, failed,
            )
        else:
            logger.info(
                "notify_weekly_summary: resumo enviado para %d membro(s) do grupo %s "
                "(done=%d, missed=%d).",
                sent, group.pk, done_count, missed_count,
            )
