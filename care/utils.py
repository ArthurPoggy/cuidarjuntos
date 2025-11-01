# ➜ novo arquivo utilitário (ou coloque no final de models.py se preferir)
from datetime import date, timedelta
from django.db import transaction
from .models import CareRecord
import uuid

def _step(recurrence: str) -> timedelta:
    if recurrence == CareRecord.Recurrence.DAILY:
        return timedelta(days=1)
    if recurrence == CareRecord.Recurrence.WEEKLY:
        return timedelta(weeks=1)
    return timedelta(0)

@transaction.atomic
def expand_recurrence(base: CareRecord):
    """
    Cria as próximas ocorrências a partir de `base.date` (exclui a base),
    até `base.repeat_until` (inclusive), copiando campos relevantes.
    """
    if base.recurrence == CareRecord.Recurrence.NONE or not base.repeat_until:
        return

    step = _step(base.recurrence)
    if step.days == 0:
        return

    series = base.series_id or uuid.uuid4()
    base.series_id = series
    base.save(update_fields=["series_id"])

    d = base.date + step
    while d <= base.repeat_until:
        CareRecord.objects.create(
            series_id=series,
            recurrence=base.recurrence,
            repeat_until=base.repeat_until,
            # copiar dados do registro
            patient=base.patient,
            type=base.type,
            date=d,
            time=base.time,
            what=base.what,
            description=base.description,
            caregiver=base.caregiver,
            created_by=base.created_by,
            # status padrão do seu modelo se houver (ex.: pendente)
        )
        d += step
