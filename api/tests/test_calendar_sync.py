"""Testes da lógica de criação de eventos no Google Calendar/Outlook (card #46).

Cobre `api/services/calendar_sync.py`. Nenhum teste chama a API real do
Google/Microsoft -- todas as chamadas HTTP externas (googleapiclient,
google-auth, msal, requests) são mockadas.
"""
from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from api.services import calendar_sync
from care.models import CareRecord, ExternalCalendarToken, Patient


class CalendarSyncTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="cuidador_cal", password="fake-test-pass-789"
        )
        self.patient = Patient.objects.create(name="Paciente Teste")
        self.record = CareRecord.objects.create(
            patient=self.patient,
            type="medication",
            what="Remédio da manhã",
            description="Tomar com água",
            date=date.today() + timedelta(days=1),
            time=time(9, 0),
            caregiver="Cuidador Teste",
        )

    def _google_token(self, expired=False):
        expires_at = (
            timezone.now() - timedelta(minutes=5)
            if expired
            else timezone.now() + timedelta(hours=1)
        )
        return ExternalCalendarToken.objects.create(
            user=self.user,
            provider=ExternalCalendarToken.Provider.GOOGLE,
            access_token="access-google-antigo",
            refresh_token="refresh-google",
            expires_at=expires_at,
        )

    def _microsoft_token(self, expired=False):
        expires_at = (
            timezone.now() - timedelta(minutes=5)
            if expired
            else timezone.now() + timedelta(hours=1)
        )
        return ExternalCalendarToken.objects.create(
            user=self.user,
            provider=ExternalCalendarToken.Provider.MICROSOFT,
            access_token="access-ms-antigo",
            refresh_token="refresh-ms",
            expires_at=expires_at,
        )


class GetGoogleServiceTests(CalendarSyncTestCase):
    def test_sem_token_retorna_none(self):
        self.assertIsNone(calendar_sync._get_google_service(self.user))

    @patch("api.services.calendar_sync.build_google_service")
    def test_token_valido_nao_renova(self, mock_build):
        token = self._google_token(expired=False)
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        with patch("google.oauth2.credentials.Credentials.refresh") as mock_refresh:
            service = calendar_sync._get_google_service(self.user)

        mock_refresh.assert_not_called()
        self.assertIs(service, mock_service)
        token.refresh_from_db()
        self.assertEqual(token.access_token, "access-google-antigo")

    @patch("api.services.calendar_sync.build_google_service")
    def test_expiracao_nula_forca_renovacao(self, mock_build):
        """Sem `expires_at` nao da para afirmar que o token vale -- renove."""
        token = ExternalCalendarToken.objects.create(
            user=self.user,
            provider=ExternalCalendarToken.Provider.GOOGLE,
            access_token="a",
            refresh_token="r",
        )
        mock_build.return_value = MagicMock()

        def _fake_refresh(self, request):
            self.token = "access-renovado"
            self.expiry = datetime.utcnow() + timedelta(hours=1)

        with patch("google.oauth2.credentials.Credentials.refresh", new=_fake_refresh):
            calendar_sync._get_google_service(self.user)

        token.refresh_from_db()
        self.assertEqual(token.access_token, "access-renovado")

    @patch("api.services.calendar_sync.build_google_service")
    def test_token_expirado_renova_e_persiste_novo_token(self, mock_build):
        token = self._google_token(expired=True)
        mock_build.return_value = MagicMock()

        def _fake_refresh(self, request):
            self.token = "access-google-novo"
            self.expiry = datetime.utcnow() + timedelta(hours=1)

        with patch("google.oauth2.credentials.Credentials.refresh", new=_fake_refresh):
            service = calendar_sync._get_google_service(self.user)

        self.assertIsNotNone(service)
        token.refresh_from_db()
        self.assertEqual(token.access_token, "access-google-novo")
        self.assertEqual(token.refresh_token, "refresh-google")
        self.assertGreater(token.expires_at, timezone.now())

    def test_refresh_falha_deleta_token_e_loga_warning(self):
        self._google_token(expired=True)

        with patch(
            "google.oauth2.credentials.Credentials.refresh",
            side_effect=Exception("token revogado"),
        ):
            with self.assertLogs("api.services.calendar_sync", level="WARNING") as logs:
                service = calendar_sync._get_google_service(self.user)

        self.assertIsNone(service)
        self.assertFalse(
            ExternalCalendarToken.objects.filter(
                user=self.user, provider=ExternalCalendarToken.Provider.GOOGLE
            ).exists()
        )
        self.assertTrue(any("renovar" in m.lower() for m in logs.output))


