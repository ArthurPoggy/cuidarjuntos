from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, TestCase
from django.urls import reverse
from urllib.parse import urlparse

from accounts.models import Profile


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


class AuthStressTests(TestCase):
    """
    Exercita fluxos de login/cadastro em volume para detectar falsas colisoes
    (ex.: usuario novo recebendo erro de 'ja existe').
    """

    def setUp(self):
        self.base_password = "SenhaForte123!"
        self.base_user = User.objects.create_user(
            username="stress-base",
            email="stress-base@example.com",
            password=self.base_password,
        )

    def _registration_payload(self, idx: int) -> dict:
        return {
            "full_name": f"Stress User {idx}",
            "cpf": str(idx).zfill(11),
            "birth_date": "1990-01-01",
            "email": f"stress{idx}@example.com",
            "username": f"stress{idx}",
            "password1": self.base_password,
            "password2": self.base_password,
        }

    def test_repeated_logins_do_not_create_duplicates(self):
        client = Client()
        for _ in range(50):
            resp = client.post(
                reverse("accounts:login"),
                {"username": self.base_user.username, "password": self.base_password},
            )
            self.assertEqual(resp.status_code, 302)
            client.logout()

        # Nenhum usuario extra deve ser criado ao longo dos logins
        self.assertEqual(User.objects.filter(username=self.base_user.username).count(), 1)

    def test_bulk_signups_with_unique_data(self):
        total = 40
        expected_usernames = []
        for i in range(total):
            client = Client()
            payload = self._registration_payload(i)
            expected_usernames.append(payload["username"])
            resp = client.post(reverse("accounts:register"), payload)
            self.assertEqual(resp.status_code, 302, msg=f"Falhou no indice {i}")

        created = User.objects.filter(username__in=expected_usernames).count()
        self.assertEqual(created, total)

    def test_duplicate_signup_requests_only_create_single_user(self):
        client = Client()
        payload = self._registration_payload(999999)

        first = client.post(reverse("accounts:register"), payload)
        self.assertEqual(first.status_code, 302)

        # Simula reenvio rapido do mesmo formulario
        second = client.post(reverse("accounts:register"), payload)
        self.assertEqual(second.status_code, 200)

        # Deve existir apenas um usuario/perfil com o username/CPF informado
        self.assertEqual(User.objects.filter(username=payload["username"]).count(), 1)
        self.assertEqual(Profile.objects.filter(cpf=payload["cpf"]).count(), 1)

        # A tela deve exibir erro de duplicidade, nao sucesso silencioso
        form = second.context.get("form")
        self.assertIsNotNone(form)
        errors = sum((err_list for err_list in form.errors.values()), []) + list(form.non_field_errors())
        self.assertTrue(any("existe" in err.lower() for err in errors))
