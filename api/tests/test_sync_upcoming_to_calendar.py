"""Testes da task diária `sync_upcoming_to_calendar` (card #45).

Cobre os critérios de aceitação:
- busca CareRecord PENDING do dia seguinte com sync_to_calendar=True;
- para cada registro elegível, chama sync_record(record, member) para cada
  membro do grupo que tenha ExternalCalendarToken;
- registros já sincronizados não são reenviados;
- falhas individuais são logadas e não interrompem os demais registros;
- a task é idempotente (rodar duas vezes não duplica eventos).

Nenhuma chamada HTTP real ao Google/Microsoft: `sync_record` é sempre
mockado.
"""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from api.tasks import sync_upcoming_to_calendar
from care.models import (
    CareGroup, CareRecord, ExternalCalendarToken, GroupMembership, Patient,
)


class SyncUpcomingToCalendarTests(TestCase):
    def setUp(self):
        self.patient = Patient.objects.create(name="Paciente Teste")
        self.group = CareGroup.objects.create(name="Grupo Teste", patient=self.patient)

        self.member_with_token = User.objects.create_user(
            username="com_token", password="fake-test-pass-1"
        )
        GroupMembership.objects.create(
            user=self.member_with_token,
            group=self.group,
            relation_to_patient="FAMILY",
        )
        ExternalCalendarToken.objects.create(
            user=self.member_with_token,
            provider=ExternalCalendarToken.Provider.GOOGLE,
            access_token="fake-access",
            refresh_token="fake-refresh",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        self.member_without_token = User.objects.create_user(
            username="sem_token", password="fake-test-pass-2"
        )
        GroupMembership.objects.create(
            user=self.member_without_token,
            group=self.group,
            relation_to_patient="CAREGIVER",
        )

        self.tomorrow = timezone.localdate() + timedelta(days=1)

    def _create_record(self, **kwargs):
        defaults = dict(
            patient=self.patient,
            caregiver="Cuidador Teste",
            what="Medicação X",
            date=self.tomorrow,
            time=timezone.now().time(),
            status=CareRecord.Status.PENDING,
            sync_to_calendar=True,
        )
        defaults.update(kwargs)
        return CareRecord.objects.create(**defaults)

    # ------------------------------------------------------------------
    # Seleção dos registros
    # ------------------------------------------------------------------

    @patch("api.services.calendar_sync.sync_record")
    def test_sincroniza_registro_elegivel_com_membro_que_tem_token(self, mock_sync):
        mock_sync.return_value = True
        record = self._create_record()

        sync_upcoming_to_calendar()

        mock_sync.assert_called_once_with(record, self.member_with_token)
        record.refresh_from_db()
        self.assertIsNotNone(record.synced_to_external_at)

    @patch("api.services.calendar_sync.sync_record")
    def test_nao_chama_sync_para_membro_sem_token(self, mock_sync):
        mock_sync.return_value = True
        self._create_record()

        sync_upcoming_to_calendar()

        called_users = [call.args[1] for call in mock_sync.call_args_list]
        self.assertNotIn(self.member_without_token, called_users)

    @patch("api.services.calendar_sync.sync_record")
    def test_ignora_registro_sem_sync_to_calendar(self, mock_sync):
        self._create_record(sync_to_calendar=False)
        sync_upcoming_to_calendar()
        mock_sync.assert_not_called()

    @patch("api.services.calendar_sync.sync_record")
    def test_ignora_registro_nao_pendente(self, mock_sync):
        self._create_record(status=CareRecord.Status.DONE)
        sync_upcoming_to_calendar()
        mock_sync.assert_not_called()

    @patch("api.services.calendar_sync.sync_record")
    def test_ignora_registro_de_outro_dia(self, mock_sync):
        self._create_record(date=self.tomorrow + timedelta(days=1))
        self._create_record(date=self.tomorrow - timedelta(days=1))
        sync_upcoming_to_calendar()
        mock_sync.assert_not_called()

    @patch("api.services.calendar_sync.sync_record")
    def test_nao_reenvia_registro_ja_sincronizado(self, mock_sync):
        self._create_record(synced_to_external_at=timezone.now())
        sync_upcoming_to_calendar()
        mock_sync.assert_not_called()

    @patch("api.services.calendar_sync.sync_record")
    def test_task_idempotente_segunda_execucao_nao_reenvia(self, mock_sync):
        mock_sync.return_value = True
        self._create_record()

        sync_upcoming_to_calendar()
        sync_upcoming_to_calendar()

        self.assertEqual(mock_sync.call_count, 1)

    # ------------------------------------------------------------------
    # Tratamento de falha
    # ------------------------------------------------------------------

    @patch("api.services.calendar_sync.sync_record")
    def test_retorno_false_nao_marca_como_sincronizado(self, mock_sync):
        """`sync_record` sinaliza falha pelo RETORNO, nao por excecao: ele
        captura os erros de rede/API internamente.

        Regressao: ignorar o retorno fazia a falha marcar
        `synced_to_external_at`, e como o filtro do proximo beat e
        `synced_to_external_at__isnull=True`, o registro nunca mais era
        tentado -- o cuidado sumia do calendario sem nada nos logs.
        """
        mock_sync.return_value = False
        record = self._create_record()

        with self.assertLogs("api.tasks", level="WARNING") as logs:
            sync_upcoming_to_calendar()

        record.refresh_from_db()
        self.assertIsNone(record.synced_to_external_at)
        self.assertTrue(any("nao sincronizado" in m for m in logs.output))

    @patch("api.services.calendar_sync.sync_record")
    def test_registro_nao_marcado_e_retentado_no_beat_seguinte(self, mock_sync):
        mock_sync.return_value = False
        self._create_record()

        with self.assertLogs("api.tasks", level="WARNING"):
            sync_upcoming_to_calendar()
        mock_sync.return_value = True
        sync_upcoming_to_calendar()

        self.assertEqual(mock_sync.call_count, 2)

    @patch("api.services.calendar_sync.sync_record")
    def test_excecao_inesperada_tambem_conta_como_falha(self, mock_sync):
        mock_sync.side_effect = RuntimeError("boom")
        record = self._create_record()

        with self.assertLogs("api.tasks", level="WARNING"):
            sync_upcoming_to_calendar()  # não deve levantar

        record.refresh_from_db()
        self.assertIsNone(record.synced_to_external_at)

    @patch("api.services.calendar_sync.sync_record")
    def test_falha_individual_nao_interrompe_os_demais(self, mock_sync):
        record_falha = self._create_record(what="Falha")
        record_ok = self._create_record(what="OK")

        def side_effect(record, member):
            return record.id != record_falha.id

        mock_sync.side_effect = side_effect

        with self.assertLogs("api.tasks", level="WARNING"):
            sync_upcoming_to_calendar()

        record_falha.refresh_from_db()
        record_ok.refresh_from_db()
        self.assertIsNone(record_falha.synced_to_external_at)
        self.assertIsNotNone(record_ok.synced_to_external_at)

    @patch("api.services.calendar_sync.sync_record")
    def test_falha_de_um_membro_nao_pula_os_outros(self, mock_sync):
        outro = User.objects.create_user("outro_com_token", password="fake-3")
        GroupMembership.objects.create(
            user=outro, group=self.group, relation_to_patient="CAREGIVER"
        )
        ExternalCalendarToken.objects.create(
            user=outro,
            provider=ExternalCalendarToken.Provider.MICROSOFT,
            access_token="a",
        )
        self._create_record()

        mock_sync.side_effect = lambda record, member: member != self.member_with_token

        with self.assertLogs("api.tasks", level="WARNING"):
            sync_upcoming_to_calendar()

        synced_members = {call.args[1] for call in mock_sync.call_args_list}
        self.assertEqual(synced_members, {self.member_with_token, outro})

    # ------------------------------------------------------------------
    # Casos de borda
    # ------------------------------------------------------------------

    @patch("api.services.calendar_sync.sync_record")
    def test_grupo_sem_ninguem_com_token_marca_como_processado(self, mock_sync):
        """Decisao explicita: sem membro elegivel nao ha o que enviar, e o
        registro e considerado processado. Como a task olha so para
        "amanha" e roda de madrugada, a janela para alguem conectar um
        calendario depois e pequena."""
        GroupMembership.objects.filter(user=self.member_with_token).delete()
        record = self._create_record()

        sync_upcoming_to_calendar()

        mock_sync.assert_not_called()
        record.refresh_from_db()
        self.assertIsNotNone(record.synced_to_external_at)

    @patch("api.services.calendar_sync.sync_record")
    def test_vinculo_inativo_nao_e_elegivel(self, mock_sync):
        ExternalCalendarToken.objects.filter(user=self.member_with_token).update(
            is_active=False
        )
        self._create_record()

        sync_upcoming_to_calendar()

        mock_sync.assert_not_called()

    @patch("api.services.calendar_sync.sync_record")
    def test_sem_registro_elegivel_nao_faz_nada(self, mock_sync):
        sync_upcoming_to_calendar()
        mock_sync.assert_not_called()
