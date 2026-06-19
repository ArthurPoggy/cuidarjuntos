from datetime import date, time
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from care.models import CareGroup, CareRecord, ChatMessage, GroupMembership, Patient


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
        self.patient = Patient.objects.create(
            name="Dona Maria", birth_date=date(1940, 1, 1),
            notes="Hipertensa",
        )
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

    # ---- contexto enviado ao modelo (proteção contra regressão) ------------

    @patch("anthropic.Anthropic")
    def test_system_prompt_includes_patient_and_records(self, mock_anthropic):
        """O contexto (paciente + registros) deve chegar à Anthropic."""
        client = _fake_anthropic_reply()
        mock_anthropic.return_value = client
        CareRecord.objects.create(
            patient=self.patient, type="medication", what="Losartana",
            date=date(2026, 5, 1), time=time(8, 0),
            caregiver="Cuidador", status=CareRecord.Status.DONE,
            description="50mg em jejum",
        )

        self.client.post("/api/v1/chat/", {"message": "Como ela está?"}, format="json")

        _, kwargs = client.messages.create.call_args
        system = kwargs["system"]
        self.assertIn("Dona Maria", system)        # nome do paciente
        self.assertIn("Hipertensa", system)        # observações de saúde
        self.assertIn("Losartana", system)         # registro recente
        self.assertIn("50mg em jejum", system)     # descrição do registro
        # A mensagem do usuário entra em messages.
        self.assertEqual(
            kwargs["messages"][-1], {"role": "user", "content": "Como ela está?"}
        )

    @patch("anthropic.Anthropic")
    def test_history_is_sent_as_context(self, mock_anthropic):
        """Mensagens anteriores do usuário/grupo entram no histórico enviado."""
        client = _fake_anthropic_reply()
        mock_anthropic.return_value = client
        ChatMessage.objects.create(
            user=self.user, group=self.group,
            role=ChatMessage.Role.USER, content="pergunta antiga",
        )
        ChatMessage.objects.create(
            user=self.user, group=self.group,
            role=ChatMessage.Role.ASSISTANT, content="resposta antiga",
        )

        self.client.post("/api/v1/chat/", {"message": "nova"}, format="json")

        _, kwargs = client.messages.create.call_args
        contents = [m["content"] for m in kwargs["messages"]]
        self.assertIn("pergunta antiga", contents)
        self.assertIn("resposta antiga", contents)

    @patch("anthropic.Anthropic")
    def test_other_group_history_not_sent(self, mock_anthropic):
        """Histórico de outro grupo não vaza para o prompt."""
        client = _fake_anthropic_reply()
        mock_anthropic.return_value = client
        other_patient = Patient.objects.create(name="Outro")
        other_group = CareGroup.objects.create(name="G2", patient=other_patient)
        ChatMessage.objects.create(
            user=self.user, group=other_group,
            role=ChatMessage.Role.USER, content="segredo de outro grupo",
        )

        self.client.post("/api/v1/chat/", {"message": "oi"}, format="json")

        _, kwargs = client.messages.create.call_args
        contents = [m["content"] for m in kwargs["messages"]]
        self.assertNotIn("segredo de outro grupo", contents)

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
    def test_anthropic_failure_returns_502_without_persistence(self, mock_anthropic):
        client = MagicMock()
        client.messages.create.side_effect = Exception("boom")
        mock_anthropic.return_value = client
        resp = self.client.post("/api/v1/chat/", {"message": "Oi"}, format="json")
        self.assertEqual(resp.status_code, 502)
        # Falha externa não deve persistir nenhuma mensagem (nem parcial).
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

    def test_history_isolated_between_users(self):
        """Um usuário não enxerga o histórico de outro usuário."""
        bob = User.objects.create_user("bob", password="pass")
        other_patient = Patient.objects.create(name="Outro")
        other_group = CareGroup.objects.create(name="G2", patient=other_patient)
        GroupMembership.objects.create(
            user=bob, group=other_group, relation_to_patient="FAMILY"
        )
        ChatMessage.objects.create(
            user=bob, group=other_group,
            role=ChatMessage.Role.USER, content="mensagem do bob",
        )

        # alice continua vendo só as suas 5
        resp = self.client.get("/api/v1/chat/history/")
        self.assertEqual(resp.data["count"], 5)
        contents = [r["content"] for r in resp.data["results"]]
        self.assertNotIn("mensagem do bob", contents)

        # bob vê só a dele
        self.client.force_authenticate(user=bob)
        resp_bob = self.client.get("/api/v1/chat/history/")
        self.assertEqual(resp_bob.data["count"], 1)
        self.assertEqual(resp_bob.data["results"][0]["content"], "mensagem do bob")


class ChatStatusTests(TestCase):
    """Endpoint de disponibilidade do assistente (gating do menu)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("alice", password="pass")
        self.client.force_authenticate(user=self.user)

    @override_settings(ANTHROPIC_API_KEY="test-key", CHAT_ASSISTANT_ENABLED=True)
    def test_status_enabled_when_configured(self):
        resp = self.client.get("/api/v1/chat/status/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["enabled"])

    @override_settings(ANTHROPIC_API_KEY="", CHAT_ASSISTANT_ENABLED=True)
    def test_status_disabled_without_key(self):
        resp = self.client.get("/api/v1/chat/status/")
        self.assertFalse(resp.data["enabled"])

    @override_settings(ANTHROPIC_API_KEY="test-key", CHAT_ASSISTANT_ENABLED=False)
    def test_status_disabled_when_feature_off(self):
        resp = self.client.get("/api/v1/chat/status/")
        self.assertFalse(resp.data["enabled"])

    def test_status_requires_auth(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get("/api/v1/chat/status/")
        self.assertEqual(resp.status_code, 401)
