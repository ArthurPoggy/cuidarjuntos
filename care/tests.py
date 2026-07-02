from datetime import date, time, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import CareGroup, CareRecord, GroupMembership, Patient
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


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class WebBulkMissedNotificationTests(TestCase):
    """Endpoint web (care:record-bulk-set-status) também deve notificar em lote.

    Cobre o mesmo cenário de BulkMissedNotificationTests (em
    api/tests/test_signals.py), mas para o fluxo web, que reimplementa a
    marcação em lote via QuerySet.update separadamente do endpoint da API.
    """

    def setUp(self):
        self.user1 = User.objects.create_user("alice", password="pass")
        self.user2 = User.objects.create_user("bob", password="pass")
        self.patient = Patient.objects.create(name="Vovó")
        self.group = CareGroup.objects.create(name="Família", patient=self.patient)
        GroupMembership.objects.create(
            user=self.user1, group=self.group, relation_to_patient="FAMILY"
        )
        GroupMembership.objects.create(
            user=self.user2, group=self.group, relation_to_patient="CAREGIVER"
        )
        self.client.force_login(self.user1)

    def _pending(self):
        return CareRecord.objects.create(
            patient=self.patient, type="medication", what="Remédio",
            date=date(2026, 6, 1), time=time(9, 0),
            caregiver="Cuidador", status=CareRecord.Status.PENDING,
        )

    @patch("api.services.push.send_push")
    def test_bulk_missed_notifies_each_record(self, mock_send):
        r1 = self._pending()
        r2 = self._pending()

        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post(
                reverse("care:record-bulk-set-status"),
                {"ids": f"{r1.id},{r2.id}", "status": "missed"},
            )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(mock_send.call_count, 2)
        r1.refresh_from_db()
        self.assertEqual(r1.status, CareRecord.Status.MISSED)

    @patch("api.services.push.send_push")
    def test_bulk_missed_skips_already_missed(self, mock_send):
        already = self._pending()
        already.status = CareRecord.Status.MISSED
        already.save(update_fields=["status"])
        mock_send.reset_mock()

        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post(
                reverse("care:record-bulk-set-status"),
                {"ids": str(already.id), "status": "missed"},
            )

        self.assertEqual(resp.status_code, 200)
        mock_send.assert_not_called()