@override_settings(CALENDAR_EVENT_DETAIL_LEVEL="full")
class SyncRecordToGoogleTests(CalendarSyncTestCase):
    @patch("api.services.calendar_sync.build_google_service")
    def test_cria_evento_com_prefixo_no_titulo(self, mock_build):
        self._google_token(expired=False)
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        result = calendar_sync.sync_record_to_google(self.record, self.user)

        self.assertTrue(result)
        insert_call = mock_service.events.return_value.insert
        insert_call.assert_called_once()
        body = insert_call.call_args.kwargs["body"]
        self.assertEqual(body["summary"], f"[CuidarJuntos] {self.record.what}")
        self.assertEqual(body["description"], self.record.description)
        insert_call.return_value.execute.assert_called_once()

    @patch("api.services.calendar_sync.build_google_service")
    def test_horario_do_evento_bate_com_o_registro(self, mock_build):
        self._google_token(expired=False)
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        calendar_sync.sync_record_to_google(self.record, self.user)

        body = mock_service.events.return_value.insert.call_args.kwargs["body"]
        start = datetime.fromisoformat(body["start"]["dateTime"])
        self.assertEqual(start.hour, 9)
        self.assertEqual(start.minute, 0)
        self.assertEqual(start.date(), self.record.date)
        # O Google infere o fuso do offset, entao ele precisa vir junto.
        self.assertIsNotNone(start.tzinfo)

    def test_sem_token_retorna_false_sem_chamar_api(self):
        result = calendar_sync.sync_record_to_google(self.record, self.user)
        self.assertFalse(result)

    @patch("api.services.calendar_sync.build_google_service")
    def test_falha_na_api_retorna_false(self, mock_build):
        self._google_token(expired=False)
        mock_service = MagicMock()
        mock_service.events.return_value.insert.return_value.execute.side_effect = (
            Exception("boom")
        )
        mock_build.return_value = mock_service

        result = calendar_sync.sync_record_to_google(self.record, self.user)
        self.assertFalse(result)


@override_settings(CALENDAR_EVENT_DETAIL_LEVEL="full")
class SyncRecordToMicrosoftTests(CalendarSyncTestCase):
    @patch("api.services.calendar_sync.requests.post")
    def test_token_valido_cria_evento_com_prefixo(self, mock_post):
        self._microsoft_token(expired=False)
        mock_response = MagicMock(status_code=201)
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = calendar_sync.sync_record_to_microsoft(self.record, self.user)

        self.assertTrue(result)
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertEqual(
            kwargs["json"]["subject"], f"[CuidarJuntos] {self.record.what}"
        )
        self.assertEqual(
            kwargs["headers"]["Authorization"], "Bearer access-ms-antigo"
        )

    @patch("api.services.calendar_sync.requests.post")
    def test_graph_recebe_datetime_sem_offset_e_em_utc(self, mock_post):
        """O Graph espera `dateTime` sem offset, com o fuso em `timeZone`.

        Mandar "...-03:00" junto de timeZone "UTC" faz o evento aparecer
        deslocado -- num lembrete de medicacao isso tem consequencia clinica.
        """
        self._microsoft_token(expired=False)
        mock_response = MagicMock(status_code=201)
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        calendar_sync.sync_record_to_microsoft(self.record, self.user)

        body = mock_post.call_args.kwargs["json"]
        self.assertEqual(body["start"]["timeZone"], "UTC")

        raw_start = body["start"]["dateTime"]
        self.assertNotIn("+", raw_start)
        self.assertFalse(raw_start.endswith("Z"))
        parsed = datetime.fromisoformat(raw_start)
        self.assertIsNone(parsed.tzinfo, "dateTime nao pode levar offset")

        # E o instante precisa ser o mesmo do registro, so que em UTC.
        expected_start, _ = calendar_sync._event_datetimes(self.record)
        self.assertEqual(
            parsed.replace(tzinfo=dt_timezone.utc),
            expected_start.astimezone(dt_timezone.utc),
        )

    @patch("api.services.calendar_sync.requests.post")
    @patch("msal.ConfidentialClientApplication.acquire_token_by_refresh_token")
    def test_token_expirado_renova_antes_de_criar_evento(self, mock_acquire, mock_post):
        token = self._microsoft_token(expired=True)
        mock_acquire.return_value = {
            "access_token": "access-ms-novo",
            "refresh_token": "refresh-ms-novo",
            "expires_in": 3600,
        }
        mock_response = MagicMock(status_code=201)
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = calendar_sync.sync_record_to_microsoft(self.record, self.user)

        self.assertTrue(result)
        token.refresh_from_db()
        self.assertEqual(token.access_token, "access-ms-novo")
        self.assertEqual(token.refresh_token, "refresh-ms-novo")
        _, kwargs = mock_post.call_args
        self.assertEqual(
            kwargs["headers"]["Authorization"], "Bearer access-ms-novo"
        )

    @patch("msal.ConfidentialClientApplication.acquire_token_by_refresh_token")
    def test_refresh_falha_deleta_token_e_loga_warning(self, mock_acquire):
        self._microsoft_token(expired=True)
        mock_acquire.return_value = {"error": "invalid_grant"}

        with self.assertLogs("api.services.calendar_sync", level="WARNING") as logs:
            result = calendar_sync.sync_record_to_microsoft(self.record, self.user)

        self.assertFalse(result)
        self.assertFalse(
            ExternalCalendarToken.objects.filter(
                user=self.user, provider=ExternalCalendarToken.Provider.MICROSOFT
            ).exists()
        )
        self.assertTrue(any("renovar" in m.lower() for m in logs.output))

    def test_sem_token_retorna_false(self):
        result = calendar_sync.sync_record_to_microsoft(self.record, self.user)
        self.assertFalse(result)


