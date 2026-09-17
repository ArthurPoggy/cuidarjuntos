"""Testes de POST /api/v1/calendar/disconnect/ (card #44).

Cobre os critérios de aceitação:
- provider obrigatório e deve ser "google" ou "microsoft" (senão 400);
- deleta o ExternalCalendarToken do usuário autenticado para aquele provedor;
- 200 {"disconnected": true} se havia token; 200 {"disconnected": false} se
  não havia (idempotente);
- tenta revogar a autorização no provedor antes de apagar localmente, e
  falha nessa revogação não impede a desconexão;
- eventos já criados no calendário externo não são removidos.

Nenhuma chamada HTTP real: `requests.post` é sempre mockado.
"""
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from care.models import ExternalCalendarToken

URL = "/api/v1/calendar/disconnect/"


class CalendarDisconnectTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("carer_cal", password="pass1234")
        self.client.force_authenticate(user=self.user)

        # Revogação no provedor é mockada por padrão: nenhum teste desta
        # suíte deve tocar a rede.
        patcher = patch("api.views.calendar_disconnect.requests.post")
        self.mock_post = patcher.start()
        self.addCleanup(patcher.stop)
        self.mock_post.return_value = MagicMock(
            status_code=200, raise_for_status=MagicMock(return_value=None)
        )

    def _make_token(self, user=None, provider="google"):
        return ExternalCalendarToken.objects.create(
            user=user or self.user,
            provider=provider,
            access_token="fake-access-token",
            refresh_token="fake-refresh-token",
            expires_at=timezone.now(),
        )

    # ------------------------------------------------------------------
    # Autenticação
    # ------------------------------------------------------------------

    def test_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post(URL, {"provider": "google"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # ------------------------------------------------------------------
    # Validação de payload (400)
    # ------------------------------------------------------------------

    def test_missing_provider_returns_400(self):
        resp = self.client.post(URL, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_blank_provider_returns_400(self):
        resp = self.client.post(URL, {"provider": ""}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_provider_returns_400(self):
        resp = self.client.post(URL, {"provider": "outlook_legacy"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ------------------------------------------------------------------
    # Desconexão com token existente (200, disconnected=True)
    # ------------------------------------------------------------------

    def test_disconnect_google_deletes_token(self):
        self._make_token(provider="google")
        resp = self.client.post(URL, {"provider": "google"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["disconnected"])
        self.assertFalse(
            ExternalCalendarToken.objects.filter(
                user=self.user, provider="google"
            ).exists()
        )

    def test_disconnect_microsoft_deletes_token(self):
        self._make_token(provider="microsoft")
        resp = self.client.post(URL, {"provider": "microsoft"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["disconnected"])
        self.assertFalse(
            ExternalCalendarToken.objects.filter(
                user=self.user, provider="microsoft"
            ).exists()
        )

    def test_disconnect_one_provider_keeps_the_other(self):
        self._make_token(provider="google")
        self._make_token(provider="microsoft")
        resp = self.client.post(URL, {"provider": "google"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["disconnected"])
        self.assertTrue(
            ExternalCalendarToken.objects.filter(
                user=self.user, provider="microsoft"
            ).exists()
        )

    # ------------------------------------------------------------------
    # Revogação no provedor
    # ------------------------------------------------------------------

    def test_desconectar_google_revoga_no_provedor(self):
        """Sem revogar, o refresh_token continua valido no Google mesmo
        depois de o app dizer que desconectou."""
        self._make_token(provider="google")

        resp = self.client.post(URL, {"provider": "google"}, format="json")

        self.assertTrue(resp.data["revoked_at_provider"])
        self.mock_post.assert_called_once()
        args, kwargs = self.mock_post.call_args
        self.assertEqual(args[0], "https://oauth2.googleapis.com/revoke")
        self.assertEqual(kwargs["data"], {"token": "fake-refresh-token"})

    def test_falha_na_revogacao_nao_impede_a_desconexao(self):
        """O token pode ja estar expirado, ou o provedor fora do ar."""
        import requests

        self._make_token(provider="google")
        self.mock_post.side_effect = requests.RequestException("provedor fora")

        with self.assertLogs("api.views.calendar_disconnect", level="WARNING"):
            resp = self.client.post(URL, {"provider": "google"}, format="json")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["disconnected"])
        self.assertFalse(resp.data["revoked_at_provider"])
        self.assertFalse(ExternalCalendarToken.objects.exists())

    def test_microsoft_nao_tenta_revogar(self):
        """A Microsoft nao expoe revogacao por token: e feita pelo usuario
        no portal da conta."""
        self._make_token(provider="microsoft")

        resp = self.client.post(URL, {"provider": "microsoft"}, format="json")

        self.assertTrue(resp.data["disconnected"])
        self.assertFalse(resp.data["revoked_at_provider"])
        self.mock_post.assert_not_called()

    # ------------------------------------------------------------------
    # Idempotência -- sem token existente (200, disconnected=False)
    # ------------------------------------------------------------------

    def test_disconnect_without_existing_token_returns_false(self):
        resp = self.client.post(URL, {"provider": "google"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["disconnected"])
        self.mock_post.assert_not_called()

    def test_disconnect_twice_is_idempotent(self):
        self._make_token(provider="google")
        first = self.client.post(URL, {"provider": "google"}, format="json")
        second = self.client.post(URL, {"provider": "google"}, format="json")
        self.assertTrue(first.data["disconnected"])
        self.assertFalse(second.data["disconnected"])

    # ------------------------------------------------------------------
    # Isolamento entre usuários
    # ------------------------------------------------------------------

    def test_does_not_delete_other_user_token(self):
        other = User.objects.create_user("other_cal", password="pass1234")
        self._make_token(user=other, provider="google")
        resp = self.client.post(URL, {"provider": "google"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["disconnected"])
        self.assertTrue(
            ExternalCalendarToken.objects.filter(
                user=other, provider="google"
            ).exists()
        )
        # E o token do outro usuario nao pode ser revogado no provedor.
        self.mock_post.assert_not_called()
