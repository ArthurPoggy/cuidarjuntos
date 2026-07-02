from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import TestCase

from care.models import Notification


class NotificationModelTests(TestCase):
    """Testes do modelo Notification (care/models.py)."""

    def setUp(self):
        self.user = User.objects.create_user("alice", password="pass")

    def _notification(self, **kwargs):
        defaults = {
            "user": self.user,
            "title": "Título de Teste",
            "body": "Corpo da notificação.",
        }
        defaults.update(kwargs)
        return Notification.objects.create(**defaults)

    # ------------------------------------------------------------------
    # Criação e campos básicos
    # ------------------------------------------------------------------

    def test_create_notification(self):
        """Notificação é criada com sucesso via ORM."""
        n = self._notification()
        self.assertIsNotNone(n.pk)

    def test_default_read_is_false(self):
        """`read` é False por padrão."""
        n = self._notification()
        self.assertFalse(n.read)

    def test_default_data_is_empty_dict(self):
        """`data` é {} por padrão."""
        n = self._notification()
        self.assertEqual(n.data, {})

    def test_created_at_is_set_automatically(self):
        """`created_at` é preenchido automaticamente."""
        n = self._notification()
        self.assertIsNotNone(n.created_at)

    def test_str_representation(self):
        """__str__ contém título e username."""
        n = self._notification(title="Novo comentário")
        self.assertIn("Novo comentário", str(n))
        self.assertIn("alice", str(n))

    # ------------------------------------------------------------------
    # JSONField
    # ------------------------------------------------------------------

    def test_json_field_stores_dict(self):
        """`data` armazena e recupera dicionário corretamente."""
        payload = {"screen": "RecordDetail", "id": 42}
        n = self._notification(data=payload)
        n.refresh_from_db()
        self.assertEqual(n.data["screen"], "RecordDetail")
        self.assertEqual(n.data["id"], 42)

    def test_json_field_stores_nested_structure(self):
        """`data` suporta estruturas aninhadas."""
        payload = {"nested": {"key": "value"}, "list": [1, 2, 3]}
        n = self._notification(data=payload)
        n.refresh_from_db()
        self.assertEqual(n.data["nested"]["key"], "value")
        self.assertEqual(n.data["list"], [1, 2, 3])

    # ------------------------------------------------------------------
    # Leitura e atualização
    # ------------------------------------------------------------------

    def test_mark_as_read(self):
        """Marcar notificação como lida persiste no banco."""
        n = self._notification()
        n.read = True
        n.save(update_fields=["read"])
        n.refresh_from_db()
        self.assertTrue(n.read)

    def test_multiple_notifications_per_user(self):
        """Usuário pode ter múltiplas notificações."""
        self._notification(title="Notif 1")
        self._notification(title="Notif 2")
        self._notification(title="Notif 3")
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 3)

    def test_unread_filter(self):
        """Filtrar notificações não lidas funciona corretamente."""
        self._notification(title="Lida", read=True)
        self._notification(title="Não lida 1")
        self._notification(title="Não lida 2")
        unread = Notification.objects.filter(user=self.user, read=False)
        self.assertEqual(unread.count(), 2)

    # ------------------------------------------------------------------
    # Ordenação
    # ------------------------------------------------------------------

    def test_ordering_newest_first(self):
        """Notificações são ordenadas da mais recente para a mais antiga."""
        n1 = self._notification(title="Primeira")
        n2 = self._notification(title="Segunda")
        n3 = self._notification(title="Terceira")
        ids = list(Notification.objects.values_list("pk", flat=True))
        self.assertEqual(ids, [n3.pk, n2.pk, n1.pk])

    def test_ordering_tiebreak_by_id_when_created_at_matches(self):
        """Com created_at empatado, o desempate ocorre por -id."""
        n1 = self._notification(title="Primeira")
        n2 = self._notification(title="Segunda")
        n3 = self._notification(title="Terceira")

        same_instant = n1.created_at
        Notification.objects.filter(pk__in=[n1.pk, n2.pk, n3.pk]).update(
            created_at=same_instant
        )

        ids = list(
            Notification.objects.filter(pk__in=[n1.pk, n2.pk, n3.pk])
            .values_list("pk", flat=True)
        )
        self.assertEqual(ids, [n3.pk, n2.pk, n1.pk])

    # ------------------------------------------------------------------
    # Cascade delete
    # ------------------------------------------------------------------

    def test_cascade_delete_on_user_delete(self):
        """Ao deletar o usuário, suas notificações são removidas (CASCADE)."""
        self._notification()
        self._notification()
        self.assertEqual(Notification.objects.count(), 2)

        self.user.delete()

        self.assertEqual(Notification.objects.count(), 0)

    def test_notifications_isolated_between_users(self):
        """Notificações de um usuário não afetam as de outro."""
        user2 = User.objects.create_user("bob", password="pass")
        self._notification(title="Alice")
        Notification.objects.create(user=user2, title="Bob", body="Corpo.")

        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)
        self.assertEqual(Notification.objects.filter(user=user2).count(), 1)

    # ------------------------------------------------------------------
    # Admin registrado
    # ------------------------------------------------------------------

    def test_notification_registered_in_admin(self):
        """Notification está registrado no Django Admin."""
        from django.contrib import admin as django_admin
        self.assertIn(Notification, django_admin.site._registry)
