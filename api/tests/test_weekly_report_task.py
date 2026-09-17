from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings

from care.models import CareGroup, CareRecord, GroupMembership, Patient

# A task cobre os últimos 7 dias (hoje-7 até ontem, inclusive), então o
# registro de teste precisa cair dentro dessa janela.
WEEK_START = date.today() - timedelta(days=6)


def _record(patient, record_date, status):
    rec = CareRecord.objects.create(
        patient=patient,
        type="other",
        what="Teste",
        date=record_date,
        time=time(10, 0),
        caregiver="Cuidador",
        status=status,
    )
    # Evita a promoção automática PENDING -> DONE em datas passadas.
    CareRecord.objects.filter(pk=rec.pk).update(status=status)
    return rec


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CELERY_TASK_ALWAYS_EAGER=True,
)
class SendWeeklyReportEmailTests(TestCase):
    """Card #60: cobertura dos 4 cenários pedidos para o envio do relatório
    semanal por e-mail, exercitando a task real `send_weekly_report`
    (api/tasks.py) — com idempotência via `WeeklyReportLog` e opt-out por
    `GroupMembership.receive_weekly_report` — em vez de uma task paralela."""

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", email="alice@example.com", password="pass"
        )
        self.patient = Patient.objects.create(name="Vovó")
        self.group = CareGroup.objects.create(name="Família", patient=self.patient)
        GroupMembership.objects.create(
            user=self.user,
            group=self.group,
            relation_to_patient="FAMILY",
            receive_weekly_report=True,
        )
        _record(self.patient, WEEK_START, CareRecord.Status.DONE)
        mail.outbox = []

    def test_sends_email_to_default_member(self):
        """Membro padrão (com e-mail, sem opt-out) recebe o relatório."""
        from api.tasks import send_weekly_report

        send_weekly_report.apply(args=[self.group.id])

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["alice@example.com"])

    def test_does_not_send_to_opted_out_member(self):
        """Membro que fez opt-out (por vínculo grupo-usuário) não recebe o relatório."""
        membership = GroupMembership.objects.get(user=self.user, group=self.group)
        membership.receive_weekly_report = False
        membership.save(update_fields=["receive_weekly_report"])

        from api.tasks import send_weekly_report

        send_weekly_report.apply(args=[self.group.id])

        self.assertEqual(len(mail.outbox), 0)

    def test_skips_member_without_email(self):
        """Membro sem e-mail cadastrado é pulado."""
        self.user.email = ""
        self.user.save(update_fields=["email"])

        from api.tasks import send_weekly_report

        send_weekly_report.apply(args=[self.group.id])

        self.assertEqual(len(mail.outbox), 0)

    def test_nonexistent_group_does_not_raise(self):
        """Grupo inexistente não derruba a task (sem exceção)."""
        from api.tasks import send_weekly_report

        try:
            send_weekly_report.apply(args=[999999], throw=True)
        except Exception as exc:  # pragma: no cover - falha explícita do teste
            self.fail(f"send_weekly_report levantou exceção inesperada: {exc}")

        self.assertEqual(len(mail.outbox), 0)
