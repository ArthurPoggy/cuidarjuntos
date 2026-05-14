from datetime import date, time
from unittest.mock import call, patch

from django.contrib.auth.models import User
from django.test import TestCase

from care.models import CareGroup, CareRecord, GroupMembership, Patient


def _make_pending_record(patient, assigned_to=None):
    return CareRecord.objects.create(
        patient=patient,
        type="medication",
        what="Amoxicilina",
        date=date(2026, 6, 1),
        time=time(9, 0),
        caregiver="Cuidador",
        status=CareRecord.Status.PENDING,
        assigned_to=assigned_to,
    )


class MissedRecordNotificationTests(TestCase):
    """Testes do signal notify_missed_record em care/signals.py."""

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
    # Cenário principal: PENDING → MISSED
    # ------------------------------------------------------------------

    @patch("api.services.push.send_push")
    def test_pending_to_missed_notifies_all_members(self, mock_send):
        """Mudança PENDING → MISSED notifica todos os membros do grupo."""
        record = _make_pending_record(self.patient)

        record.status = CareRecord.Status.MISSED
        record.missed_reason = "Cuidador não compareceu"
        record.save(update_fields=["status", "missed_reason"])

        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        self.assertEqual(set(kwargs["user_ids"]), {self.user1.id, self.user2.id})
        self.assertEqual(kwargs["title"], "Cuidado não realizado")
        self.assertIn("Medicação", kwargs["body"])
        self.assertIn("09:00", kwargs["body"])
        self.assertEqual(kwargs["data"]["screen"], "RecordDetail")
        self.assertEqual(kwargs["data"]["id"], record.id)

    @patch("api.services.push.send_push")
    def test_done_to_missed_notifies(self, mock_send):
        """Mudança DONE → MISSED também notifica (registro revertido)."""
        record = _make_pending_record(self.patient)
        record.status = CareRecord.Status.DONE
        record.save(update_fields=["status"])
        mock_send.reset_mock()

        record.status = CareRecord.Status.MISSED
        record.save(update_fields=["status"])

        mock_send.assert_called_once()

    # ------------------------------------------------------------------
    # Sem notificação (cenários negativos)
    # ------------------------------------------------------------------

    @patch("api.services.push.send_push")
    def test_creation_with_missed_status_no_notification(self, mock_send):
        """Criação direta com status MISSED não notifica (created=True)."""
        CareRecord.objects.create(
            patient=self.patient,
            type="other",
            what="Criado como missed",
            date=date(2026, 6, 1),
            time=time(10, 0),
            caregiver="Cuidador",
            status=CareRecord.Status.MISSED,
        )
        mock_send.assert_not_called()

    @patch("api.services.push.send_push")
    def test_already_missed_no_duplicate_notification(self, mock_send):
        """Salvar um registro que já está MISSED não gera notificação duplicada."""
        record = _make_pending_record(self.patient)
        record.status = CareRecord.Status.MISSED
        record.save(update_fields=["status"])
        mock_send.reset_mock()

        # Salvar novamente sem mudar o status
        record.missed_reason = "Atualização de motivo"
        record.save(update_fields=["missed_reason"])

        mock_send.assert_not_called()

    @patch("api.services.push.send_push")
    def test_already_missed_full_save_no_duplicate(self, mock_send):
        """Full save de registro já MISSED não notifica novamente."""
        record = _make_pending_record(self.patient)
        record.status = CareRecord.Status.MISSED
        record.save(update_fields=["status"])
        mock_send.reset_mock()

        # Full save sem trocar status
        record.save()

        mock_send.assert_not_called()

    @patch("api.services.push.send_push")
    def test_status_change_to_done_no_notification(self, mock_send):
        """Mudança para DONE não notifica."""
        record = _make_pending_record(self.patient)
        record.status = CareRecord.Status.DONE
        record.save(update_fields=["status"])

        mock_send.assert_not_called()

    @patch("api.services.push.send_push")
    def test_non_status_update_no_notification(self, mock_send):
        """Salvar apenas outros campos (update_fields sem 'status') não notifica."""
        record = _make_pending_record(self.patient)
        record.what = "Ibuprofeno"
        record.save(update_fields=["what"])

        mock_send.assert_not_called()

    # ------------------------------------------------------------------
    # Resiliência
    # ------------------------------------------------------------------

    @patch("api.services.push.send_push")
    def test_patient_without_care_group_no_crash(self, mock_send):
        """Paciente sem CareGroup: signal não lança exceção."""
        orphan = Patient.objects.create(name="Paciente Sem Grupo")
        record = CareRecord.objects.create(
            patient=orphan,
            type="other",
            what="Sem grupo",
            date=date(2026, 6, 1),
            time=time(8, 0),
            caregiver="Cuidador",
            status=CareRecord.Status.PENDING,
        )

        record.status = CareRecord.Status.MISSED
        record.save(update_fields=["status"])  # não deve lançar exceção

        mock_send.assert_not_called()

    @patch("api.services.push.send_push")
    def test_group_without_members_no_crash(self, mock_send):
        """Grupo sem membros: signal não lança exceção e não chama send_push."""
        empty_patient = Patient.objects.create(name="Paciente Isolado")
        CareGroup.objects.create(name="GrupoVazio", patient=empty_patient)
        record = CareRecord.objects.create(
            patient=empty_patient,
            type="other",
            what="Isolado",
            date=date(2026, 6, 1),
            time=time(8, 0),
            caregiver="Cuidador",
            status=CareRecord.Status.PENDING,
        )

        record.status = CareRecord.Status.MISSED
        record.save(update_fields=["status"])

        mock_send.assert_not_called()

    @patch("api.services.push.send_push", side_effect=Exception("Falha de rede"))
    def test_send_push_failure_does_not_crash_signal(self, mock_send):
        """Falha no send_push é capturada — o signal não propaga a exceção."""
        record = _make_pending_record(self.patient)

        record.status = CareRecord.Status.MISSED
        record.save(update_fields=["status"])  # não deve lançar exceção

        mock_send.assert_called_once()

    # ------------------------------------------------------------------
    # Payload
    # ------------------------------------------------------------------

    @patch("api.services.push.send_push")
    def test_payload_contains_record_type_and_time(self, mock_send):
        """Corpo do push contém tipo de registro e horário formatado."""
        record = CareRecord.objects.create(
            patient=self.patient,
            type="meal",
            what="Almoço",
            date=date(2026, 6, 1),
            time=time(12, 30),
            caregiver="Cuidador",
            status=CareRecord.Status.PENDING,
        )

        record.status = CareRecord.Status.MISSED
        record.save(update_fields=["status"])

        _, kwargs = mock_send.call_args
        self.assertIn("Alimentação", kwargs["body"])
        self.assertIn("12:30", kwargs["body"])
