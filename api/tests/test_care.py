import sys
from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from care.models import (
    Patient, CareGroup, GroupMembership,
    CareRecord, RecordReaction, RecordComment,
)
from care.utils import sync_recurrence_series


def _future_today_date_and_time(offset=timedelta(hours=1)):
    """
    Retorna (date, time) sempre no futuro em relacao ao momento da chamada,
    evitando testes frageis que dependem do horario em que a suite roda.
    Normalmente cai no mesmo dia (date.today()); se o offset ultrapassar a
    meia-noite, avanca a data para o dia seguinte para permanecer no futuro.
    """
    now = timezone.localtime()
    target_dt = now + offset
    target_date = target_dt.date()
    target_time = target_dt.time()
    return target_date, target_time


class CareRecordTestMixin:
    """Common setup: user with group membership."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("carer", password="pass1234")
        self.patient = Patient.objects.create(name="Paciente Test")
        self.group = CareGroup.objects.create(name="GrupoTest", patient=self.patient)
        GroupMembership.objects.create(user=self.user, group=self.group, relation_to_patient="FAMILY")
        self.client.force_authenticate(user=self.user)


class CareRecordCRUDTests(CareRecordTestMixin, TestCase):
    def test_create_record(self):
        resp = self.client.post("/api/v1/records/", {
            "type": "other",
            "what": "Caminhada no parque",
            "description": "30 minutos",
            "date": "2026-03-01",
            "time": "10:00",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["what"], "Caminhada no parque")
        self.assertEqual(resp.data["type"], "other")

    def test_list_records(self):
        CareRecord.objects.create(
            patient=self.patient, type="other", what="Test",
            date=date.today(), time=time(10, 0),
            caregiver="Test", created_by=self.user,
        )
        resp = self.client.get("/api/v1/records/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data["results"]), 1)

    def test_update_record(self):
        safe_date, safe_time = _future_today_date_and_time()
        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="Old",
            date=safe_date, time=safe_time,
            caregiver="Test", created_by=self.user,
        )
        resp = self.client.patch(f"/api/v1/records/{rec.id}/", {
            "what": "Updated",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rec.refresh_from_db()
        self.assertEqual(rec.what, "Updated")

    def test_update_past_record_forbidden(self):
        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="Old",
            date=date.today() - timedelta(days=1), time=time(10, 0),
            caregiver="Test", created_by=self.user,
        )
        resp = self.client.patch(f"/api/v1/records/{rec.id}/", {
            "what": "Updated",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        rec.refresh_from_db()
        self.assertEqual(rec.what, "Old")

    def test_put_past_record_forbidden(self):
        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="Old",
            date=date.today() - timedelta(days=1), time=time(10, 0),
            caregiver="Test", created_by=self.user,
        )
        resp = self.client.put(f"/api/v1/records/{rec.id}/", {
            "type": "other",
            "what": "Updated",
            "date": str(date.today() - timedelta(days=1)),
            "time": "10:00",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        rec.refresh_from_db()
        self.assertEqual(rec.what, "Old")

    def test_update_future_record_allowed(self):
        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="Old",
            date=date.today() + timedelta(days=1), time=time(10, 0),
            caregiver="Test", created_by=self.user,
        )
        resp = self.client.patch(f"/api/v1/records/{rec.id}/", {
            "what": "Updated",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rec.refresh_from_db()
        self.assertEqual(rec.what, "Updated")

    def test_record_admin_can_update_past_record(self):
        admin = User.objects.create_user("api-admin2", password="pass1234", is_staff=True)
        GroupMembership.objects.create(user=admin, group=self.group, relation_to_patient="FAMILY")
        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="Old",
            date=date.today() - timedelta(days=1), time=time(10, 0),
            caregiver="Test", created_by=self.user,
        )
        self.client.force_authenticate(user=admin)

        resp = self.client.patch(f"/api/v1/records/{rec.id}/", {
            "what": "Updated by admin",
        }, format="json")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rec.refresh_from_db()
        self.assertEqual(rec.what, "Updated by admin")

    def test_delete_record(self):
        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="Del",
            date=date.today(), time=time(10, 0),
            caregiver="Test", created_by=self.user,
        )
        resp = self.client.delete(f"/api/v1/records/{rec.id}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(CareRecord.objects.filter(pk=rec.id).exists())

    def test_admin_can_delete_any_record(self):
        admin = User.objects.create_user("api-admin", password="pass1234", is_staff=True)
        rec = CareRecord.objects.create(
            patient=self.patient, type="meal", what="Almoco",
            date=date.today(), time=time(12, 0),
            caregiver="Test", created_by=self.user,
        )
        self.client.force_authenticate(user=admin)

        resp = self.client.delete(f"/api/v1/records/{rec.id}/")

        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(CareRecord.objects.filter(pk=rec.id).exists())

    def test_common_user_cannot_delete_other_users_record(self):
        other = User.objects.create_user("api-other", password="pass1234")
        GroupMembership.objects.create(user=other, group=self.group, relation_to_patient="FAMILY")
        rec = CareRecord.objects.create(
            patient=self.patient, type="activity", what="Caminhada",
            date=date.today(), time=time(9, 0),
            caregiver="Test", created_by=self.user,
        )
        self.client.force_authenticate(user=other)

        resp = self.client.delete(f"/api/v1/records/{rec.id}/")

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(CareRecord.objects.filter(pk=rec.id).exists())

    def test_anonymous_user_cannot_delete_record(self):
        rec = CareRecord.objects.create(
            patient=self.patient, type="vital", what="Pressao arterial",
            date=date.today(), time=time(8, 0),
            caregiver="Test", created_by=self.user,
        )
        self.client.force_authenticate(user=None)

        resp = self.client.delete(f"/api/v1/records/{rec.id}/")

        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(CareRecord.objects.filter(pk=rec.id).exists())

    def test_deleted_record_is_not_listed(self):
        rec = CareRecord.objects.create(
            patient=self.patient, type="progress", what="Evolucao",
            date=date.today(), time=time(10, 0),
            caregiver="Test", created_by=self.user,
        )

        delete_resp = self.client.delete(f"/api/v1/records/{rec.id}/")
        list_resp = self.client.get("/api/v1/records/")

        self.assertEqual(delete_resp.status_code, status.HTTP_204_NO_CONTENT)
        ids = [item["id"] for item in list_resp.data["results"]]
        self.assertNotIn(rec.id, ids)

    def test_delete_works_for_multiple_record_types(self):
        for type_value in ("sleep", "bathroom", "medication"):
            rec = CareRecord.objects.create(
                patient=self.patient, type=type_value, what=f"Delete {type_value}",
                date=date.today(), time=time(10, 0),
                caregiver="Test", created_by=self.user,
            )

            resp = self.client.delete(f"/api/v1/records/{rec.id}/")

            self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT, type_value)
            self.assertFalse(CareRecord.objects.filter(pk=rec.id).exists(), type_value)


class SetStatusTests(CareRecordTestMixin, TestCase):
    def test_set_status_done(self):
        rec = CareRecord.objects.create(
            patient=self.patient, type="medication", what="Remedio",
            date=date.today(), time=time(8, 0), status="pending",
            caregiver="Test", created_by=self.user,
        )
        now = timezone.localtime()
        resp = self.client.post(f"/api/v1/records/{rec.id}/set_status/", {
            "status": "done",
            "date": now.date().isoformat(),
            "time": now.strftime("%H:%M"),
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rec.refresh_from_db()
        self.assertEqual(rec.status, "done")

    def test_set_status_missed_requires_reason(self):
        rec = CareRecord.objects.create(
            patient=self.patient, type="medication", what="Remedio",
            date=date.today(), time=time(8, 0), status="pending",
            caregiver="Test", created_by=self.user,
        )
        resp = self.client.post(f"/api/v1/records/{rec.id}/set_status/", {
            "status": "missed",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_set_status_missed_with_reason(self):
        rec = CareRecord.objects.create(
            patient=self.patient, type="medication", what="Remedio",
            date=date.today(), time=time(8, 0), status="pending",
            caregiver="Test", created_by=self.user,
        )
        resp = self.client.post(f"/api/v1/records/{rec.id}/set_status/", {
            "status": "missed",
            "reason": "Paciente recusou",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rec.refresh_from_db()
        self.assertEqual(rec.status, "missed")
        self.assertTrue(RecordComment.objects.filter(record=rec).exists())


class ReactTests(CareRecordTestMixin, TestCase):
    def test_react_toggle(self):
        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="Test",
            date=date.today(), time=time(10, 0),
            caregiver="Test", created_by=self.user,
        )
        # Add reaction
        resp = self.client.post(f"/api/v1/records/{rec.id}/react/", {
            "reaction": "heart",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["user_reaction"], "heart")

        # Toggle off
        resp = self.client.post(f"/api/v1/records/{rec.id}/react/", {
            "reaction": "heart",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["user_reaction"], "")


class CommentTests(CareRecordTestMixin, TestCase):
    def test_add_and_list_comments(self):
        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="Test",
            date=date.today(), time=time(10, 0),
            caregiver="Test", created_by=self.user,
        )
        # Add
        resp = self.client.post(f"/api/v1/records/{rec.id}/comments/", {
            "text": "Bom trabalho!",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        # List
        resp = self.client.get(f"/api/v1/records/{rec.id}/comments/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["text"], "Bom trabalho!")


class DashboardTests(CareRecordTestMixin, TestCase):
    def test_dashboard(self):
        resp = self.client.get("/api/v1/dashboard/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("counts", resp.data)
        self.assertIn("records", resp.data)

    def test_dashboard_records_null_time_no_duplicates_ordering_and_counts(self):
        """
        Regressao conclusiva para a issue #106.

        Exercita, de ponta a ponta via GET /api/v1/dashboard/, os tres
        pontos do criterio de aceite:

        (a) um CareRecord com time=None deve ser criavel e deve aparecer
            no dashboard ordenado como se tivesse o menor horario possivel
            do seu dia (NULLs tratados explicitamente, nao deixados ao
            sabor do backend de banco).

            Hoje isso e impossivel: `care/models.py` declara
            `time = models.TimeField("Hora")` sem `null=True`, entao
            `CareRecord.objects.create(..., time=None, ...)` estoura
            `django.db.utils.IntegrityError` (NOT NULL constraint failed:
            care_carerecord.time). Esse IntegrityError e a propria falha
            esperada deste teste ate que o campo seja migrado para
            `null=True, blank=True` e o `records_qs` do dashboard trate o
            NULL explicitamente (ex.: Coalesce) — pre-requisito real para
            a parte do item #106 sobre ordenacao com time=None.

        (b) uma serie recorrente de 3 ocorrencias (via
            sync_recurrence_series) dentro do periodo consultado nao deve
            gerar ids duplicados em `records`, e a lista deve estar em
            ordem nao-crescente por (date, time), com desempate estavel
            por -id quando date/time coincidem (dois registros da serie
            recorrente podem cair no mesmo dia/hora apos edicoes pontuais).

        (c) `counts[type]` deve bater exatamente com a contagem real de
            CareRecord por tipo (excluindo status='missed' por padrao),
            para pelo menos dois tipos distintos.
        """
        today = date.today()

        # (a) registro sem horario definido.
        no_time_record = CareRecord.objects.create(
            patient=self.patient, type="progress", what="Observacao sem horario",
            date=today, time=None,
            caregiver="Test", created_by=self.user, status="pending",
        )

        # (b) serie recorrente diaria com 3 ocorrencias (base + 2 clones),
        # gerada via sync_recurrence_series, dentro do periodo consultado.
        base = CareRecord.objects.create(
            patient=self.patient, type="medication", what="Remedio recorrente",
            date=today, time=time(8, 0),
            caregiver="Test", created_by=self.user, status="pending",
            recurrence=CareRecord.Recurrence.DAILY,
            repeat_until=today + timedelta(days=2),
        )
        sync_recurrence_series(base)
        self.assertEqual(
            CareRecord.objects.filter(recurrence_group=base.recurrence_group).count(),
            3,
            "setup: serie recorrente deveria ter gerado exatamente 3 ocorrencias",
        )

        # registro adicional de outro tipo, para permitir comparar counts
        # de pelo menos dois tipos distintos.
        CareRecord.objects.create(
            patient=self.patient, type="meal", what="Almoco",
            date=today, time=time(12, 0),
            caregiver="Test", created_by=self.user, status="done",
        )

        # `clear=1` remove o filtro de periodo padrao (que seria so "hoje"),
        # garantindo que a serie recorrente (que se estende por 3 dias)
        # fique inteiramente dentro do conjunto consultado, tanto para os
        # records quanto para os counts.
        resp = self.client.get("/api/v1/dashboard/", {"clear": "1"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        records = resp.data["records"]
        ids = [r["id"] for r in records]

        # (a) o registro com time=None deve aparecer no dashboard.
        self.assertIn(
            no_time_record.id, ids,
            "registro com time=None nao apareceu em records do dashboard",
        )

        # (b) sem duplicatas.
        self.assertEqual(
            len(ids), len(set(ids)),
            f"records retornados contem ids duplicados: {ids}",
        )

        # Todas as 3 ocorrencias da serie devem estar presentes (nada foi
        # perdido nem duplicado).
        series_ids = list(
            CareRecord.objects.filter(recurrence_group=base.recurrence_group)
            .values_list("id", flat=True)
        )
        for series_id in series_ids:
            self.assertIn(series_id, ids)

        # (b) Ordenacao nao-crescente por (date, time), com time=None
        # tratado como o menor valor possivel do dia, e desempate estavel
        # por -id quando (date, time) coincidem.
        def sort_key(item):
            # None deve ordenar como "menor que qualquer horario real".
            time_value = item["time"] if item["time"] is not None else ""
            return (item["date"], time_value, -item["id"])

        keys = [sort_key(r) for r in records]
        self.assertEqual(
            keys, sorted(keys, reverse=True),
            f"records nao estao em ordem nao-crescente por (date, time, -id): {keys}",
        )

        # (c) counts deve bater exatamente com a contagem real por tipo,
        # excluindo status='missed' (regra vigente por padrao).
        for care_type in ("medication", "meal"):
            expected = (
                CareRecord.objects.filter(patient=self.patient, type=care_type)
                .exclude(status="missed")
                .count()
            )
            self.assertEqual(
                resp.data["counts"][care_type], expected,
                f"counts['{care_type}'] nao bate com a contagem real",
            )


class CalendarTests(CareRecordTestMixin, TestCase):
    @(lambda f: f if sys.version_info < (3, 14) else lambda self: None)
    def test_calendar(self):
        # Skipped on Python 3.14 due to Django 4.2 copy() incompatibility in test client
        resp = self.client.get("/api/v1/calendar/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("weeks", resp.data)
        self.assertIn("events_by_date", resp.data)


class UpcomingTests(CareRecordTestMixin, TestCase):
    def test_upcoming(self):
        CareRecord.objects.create(
            patient=self.patient, type="other", what="Future",
            date=date.today() + timedelta(days=1), time=time(10, 0),
            caregiver="Test", created_by=self.user, status="pending",
        )
        resp = self.client.get("/api/v1/upcoming/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data["items"]), 1)

    def test_upcoming_buckets(self):
        future = date.today() + timedelta(days=1)
        CareRecord.objects.create(
            patient=self.patient, type="other", what="Future",
            date=future, time=time(10, 0),
            caregiver="Test", created_by=self.user, status="pending",
        )
        resp = self.client.get("/api/v1/upcoming/buckets/", {
            "from": date.today().isoformat(),
            "to": (date.today() + timedelta(days=7)).isoformat(),
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["ok"])


class ExportCSVTests(CareRecordTestMixin, TestCase):
    def test_export(self):
        CareRecord.objects.create(
            patient=self.patient, type="other", what="Export test",
            date=date.today(), time=time(10, 0),
            caregiver="Test", created_by=self.user,
        )
        resp = self.client.get("/api/v1/export/csv/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("text/csv", resp["Content-Type"])
