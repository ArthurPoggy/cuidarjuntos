# care/utils.py
from __future__ import annotations

import uuid
from calendar import monthrange
from datetime import date, timedelta
from typing import Optional

from django.db import transaction

from .models import CareRecord


def _advance_date(current: date, recurrence: str) -> Optional[date]:
    if recurrence == CareRecord.Recurrence.DAILY:
        return current + timedelta(days=1)
    if recurrence == CareRecord.Recurrence.WEEKLY:
        return current + timedelta(weeks=1)
    if recurrence == CareRecord.Recurrence.MONTHLY:
        year = current.year + (current.month // 12)
        month = (current.month % 12) + 1
        # garante que o dia exista no mês alvo
        day = min(current.day, monthrange(year, month)[1])
        return current.replace(year=year, month=month, day=day)
    return None


def _clear_series(base: CareRecord, group_id):
    if group_id:
        CareRecord.objects.filter(recurrence_group=group_id).exclude(pk=base.pk).delete()
    if (
        base.recurrence_group
        or base.recurrence != CareRecord.Recurrence.NONE
        or base.repeat_until
    ):
        base.recurrence_group = None
        base.recurrence = CareRecord.Recurrence.NONE
        base.repeat_until = None
        base.save(update_fields=["recurrence_group", "recurrence", "repeat_until"])


@transaction.atomic
def sync_recurrence_series(base: CareRecord, previous_group=None):
    """
    Garante que as ocorrências recorrentes estejam em sincronia com o registro-base.
    - Quando sem recorrência: remove futuras ocorrências e limpa campos.
    - Quando recorrente: recria a série a partir do próximo agendamento até repeat_until.
    """
    recurrence = (base.recurrence or CareRecord.Recurrence.NONE).lower()
    until = base.repeat_until
    if (
        recurrence == CareRecord.Recurrence.NONE
        or not until
        or not base.date
        or until < base.date
    ):
        _clear_series(base, previous_group or base.recurrence_group)
        return

    step_source = base.date
    group_id = previous_group or base.recurrence_group or uuid.uuid4()

    # garante que o registro atual armazenará o identificador e os campos da recorrência
    base.recurrence_group = group_id
    base.recurrence = recurrence
    base.repeat_until = until
    base.save(update_fields=["recurrence_group", "recurrence", "repeat_until"])

    CareRecord.objects.filter(recurrence_group=group_id).exclude(pk=base.pk).delete()

    clones = []
    cursor = step_source
    while True:
        cursor = _advance_date(cursor, recurrence)
        if cursor is None or cursor > until:
            break
        clones.append(
            CareRecord(
                recurrence_group=group_id,
                recurrence=recurrence,
                repeat_until=until,
                patient=base.patient,
                caregiver=base.caregiver,
                type=base.type,
                what=base.what,
                medication=base.medication,
                capsule_quantity=base.capsule_quantity,
                description=base.description,
                progress_trend=base.progress_trend,
                is_exception=base.is_exception,
                date=cursor,
                time=base.time,
                status=CareRecord.Status.PENDING,
                created_by=base.created_by,
            )
        )

    if clones:
        CareRecord.objects.bulk_create(clones, ignore_conflicts=True)
