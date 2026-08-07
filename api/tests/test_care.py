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

    def _bucket_ids_for_date(self, resp_data, date_iso):
        """Retorna a lista de ids de items no bucket cuja date_iso == date_iso."""
        for bucket in resp_data["buckets"]:
            if bucket["date_iso"] == date_iso:
                return [item["id"] for item in bucket["items"]]
        return []

    def _assert_record_only_in_bucket(self, resp_data, record_id, expected_date_iso):
        """
        Garante que record_id aparece exclusivamente no bucket cujo
        date_iso == expected_date_iso, e em nenhum outro bucket do payload.
        """
        found_in = [
            bucket["date_iso"]
            for bucket in resp_data["buckets"]
            if record_id in [item["id"] for item in bucket["items"]]
        ]
        self.assertEqual(
            found_in, [expected_date_iso],
            f"esperado record {record_id} apenas no bucket {expected_date_iso}, encontrado em {found_in}",
        )

    def test_upcoming_buckets_week_range_boundary_from_date_included(self):
        """
        Um CareRecord com date == dfrom (limite inicial do range semanal)
        deve aparecer no bucket date_iso == dfrom.isoformat().
        Usamos um range totalmente no futuro para não esbarrar na exclusão
        de horários passados do dia de hoje.
        """
        dfrom = date.today() + timedelta(days=10)
        dto = dfrom + timedelta(days=6)  # range de semana (7 dias)

        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="No limite inicial",
            date=dfrom, time=time(9, 0),
            caregiver="Test", created_by=self.user, status="pending",
        )

        resp = self.client.get("/api/v1/upcoming/buckets/", {
            "from": dfrom.isoformat(),
            "to": dto.isoformat(),
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["ok"])
        self._assert_record_only_in_bucket(resp.data, rec.id, dfrom.isoformat())

    def test_upcoming_buckets_week_range_boundary_to_date_included(self):
        """
        Um CareRecord com date == dto (limite final do range semanal)
        deve aparecer no bucket date_iso == dto.isoformat().
        """
        dfrom = date.today() + timedelta(days=10)
        dto = dfrom + timedelta(days=6)

        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="No limite final",
            date=dto, time=time(9, 0),
            caregiver="Test", created_by=self.user, status="pending",
        )

        resp = self.client.get("/api/v1/upcoming/buckets/", {
            "from": dfrom.isoformat(),
            "to": dto.isoformat(),
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["ok"])
        self._assert_record_only_in_bucket(resp.data, rec.id, dto.isoformat())

    def test_upcoming_buckets_week_range_excludes_records_outside_range(self):
        """
        Registros com date fora de [dfrom, dto] (um dia antes de dfrom e um
        dia depois de dto) não devem aparecer em nenhum bucket do payload.
        """
        dfrom = date.today() + timedelta(days=10)
        dto = dfrom + timedelta(days=6)

        before = CareRecord.objects.create(
            patient=self.patient, type="other", what="Antes do range",
            date=dfrom - timedelta(days=1), time=time(9, 0),
            caregiver="Test", created_by=self.user, status="pending",
        )
        after = CareRecord.objects.create(
            patient=self.patient, type="other", what="Depois do range",
            date=dto + timedelta(days=1), time=time(9, 0),
            caregiver="Test", created_by=self.user, status="pending",
        )

        resp = self.client.get("/api/v1/upcoming/buckets/", {
            "from": dfrom.isoformat(),
            "to": dto.isoformat(),
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["ok"])

        all_ids = {
            item["id"]
            for bucket in resp.data["buckets"]
            for item in bucket["items"]
        }
        self.assertNotIn(before.id, all_ids)
        self.assertNotIn(after.id, all_ids)

    def test_upcoming_buckets_month_crossing_range(self):
        """
        Range de mês que cruza a virada de mês (ex.: do último dia de um mês
        ao primeiro dia do mês seguinte). Registros no último dia do mês
        anterior e no primeiro dia do mês seguinte devem aparecer cada um
        exclusivamente no bucket de sua própria data; um registro fora do
        range (dois dias depois de dto) deve ser omitido.
        """
        # Ponto de partida bem no futuro para não colidir com o "hoje" da suite.
        anchor = date.today() + timedelta(days=60)
        # Último dia do mês de anchor.
        next_month_first = anchor.replace(day=28) + timedelta(days=4)
        last_day_of_month = next_month_first - timedelta(days=next_month_first.day)
        first_day_next_month = last_day_of_month + timedelta(days=1)

        dfrom = last_day_of_month
        dto = first_day_next_month + timedelta(days=1)  # cobre a virada de mês

        rec_last_day = CareRecord.objects.create(
            patient=self.patient, type="other", what="Ultimo dia do mes",
            date=last_day_of_month, time=time(9, 0),
            caregiver="Test", created_by=self.user, status="pending",
        )
        rec_first_day_next = CareRecord.objects.create(
            patient=self.patient, type="other", what="Primeiro dia do mes seguinte",
            date=first_day_next_month, time=time(9, 0),
            caregiver="Test", created_by=self.user, status="pending",
        )
        rec_outside = CareRecord.objects.create(
            patient=self.patient, type="other", what="Fora do range",
            date=dto + timedelta(days=2), time=time(9, 0),
            caregiver="Test", created_by=self.user, status="pending",
        )

        resp = self.client.get("/api/v1/upcoming/buckets/", {
            "from": dfrom.isoformat(),
            "to": dto.isoformat(),
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["ok"])

        self._assert_record_only_in_bucket(
            resp.data, rec_last_day.id, last_day_of_month.isoformat()
        )
        self._assert_record_only_in_bucket(
            resp.data, rec_first_day_next.id, first_day_next_month.isoformat()
        )

        all_ids = {
            item["id"]
            for bucket in resp.data["buckets"]
            for item in bucket["items"]
        }
        self.assertNotIn(rec_outside.id, all_ids)


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
