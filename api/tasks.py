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


# Reivindicação sem entrega confirmada por mais tempo que isso é considerada
# abandonada (worker morreu entre o claim e o envio) e pode ser refeita.
WEEKLY_SUMMARY_STALE_CLAIM = timedelta(minutes=15)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def notify_weekly_summary(self):
    """Envia resumo semanal de cuidados para todos os membros de cada grupo.

    Projetada para rodar toda segunda-feira às 09h00 via CELERY_BEAT_SCHEDULE.
    Cobre os 7 dias anteriores (seg–dom da semana passada).

    Idempotência + concorrência: cada grupo é "reivindicado" criando o
    WeeklySummaryLog (UniqueConstraint group+week_start) ANTES do envio, com
    `delivered_at` ainda nulo — o claim marca "processando", não "enviado".
    Só a instância que cria o log prossegue; concorrentes recebem
    created=False e pulam. `delivered_at` só é preenchido após confirmar
    sent > 0, então se o worker morrer entre o claim e o envio (ex.: kill -9,
    OOM — não uma exceção Python capturável), o grupo fica com um claim
    "pendurado" em vez de marcado como notificado; claims mais velhos que
    WEEKLY_SUMMARY_STALE_CLAIM sem `delivered_at` são tratados como
    abandonados e reprocessados. Se o envio falhar totalmente (exceção ou
    nenhum push entregue), o log é removido para o grupo voltar a ser
    elegível num próximo retry. Em entrega parcial (sent > 0 e failed > 0) o
    log é marcado como entregue e o envio NÃO é refeito, para não notificar
    novamente quem já recebeu.

    Uma falha (exceção ou entrega=0) num grupo não interrompe os demais: é
    registrada e a task só agenda retry do lote (via idempotência, grupos já
    entregues são pulados) depois de tentar todos os grupos.
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

    # Logs existentes desta semana — fast-path para evitar get_or_create
    # desnecessário; o claim autoritativo continua sendo o get_or_create
    # abaixo. Indexado por grupo para decidir entre "já entregue", "em
    # andamento por outra instância" ou "claim abandonado" (ver docstring).
    logs_by_group = {
        log.group_id: log
        for log in WeeklySummaryLog.objects.filter(
            group_id__in=group_ids, week_start=week_start
        )
    }

    stale_before = timezone.now() - WEEKLY_SUMMARY_STALE_CLAIM
    needs_retry = False

    for group in groups:
        existing_log = logs_by_group.get(group.id)
        if existing_log is not None:
            if existing_log.delivered_at is not None:
                logger.debug(
                    "notify_weekly_summary: grupo %s já notificado na semana "
                    "%s, pulando.",
                    group.pk, week_start,
                )
                continue
            if existing_log.claimed_at >= stale_before:
                logger.debug(
                    "notify_weekly_summary: grupo %s reivindicado recentemente "
                    "por outra instância na semana %s, pulando.",
                    group.pk, week_start,
                )
                continue
            # Claim antigo sem entrega confirmada: worker provavelmente
            # morreu no meio do envio. Libera para reprocessar agora.
            logger.warning(
                "notify_weekly_summary: claim abandonado (sem entrega desde "
                "%s) no grupo %s; reprocessando.",
                existing_log.claimed_at, group.pk,
            )
            WeeklySummaryLog.objects.filter(pk=existing_log.pk).delete()

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

        # Claim atômico: cria o log ANTES do envio, com delivered_at nulo.
        # get_or_create depende da UniqueConstraint(group, week_start);
        # concorrentes recebem created=False e não reenviam.
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

        def _release_claim(log=log):
            """Remove o log para o grupo voltar a ser elegível num retry."""
            WeeklySummaryLog.objects.filter(pk=log.pk).delete()

        # Falha aqui (exceção ou entrega=0) não deve impedir o processamento
        # dos demais grupos do lote — só marca que o lote precisa de retry.
        try:
            summary = send_push(
                user_ids=user_ids,
                title="Resumo semanal de cuidados",
                body=body,
                data={"screen": "Dashboard"},
            )
        except Exception:
            _release_claim()
            logger.exception(
                "notify_weekly_summary: falha ao enviar push para grupo %s.", group.pk
            )
            needs_retry = True
            continue

        summary = summary or {}
        failed = summary.get("failed", 0)
        sent = summary.get("sent", 0)

        if not sent:
            # Nenhum push entregue: ou não há tokens ativos, ou todos falharam.
            # Liberamos o claim. Só marcamos o lote para retry se houve falha
            # de fato (failed > 0); ausência de token não justifica retry.
            _release_claim()
            if failed:
                logger.warning(
                    "notify_weekly_summary: 0 entregues e %d falha(s) no grupo %s; "
                    "lote será reagendado.",
                    failed, group.pk,
                )
                needs_retry = True
            else:
                logger.info(
                    "notify_weekly_summary: grupo %s sem token ativo; claim liberado.",
                    group.pk,
                )
            continue

        # sent > 0: marcamos o log como entregue (idempotência). Em entrega
        # parcial NÃO refazemos o envio, para não notificar de novo quem já
        # recebeu — o retry do lote inteiro reenviaria para todos.
        log.delivered_at = timezone.now()
        log.save(update_fields=["delivered_at"])

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

    if needs_retry:
        raise self.retry(
            exc=RuntimeError("notify_weekly_summary: um ou mais grupos falharam no lote")
        )
