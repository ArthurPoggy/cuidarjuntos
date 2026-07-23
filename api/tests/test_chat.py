from datetime import date, time
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from care.models import CareGroup, ChatMessage, GroupMembership, Patient


def _fake_anthropic_reply(text="Olá! Como posso ajudar?"):
    """Monta um cliente Anthropic falso cujo messages.create devolve `text`."""
    block = MagicMock()
    block.text = text
    response = MagicMock()
    response.content = [block]
    client = MagicMock()
    client.messages.create.return_value = response
    return client


@override_settings(ANTHROPIC_API_KEY="test-key", CHAT_ASSISTANT_ENABLED=True)
class ChatViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("alice", password="pass")
        self.patient = Patient.objects.create(name="Vovó")
        self.group = CareGroup.objects.create(name="Família", patient=self.patient)
        GroupMembership.objects.create(
            user=self.user, group=self.group, relation_to_patient="FAMILY"
        )
        self.client.force_authenticate(user=self.user)

    # ---- sucesso -----------------------------------------------------------

    @patch("anthropic.Anthropic")
    def test_chat_success_persists_messages(self, mock_anthropic):
        mock_anthropic.return_value = _fake_anthropic_reply("Resposta da IA.")
        resp = self.client.post("/api/v1/chat/", {"message": "Oi"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["reply"], "Resposta da IA.")
        roles = list(
            ChatMessage.objects.filter(user=self.user, group=self.group)
            .order_by("created_at").values_list("role", "content")
        )
        self.assertEqual(roles, [("user", "Oi"), ("assistant", "Resposta da IA.")])

    @patch("anthropic.Anthropic")
    def test_chat_passes_timeout(self, mock_anthropic):
        mock_anthropic.return_value = _fake_anthropic_reply()
        self.client.post("/api/v1/chat/", {"message": "Oi"}, format="json")
        _, kwargs = mock_anthropic.call_args
        self.assertIn("timeout", kwargs)

    # ---- validações --------------------------------------------------------

    @patch("anthropic.Anthropic")
    def test_empty_message_returns_400(self, mock_anthropic):
        resp = self.client.post("/api/v1/chat/", {"message": "   "}, format="json")
        self.assertEqual(resp.status_code, 400)
        mock_anthropic.assert_not_called()

    @patch("anthropic.Anthropic")
    def test_message_too_long_returns_400(self, mock_anthropic):
        resp = self.client.post(
            "/api/v1/chat/", {"message": "x" * 5000}, format="json"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data.get("code"), "MESSAGE_TOO_LONG")
        mock_anthropic.assert_not_called()

    @patch("anthropic.Anthropic")
    def test_user_without_group_returns_403(self, mock_anthropic):
        loner = User.objects.create_user("bob", password="pass")
        self.client.force_authenticate(user=loner)
        resp = self.client.post("/api/v1/chat/", {"message": "Oi"}, format="json")
        self.assertEqual(resp.status_code, 403)
        mock_anthropic.assert_not_called()

    # ---- feature desabilitada / sem chave ----------------------------------

    @override_settings(ANTHROPIC_API_KEY="")
    @patch("anthropic.Anthropic")
    def test_missing_key_returns_503(self, mock_anthropic):
        resp = self.client.post("/api/v1/chat/", {"message": "Oi"}, format="json")
        self.assertEqual(resp.status_code, 503)
        mock_anthropic.assert_not_called()

    @override_settings(CHAT_ASSISTANT_ENABLED=False)
    @patch("anthropic.Anthropic")
    def test_feature_disabled_returns_503(self, mock_anthropic):
        resp = self.client.post("/api/v1/chat/", {"message": "Oi"}, format="json")
        self.assertEqual(resp.status_code, 503)
        mock_anthropic.assert_not_called()

    # ---- falha externa -----------------------------------------------------

    @patch("anthropic.Anthropic")
    def test_anthropic_failure_returns_502(self, mock_anthropic):
        client = MagicMock()
        client.messages.create.side_effect = Exception("boom")
        mock_anthropic.return_value = client
        resp = self.client.post("/api/v1/chat/", {"message": "Oi"}, format="json")
        self.assertEqual(resp.status_code, 502)
        # Falha externa não deve persistir mensagens.
        self.assertEqual(ChatMessage.objects.count(), 0)

    def test_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post("/api/v1/chat/", {"message": "Oi"}, format="json")
        self.assertEqual(resp.status_code, 401)


@override_settings(ANTHROPIC_API_KEY="test-key", CHAT_ASSISTANT_ENABLED=True)
class ChatHistoryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("alice", password="pass")
        self.patient = Patient.objects.create(name="Vovó")
        self.group = CareGroup.objects.create(name="Família", patient=self.patient)
        GroupMembership.objects.create(
            user=self.user, group=self.group, relation_to_patient="FAMILY"
        )
        self.client.force_authenticate(user=self.user)
        for i in range(5):
            ChatMessage.objects.create(
                user=self.user, group=self.group,
                role=ChatMessage.Role.USER, content=f"msg {i}",
            )

    def test_history_returns_count_and_results(self):
        resp = self.client.get("/api/v1/chat/history/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 5)
        self.assertEqual(len(resp.data["results"]), 5)

    def test_history_pagination_limit_offset(self):
        resp = self.client.get("/api/v1/chat/history/?limit=2&offset=1")
        self.assertEqual(resp.data["count"], 5)
        contents = [r["content"] for r in resp.data["results"]]
        self.assertEqual(contents, ["msg 1", "msg 2"])

    def test_history_without_group_is_empty(self):
        loner = User.objects.create_user("bob", password="pass")
        self.client.force_authenticate(user=loner)
        resp = self.client.get("/api/v1/chat/history/")
        self.assertEqual(resp.data, {"count": 0, "results": []})
