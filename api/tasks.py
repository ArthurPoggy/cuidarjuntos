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

    Idempotente: cada registro só gera notificação uma vez. Após o envio
    bem-sucedido grava-se `notified_at`, e a query ignora registros já
    notificados. Isso protege contra retries, execuções manuais e múltiplas
    instâncias do beat. Falha de entrega (exceção ou `failed > 0` no retorno
    de `send_push`) dispara `self.retry` sem marcar `notified_at`.
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

        try:
            summary = send_push(
                user_ids=user_ids,
                title=title,
                body=body,
                data={"screen": "RecordDetail", "id": record.id},
            )
        except Exception as exc:
            logger.exception(
                "notify_upcoming_records: falha ao enviar notificação para registro %d.",
                record.id,
            )
            raise self.retry(exc=exc)

        # send_push captura falhas de rede/Expo e devolve um resumo em vez de
        # propagar exceção. Tratamos failed > 0 como entrega malsucedida.
        failed = (summary or {}).get("failed", 0)
        if failed:
            logger.warning(
                "notify_upcoming_records: %d falha(s) de entrega no registro %d; "
                "agendando retry.",
                failed,
                record.id,
            )
            raise self.retry(
                exc=RuntimeError(f"{failed} push(es) falharam no registro {record.id}")
            )

        record.notified_at = timezone.now()
        record.save(update_fields=["notified_at"])
        logger.info(
            "notify_upcoming_records: notificação enviada para %d usuário(s) "
            "(registro %d).",
            len(user_ids),
            record.id,
        )
