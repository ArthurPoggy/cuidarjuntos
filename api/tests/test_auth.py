from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import Profile


class RegisterTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/v1/auth/register/"

    def test_register_success(self):
        data = {
            "full_name": "Maria Silva",
            "cpf": "12345678901",
            "birth_date": "1990-05-15",
            "email": "maria@test.com",
            "username": "maria",
            "password": "securepass123",
        }
        resp = self.client.post(self.url, data, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("tokens", resp.data)
        self.assertIn("access", resp.data["tokens"])
        self.assertIn("refresh", resp.data["tokens"])
        self.assertEqual(resp.data["user"]["username"], "maria")

        user = User.objects.get(username="maria")
        self.assertEqual(user.email, "maria@test.com")
        self.assertEqual(user.profile.cpf, "12345678901")
        self.assertEqual(user.profile.full_name, "Maria Silva")

    def test_register_duplicate_email(self):
        User.objects.create_user("existing", email="maria@test.com", password="pass1234")
        data = {
            "full_name": "Maria",
            "cpf": "12345678901",
            "email": "maria@test.com",
            "username": "maria2",
            "password": "securepass123",
        }
        resp = self.client.post(self.url, data, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_duplicate_cpf(self):
        user = User.objects.create_user("old", email="old@test.com", password="pass1234")
        Profile.objects.filter(user=user).update(cpf="12345678901")
        data = {
            "full_name": "Maria",
            "cpf": "12345678901",
            "email": "new@test.com",
            "username": "newuser",
            "password": "securepass123",
        }
        resp = self.client.post(self.url, data, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_short_cpf(self):
        data = {
            "full_name": "Maria",
            "cpf": "1234",
            "email": "maria@test.com",
            "username": "maria",
            "password": "securepass123",
        }
        resp = self.client.post(self.url, data, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_username_with_spaces(self):
        data = {
            "full_name": "Maria",
            "cpf": "12345678901",
            "email": "maria@test.com",
            "username": "maria silva",
            "password": "securepass123",
        }
        resp = self.client.post(self.url, data, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class TokenTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("testuser", password="testpass123")

    def test_token_obtain(self):
        resp = self.client.post(
            "/api/v1/auth/token/",
            {"username": "testuser", "password": "testpass123"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)

    def test_token_refresh(self):
        resp = self.client.post(
            "/api/v1/auth/token/",
            {"username": "testuser", "password": "testpass123"},
            format="json",
        )
        refresh = resp.data["refresh"]
        resp2 = self.client.post(
            "/api/v1/auth/token/refresh/",
            {"refresh": refresh},
            format="json",
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp2.data)


class MeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("testuser", password="testpass123", email="test@test.com")
        self.client.force_authenticate(user=self.user)

    def test_me_authenticated(self):
        resp = self.client.get("/api/v1/auth/me/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["username"], "testuser")

    def test_me_unauthenticated(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get("/api/v1/auth/me/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
