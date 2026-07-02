import logging
from datetime import timedelta

from celery import shared_task
from django.db.models import Q
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
def send_comment_notification_task(self, user_id, record_id, commenter_name):
    """Envia, em background, o push de "novo comentário" ao autor do registro.

    Disparada por `care.signals.notify_comment_created` via
    `transaction.on_commit`, de modo que a chamada externa à Expo não bloqueia
    a request. As checagens de elegibilidade (autor existe, não é o próprio
    comentarista, ainda pertence ao grupo) já rodaram de forma síncrona no
    signal, mas entre o enfileiramento e a execução da task o usuário pode ter
    saído do grupo — por isso a pertença ao grupo é revalidada aqui, logo
    antes do envio, já que a notificação carrega dado de cuidado/saúde. Em
    falha de entrega (exceção ou `failed > 0`) agenda retry.
    """
    from api.services.push import send_push

    try:
        record = CareRecord.objects.select_related("patient__care_group").get(pk=record_id)
    except CareRecord.DoesNotExist:
        logger.warning(
            "send_comment_notification_task: registro %s não existe mais, pulando.",
            record_id,
        )
        return

    try:
        group = record.patient.care_group
    except Exception:
        group = None
    if not group or not GroupMembership.objects.filter(group=group, user_id=user_id).exists():
        logger.info(
            "send_comment_notification_task: usuário %s não é mais membro do "
            "grupo do registro %s, pulando envio.",
            user_id,
            record_id,
        )
        return

    # Corpo neutro: não inclui o conteúdo do registro para não vazar dados de
    # saúde na tela de bloqueio; detalhes seguem em `data`.
    body = f"{commenter_name} comentou em um registro."

    try:
        summary = send_push(
            user_ids=[user_id],
            title="Novo comentário",
            body=body,
            data={"screen": "RecordDetail", "id": record_id},
        )
    except Exception as exc:
        logger.exception(
            "send_comment_notification_task: falha ao enviar push do registro %s.",
            record_id,
        )
        raise self.retry(exc=exc)

    failed = (summary or {}).get("failed", 0)
    if failed:
        logger.warning(
            "send_comment_notification_task: %d falha(s) de entrega no registro %s; "
            "agendando retry.",
            failed,
            record_id,
        )
        raise self.retry(
            exc=RuntimeError(f"{failed} push(es) falharam no registro {record_id}")
        )


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_missed_notification_task(self, record_id):
    """Envia, em background, o push de "cuidado não realizado" de um registro.

    Disparada por `care.signals.queue_missed_notification` via
    `transaction.on_commit`, de modo que a chamada externa à Expo não bloqueia
    a request (especialmente nos fluxos de marcação em lote, que enfileiram
    uma task por registro). Em falha de entrega (exceção ou `failed > 0` no
    retorno de `send_push`) agenda retry.
    """
    from care.models import CareRecord
    from care.signals import send_missed_notification

    try:
        record = CareRecord.objects.select_related("patient__care_group").get(
            pk=record_id
        )
    except CareRecord.DoesNotExist:
        logger.warning(
            "send_missed_notification_task: registro %s não existe mais, ignorando.",
            record_id,
        )
        return

    try:
        summary = send_missed_notification(record)
    except Exception as exc:
        logger.exception(
            "send_missed_notification_task: falha ao enviar push do registro %s.",
            record_id,
        )
        raise self.retry(exc=exc)

    failed = (summary or {}).get("failed", 0)
    if failed:
        logger.warning(
            "send_missed_notification_task: %d falha(s) de entrega no registro %s; "
            "agendando retry.",
            failed,
            record_id,
        )
        raise self.retry(
            exc=RuntimeError(f"{failed} push(es) falharam no registro {record_id}")
        )
