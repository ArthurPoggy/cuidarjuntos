from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from .models import CareRecord, Patient
from .utils import sync_recurrence_series


class RecurrenceUtilsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="Senha123!")
        self.patient = Patient.objects.create(name="Paciente Teste")

    def test_daily_recurrence_generates_future_records(self):
        start = date.today() + timedelta(days=1)
        record = CareRecord.objects.create(
            patient=self.patient,
            caregiver="Tester",
            type=CareRecord.Type.MEDICATION,
            what="Remédio",
            date=start,
            time=time(9, 0),
            recurrence=CareRecord.Recurrence.DAILY,
            repeat_until=start + timedelta(days=2),
            created_by=self.user,
        )

        sync_recurrence_series(record)

        series_qs = CareRecord.objects.filter(recurrence_group=record.recurrence_group)
        self.assertEqual(series_qs.count(), 3)  # registro base + 2 futuras ocorrências
        future_dates = sorted(series_qs.values_list("date", flat=True))
        self.assertEqual(future_dates[0], start)
        self.assertEqual(future_dates[-1], start + timedelta(days=2))

    def test_clearing_recurrence_removes_clones(self):
        start = date.today() + timedelta(days=1)
        record = CareRecord.objects.create(
            patient=self.patient,
            caregiver="Tester",
            type=CareRecord.Type.MEAL,
            what="Lanche",
            date=start,
            time=time(15, 30),
            recurrence=CareRecord.Recurrence.WEEKLY,
            repeat_until=start + timedelta(weeks=2),
            created_by=self.user,
        )

        sync_recurrence_series(record)
        self.assertTrue(CareRecord.objects.filter(recurrence_group=record.recurrence_group).count() > 1)

        previous_group = record.recurrence_group
        record.recurrence = CareRecord.Recurrence.NONE
        record.repeat_until = None
        sync_recurrence_series(record, previous_group=previous_group)

        record.refresh_from_db()
        self.assertIsNone(record.recurrence_group)
        self.assertFalse(
            CareRecord.objects.exclude(pk=record.pk).filter(recurrence_group=previous_group).exists()
        )
