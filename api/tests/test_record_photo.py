import io
from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from care.models import Patient, CareGroup, GroupMembership, CareRecord


def _future_today_date_and_time(offset=timedelta(hours=1)):
    now = timezone.localtime()
    target_dt = now + offset
    return target_dt.date(), target_dt.time()


def _tiny_png():
    """1x1 transparent PNG, valid enough for Pillow/ImageField validation."""
    return io.BytesIO(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def _make_upload(name="foto.png"):
    from django.core.files.uploadedfile import SimpleUploadedFile
    return SimpleUploadedFile(name, _tiny_png().read(), content_type="image/png")


class RecordPhotoTestMixin:
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("carer_foto", password="pass1234")
        self.patient = Patient.objects.create(name="Paciente Foto")
        self.group = CareGroup.objects.create(name="GrupoFoto", patient=self.patient)
        GroupMembership.objects.create(user=self.user, group=self.group, relation_to_patient="FAMILY")
        self.client.force_authenticate(user=self.user)


@override_settings(MEDIA_ROOT="/tmp/cuidarjuntos_test_media")
class RecordPhotoUploadTests(RecordPhotoTestMixin, TestCase):
    def test_create_record_with_photo(self):
        resp = self.client.post(
            "/api/v1/records/",
            {
                "type": "other",
                "what": "Caminhada",
                "date": "2026-03-01",
                "time": "10:00",
                "photo": _make_upload(),
            },
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)
        self.assertTrue(resp.data.get("photo"))
        self.assertIn("http", resp.data["photo"])

        rec = CareRecord.objects.get(pk=resp.data["id"])
        self.assertTrue(bool(rec.photo))

    def test_create_record_without_photo_has_null_photo(self):
        resp = self.client.post(
            "/api/v1/records/",
            {
                "type": "other",
                "what": "Sem foto",
                "date": "2026-03-01",
                "time": "10:00",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertFalse(resp.data.get("photo"))

    def test_update_record_attach_photo(self):
        safe_date, safe_time = _future_today_date_and_time()
        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="Antigo",
            date=safe_date, time=safe_time,
            caregiver="Test", created_by=self.user,
        )
        resp = self.client.patch(
            f"/api/v1/records/{rec.id}/",
            {"photo": _make_upload()},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        rec.refresh_from_db()
        self.assertTrue(bool(rec.photo))

    def test_get_record_detail_returns_photo_url(self):
        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="Com foto",
            date=date(2026, 3, 1), time=time(9, 0),
            caregiver="Test", created_by=self.user,
        )
        rec.photo.save("foto.png", _make_upload(), save=True)

        resp = self.client.get(f"/api/v1/records/{rec.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get("photo"))
        self.assertIn("http", resp.data["photo"])

    def test_photo_upload_rejects_non_image_file(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        bogus = SimpleUploadedFile("nota.txt", b"nao sou uma imagem", content_type="text/plain")
        resp = self.client.post(
            "/api/v1/records/",
            {
                "type": "other",
                "what": "Invalido",
                "date": "2026-03-01",
                "time": "10:00",
                "photo": bogus,
            },
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_record_remove_photo(self):
        safe_date, safe_time = _future_today_date_and_time()
        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="Com foto",
            date=safe_date, time=safe_time,
            caregiver="Test", created_by=self.user,
        )
        rec.photo.save("foto.png", _make_upload(), save=True)
        self.assertTrue(bool(rec.photo))

        resp = self.client.patch(
            f"/api/v1/records/{rec.id}/",
            {"photo": None},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertFalse(resp.data.get("photo"))

        rec.refresh_from_db()
        self.assertFalse(bool(rec.photo))

    def test_photo_isolated_across_groups(self):
        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="Privado",
            date=date(2026, 3, 1), time=time(9, 0),
            caregiver="Test", created_by=self.user,
        )
        rec.photo.save("foto.png", _make_upload(), save=True)

        other_patient = Patient.objects.create(name="Outro Paciente")
        other_group = CareGroup.objects.create(name="OutroGrupo", patient=other_patient)
        other_user = User.objects.create_user("outro_foto", password="pass1234")
        GroupMembership.objects.create(user=other_user, group=other_group, relation_to_patient="FAMILY")

        other_client = APIClient()
        other_client.force_authenticate(user=other_user)
        resp = other_client.get(f"/api/v1/records/{rec.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
