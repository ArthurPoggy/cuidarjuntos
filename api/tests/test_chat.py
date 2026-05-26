from datetime import date, time
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from care.models import Patient, CareGroup, GroupMembership, CareRecord, ChatMessage


def _fake_anthropic_response(text):
    """Imita a resposta da SDK: objeto com .content = [bloco com .text]."""
    block = MagicMock()
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


@override_settings(ANTHROPIC_API_KEY="test-key", ANTHROPIC_MODEL="claude-haiku-4-5-20251001")
class ChatEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("alice", password="pass1234")
        self.client.force_authenticate(user=self.user)

        self.patient = Patient.objects.create(name="João", birth_date=date(1950, 3, 20))
        self.group = CareGroup.objects.create(name="Família", patient=self.patient)
        GroupMembership.objects.create(
            user=self.user, group=self.group, relation_to_patient="FAMILY"
        )
        CareRecord.objects.create(
            patient=self.patient, caregiver="Alice", type="medication",
            what="Losartana", date=date.today(), time=time(8, 0),
            status=CareRecord.Status.DONE,
        )

    @patch("api.views.chat.anthropic.Anthropic")
    def test_resposta_retornada(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            _fake_anthropic_response("O João tomou a medicação hoje.")
        )

        resp = self.client.post(
            "/api/v1/chat/", {"message": "Como está o paciente?"}, format="json"
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["reply"], "O João tomou a medicação hoje.")

        msgs = ChatMessage.objects.filter(user=self.user, group=self.group).order_by("created_at")
        self.assertEqual(msgs.count(), 2)
        self.assertEqual(msgs[0].role, ChatMessage.Role.USER)
        self.assertEqual(msgs[0].content, "Como está o paciente?")
        self.assertEqual(msgs[1].role, ChatMessage.Role.ASSISTANT)
        self.assertEqual(msgs[1].content, "O João tomou a medicação hoje.")

    @patch("api.views.chat.anthropic.Anthropic")
    def test_mensagem_vazia_retorna_400(self, mock_anthropic):
        resp = self.client.post("/api/v1/chat/", {"message": "   "}, format="json")

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        mock_anthropic.assert_not_called()
        self.assertEqual(ChatMessage.objects.count(), 0)

    def test_sem_autenticacao_bloqueado_401(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post("/api/v1/chat/", {"message": "oi"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("api.views.chat.anthropic.Anthropic")
    def test_sem_grupo_retorna_403(self, mock_anthropic):
        GroupMembership.objects.filter(user=self.user).delete()
        resp = self.client.post("/api/v1/chat/", {"message": "oi"}, format="json")

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        mock_anthropic.assert_not_called()

    @override_settings(ANTHROPIC_API_KEY="")
    def test_sem_api_key_retorna_503(self):
        # 5xx é logado por Django em "django.request"; capturar o log evita que o
        # AdminEmailHandler renderize o template de debug durante o teste.
        with self.assertLogs("django.request", level="ERROR"):
            resp = self.client.post("/api/v1/chat/", {"message": "oi"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(ChatMessage.objects.count(), 0)

    @patch("api.views.chat.anthropic.Anthropic")
    def test_history_retorna_mensagens(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            _fake_anthropic_response("resposta")
        )
        self.client.post("/api/v1/chat/", {"message": "primeira"}, format="json")

        resp = self.client.get("/api/v1/chat/history/")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["results"]), 2)
        self.assertEqual(resp.data["results"][0]["content"], "primeira")
