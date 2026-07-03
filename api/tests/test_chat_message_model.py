from django.contrib.auth.models import User
from django.test import TestCase

from care.models import CareGroup, ChatMessage, Patient


class ChatMessageModelTests(TestCase):
    """Testes do modelo ChatMessage (care/models.py)."""

    def setUp(self):
        self.user = User.objects.create_user("alice", password="pass")
        self.patient = Patient.objects.create(name="Vovó")
        self.group = CareGroup.objects.create(name="Família", patient=self.patient)

    def _msg(self, **kwargs):
        defaults = {
            "user": self.user,
            "group": self.group,
            "role": ChatMessage.Role.USER,
            "content": "Olá, assistente.",
        }
        defaults.update(kwargs)
        return ChatMessage.objects.create(**defaults)

    def test_create_message(self):
        m = self._msg()
        self.assertIsNotNone(m.pk)
        self.assertIsNotNone(m.created_at)

    def test_role_choices(self):
        u = self._msg(role=ChatMessage.Role.USER)
        a = self._msg(role=ChatMessage.Role.ASSISTANT)
        self.assertEqual(u.role, "user")
        self.assertEqual(a.role, "assistant")

    def test_str_contains_role_and_user(self):
        m = self._msg(role=ChatMessage.Role.ASSISTANT)
        s = str(m)
        self.assertIn("Assistente", s)
        self.assertIn("alice", s)

    def test_ordering_oldest_first(self):
        m1 = self._msg(content="primeira")
        m2 = self._msg(content="segunda")
        m3 = self._msg(content="terceira")
        ids = list(ChatMessage.objects.values_list("pk", flat=True))
        self.assertEqual(ids, [m1.pk, m2.pk, m3.pk])

    def test_partition_by_user_and_group(self):
        """Histórico não vaza entre usuários nem entre grupos."""
        other_user = User.objects.create_user("bob", password="pass")
        other_patient = Patient.objects.create(name="Vovô")
        other_group = CareGroup.objects.create(name="Família 2", patient=other_patient)

        self._msg(content="da alice no grupo 1")
        ChatMessage.objects.create(
            user=other_user, group=self.group,
            role=ChatMessage.Role.USER, content="do bob no grupo 1",
        )
        ChatMessage.objects.create(
            user=self.user, group=other_group,
            role=ChatMessage.Role.USER, content="da alice no grupo 2",
        )

        alice_g1 = ChatMessage.objects.filter(user=self.user, group=self.group)
        self.assertEqual(alice_g1.count(), 1)
        self.assertEqual(alice_g1.first().content, "da alice no grupo 1")

    def test_cascade_delete_on_user(self):
        self._msg()
        self._msg()
        self.assertEqual(ChatMessage.objects.count(), 2)
        self.user.delete()
        self.assertEqual(ChatMessage.objects.count(), 0)

    def test_cascade_delete_on_group(self):
        self._msg()
        self.assertEqual(ChatMessage.objects.count(), 1)
        self.group.delete()
        self.assertEqual(ChatMessage.objects.count(), 0)
