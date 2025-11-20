from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from urllib.parse import urlparse


class PasswordResetFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="gabriel",
            email="gabriel@example.com",
            password="SenhaInicial123",
        )

    def test_password_reset_request_and_confirm(self):
        response = self.client.post(
            reverse("accounts:password_reset"),
            {"email": self.user.email},
        )
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)

        reset_link = next(
            (line.strip() for line in mail.outbox[0].body.splitlines() if "/accounts/reset/" in line),
            "",
        )
        self.assertTrue(reset_link)
        path = urlparse(reset_link).path

        get_response = self.client.get(path, follow=True)
        target_path = get_response.request.get("PATH_INFO", path)

        resp = self.client.post(
            target_path,
            {
                "new_password1": "NovaSenhaSegura123",
                "new_password2": "NovaSenhaSegura123",
            },
        )
        self.assertEqual(resp.status_code, 302)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NovaSenhaSegura123"))