class EventDetailLevelTests(CalendarSyncTestCase):
    """Por padrao o evento nao carrega dado de saude para o terceiro."""

    def test_default_e_discreto(self):
        self.assertEqual(
            calendar_sync._event_title(self.record), "[CuidarJuntos] Cuidado agendado"
        )
        self.assertEqual(calendar_sync._event_description(self.record), "")
        self.assertNotIn("Remédio", calendar_sync._event_title(self.record))

    @override_settings(CALENDAR_EVENT_DETAIL_LEVEL="full")
    def test_modo_full_inclui_o_que_e_a_descricao(self):
        self.assertEqual(
            calendar_sync._event_title(self.record),
            "[CuidarJuntos] Remédio da manhã",
        )
        self.assertEqual(
            calendar_sync._event_description(self.record), "Tomar com água"
        )


class SyncRecordTests(CalendarSyncTestCase):
    @patch("api.services.calendar_sync.sync_record_to_google")
    @patch("api.services.calendar_sync.sync_record_to_microsoft")
    def test_usa_google_quando_so_ele_esta_conectado(self, mock_ms, mock_google):
        self._google_token()
        mock_google.return_value = True

        result = calendar_sync.sync_record(self.record, self.user)

        self.assertTrue(result)
        mock_google.assert_called_once_with(self.record, self.user)
        mock_ms.assert_not_called()

    @patch("api.services.calendar_sync.sync_record_to_google")
    @patch("api.services.calendar_sync.sync_record_to_microsoft")
    def test_usa_microsoft_quando_so_ele_esta_conectado(self, mock_ms, mock_google):
        self._microsoft_token()
        mock_ms.return_value = True

        result = calendar_sync.sync_record(self.record, self.user)

        self.assertTrue(result)
        mock_ms.assert_called_once_with(self.record, self.user)
        mock_google.assert_not_called()

    @patch("api.services.calendar_sync.sync_record_to_google")
    @patch("api.services.calendar_sync.sync_record_to_microsoft")
    def test_com_os_dois_conectados_sincroniza_em_ambos(self, mock_ms, mock_google):
        """Um `.first()` sem ordenacao mandaria o evento para um calendario
        imprevisivel, sem o usuario saber qual."""
        self._google_token()
        self._microsoft_token()
        mock_google.return_value = True
        mock_ms.return_value = True

        result = calendar_sync.sync_record(self.record, self.user)

        self.assertTrue(result)
        mock_google.assert_called_once_with(self.record, self.user)
        mock_ms.assert_called_once_with(self.record, self.user)

    @patch("api.services.calendar_sync.sync_record_to_google")
    @patch("api.services.calendar_sync.sync_record_to_microsoft")
    def test_falha_em_um_provedor_faz_o_todo_falhar(self, mock_ms, mock_google):
        """O chamador usa o retorno para decidir se reprocessa depois."""
        self._google_token()
        self._microsoft_token()
        mock_google.return_value = True
        mock_ms.return_value = False

        self.assertFalse(calendar_sync.sync_record(self.record, self.user))
        # O provedor que funcionou nao pode ser pulado por causa do outro.
        mock_google.assert_called_once()

    def test_sem_nenhum_token_retorna_false(self):
        self.assertFalse(calendar_sync.sync_record(self.record, self.user))
