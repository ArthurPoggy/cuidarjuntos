# care/signals.py
import logging

from django.db import transaction
from django.db.models.signals import post_save
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


@receiver(post_save, sender="care.RecordComment")
def notify_comment_created(sender, instance, created, **kwargs):
    """Quando novo comentário é criado, notifica o created_by do registro."""
    if not created:
        return

    from .models import GroupMembership

    record = instance.record
    record_author = record.created_by

    if not record_author or record_author.id == instance.user_id:
        return

    # Segurança: só notifica o autor se ele ainda pertencer ao grupo do
    # paciente. Caso tenha saído do grupo, não deve mais receber dados de
    # saúde de novos comentários.
    try:
        group = record.patient.care_group
    except Exception:
        logger.warning(
            "notify_comment_created: registro %s sem grupo de cuidado, pulando.",
            record.pk,
        )
        return

    if not GroupMembership.objects.filter(
        group=group, user_id=record_author.id
    ).exists():
        logger.debug(
            "notify_comment_created: autor %s não é mais membro do grupo %s, pulando.",
            record_author.pk, group.pk,
        )
        return

    commenter_name = _display_name(instance.user)
    author_id = record_author.id
    record_id = record.id

    def _dispatch():
        # O envio real (chamada externa à Expo) roda em background via Celery,
        # para não bloquear/antecipar a transação de escrita. As checagens de
        # elegibilidade acima já rodaram de forma síncrona, então só registros
        # válidos chegam a enfileirar uma task.
        from api.tasks import send_comment_notification_task

        try:
            send_comment_notification_task.delay(author_id, record_id, commenter_name)
        except Exception:
            # Falha ao enfileirar (ex.: broker indisponível) é apenas
            # registrada em log, sem propagar ao on_commit e sem retry aqui —
            # a notificação de comentário é best-effort, e propagar quebraria
            # a request mesmo com o comentário já salvo com sucesso.
            logger.exception(
                "notify_comment_created: falha ao enfileirar task do registro %s.",
                record_id,
            )

    transaction.on_commit(_dispatch)
