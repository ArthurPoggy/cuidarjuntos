# care/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


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
