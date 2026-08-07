# api/tests/test_admin_security.py
"""
Testes de seguranca e integridade de dados de saude (tarefa #111):

(a) Endpoints administrativos em api/views/admin.py (protegidos por
    api.permissions.IsSuperUser) devem retornar 403 para qualquer usuario
    autenticado que NAO seja superuser -- inclusive staff sem is_superuser,
    e usuarios comuns. Sem autenticacao, 401/403 (nunca 200).

(b) Configuracao de transporte seguro em producao: cuidarjuntos/settings_production.py
    NAO PODE herdar os valores inseguros de desenvolvimento (settings.py tem
    DEBUG=True, CSRF_COOKIE_SECURE=False, SESSION_COOKIE_SECURE=False, o que
    e aceitavel apenas em dev). O settings_production deve garantir
    SECURE_SSL_REDIRECT=True, CSRF_COOKIE_SECURE=True, SESSION_COOKIE_SECURE=True
    e DEBUG=False.
"""
import importlib

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from care.models import CareGroup, GroupMembership, Patient


class AdminOverviewPermissionTest(TestCase):
    """api/views/admin.py::admin_overview eh protegido por IsSuperUser.
    Usuarios comuns (nao staff/superuser) e usuarios staff (mas nao
    superuser) devem receber 403, nunca 200."""

    url = "/api/v1/admin/overview/"

    def setUp(self):
        self.client = APIClient()

        self.regular_user = User.objects.create_user(
            "regular", password="pass1234"
        )

        self.staff_non_super = User.objects.create_user(
            "staffuser", password="pass1234", is_staff=True
        )

        self.superuser = User.objects.create_superuser(
            "boss", email="boss@test.com", password="pass1234"
        )

        # Usuario comum com vinculo normal a um grupo de cuidado (garante
        # que a permissao barrada nao depende de o usuario nao ter grupo).
        self.patient = Patient.objects.create(name="Paciente")
        self.group = CareGroup.objects.create(name="Grupo", patient=self.patient)
        GroupMembership.objects.create(
            user=self.regular_user, group=self.group, relation_to_patient="FAMILY"
        )

    def test_anonymous_cannot_access_admin_overview(self):
        resp = self.client.get(self.url)
        self.assertIn(
            resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
            f"usuario anonimo deveria ser barrado do endpoint admin, "
            f"obtido {resp.status_code}",
        )

    def test_regular_user_gets_403(self):
        self.client.force_authenticate(user=self.regular_user)
        resp = self.client.get(self.url)
        self.assertEqual(
            resp.status_code, status.HTTP_403_FORBIDDEN,
            f"usuario comum (nao staff/superuser) deveria receber 403 do "
            f"endpoint admin/overview, obtido {resp.status_code} "
            f"(corpo: {resp.content!r})",
        )

    def test_staff_non_superuser_gets_403(self):
        """is_staff=True sozinho NAO deve bastar para acessar rotas admin:
        IsSuperUser exige especificamente is_superuser."""
        self.client.force_authenticate(user=self.staff_non_super)
        resp = self.client.get(self.url)
        self.assertEqual(
            resp.status_code, status.HTTP_403_FORBIDDEN,
            f"usuario staff (mas nao superuser) deveria receber 403 do "
            f"endpoint admin/overview, obtido {resp.status_code} "
            f"(corpo: {resp.content!r})",
        )

    def test_superuser_can_access_admin_overview(self):
        self.client.force_authenticate(user=self.superuser)
        resp = self.client.get(self.url)
        self.assertEqual(
            resp.status_code, status.HTTP_200_OK,
            f"superuser deveria conseguir acessar admin/overview, obtido "
            f"{resp.status_code} (corpo: {resp.content!r})",
        )


class ProductionSettingsSecureTransportTest(TestCase):
    """cuidarjuntos/settings_production.py nao pode herdar configuracoes
    inseguras de desenvolvimento. Importa o modulo diretamente (nao via
    django.conf.settings, que neste projeto de testes carrega
    cuidarjuntos.settings, o modulo de DEV) para inspecionar exatamente os
    valores que seriam usados em producao."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.prod_settings = importlib.import_module("cuidarjuntos.settings_production")

    def test_debug_is_false(self):
        self.assertIs(
            self.prod_settings.DEBUG, False,
            "settings_production.DEBUG deve ser False",
        )

    def test_session_cookie_secure(self):
        self.assertIs(
            self.prod_settings.SESSION_COOKIE_SECURE, True,
            "settings_production.SESSION_COOKIE_SECURE deve ser True",
        )

    def test_csrf_cookie_secure(self):
        self.assertIs(
            self.prod_settings.CSRF_COOKIE_SECURE, True,
            "settings_production.CSRF_COOKIE_SECURE deve ser True",
        )

    def test_secure_ssl_redirect(self):
        self.assertIs(
            getattr(self.prod_settings, "SECURE_SSL_REDIRECT", False), True,
            "settings_production.SECURE_SSL_REDIRECT deve ser True para "
            "forcar redirecionamento HTTP -> HTTPS em producao (o modulo "
            "atualmente nao define essa variavel, entao o Django usa o "
            "default inseguro False).",
        )

    def test_unified_web_domain_is_allowed_host(self):
        """O dominio unico do app (Vercel), que faz proxy do acesso desktop
        para este backend via frontend/middleware.ts, precisa estar em
        ALLOWED_HOSTS, senao o Django rejeita o Host header com
        DisallowedHost assim que o proxy comeca a repassar requisicoes."""
        self.assertIn(
            self.prod_settings.UNIFIED_WEB_DOMAIN,
            self.prod_settings.ALLOWED_HOSTS,
        )

    def test_unified_web_domain_is_csrf_trusted_origin(self):
        expected_origin = f"https://{self.prod_settings.UNIFIED_WEB_DOMAIN}"
        self.assertIn(expected_origin, self.prod_settings.CSRF_TRUSTED_ORIGINS)
