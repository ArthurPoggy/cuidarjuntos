# care/signals.py
import logging

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


def _display_name(user):
    if not user:
        return ""
    profile = getattr(user, "profile", None)
    if profile and getattr(profile, "full_name", ""):
        return profile.full_name
    full = (user.get_full_name() or "").strip()
    return full or user.username


@receiver(post_save, sender="care.ChecklistItem")
def checklist_to_record(sender, instance, created, update_fields, **kwargs):
    """Quando um ChecklistItem é marcado como feito, cria/atualiza o CareRecord vinculado."""
    # Só age quando o campo 'done' foi salvo
    if update_fields is not None and "done" not in update_fields:
        return

    from .models import CareRecord, ChecklistItem  # import local evita circular

    if instance.done:
        if instance.linked_record_id:
            # Já existe vínculo — apenas atualiza o status
            CareRecord.objects.filter(pk=instance.linked_record_id).update(
                status=CareRecord.Status.DONE
            )
        else:
            # Cria um novo CareRecord representando essa tarefa
            patient = instance.group.patient
            actor = instance.assigned_to or instance.created_by
            record = CareRecord(
                patient=patient,
                caregiver=_display_name(actor),
                type=CareRecord.Type.OTHER,
                what=instance.title,
                date=instance.date,
                time=timezone.localtime().time(),
                status=CareRecord.Status.DONE,
                created_by=instance.created_by,
                assigned_to=instance.assigned_to,
            )
            # Evita o auto-done do save() (já queremos DONE)
            record.status = CareRecord.Status.DONE
            # Chamamos super().save() diretamente via save() normal;
            # o signal de CareRecord irá disparar mas checklist_item ainda não existe,
            # então não fará nada.
            record.save()
            # Vincula sem disparar post_save do ChecklistItem novamente
            ChecklistItem.objects.filter(pk=instance.pk).update(linked_record=record)
    else:
        if instance.linked_record_id:
            # Desmarcou — volta o registro para Pendente
            CareRecord.objects.filter(pk=instance.linked_record_id).update(
                status=CareRecord.Status.PENDING
            )


@receiver(pre_save, sender="care.CareRecord")
def cache_carerecord_prev_status(sender, instance, update_fields=None, **kwargs):
    """Guarda o status atual antes da alteração para comparação em post_save."""
    # Save parcial que não toca em 'status' não precisa da comparação: evita
    # uma query extra ao banco em cada save.
    if update_fields is not None and "status" not in update_fields:
        return
    if instance.pk:
        try:
            instance._prev_status = sender.objects.get(pk=instance.pk).status
        except sender.DoesNotExist:
            instance._prev_status = None
    else:
        instance._prev_status = None


def send_missed_notification(record):
    """Envia push de 'cuidado não realizado' a todos os membros do grupo.

    Reutilizável: chamado tanto pelo signal de CareRecord quanto pelos fluxos
    de marcação em lote (que usam QuerySet.update e não disparam signals).
    """
    from .models import GroupMembership

    try:
        group = record.patient.care_group
    except Exception:
        logger.warning(
            "send_missed_notification: registro %s sem grupo de cuidado, pulando.",
            record.pk,
        )
        return None

    user_ids = list(
        GroupMembership.objects.filter(group=group).values_list("user_id", flat=True)
    )
    if not user_ids:
        logger.debug(
            "send_missed_notification: grupo %s sem membros, pulando registro %s.",
            group.pk, record.pk,
        )
        return None

    try:
        from api.services.push import send_push
    except ImportError:
        logger.warning("send_missed_notification: api.services.push não disponível.")
        return None

    record_time = record.time.strftime("%H:%M") if record.time else ""
    # Corpo genérico: sem detalhes sensíveis (tipo/medicação) que possam
    # aparecer na tela de bloqueio fora do app autenticado. Detalhes em `data`.
    body = (
        f"Um cuidado agendado às {record_time} não foi realizado."
        if record_time else "Um cuidado agendado não foi realizado."
    )

    # Exceções de send_push propagam para que a task possa agendar retry.
    summary = send_push(
        user_ids=user_ids,
        title="Cuidado não realizado",
        body=body,
        data={"screen": "RecordDetail", "id": record.id},
    )
    logger.info(
        "send_missed_notification: push enviado para %d membro(s) (registro %s).",
        len(user_ids), record.pk,
    )
    return summary


def queue_missed_notification(record):
    """Agenda o envio do push para após o commit da transação.

    O envio real roda numa task Celery (`send_missed_notification_task`), de
    modo que a chamada externa à Expo não bloqueia a request — relevante nos
    fluxos de marcação em lote, que enfileiram uma task por registro. O
    `on_commit` garante que nada é enfileirado se a transação for revertida.

    Falhas ao enfileirar (ex.: broker indisponível) são apenas registradas em
    log para não propagar ao `on_commit` e quebrar a request; a notificação de
    "não realizado" é best-effort.
    """
    record_id = record.id

    def _dispatch():
        from api.tasks import send_missed_notification_task

        try:
            send_missed_notification_task.delay(record_id)
        except Exception:
            logger.exception(
                "queue_missed_notification: falha ao enfileirar task do registro %s.",
                record_id,
            )

    transaction.on_commit(_dispatch)


@receiver(post_save, sender="care.CareRecord")
def notify_missed_record(sender, instance, created, update_fields, **kwargs):
    """Quando status muda para MISSED, notifica todos os membros do grupo via push."""
    if created:
        return
    if update_fields is not None and "status" not in update_fields:
        return

    from .models import CareRecord  # import local evita circular

    if instance.status != CareRecord.Status.MISSED:
        return

    prev = getattr(instance, "_prev_status", None)
    if prev == CareRecord.Status.MISSED:
        return  # já estava MISSED — evita notificação duplicada

    queue_missed_notification(instance)


@receiver(post_save, sender="care.CareRecord")
def record_to_checklist(sender, instance, update_fields, **kwargs):
    """Quando o status de um CareRecord muda, atualiza o ChecklistItem vinculado (se houver)."""
    # Só age quando 'status' foi salvo
    if update_fields is not None and "status" not in update_fields:
        return

    from .models import ChecklistItem

    try:
        item = instance.checklist_item  # reverse OneToOne
    except Exception:
        return

    new_done = instance.status == "done"
    if item.done != new_done:
        ChecklistItem.objects.filter(pk=item.pk).update(done=new_done)
