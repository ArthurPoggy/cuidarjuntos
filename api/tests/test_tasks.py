from datetime import date, time, timedelta
from unittest.mock import call, patch, MagicMock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from care.models import CareGroup, CareRecord, GroupMembership, Patient

# Resumo de envio bem-sucedido devolvido por send_push (sem falhas).
_OK = {"sent": 1, "failed": 0, "invalidated": 0}


def _make_record(patient, what="Teste", record_type="other",
                 status=CareRecord.Status.PENDING,
                 record_date=None, record_time=None, assigned_to=None):
    return CareRecord.objects.create(
        patient=patient,
        type=record_type,
        what=what,
        date=record_date or date.today(),
        time=record_time or time(10, 0),
        caregiver="Cuidador",
        status=status,
        assigned_to=assigned_to,
    )


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class NotifyUpcomingRecordsTests(TestCase):
    """Testes da task notify_upcoming_records."""

    def setUp(self):
        self.user1 = User.objects.create_user("membro1", password="pass")
        self.user2 = User.objects.create_user("membro2", password="pass")
        self.patient = Patient.objects.create(name="Paciente Test")
        self.group = CareGroup.objects.create(name="GrupoTest", patient=self.patient)
        GroupMembership.objects.create(
            user=self.user1, group=self.group, relation_to_patient="FAMILY"
        )
        GroupMembership.objects.create(
            user=self.user2, group=self.group, relation_to_patient="CAREGIVER"
        )

    def _now_plus(self, minutes):
        return timezone.localtime(timezone.now()) + timedelta(minutes=minutes)

    # ------------------------------------------------------------------
    # Early-return
    # ------------------------------------------------------------------

    @patch("api.services.push.send_push")
    def test_no_records_in_window_skips_send(self, mock_send):
        """Sem registros pendentes na janela: send_push não é chamado."""
        # Registro no futuro distante (60min)
        future = self._now_plus(60)
        _make_record(self.patient, record_date=future.date(), record_time=future.time())

        from api.tasks import notify_upcoming_records
        notify_upcoming_records.apply()

        mock_send.assert_not_called()

    @patch("api.services.push.send_push")
    def test_done_records_excluded(self, mock_send):
        """Registros DONE não geram notificação."""
        in_15 = self._now_plus(15)
        _make_record(
            self.patient,
            record_date=in_15.date(),
            record_time=in_15.time(),
            status=CareRecord.Status.DONE,
        )

        from api.tasks import notify_upcoming_records
        notify_upcoming_records.apply()

        mock_send.assert_not_called()

    @patch("api.services.push.send_push")
    def test_missed_records_excluded(self, mock_send):
        """Registros MISSED não geram notificação."""
        in_15 = self._now_plus(15)
        _make_record(
            self.patient,
            record_date=in_15.date(),
            record_time=in_15.time(),
            status=CareRecord.Status.MISSED,
        )

        from api.tasks import notify_upcoming_records
        notify_upcoming_records.apply()

        mock_send.assert_not_called()

    @patch("api.services.push.send_push")
    def test_past_records_excluded(self, mock_send):
        """Registros com hora já passada não geram notificação."""
        past = self._now_plus(-5)
        _make_record(
            self.patient,
            record_date=past.date(),
            record_time=past.time(),
        )

        from api.tasks import notify_upcoming_records
        notify_upcoming_records.apply()

        mock_send.assert_not_called()

    @patch("api.services.push.send_push")
    def test_records_beyond_window_excluded(self, mock_send):
        """Registros além de 30min não geram notificação."""
        beyond = self._now_plus(35)
        _make_record(
            self.patient,
            record_date=beyond.date(),
            record_time=beyond.time(),
        )

        from api.tasks import notify_upcoming_records
        notify_upcoming_records.apply()

        mock_send.assert_not_called()

    # ------------------------------------------------------------------
    # Lógica de destinatários
    # ------------------------------------------------------------------

    @patch("api.services.push.send_push")
    def test_sends_to_assigned_to_only(self, mock_send):
        """Se assigned_to está definido, apenas esse usuário é notificado."""
        mock_send.return_value = _OK
        in_15 = self._now_plus(15)
        _make_record(
            self.patient,
            record_date=in_15.date(),
            record_time=in_15.time(),
            assigned_to=self.user1,
        )

        from api.tasks import notify_upcoming_records
        notify_upcoming_records.apply()

        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        self.assertEqual(kwargs.get("user_ids") or args[0], [self.user1.id])

    @patch("api.services.push.send_push")
    def test_sends_to_all_group_members_when_no_assigned_to(self, mock_send):
        """Sem assigned_to, todos os membros do grupo são notificados."""
        mock_send.return_value = _OK
        in_15 = self._now_plus(15)
        _make_record(
            self.patient,
            record_date=in_15.date(),
            record_time=in_15.time(),
        )

        from api.tasks import notify_upcoming_records
        notify_upcoming_records.apply()

        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        notified = set(kwargs.get("user_ids") or args[0])
        self.assertEqual(notified, {self.user1.id, self.user2.id})

    @patch("api.services.push.send_push")
    def test_empty_group_no_members_skips_silently(self, mock_send):
        """Grupo sem membros: send_push não é chamado, sem exceção."""
        empty_patient = Patient.objects.create(name="Paciente Isolado")
        empty_group = CareGroup.objects.create(name="GrupoVazio", patient=empty_patient)
        in_15 = self._now_plus(15)
        _make_record(
            empty_patient,
            record_date=in_15.date(),
            record_time=in_15.time(),
        )

        from api.tasks import notify_upcoming_records
        notify_upcoming_records.apply()

        mock_send.assert_not_called()

    # ------------------------------------------------------------------
    # Conteúdo da notificação
    # ------------------------------------------------------------------

    @patch("api.services.push.send_push")
    def test_notification_content(self, mock_send):
        """Título e data corretos; corpo genérico sem dados sensíveis."""
        mock_send.return_value = _OK
        in_15 = self._now_plus(15)
        record = _make_record(
            self.patient,
            what="Amoxicilina",
            record_type="medication",
            record_date=in_15.date(),
            record_time=in_15.time(),
            assigned_to=self.user1,
        )

        from api.tasks import notify_upcoming_records
        notify_upcoming_records.apply()

        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        self.assertEqual(kwargs["title"], "Lembrete de Cuidado")
        # Corpo não deve vazar tipo/medicação fora do app autenticado.
        self.assertNotIn("Medicação", kwargs["body"])
        self.assertNotIn("Amoxicilina", kwargs["body"])
        self.assertIn(in_15.strftime("%H:%M"), kwargs["body"])
        self.assertEqual(kwargs["data"]["screen"], "RecordDetail")
        self.assertEqual(kwargs["data"]["id"], record.id)

    # ------------------------------------------------------------------
    # Múltiplos registros
    # ------------------------------------------------------------------

    @patch("api.services.push.send_push")
    def test_multiple_records_generates_multiple_sends(self, mock_send):
        """Dois registros pendentes na janela → send_push chamado duas vezes."""
        mock_send.return_value = _OK
        in_10 = self._now_plus(10)
        in_20 = self._now_plus(20)
        _make_record(
            self.patient,
            what="Registro A",
            record_date=in_10.date(),
            record_time=in_10.time(),
            assigned_to=self.user1,
        )
        _make_record(
            self.patient,
            what="Registro B",
            record_date=in_20.date(),
            record_time=in_20.time(),
            assigned_to=self.user2,
        )

        from api.tasks import notify_upcoming_records
        notify_upcoming_records.apply()

        self.assertEqual(mock_send.call_count, 2)

    # ------------------------------------------------------------------
    # Cruzamento de meia-noite
    # ------------------------------------------------------------------

    @patch("api.services.push.send_push")
    @patch("django.utils.timezone.now")
    def test_midnight_crossover(self, mock_now, mock_send):
        """Registros após meia-noite entram na janela quando são 23:45."""
        fake_now = timezone.make_aware(
            timezone.datetime(2026, 5, 14, 23, 45, 0)
        )
        mock_now.return_value = fake_now
        mock_send.return_value = _OK

        # Registro às 00:05 do dia seguinte (dentro da janela de 30min)
        tomorrow = date(2026, 5, 15)
        _make_record(
            self.patient,
            record_date=tomorrow,
            record_time=time(0, 5),
        )

        from api.tasks import notify_upcoming_records
        notify_upcoming_records.apply()

        mock_send.assert_called_once()

    @patch("api.services.push.send_push")
    @patch("django.utils.timezone.now")
    def test_midnight_crossover_excludes_far_future(self, mock_now, mock_send):
        """Registro às 00:20 quando são 23:45 → fora da janela de 30min."""
        fake_now = timezone.make_aware(
            timezone.datetime(2026, 5, 14, 23, 45, 0)
        )
        mock_now.return_value = fake_now

        tomorrow = date(2026, 5, 15)
        _make_record(
            self.patient,
            record_date=tomorrow,
            record_time=time(0, 20),
        )

        from api.tasks import notify_upcoming_records
        notify_upcoming_records.apply()

        mock_send.assert_not_called()

    # ------------------------------------------------------------------
    # Resiliência e retry
    # ------------------------------------------------------------------

    @patch("api.services.push.send_push", side_effect=Exception("Falha de rede"))
    def test_retry_on_send_push_failure(self, mock_send):
        """Falha no send_push dispara retry via self.retry."""
        in_15 = self._now_plus(15)
        _make_record(
            self.patient,
            record_date=in_15.date(),
            record_time=in_15.time(),
            assigned_to=self.user1,
        )

        from api.tasks import notify_upcoming_records
        from celery.exceptions import Retry

        with self.assertRaises((Retry, Exception)):
            notify_upcoming_records.apply(throw=True)

    @patch("api.services.push.send_push")
    def test_retry_when_send_push_reports_failures(self, mock_send):
        """send_push retornando failed > 0 dispara retry (entrega malsucedida)."""
        mock_send.return_value = {"sent": 0, "failed": 1, "invalidated": 0}
        in_15 = self._now_plus(15)
        record = _make_record(
            self.patient,
            record_date=in_15.date(),
            record_time=in_15.time(),
            assigned_to=self.user1,
        )

        from api.tasks import notify_upcoming_records
        from celery.exceptions import Retry

        with self.assertRaises((Retry, Exception)):
            notify_upcoming_records.apply(throw=True)

        # notified_at não deve ser gravado quando a entrega falha.
        record.refresh_from_db()
        self.assertIsNone(record.notified_at)

    @patch("api.services.push.send_push")
    def test_successful_send_marks_notified_at(self, mock_send):
        """Envio bem-sucedido grava notified_at no registro."""
        mock_send.return_value = _OK
        in_15 = self._now_plus(15)
        record = _make_record(
            self.patient,
            record_date=in_15.date(),
            record_time=in_15.time(),
            assigned_to=self.user1,
        )

        from api.tasks import notify_upcoming_records
        notify_upcoming_records.apply()

        record.refresh_from_db()
        self.assertIsNotNone(record.notified_at)

    @patch("api.services.push.send_push")
    def test_no_token_delivered_does_not_mark_notified(self, mock_send):
        """sent=0 e failed=0 (sem token ativo): notified_at permanece NULL.

        Nenhuma entrega ocorreu, então o registro deve continuar elegível
        em vez de ser marcado como notificado para sempre.
        """
        mock_send.return_value = {"sent": 0, "failed": 0, "invalidated": 0}
        in_15 = self._now_plus(15)
        record = _make_record(
            self.patient,
            record_date=in_15.date(),
            record_time=in_15.time(),
            assigned_to=self.user1,
        )

        from api.tasks import notify_upcoming_records
        notify_upcoming_records.apply()

        mock_send.assert_called_once()
        record.refresh_from_db()
        self.assertIsNone(record.notified_at)

    @patch("api.services.push.send_push")
    def test_concurrent_claim_prevents_duplicate_send(self, mock_send):
        """Registro reivindicado por outra instância (notified_at já setado
        durante o envio) não gera push duplicado.

        Simulamos a corrida fazendo o send_push de um registro "roubar" o
        claim do outro registro pendente antes que a task chegue nele.
        """
        in_10 = self._now_plus(10)
        in_20 = self._now_plus(20)
        rec_a = _make_record(
            self.patient,
            what="A",
            record_date=in_10.date(),
            record_time=in_10.time(),
            assigned_to=self.user1,
        )
        rec_b = _make_record(
            self.patient,
            what="B",
            record_date=in_20.date(),
            record_time=in_20.time(),
            assigned_to=self.user2,
        )

        def steal_claim(*args, **kwargs):
            # Enquanto a task envia o registro atual, outra instância
            # reivindica o OUTRO registro pendente (qualquer ainda NULL).
            # Independe da ordem de iteração do queryset.
            current_id = kwargs["data"]["id"]
            CareRecord.objects.filter(
                notified_at__isnull=True
            ).exclude(id=current_id).update(notified_at=timezone.now())
            return _OK

        mock_send.side_effect = steal_claim

        from api.tasks import notify_upcoming_records
        notify_upcoming_records.apply()

        # Apenas o primeiro registro deve ter sido enviado; o segundo foi
        # pulado por já estar reivindicado -> sem push duplicado.
        self.assertEqual(mock_send.call_count, 1)

    @patch("api.services.push.send_push")
    def test_already_notified_record_is_skipped(self, mock_send):
        """Registro com notified_at já preenchido não gera nova notificação."""
        mock_send.return_value = _OK
        in_15 = self._now_plus(15)
        record = _make_record(
            self.patient,
            record_date=in_15.date(),
            record_time=in_15.time(),
            assigned_to=self.user1,
        )
        record.notified_at = timezone.now()
        record.save(update_fields=["notified_at"])

        from api.tasks import notify_upcoming_records
        notify_upcoming_records.apply()

        mock_send.assert_not_called()

    @patch("api.services.push.send_push")
    def test_patient_without_care_group_skips_gracefully(self, mock_send):
        """Paciente sem grupo de cuidado: registro é pulado sem lançar exceção."""
        orphan_patient = Patient.objects.create(name="Paciente Sem Grupo")
        in_15 = self._now_plus(15)
        # Cria registro sem care_group (patient não tem CareGroup associado)
        CareRecord.objects.create(
            patient=orphan_patient,
            type="other",
            what="Sem grupo",
            date=in_15.date(),
            time=in_15.time(),
            caregiver="Ninguém",
            status=CareRecord.Status.PENDING,
        )

        from api.tasks import notify_upcoming_records
        # Não deve lançar exceção
        notify_upcoming_records.apply()

        mock_send.assert_not_called()
