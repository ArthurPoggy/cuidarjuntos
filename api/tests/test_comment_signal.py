from datetime import date, time
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from care.models import CareGroup, CareRecord, GroupMembership, Patient, RecordComment


def _make_record(patient, creator):
    return CareRecord.objects.create(
        patient=patient,
        type="medication",
        what="Dipirona 500mg",
        date=date(2026, 6, 1),
        time=time(8, 0),
        caregiver="Cuidador",
        status=CareRecord.Status.PENDING,
        created_by=creator,
    )


class CommentNotificationTests(TestCase):
    """Testes do signal notify_comment_created em care/signals.py."""

    def setUp(self):
        self.author = User.objects.create_user("alice", password="pass")
        self.commenter = User.objects.create_user("bob", password="pass")
        self.patient = Patient.objects.create(name="Vovó")
        self.group = CareGroup.objects.create(name="Família", patient=self.patient)
        GroupMembership.objects.create(
            user=self.author, group=self.group, relation_to_patient="FAMILY"
        )
        GroupMembership.objects.create(
            user=self.commenter, group=self.group, relation_to_patient="CAREGIVER"
        )
        self.record = _make_record(self.patient, creator=self.author)

    # ------------------------------------------------------------------
    # Cenário principal
    # ------------------------------------------------------------------

    @patch("api.services.push.send_push")
    def test_new_comment_notifies_record_creator(self, mock_send):
        """Novo comentário de outro usuário notifica o created_by do registro."""
        with self.captureOnCommitCallbacks(execute=True):
            RecordComment.objects.create(
                record=self.record,
                user=self.commenter,
                text="Ele tomou sem dificuldade.",
            )

        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        self.assertEqual(kwargs["user_ids"], [self.author.id])
        self.assertEqual(kwargs["title"], "Novo comentário")
        self.assertIn("bob", kwargs["body"])
        # Corpo neutro: não vaza o conteúdo do registro.
        self.assertNotIn("Dipirona 500mg", kwargs["body"])
        self.assertEqual(kwargs["data"]["screen"], "RecordDetail")
        self.assertEqual(kwargs["data"]["id"], self.record.id)

    # ------------------------------------------------------------------
    # Sem notificação
    # ------------------------------------------------------------------

    @patch("api.services.push.send_push")
    def test_creator_comments_own_record_no_notification(self, mock_send):
        """Criador comentando no próprio registro não gera notificação."""
        RecordComment.objects.create(
            record=self.record,
            user=self.author,
            text="Tudo bem.",
        )

        mock_send.assert_not_called()

    @patch("api.services.push.send_push")
    def test_record_without_creator_no_notification(self, mock_send):
        """Registro sem created_by: nenhuma notificação é enviada."""
        record_no_creator = CareRecord.objects.create(
            patient=self.patient,
            type="other",
            what="Atividade física",
            date=date(2026, 6, 1),
            time=time(10, 0),
            caregiver="Anônimo",
            status=CareRecord.Status.PENDING,
            created_by=None,
        )

        RecordComment.objects.create(
            record=record_no_creator,
            user=self.commenter,
            text="Parabéns!",
        )

        mock_send.assert_not_called()

    @patch("api.services.push.send_push")
    def test_comment_update_no_notification(self, mock_send):
        """Atualização de comentário existente (created=False) não notifica."""
        comment = RecordComment.objects.create(
            record=self.record,
            user=self.commenter,
            text="Primeiro texto.",
        )
        mock_send.reset_mock()

        comment.text = "Texto corrigido."
        comment.save()

        mock_send.assert_not_called()

    # ------------------------------------------------------------------
    # Resiliência
    # ------------------------------------------------------------------

    @patch("api.services.push.send_push", side_effect=Exception("Timeout"))
    def test_send_push_failure_does_not_raise(self, mock_send):
        """Falha no send_push é capturada — o signal não propaga a exceção."""
        with self.captureOnCommitCallbacks(execute=True):
            RecordComment.objects.create(
                record=self.record,
                user=self.commenter,
                text="Comentário que falha ao notificar.",
            )

        mock_send.assert_called_once()  # foi chamado, mas exceção foi absorvida

    @patch("api.services.push.send_push")
    def test_author_not_in_group_no_notification(self, mock_send):
        """Autor que saiu do grupo não recebe notificação de novos comentários."""
        GroupMembership.objects.filter(user=self.author).delete()

        with self.captureOnCommitCallbacks(execute=True):
            RecordComment.objects.create(
                record=self.record,
                user=self.commenter,
                text="Comentário após o autor sair do grupo.",
            )

        mock_send.assert_not_called()

    # ------------------------------------------------------------------
    # Conteúdo do payload
    # ------------------------------------------------------------------

    @patch("api.services.push.send_push")
    def test_payload_uses_display_name(self, mock_send):
        """Nome exibido no corpo usa full_name do perfil quando disponível."""
        self.commenter.first_name = "Roberto"
        self.commenter.last_name = "Silva"
        self.commenter.save()

        with self.captureOnCommitCallbacks(execute=True):
            RecordComment.objects.create(
                record=self.record,
                user=self.commenter,
                text="Observação clínica.",
            )

        _, kwargs = mock_send.call_args
        self.assertIn("Roberto Silva", kwargs["body"])

    @patch("api.services.push.send_push")
    def test_payload_data_points_to_correct_record(self, mock_send):
        """data.id aponta para o registro correto."""
        second_record = _make_record(self.patient, creator=self.author)

        with self.captureOnCommitCallbacks(execute=True):
            RecordComment.objects.create(
                record=second_record,
                user=self.commenter,
                text="Comentário no segundo registro.",
            )

        _, kwargs = mock_send.call_args
        self.assertEqual(kwargs["data"]["id"], second_record.id)
        self.assertNotEqual(kwargs["data"]["id"], self.record.id)
