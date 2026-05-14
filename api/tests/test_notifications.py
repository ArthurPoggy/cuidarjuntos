from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from care.models import Notification


class NotificationBaseTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("alice", password="pass1234")
        self.other = User.objects.create_user("bob", password="pass1234")
        self.client.force_authenticate(user=self.user)

        self.n1 = Notification.objects.create(user=self.user, title="Título 1", body="Corpo 1")
        self.n2 = Notification.objects.create(user=self.user, title="Título 2", body="Corpo 2", read=True)
        Notification.objects.create(user=self.other, title="De outro", body="Não deve aparecer")


class NotificationListTests(NotificationBaseTestCase):
    def test_list_returns_only_own_notifications(self):
        resp = self.client.get("/api/v1/notifications/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 2)
        ids = {r["id"] for r in resp.data["results"]}
        self.assertIn(self.n1.id, ids)
        self.assertIn(self.n2.id, ids)

    def test_filter_unread(self):
        resp = self.client.get("/api/v1/notifications/", {"unread": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["id"], self.n1.id)

    def test_filter_read_true(self):
        resp = self.client.get("/api/v1/notifications/", {"read": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["id"], self.n2.id)

    def test_filter_read_false(self):
        resp = self.client.get("/api/v1/notifications/", {"read": "false"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["id"], self.n1.id)

    def test_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get("/api/v1/notifications/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class NotificationPatchTests(NotificationBaseTestCase):
    def test_mark_single_as_read(self):
        resp = self.client.patch(f"/api/v1/notifications/{self.n1.id}/", {"read": True}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.n1.refresh_from_db()
        self.assertTrue(self.n1.read)

    def test_cannot_patch_other_users_notification(self):
        other_notif = Notification.objects.get(user=self.other)
        resp = self.client.patch(f"/api/v1/notifications/{other_notif.id}/", {"read": True}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_patch_returns_401(self):
        self.client.force_authenticate(user=None)
        resp = self.client.patch(f"/api/v1/notifications/{self.n1.id}/", {"read": True}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class NotificationMarkAllReadTests(NotificationBaseTestCase):
    def test_mark_all_read(self):
        resp = self.client.post("/api/v1/notifications/mark_all_read/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["marked"], 1)
        self.n1.refresh_from_db()
        self.assertTrue(self.n1.read)

    def test_mark_all_read_affects_only_own(self):
        self.client.post("/api/v1/notifications/mark_all_read/")
        other_notif = Notification.objects.get(user=self.other)
        self.assertFalse(other_notif.read)

    def test_unauthenticated_mark_all_returns_401(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post("/api/v1/notifications/mark_all_read/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class NotificationMethodTests(NotificationBaseTestCase):
    def test_post_not_allowed(self):
        resp = self.client.post("/api/v1/notifications/", {"title": "x", "body": "y"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_not_allowed(self):
        resp = self.client.delete(f"/api/v1/notifications/{self.n1.id}/")
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
