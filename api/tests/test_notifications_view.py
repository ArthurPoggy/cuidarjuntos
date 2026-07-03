from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from care.models import Notification


class NotificationViewTests(TestCase):
    """Testes do NotificationViewSet: filtro de não lidas e mark_all_read."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("alice", password="pass")
        self.other = User.objects.create_user("bob", password="pass")
        self.client.force_authenticate(user=self.user)

        # 2 não lidas + 1 lida para o usuário; 1 para outro usuário (isolamento)
        Notification.objects.create(user=self.user, title="N1", body="b", read=False)
        Notification.objects.create(user=self.user, title="N2", body="b", read=False)
        Notification.objects.create(user=self.user, title="N3", body="b", read=True)
        Notification.objects.create(user=self.other, title="X", body="b", read=False)

    def _count(self, resp):
        # Suporta resposta paginada (count) ou lista simples.
        data = resp.data
        if isinstance(data, dict) and "count" in data:
            return data["count"]
        results = data.get("results", data) if isinstance(data, dict) else data
        return len(results)

    def test_list_returns_only_own_notifications(self):
        resp = self.client.get("/api/v1/notifications/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._count(resp), 3)

    def test_unread_filter(self):
        """?unread=true retorna apenas as não lidas do usuário."""
        resp = self.client.get("/api/v1/notifications/?unread=true")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._count(resp), 2)

    def test_read_false_filter(self):
        """?read=false é equivalente a ?unread=true."""
        resp = self.client.get("/api/v1/notifications/?read=false")
        self.assertEqual(self._count(resp), 2)

    def test_read_true_filter(self):
        """?read=true retorna apenas as lidas."""
        resp = self.client.get("/api/v1/notifications/?read=true")
        self.assertEqual(self._count(resp), 1)

    def test_mark_all_read_marks_every_unread(self):
        """mark_all_read marca todas as não lidas do usuário, ignorando filtros."""
        resp = self.client.post(
            "/api/v1/notifications/mark_all_read/?unread=true", format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["marked"], 2)
        self.assertEqual(
            Notification.objects.filter(user=self.user, read=False).count(), 0
        )

    def test_mark_all_read_does_not_affect_other_users(self):
        self.client.post("/api/v1/notifications/mark_all_read/", format="json")
        self.assertEqual(
            Notification.objects.filter(user=self.other, read=False).count(), 1
        )
