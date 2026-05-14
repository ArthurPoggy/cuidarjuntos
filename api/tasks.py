import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def notify_weekly_summary(self):
    """Envia resumo semanal de cuidados para todos os membros de cada grupo.

    Projetada para rodar toda segunda-feira às 09h00 via CELERY_BEAT_SCHEDULE.
    Cobre os 7 dias anteriores (seg–dom da semana passada).

    Idempotente: apenas lê dados do banco e envia push — reexecutar na
    mesma segunda-feira envia a notificação novamente, o que é aceitável
    (sem escrita duplicada no banco).
    """
    from care.models import CareGroup, CareRecord, GroupMembership
    from api.services.push import send_push

    today = timezone.localdate()
    week_start = today - timedelta(days=7)
    week_end = today - timedelta(days=1)

    groups = CareGroup.objects.select_related("patient").all()

    if not groups.exists():
        logger.info("notify_weekly_summary: nenhum grupo encontrado.")
        return

    for group in groups:
        records_qs = CareRecord.objects.filter(
            patient=group.patient,
            date__range=(week_start, week_end),
        )

        done_count = records_qs.filter(status=CareRecord.Status.DONE).count()
        missed_count = records_qs.filter(status=CareRecord.Status.MISSED).count()

        if done_count == 0 and missed_count == 0:
            logger.debug(
                "notify_weekly_summary: grupo %s sem atividade na semana, pulando.",
                group.pk,
            )
            continue

        user_ids = list(
            GroupMembership.objects.filter(group=group)
            .values_list("user_id", flat=True)
        )

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

        try:
            send_push(
                user_ids=user_ids,
                title="Resumo semanal de cuidados",
                body=body,
                data={"screen": "Dashboard"},
            )
            logger.info(
                "notify_weekly_summary: resumo enviado para %d membro(s) do grupo %s "
                "(done=%d, missed=%d).",
                len(user_ids), group.pk, done_count, missed_count,
            )
        except Exception as exc:
            logger.exception(
                "notify_weekly_summary: falha ao enviar push para grupo %s.", group.pk
            )
            raise self.retry(exc=exc)
