"""Testes do fluxo OAuth de conexão com o Microsoft Outlook (card #47).

Nenhuma chamada real à Microsoft: `msal.ConfidentialClientApplication` é
sempre mockado.
"""
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core import signing
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from care.models import ExternalCalendarToken

MICROSOFT_SETTINGS = dict(
    MICROSOFT_CLIENT_ID="fake-client-id",
    MICROSOFT_CLIENT_SECRET="fake-client-secret",
    MICROSOFT_TENANT_ID="fake-tenant-id",
    MICROSOFT_REDIRECT_URI="http://testserver/api/v1/calendar/microsoft/callback/",
    CALENDAR_INTEGRATION_DEEP_LINK="cuidarjuntos://integrations",
)

STATE_SALT = "api.views.calendar.microsoft-oauth-state"


@override_settings(**MICROSOFT_SETTINGS)
class MicrosoftCalendarAuthTests(TestCase):
    """GET /api/v1/calendar/microsoft/auth/"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("carer", password="pass1234")

    def test_requires_authentication(self):
        resp = self.client.get("/api/v1/calendar/microsoft/auth/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("api.views.calendar_microsoft.msal.ConfidentialClientApplication")
    def test_returns_authorization_url_from_msal(self, mock_app_cls):
        mock_app = MagicMock()
        mock_app.get_authorization_request_url.return_value = (
            "https://login.microsoftonline.com/fake-tenant-id/oauth2/v2.0/authorize?fake=1"
        )
        mock_app_cls.return_value = mock_app

        self.client.force_authenticate(user=self.user)
        resp = self.client.get("/api/v1/calendar/microsoft/auth/")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("auth_url", resp.data)
        self.assertTrue(
            resp.data["auth_url"].startswith("https://login.microsoftonline.com/")
        )

        # Confirma que o app MSAL foi construído com as credenciais de settings
        # (fake em teste) e não bateu em nenhuma API real.
        mock_app_cls.assert_called_once()
        _, kwargs = mock_app_cls.call_args
        self.assertEqual(kwargs["client_id"], "fake-client-id")
        self.assertEqual(kwargs["client_credential"], "fake-client-secret")
        self.assertIn("fake-tenant-id", kwargs["authority"])

        # O escopo Calendars.ReadWrite deve ter sido solicitado.
        call_args, _ = mock_app.get_authorization_request_url.call_args
        self.assertIn("Calendars.ReadWrite", call_args[0])

    @patch("api.views.calendar_microsoft.msal.ConfidentialClientApplication")
    def test_state_param_is_signed_and_carries_user(self, mock_app_cls):
        mock_app = MagicMock()
        mock_app.get_authorization_request_url.return_value = "https://example.test/auth"
        mock_app_cls.return_value = mock_app

        self.client.force_authenticate(user=self.user)
        self.client.get("/api/v1/calendar/microsoft/auth/")

        _, call_kwargs = mock_app.get_authorization_request_url.call_args
        payload = signing.loads(call_kwargs["state"], salt=STATE_SALT)
        self.assertEqual(payload["user_id"], self.user.id)

    @override_settings(MICROSOFT_CLIENT_SECRET="")
    def test_credencial_ausente_responde_503_e_nao_monta_fluxo(self):
        """Config faltando é erro NOSSO -- melhor 503 aqui do que um erro
        opaco da Microsoft depois do redirect."""
        self.client.force_authenticate(user=self.user)

        # `assertLogs("django.request")`: neste ambiente (Python 3.14) o
        # AdminEmailHandler quebra ao montar o e-mail de erro de qualquer
        # resposta 5xx; o assertLogs substitui os handlers durante o bloco.
        with self.assertLogs("api.views.calendar_microsoft", level="ERROR") as logs:
            with self.assertLogs("django.request", level="ERROR"):
                with patch(
                    "api.views.calendar_microsoft.msal.ConfidentialClientApplication"
                ) as mock_app_cls:
                    resp = self.client.get(
                        "/api/v1/calendar/microsoft/auth/",
                        HTTP_ACCEPT="application/json",
                    )

        self.assertEqual(resp.status_code, 503)
        mock_app_cls.assert_not_called()
        self.assertTrue(any("MICROSOFT_CLIENT_SECRET" in m for m in logs.output))


@override_settings(**MICROSOFT_SETTINGS)
class MicrosoftCalendarCallbackTests(TestCase):
    """GET /api/v1/calendar/microsoft/callback/"""

    URL = "/api/v1/calendar/microsoft/callback/"

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("carer", password="pass1234")

    def _valid_state(self, user=None):
        return signing.dumps(
            {"user_id": (user or self.user).id}, salt=STATE_SALT
        )

    def test_missing_code_or_state_redirects_with_reason(self):
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, status.HTTP_302_FOUND)
        self.assertEqual(
            resp.url, "cuidarjuntos://integrations?error=missing_code"
        )

    def test_provider_error_is_forwarded_url_encoded(self):
        """`error` vem de um endpoint publico: um "&" cru injetaria
        parametros extras no deep link (ex.: um connected=microsoft falso)."""
        resp = self.client.get(self.URL, {"error": "x&connected=microsoft"})
        self.assertEqual(resp.status_code, status.HTTP_302_FOUND)
        self.assertEqual(
            resp.url,
            "cuidarjuntos://integrations?error=x%26connected%3Dmicrosoft",
        )
        self.assertNotIn("connected=microsoft", resp.url)

    def test_invalid_state_redirects_with_reason(self):
        resp = self.client.get(
            self.URL, {"code": "abc", "state": "not-a-valid-signed-state"}
        )
        self.assertEqual(resp.status_code, status.HTTP_302_FOUND)
        self.assertEqual(
            resp.url, "cuidarjuntos://integrations?error=invalid_state"
        )

    def test_expired_state_tem_motivo_proprio(self):
        with patch(
            "django.core.signing.loads",
            side_effect=signing.SignatureExpired("velho"),
        ):
            resp = self.client.get(
                self.URL, {"code": "abc", "state": self._valid_state()}
            )
        self.assertEqual(resp.status_code, status.HTTP_302_FOUND)
        self.assertEqual(
            resp.url, "cuidarjuntos://integrations?error=expired_state"
        )

    def test_unknown_user_in_state_redirects_with_reason(self):
        state = signing.dumps({"user_id": 999999}, salt=STATE_SALT)
        resp = self.client.get(self.URL, {"code": "abc", "state": state})
        self.assertEqual(resp.status_code, status.HTTP_302_FOUND)
        self.assertEqual(
            resp.url, "cuidarjuntos://integrations?error=invalid_state"
        )

    @patch("api.views.calendar_microsoft.msal.ConfidentialClientApplication")
    def test_invalid_token_exchange_redirects_with_reason(self, mock_app_cls):
        mock_app = MagicMock()
        mock_app.acquire_token_by_authorization_code.return_value = {
            "error": "invalid_grant",
            "error_description": "code inválido ou expirado",
        }
        mock_app_cls.return_value = mock_app

        resp = self.client.get(
            self.URL, {"code": "bad-code", "state": self._valid_state()}
        )

        self.assertEqual(resp.status_code, status.HTTP_302_FOUND)
        self.assertEqual(
            resp.url, "cuidarjuntos://integrations?error=token_exchange_failed"
        )
        self.assertFalse(
            ExternalCalendarToken.objects.filter(
                user=self.user, provider="microsoft"
            ).exists()
        )

    @patch("api.views.calendar_microsoft.msal.ConfidentialClientApplication")
    def test_consentimento_sem_o_escopo_pedido_nao_salva_vinculo(self, mock_app_cls):
        """Salvar aqui faria o app dizer "conectado" e a falha so apareceria
        muito depois, num 403 ao criar o evento."""
        mock_app = MagicMock()
        mock_app.acquire_token_by_authorization_code.return_value = {
            "access_token": "fake-access-token",
            "refresh_token": "fake-refresh-token",
            "expires_in": 3600,
            "scope": ["Calendars.Read"],  # menos do que pedimos
        }
        mock_app_cls.return_value = mock_app

        resp = self.client.get(
            self.URL, {"code": "good-code", "state": self._valid_state()}
        )

        self.assertEqual(
            resp.url, "cuidarjuntos://integrations?error=insufficient_scope"
        )
        self.assertFalse(ExternalCalendarToken.objects.exists())

    @patch("api.views.calendar_microsoft.msal.ConfidentialClientApplication")
    def test_escopo_ausente_na_resposta_nao_bloqueia(self, mock_app_cls):
        """Nem todo fluxo devolve `scope`; ausencia nao e recusa."""
        mock_app = MagicMock()
        mock_app.acquire_token_by_authorization_code.return_value = {
            "access_token": "fake-access-token",
            "expires_in": 3600,
        }
        mock_app_cls.return_value = mock_app

        resp = self.client.get(
            self.URL, {"code": "good-code", "state": self._valid_state()}
        )

        self.assertEqual(
            resp.url, "cuidarjuntos://integrations?connected=microsoft"
        )
        self.assertTrue(ExternalCalendarToken.objects.exists())

    @patch("api.views.calendar_microsoft.msal.ConfidentialClientApplication")
    def test_successful_exchange_saves_token_and_redirects(self, mock_app_cls):
        mock_app = MagicMock()
        mock_app.acquire_token_by_authorization_code.return_value = {
            "access_token": "fake-access-token",
            "refresh_token": "fake-refresh-token",
            "expires_in": 3600,
            "scope": ["Calendars.ReadWrite"],
            "id_token_claims": {"preferred_username": "carer@example.com"},
        }
        mock_app_cls.return_value = mock_app

        resp = self.client.get(
            self.URL, {"code": "good-code", "state": self._valid_state()}
        )

        self.assertEqual(resp.status_code, status.HTTP_302_FOUND)
        self.assertEqual(
            resp.url, "cuidarjuntos://integrations?connected=microsoft"
        )

        token = ExternalCalendarToken.objects.get(
            user=self.user, provider="microsoft"
        )
        self.assertEqual(token.access_token, "fake-access-token")
        self.assertEqual(token.refresh_token, "fake-refresh-token")
        self.assertEqual(token.account_email, "carer@example.com")
        self.assertEqual(token.scope, "Calendars.ReadWrite")
        self.assertIsNotNone(token.expires_at)

        # O token não pode ser gravado em texto puro no banco (criptografado
        # em repouso via django-cryptography). Cursor bruto para evitar que
        # o ORM decripte o valor automaticamente ao ler.
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT access_token FROM care_externalcalendartoken WHERE id = %s",
                [token.id],
            )
            raw_access_token = cursor.fetchone()[0]
        if isinstance(raw_access_token, str):
            raw_access_token = raw_access_token.encode("utf-8", errors="ignore")
        self.assertNotIn(b"fake-access-token", raw_access_token)

    @patch("api.views.calendar_microsoft.msal.ConfidentialClientApplication")
    def test_callback_overwrites_existing_token(self, mock_app_cls):
        ExternalCalendarToken.objects.create(
            user=self.user,
            provider=ExternalCalendarToken.Provider.MICROSOFT,
            access_token="old-token",
            refresh_token="old-refresh",
        )

        mock_app = MagicMock()
        mock_app.acquire_token_by_authorization_code.return_value = {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
            "scope": "Calendars.ReadWrite",
        }
        mock_app_cls.return_value = mock_app

        self.client.get(
            self.URL, {"code": "good-code", "state": self._valid_state()}
        )

        self.assertEqual(
            ExternalCalendarToken.objects.filter(
                user=self.user, provider="microsoft"
            ).count(),
            1,
        )
        token = ExternalCalendarToken.objects.get(
            user=self.user, provider="microsoft"
        )
        self.assertEqual(token.access_token, "new-access-token")
        # `scope` como string crua (a Microsoft varia entre lista e string).
        self.assertEqual(token.scope, "Calendars.ReadWrite")
