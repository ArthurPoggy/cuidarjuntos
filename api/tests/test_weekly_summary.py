from datetime import date, time, timedelta
from unittest.mock import call, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from care.models import CareGroup, CareRecord, GroupMembership, Patient

# "Hoje" fixo = segunda-feira 2026-05-11
# Semana coberta: 2026-05-04 (seg) a 2026-05-10 (dom)
FAKE_TODAY = date(2026, 5, 11)
WEEK_START = date(2026, 5, 4)
WEEK_END = date(2026, 5, 10)

# Resumo de envio bem-sucedido devolvido por send_push (sem falhas).
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
class NotifyWeeklySummaryTests(TestCase):
    """Testes da task notify_weekly_summary."""

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

    # ------------------------------------------------------------------
    # Cenário principal
    # ------------------------------------------------------------------

    @patch("api.services.push.send_push", return_value=_OK)
    def test_sends_summary_with_correct_counts(self, mock_send, _mock_date):
        """Grupo com atividade recebe resumo com contagens corretas."""
        _record(self.patient, WEEK_START, CareRecord.Status.DONE)
        _record(self.patient, WEEK_START, CareRecord.Status.DONE)
        _record(self.patient, WEEK_END, CareRecord.Status.MISSED)

        from api.tasks import notify_weekly_summary
        notify_weekly_summary.apply()

        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        self.assertIn("2 realizados", kwargs["body"])
        self.assertIn("1 não realizado", kwargs["body"])
        self.assertEqual(kwargs["title"], "Resumo semanal de cuidados")
        self.assertEqual(kwargs["data"]["screen"], "Dashboard")

    @patch("api.services.push.send_push", return_value=_OK)
    def test_notifies_all_group_members(self, mock_send, _mock_date):
        """Todos os membros do grupo recebem a notificação."""
        _record(self.patient, WEEK_START, CareRecord.Status.DONE)

        from api.tasks import notify_weekly_summary
        notify_weekly_summary.apply()

        _, kwargs = mock_send.call_args
        self.assertEqual(set(kwargs["user_ids"]), {self.user1.id, self.user2.id})

    # ------------------------------------------------------------------
    # Early-return / grupos ignorados
    # ------------------------------------------------------------------

    @patch("api.services.push.send_push")
    def test_no_groups_skips_send(self, mock_send, _mock_date):
        """Sem grupos cadastrados: send_push não é chamado."""
        GroupMembership.objects.all().delete()
        CareGroup.objects.all().delete()
        Patient.objects.all().delete()

        from api.tasks import notify_weekly_summary
        notify_weekly_summary.apply()

        mock_send.assert_not_called()

    @patch("api.services.push.send_push")
    def test_group_with_no_activity_is_skipped(self, mock_send, _mock_date):
        """Grupo sem registros na semana não recebe push."""
        from api.tasks import notify_weekly_summary
        notify_weekly_summary.apply()

        mock_send.assert_not_called()

    @patch("api.services.push.send_push")
    def test_group_without_members_is_skipped(self, mock_send, _mock_date):
        """Grupo sem membros não chama send_push."""
        GroupMembership.objects.all().delete()
        _record(self.patient, WEEK_START, CareRecord.Status.DONE)

        from api.tasks import notify_weekly_summary
        notify_weekly_summary.apply()

        mock_send.assert_not_called()

    # ------------------------------------------------------------------
    # Janela temporal
    # ------------------------------------------------------------------

    @patch("api.services.push.send_push")
    def test_records_outside_window_not_counted(self, mock_send, _mock_date):
        """Registros fora da janela (hoje e antes de 7 dias atrás) não entram."""
        # Hoje (2026-05-11) — fora da janela
        _record(self.patient, FAKE_TODAY, CareRecord.Status.DONE)
        # Há 8 dias (2026-05-03) — fora da janela
        _record(self.patient, FAKE_TODAY - timedelta(days=8), CareRecord.Status.DONE)

        from api.tasks import notify_weekly_summary
        notify_weekly_summary.apply()

        mock_send.assert_not_called()

    @patch("api.services.push.send_push", return_value=_OK)
    def test_boundary_dates_included(self, mock_send, _mock_date):
        """Datas nas bordas da janela (week_start e week_end) são incluídas."""
        _record(self.patient, WEEK_START, CareRecord.Status.DONE)   # borda início
        _record(self.patient, WEEK_END, CareRecord.Status.MISSED)    # borda fim

        from api.tasks import notify_weekly_summary
        notify_weekly_summary.apply()

        _, kwargs = mock_send.call_args
        self.assertIn("1 realizado", kwargs["body"])
        self.assertIn("1 não realizado", kwargs["body"])

    @patch("api.services.push.send_push")
    def test_pending_records_not_counted(self, mock_send, _mock_date):
        """Registros PENDING não entram nas contagens (só DONE e MISSED)."""
        _record(self.patient, WEEK_START, CareRecord.Status.PENDING)

        from api.tasks import notify_weekly_summary
        notify_weekly_summary.apply()

        mock_send.assert_not_called()

    # ------------------------------------------------------------------
    # Múltiplos grupos
    # ------------------------------------------------------------------

    @patch("api.services.push.send_push", return_value=_OK)
    def test_multiple_groups_each_get_own_push(self, mock_send, _mock_date):
        """Dois grupos com atividade: send_push chamado uma vez por grupo."""
        user3 = User.objects.create_user("carol", password="pass")
        patient2 = Patient.objects.create(name="Vovô")
        group2 = CareGroup.objects.create(name="Família 2", patient=patient2)
        GroupMembership.objects.create(
            user=user3, group=group2, relation_to_patient="FAMILY"
        )

        _record(self.patient, WEEK_START, CareRecord.Status.DONE)
        _record(patient2, WEEK_START, CareRecord.Status.MISSED)

        from api.tasks import notify_weekly_summary
        notify_weekly_summary.apply()

        self.assertEqual(mock_send.call_count, 2)

    @patch("api.services.push.send_push", return_value=_OK)
    def test_groups_isolated_counts(self, mock_send, _mock_date):
        """Registros de um grupo não aparecem no resumo do outro."""
        user3 = User.objects.create_user("carol", password="pass")
        patient2 = Patient.objects.create(name="Vovô")
        group2 = CareGroup.objects.create(name="Família 2", patient=patient2)
        GroupMembership.objects.create(
            user=user3, group=group2, relation_to_patient="FAMILY"
        )

        # grupo1: 3 done; grupo2: 1 missed
        _record(self.patient, WEEK_START, CareRecord.Status.DONE)
        _record(self.patient, WEEK_START, CareRecord.Status.DONE)
        _record(self.patient, WEEK_START, CareRecord.Status.DONE)
        _record(patient2, WEEK_START, CareRecord.Status.MISSED)

        from api.tasks import notify_weekly_summary
        notify_weekly_summary.apply()

        calls = {frozenset(c[1]["user_ids"]): c[1]["body"] for c in mock_send.call_args_list}
        body_group1 = calls[frozenset([self.user1.id, self.user2.id])]
        body_group2 = calls[frozenset([user3.id])]

        self.assertIn("3 realizados", body_group1)
        self.assertIn("0 não realizados", body_group1)
        self.assertIn("0 realizados", body_group2)
        self.assertIn("1 não realizado", body_group2)

    # ------------------------------------------------------------------
    # Resiliência e retry
    # ------------------------------------------------------------------

    @patch("api.services.push.send_push", side_effect=Exception("Redis timeout"))
    def test_retry_on_send_push_failure(self, mock_send, _mock_date):
        """Falha no send_push dispara retry via self.retry."""
        _record(self.patient, WEEK_START, CareRecord.Status.DONE)

        from api.tasks import notify_weekly_summary
        from celery.exceptions import Retry

        with self.assertRaises((Retry, Exception)):
            notify_weekly_summary.apply(throw=True)

    @patch(
        "api.services.push.send_push",
        return_value={"sent": 0, "failed": 1, "invalidated": 0},
    )
    def test_retry_when_send_push_reports_failures(self, mock_send, _mock_date):
        """send_push retornando failed > 0 dispara retry e não grava log."""
        from care.models import WeeklySummaryLog

        _record(self.patient, WEEK_START, CareRecord.Status.DONE)

        from api.tasks import notify_weekly_summary
        from celery.exceptions import Retry

        with self.assertRaises((Retry, Exception)):
            notify_weekly_summary.apply(throw=True)

        # Entrega falhou: nenhum log de idempotência deve ser criado.
        self.assertFalse(
            WeeklySummaryLog.objects.filter(
                group=self.group, week_start=WEEK_START
            ).exists()
        )

    # ------------------------------------------------------------------
    # Idempotência
    # ------------------------------------------------------------------

    @patch("api.services.push.send_push", return_value=_OK)
    def test_successful_send_creates_log(self, mock_send, _mock_date):
        """Envio bem-sucedido grava WeeklySummaryLog do grupo + semana."""
        from care.models import WeeklySummaryLog

        _record(self.patient, WEEK_START, CareRecord.Status.DONE)

        from api.tasks import notify_weekly_summary
        notify_weekly_summary.apply()

        self.assertTrue(
            WeeklySummaryLog.objects.filter(
                group=self.group, week_start=WEEK_START
            ).exists()
        )

    @patch("api.services.push.send_push", return_value=_OK)
    def test_already_notified_group_is_skipped(self, mock_send, _mock_date):
        """Grupo com log da semana não é notificado novamente (reexecução)."""
        from care.models import WeeklySummaryLog

        _record(self.patient, WEEK_START, CareRecord.Status.DONE)
        WeeklySummaryLog.objects.create(group=self.group, week_start=WEEK_START)

        from api.tasks import notify_weekly_summary
        notify_weekly_summary.apply()

        mock_send.assert_not_called()

    @patch("api.services.push.send_push", return_value=_OK)
    def test_rerun_does_not_send_twice(self, mock_send, _mock_date):
        """Duas execuções na mesma semana enviam apenas uma vez."""
        _record(self.patient, WEEK_START, CareRecord.Status.DONE)

        from api.tasks import notify_weekly_summary
        notify_weekly_summary.apply()
        notify_weekly_summary.apply()

        mock_send.assert_called_once()

    # ------------------------------------------------------------------
    # Gramática do corpo (singular/plural)
    # ------------------------------------------------------------------

    @patch("api.services.push.send_push", return_value=_OK)
    def test_singular_grammar_done(self, mock_send, _mock_date):
        """1 realizado (sem 's')."""
        _record(self.patient, WEEK_START, CareRecord.Status.DONE)

        from api.tasks import notify_weekly_summary
        notify_weekly_summary.apply()

        _, kwargs = mock_send.call_args
        self.assertIn("1 realizado,", kwargs["body"])
        self.assertNotIn("1 realizados", kwargs["body"])

    @patch("api.services.push.send_push", return_value=_OK)
    def test_plural_grammar_missed(self, mock_send, _mock_date):
        """2+ não realizados (com 's')."""
        _record(self.patient, WEEK_START, CareRecord.Status.DONE)
        _record(self.patient, WEEK_START, CareRecord.Status.MISSED)
        _record(self.patient, WEEK_START, CareRecord.Status.MISSED)

        from api.tasks import notify_weekly_summary
        notify_weekly_summary.apply()

        _, kwargs = mock_send.call_args
        self.assertIn("2 não realizados", kwargs["body"])
