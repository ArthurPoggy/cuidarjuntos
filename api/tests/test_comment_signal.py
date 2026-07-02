from datetime import date, time
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

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


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class CommentNotificationTests(TestCase):
    """Testes do signal notify_comment_created em care/signals.py.

    Modo eager: a task de envio enfileirada via on_commit roda inline, de modo
    que os testes continuam observando a chamada a send_push de ponta a ponta.
    """

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


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class SendCommentNotificationTaskTests(TestCase):
    """Testes da task Celery send_comment_notification_task.

    A task revalida a pertença ao grupo antes do envio (o autor pode ter
    saído do grupo entre o enfileiramento e a execução), então os testes
    usam fixtures reais de CareRecord/GroupMembership em vez de IDs soltos.
    """

    def setUp(self):
        self.author = User.objects.create_user("alice", password="pass")
        self.patient = Patient.objects.create(name="Vovó")
        self.group = CareGroup.objects.create(name="Família", patient=self.patient)
        GroupMembership.objects.create(
            user=self.author, group=self.group, relation_to_patient="FAMILY"
        )
        self.record = _make_record(self.patient, creator=self.author)

    @patch("api.services.push.send_push")
    def test_task_sends_push(self, mock_send):
        mock_send.return_value = {"sent": 1, "failed": 0, "invalidated": 0}

        from api.tasks import send_comment_notification_task
        send_comment_notification_task.apply(args=[self.author.id, self.record.id, "Bob"])

        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        self.assertEqual(kwargs["user_ids"], [self.author.id])
        self.assertIn("Bob", kwargs["body"])
        self.assertEqual(kwargs["data"]["id"], self.record.id)

    @patch("api.services.push.send_push")
    def test_task_retries_on_delivery_failure(self, mock_send):
        mock_send.return_value = {"sent": 0, "failed": 1, "invalidated": 0}

        from api.tasks import send_comment_notification_task
        from celery.exceptions import Retry

        with self.assertRaises((Retry, Exception)):
            send_comment_notification_task.apply(
                args=[self.author.id, self.record.id, "Bob"], throw=True
            )

    @patch("api.services.push.send_push")
    def test_task_skips_when_author_left_group_before_execution(self, mock_send):
        """Se o autor saiu do grupo entre o enfileiramento e a execução da
        task, o envio é revalidado e cancelado (não confia apenas na checagem
        síncrona já feita no signal)."""
        GroupMembership.objects.filter(user=self.author).delete()

        from api.tasks import send_comment_notification_task
        send_comment_notification_task.apply(args=[self.author.id, self.record.id, "Bob"])

        mock_send.assert_not_called()

    @patch("api.services.push.send_push")
    def test_task_skips_when_record_deleted_before_execution(self, mock_send):
        record_id = self.record.id
        self.record.delete()

        from api.tasks import send_comment_notification_task
        send_comment_notification_task.apply(args=[self.author.id, record_id, "Bob"])

        mock_send.assert_not_called()
