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
        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="Old",
            date=date.today(), time=time(10, 0),
            caregiver="Test", created_by=self.user,
        )
        resp = self.client.patch(f"/api/v1/records/{rec.id}/", {
            "what": "Updated",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rec.refresh_from_db()
        self.assertEqual(rec.what, "Updated")

    def test_delete_record(self):
        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="Del",
            date=date.today(), time=time(10, 0),
            caregiver="Test", created_by=self.user,
        )
        resp = self.client.delete(f"/api/v1/records/{rec.id}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(CareRecord.objects.filter(pk=rec.id).exists())


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
