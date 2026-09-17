"""Testes do fluxo OAuth de conexão com o Google Calendar (card #48).

Nunca chamamos a API real do Google aqui: `Flow.authorization_url` e
`Flow.fetch_token` são sempre mockados.
"""
from datetime import datetime, timezone as dt_timezone
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core import signing
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from care.models import ExternalCalendarToken

FAKE_SETTINGS = dict(
    GOOGLE_CLIENT_ID="fake-client-id.apps.googleusercontent.com",
    GOOGLE_CLIENT_SECRET="fake-client-secret-testing-only",
    GOOGLE_CALENDAR_REDIRECT_URI="http://testserver/api/v1/calendar/google/callback/",
    CALENDAR_INTEGRATION_DEEP_LINK="cuidarjuntos://integrations",
)


def _credentials_mock(token="fake-access-token", refresh="fake-refresh-token",
                      expiry=datetime(2026, 1, 1, 12, 0, 0), scopes=None):
    credentials = MagicMock()
    credentials.token = token
    credentials.refresh_token = refresh
    credentials.expiry = expiry
    credentials.scopes = scopes or ["https://www.googleapis.com/auth/calendar.events"]
    return credentials


@override_settings(**FAKE_SETTINGS)
class GoogleAuthUrlTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            "cuidadora", password="test-fake-password-123"
        )
        self.url = "/api/v1/calendar/google/auth/"

    def test_requires_authentication(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("api.views.calendar_google.Flow")
    def test_returns_google_authorization_url_with_calendar_scope(self, mock_flow_cls):
        mock_flow = MagicMock()
        mock_flow.authorization_url.return_value = (
            "https://accounts.google.com/o/oauth2/auth?fake=1",
            "state-value",
        )
        mock_flow_cls.from_client_config.return_value = mock_flow

        self.client.force_authenticate(self.user)
        resp = self.client.get(self.url)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(
            resp.data["auth_url"], "https://accounts.google.com/o/oauth2/auth?fake=1"
        )

        # Confere que o Flow foi montado com o escopo de eventos do calendário.
        _, kwargs = mock_flow_cls.from_client_config.call_args
        self.assertIn(
            "https://www.googleapis.com/auth/calendar.events", kwargs["scopes"]
        )

        # O state passado para authorization_url deve identificar o usuário logado.
        _, auth_kwargs = mock_flow.authorization_url.call_args
        payload = signing.loads(
            auth_kwargs["state"], salt="calendar-google-oauth", max_age=600
        )
        self.assertEqual(payload["user_id"], self.user.id)

    @override_settings(GOOGLE_CLIENT_SECRET="")
    def test_credencial_ausente_responde_503_e_nao_monta_fluxo(self):
        """Config faltando é erro NOSSO -- melhor 503 aqui do que um
        `invalid_client` opaco vindo do Google depois do redirect."""
        self.client.force_authenticate(self.user)

        # `assertLogs("django.request")` não é decoração: neste ambiente
        # (Python 3.14) o AdminEmailHandler quebra ao montar o e-mail de
        # erro de qualquer resposta 5xx, e o assertLogs substitui os
        # handlers do logger durante o bloco, contornando isso. De quebra,
        # confere que a falha de configuração foi de fato registrada.
        with self.assertLogs("api.views.calendar_google", level="ERROR") as logs:
            with self.assertLogs("django.request", level="ERROR"):
                with patch("api.views.calendar_google.Flow") as mock_flow_cls:
                    resp = self.client.get(self.url, HTTP_ACCEPT="application/json")

        self.assertEqual(resp.status_code, 503)
        mock_flow_cls.from_client_config.assert_not_called()
        self.assertTrue(any("GOOGLE_CLIENT_SECRET" in m for m in logs.output))


@override_settings(**FAKE_SETTINGS)
class GoogleAuthCallbackTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            "cuidador", password="test-fake-password-123"
        )
        self.url = "/api/v1/calendar/google/callback/"

    def _signed_state(self, user_id=None):
        return signing.dumps(
            {"user_id": user_id if user_id is not None else self.user.id},
            salt="calendar-google-oauth",
        )

    def test_google_error_redirects_with_error_param(self):
        resp = self.client.get(self.url, {"error": "access_denied"})
        self.assertEqual(resp.status_code, status.HTTP_302_FOUND)
        self.assertEqual(
            resp["Location"], "cuidarjuntos://integrations?error=access_denied"
        )
        self.assertFalse(ExternalCalendarToken.objects.exists())

    def test_error_param_is_url_encoded_and_cannot_inject_extra_params(self):
        # `error` vem direto do querystring de um endpoint público (AllowAny),
        # controlável por qualquer chamador (não só o Google). Um valor com
        # "&" cru injetaria parâmetros extras no deep link (ex.: um
        # "connected=google" falso). Precisa vir url-encoded.
        malicious_error = "x&connected=google"
        resp = self.client.get(self.url, {"error": malicious_error})
        self.assertEqual(resp.status_code, status.HTTP_302_FOUND)
        location = resp["Location"]
        self.assertEqual(
            location,
            "cuidarjuntos://integrations?error=x%26connected%3Dgoogle",
        )
        self.assertNotIn("connected=google", location)
        self.assertFalse(ExternalCalendarToken.objects.exists())

    def test_missing_code_redirects_with_error(self):
        resp = self.client.get(self.url, {"state": self._signed_state()})
        self.assertEqual(resp.status_code, status.HTTP_302_FOUND)
        self.assertIn("error=", resp["Location"])

    def test_invalid_state_redirects_with_error(self):
        resp = self.client.get(self.url, {"code": "abc123", "state": "adulterado"})
        self.assertEqual(resp.status_code, status.HTTP_302_FOUND)
        self.assertIn("error=invalid_state", resp["Location"])
        self.assertFalse(ExternalCalendarToken.objects.exists())

    def test_expired_state_tem_motivo_proprio(self):
        """O app precisa distinguir "expirou, tente de novo" de "adulterado"."""
        with patch(
            "django.core.signing.loads", side_effect=signing.SignatureExpired("velho")
        ):
            resp = self.client.get(
                self.url, {"code": "abc123", "state": self._signed_state()}
            )
        self.assertEqual(resp.status_code, status.HTTP_302_FOUND)
        self.assertIn("error=expired_state", resp["Location"])

    def test_unknown_user_in_state_redirects_with_error(self):
        resp = self.client.get(
            self.url, {"code": "abc", "state": self._signed_state(user_id=999999)}
        )
        self.assertEqual(resp.status_code, status.HTTP_302_FOUND)
        self.assertIn("error=invalid_state", resp["Location"])
        self.assertFalse(ExternalCalendarToken.objects.exists())

    @patch("api.views.calendar_google.Flow")
    def test_valid_code_exchanges_token_and_saves_it(self, mock_flow_cls):
        mock_flow = MagicMock()
        mock_flow.credentials = _credentials_mock()
        mock_flow_cls.from_client_config.return_value = mock_flow

        resp = self.client.get(
            self.url, {"code": "auth-code-123", "state": self._signed_state()}
        )

        self.assertEqual(resp.status_code, status.HTTP_302_FOUND)
        self.assertEqual(
            resp["Location"], "cuidarjuntos://integrations?connected=google"
        )

        mock_flow.fetch_token.assert_called_once_with(code="auth-code-123")

        token = ExternalCalendarToken.objects.get(
            user=self.user, provider=ExternalCalendarToken.Provider.GOOGLE
        )
        self.assertEqual(token.access_token, "fake-access-token")
        self.assertEqual(token.refresh_token, "fake-refresh-token")
        self.assertTrue(token.is_active)

    @patch("api.views.calendar_google.Flow")
    def test_expiry_naive_do_google_e_gravada_como_utc(self, mock_flow_cls):
        mock_flow = MagicMock()
        mock_flow.credentials = _credentials_mock(
            expiry=datetime(2026, 1, 1, 12, 0, 0)
        )
        mock_flow_cls.from_client_config.return_value = mock_flow

        self.client.get(
            self.url, {"code": "auth-code-123", "state": self._signed_state()}
        )

        token = ExternalCalendarToken.objects.get(user=self.user)
        self.assertEqual(
            token.expires_at, datetime(2026, 1, 1, 12, 0, 0, tzinfo=dt_timezone.utc)
        )

    @patch("api.views.calendar_google.Flow")
    def test_escopo_concedido_e_persistido(self, mock_flow_cls):
        mock_flow = MagicMock()
        mock_flow.credentials = _credentials_mock(
            scopes=["https://www.googleapis.com/auth/calendar.events"]
        )
        mock_flow_cls.from_client_config.return_value = mock_flow

        self.client.get(
            self.url, {"code": "auth-code-123", "state": self._signed_state()}
        )

        token = ExternalCalendarToken.objects.get(user=self.user)
        self.assertTrue(
            token.has_scope("https://www.googleapis.com/auth/calendar.events")
        )

    @patch("api.views.calendar_google.Flow")
    def test_sem_refresh_token_o_vinculo_nao_e_salvo(self, mock_flow_cls):
        """Gravar um vinculo sem refresh_token cria uma integracao que morre
        na primeira expiracao e some sozinha -- melhor recusar agora."""
        mock_flow = MagicMock()
        mock_flow.credentials = _credentials_mock(refresh=None)
        mock_flow_cls.from_client_config.return_value = mock_flow

        resp = self.client.get(
            self.url, {"code": "auth-code-123", "state": self._signed_state()}
        )

        self.assertEqual(resp.status_code, status.HTTP_302_FOUND)
        self.assertIn("error=no_refresh_token", resp["Location"])
        self.assertFalse(ExternalCalendarToken.objects.exists())

    @patch("api.views.calendar_google.Flow")
    def test_reconexao_sem_refresh_token_preserva_o_ja_salvo(self, mock_flow_cls):
        """O Google so devolve refresh_token na primeira autorizacao: numa
        reconexao, manter o que ja temos e melhor do que recusar."""
        ExternalCalendarToken.objects.create(
            user=self.user,
            provider=ExternalCalendarToken.Provider.GOOGLE,
            access_token="token-antigo",
            refresh_token="refresh-que-ja-tinhamos",
        )
        mock_flow = MagicMock()
        mock_flow.credentials = _credentials_mock(
            token="token-novo", refresh=None
        )
        mock_flow_cls.from_client_config.return_value = mock_flow

        resp = self.client.get(
            self.url, {"code": "novo-code", "state": self._signed_state()}
        )

        self.assertEqual(
            resp["Location"], "cuidarjuntos://integrations?connected=google"
        )
        token = ExternalCalendarToken.objects.get(user=self.user)
        self.assertEqual(token.access_token, "token-novo")
        self.assertEqual(token.refresh_token, "refresh-que-ja-tinhamos")

    @patch("api.views.calendar_google.Flow")
    def test_reconnecting_overwrites_existing_token(self, mock_flow_cls):
        ExternalCalendarToken.objects.create(
            user=self.user,
            provider=ExternalCalendarToken.Provider.GOOGLE,
            access_token="token-antigo",
            refresh_token="refresh-antigo",
            expires_at=datetime(2020, 1, 1, tzinfo=dt_timezone.utc),
        )

        mock_flow = MagicMock()
        mock_flow.credentials = _credentials_mock(
            token="token-novo",
            refresh="refresh-novo",
            expiry=datetime(2026, 6, 1, 12, 0, 0),
        )
        mock_flow_cls.from_client_config.return_value = mock_flow

        resp = self.client.get(
            self.url, {"code": "novo-code", "state": self._signed_state()}
        )

        self.assertEqual(resp.status_code, status.HTTP_302_FOUND)
        self.assertEqual(
            ExternalCalendarToken.objects.filter(
                user=self.user, provider=ExternalCalendarToken.Provider.GOOGLE
            ).count(),
            1,
        )
        token = ExternalCalendarToken.objects.get(
            user=self.user, provider=ExternalCalendarToken.Provider.GOOGLE
        )
        self.assertEqual(token.access_token, "token-novo")
        self.assertEqual(token.refresh_token, "refresh-novo")

    @patch("api.views.calendar_google.Flow")
    def test_fetch_token_failure_redirects_with_error(self, mock_flow_cls):
        mock_flow = MagicMock()
        mock_flow.fetch_token.side_effect = Exception("boom")
        mock_flow_cls.from_client_config.return_value = mock_flow

        with self.assertLogs("api.views.calendar_google", level="ERROR") as logs:
            resp = self.client.get(
                self.url, {"code": "auth-code-123", "state": self._signed_state()}
            )

        self.assertEqual(resp.status_code, status.HTTP_302_FOUND)
        self.assertIn("error=token_exchange_failed", resp["Location"])
        self.assertFalse(ExternalCalendarToken.objects.exists())
        # A falha precisa deixar rastro: sem log, em producao so sobra o
        # "?error=token_exchange_failed" na tela do usuario.
        self.assertTrue(any("Falha ao trocar code" in m for m in logs.output))
