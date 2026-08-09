from datetime import date, time
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from care.models import CareGroup, CareRecord, GroupMembership, Patient

FAKE_TODAY = date(2026, 5, 11)
WEEK_START = date(2026, 5, 4)
WEEK_END = date(2026, 5, 10)

_OK = {"sent": 1, "failed": 0, "invalidated": 0}


def _record(patient, record_date, status):
    return CareRecord.objects.create(
        patient=patient,
        type="other",
        what="Teste",
        date=record_date,
        time=time(10, 0),
        caregiver="Cuidador",
        status=status,
    )


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
@patch("django.utils.timezone.localdate", return_value=FAKE_TODAY)
class SendWeeklyReportTaskTests(TestCase):
    """Testes da task `send_weekly_report`, disparada por grupo."""

    def setUp(self):
        self.user1 = User.objects.create_user("alice", password="pass")
        self.patient = Patient.objects.create(name="Vovó")
        self.group = CareGroup.objects.create(name="Família", patient=self.patient)
        GroupMembership.objects.create(
            user=self.user1, group=self.group, relation_to_patient="FAMILY"
        )

    @patch("api.services.push.send_push", return_value=_OK)
    def test_sends_report_for_given_group_only(self, mock_send, _mock_date):
        _record(self.patient, WEEK_START, CareRecord.Status.DONE)

        from api.tasks import send_weekly_report
        send_weekly_report.apply(args=[self.group.pk])

        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        self.assertEqual(set(kwargs["user_ids"]), {self.user1.id})

    @patch("api.services.push.send_push")
    def test_unknown_group_id_does_not_raise(self, mock_send, _mock_date):
        from api.tasks import send_weekly_report
        send_weekly_report.apply(args=[999999])

        mock_send.assert_not_called()

    @patch("api.services.push.send_push")
    def test_group_with_no_activity_is_skipped(self, mock_send, _mock_date):
        from api.tasks import send_weekly_report
        send_weekly_report.apply(args=[self.group.pk])

        mock_send.assert_not_called()
