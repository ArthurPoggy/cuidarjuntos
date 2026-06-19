import logging
from datetime import timedelta

from celery import shared_task
from django.db.models import Count, Q
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def notify_weekly_summary(self):
    """Envia resumo semanal de cuidados para todos os membros de cada grupo.

    Projetada para rodar toda segunda-feira às 09h00 via CELERY_BEAT_SCHEDULE.
    Cobre os 7 dias anteriores (seg–dom da semana passada).

    Idempotente por grupo + período: grava um WeeklySummaryLog após o envio
    bem-sucedido e pula grupos já registrados, evitando notificações duplicadas
    em reexecuções, deploys ou múltiplas instâncias do beat.
    """
    from care.models import CareGroup, CareRecord, GroupMembership, WeeklySummaryLog
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

    # Grupos já notificados nesta semana (idempotência) — uma única query.
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

        try:
            summary = send_push(
                user_ids=user_ids,
                title="Resumo semanal de cuidados",
                body=body,
                data={"screen": "Dashboard"},
            )
        except Exception as exc:
            logger.exception(
                "notify_weekly_summary: falha ao enviar push para grupo %s.", group.pk
            )
            raise self.retry(exc=exc)

        # send_push captura falhas de rede/Expo e devolve um resumo em vez de
        # propagar exceção; tratamos failed > 0 como entrega malsucedida.
        failed = (summary or {}).get("failed", 0)
        if failed:
            logger.warning(
                "notify_weekly_summary: %d falha(s) de entrega no grupo %s; "
                "agendando retry.",
                failed, group.pk,
            )
            raise self.retry(
                exc=RuntimeError(f"{failed} push(es) falharam no grupo {group.pk}")
            )

        # Idempotência: registra que o resumo desta semana foi enviado.
        WeeklySummaryLog.objects.get_or_create(group=group, week_start=week_start)
        logger.info(
            "notify_weekly_summary: resumo enviado para %d membro(s) do grupo %s "
            "(done=%d, missed=%d).",
            len(user_ids), group.pk, done_count, missed_count,
        )
