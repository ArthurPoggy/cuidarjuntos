"""
Testes de isolamento entre grupos (Task #111).

Cobrem CareRecordViewSet (rotas de detail e actions customizadas),
os endpoints standalone de care/ (dashboard_data, calendar_data,
upcoming_data, upcoming_buckets, export_csv, reschedule,
bulk_set_status) e o MedicationViewSet.

Criterio de aceite: qualquer tentativa de um usuario do Grupo A de
ler/editar/excluir/exportar dados que pertencem ao Grupo B deve
retornar 403/404 (nunca 200), e a resposta nao pode conter nenhum
dado do registro/medicamento do outro grupo. Usuarios sem
GroupMembership tambem nao podem acessar nenhum endpoint de care/.
"""
from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from care.models import (
    Patient, CareGroup, GroupMembership,
    CareRecord, Medication, MedicationStockEntry,
)


class TwoGroupsTestMixin:
    """
    Monta dois grupos de cuidado totalmente independentes (A e B), cada
    um com seu paciente, usuario, registro de cuidado e medicamento.
    O client fica autenticado como o usuario do Grupo A por padrao.
    """

    def setUp(self):
        self.client = APIClient()

        # Grupo A
        self.user_a = User.objects.create_user("usera", password="pass1234")
        self.patient_a = Patient.objects.create(name="Paciente A")
        self.group_a = CareGroup.objects.create(name="GrupoA", patient=self.patient_a)
        GroupMembership.objects.create(
            user=self.user_a, group=self.group_a, relation_to_patient="FAMILY"
        )

        # Grupo B
        self.user_b = User.objects.create_user("userb", password="pass1234")
        self.patient_b = Patient.objects.create(name="Paciente B")
        self.group_b = CareGroup.objects.create(name="GrupoB", patient=self.patient_b)
        GroupMembership.objects.create(
            user=self.user_b, group=self.group_b, relation_to_patient="FAMILY"
        )

        # Registro de cuidado do Grupo B (dado sensivel que o Grupo A
        # jamais deve conseguir ler/editar/excluir).
        self.record_b = CareRecord.objects.create(
            patient=self.patient_b, type="vital", what="Pressao arterial confidencial B",
            description="Detalhe sensivel do paciente B",
            date=date.today() + timedelta(days=1), time=time(9, 0),
            caregiver="Cuidador B", created_by=self.user_b, status="pending",
        )

        # Medicamento do Grupo B.
        self.medication_b = Medication.objects.create(
            group=self.group_b, name="RemedioSigilosoB", dosage="999mg",
        )
        self.stock_entry_b = MedicationStockEntry.objects.create(
            medication=self.medication_b, quantity=50, created_by=self.user_b,
        )

        # Registro/medicamento equivalentes no Grupo A, usados apenas
        # para garantir que o usuario A continua enxergando seus proprios
        # dados normalmente.
        self.record_a = CareRecord.objects.create(
            patient=self.patient_a, type="other", what="Registro do proprio grupo A",
            date=date.today() + timedelta(days=1), time=time(10, 0),
            caregiver="Cuidador A", created_by=self.user_a, status="pending",
        )
        self.medication_a = Medication.objects.create(
            group=self.group_a, name="RemedioA", dosage="10mg",
        )

        self.client.force_authenticate(user=self.user_a)

    def assert_no_group_b_leak(self, response):
        """Garante que nenhum dado sensivel do Grupo B vazou na resposta."""
        body = str(response.content)
        self.assertNotIn("Pressao arterial confidencial B", body)
        self.assertNotIn("Detalhe sensivel do paciente B", body)
        self.assertNotIn("RemedioSigilosoB", body)


class CareRecordDetailRoutesCrossGroupTests(TwoGroupsTestMixin, TestCase):
    """Rotas de detalhe (/records/{id}/...) do CareRecordViewSet."""

    def test_cannot_read_other_group_record_via_detail(self):
        resp = self.client.get(f"/api/v1/records/{self.record_b.id}/")
        self.assertIn(resp.status_code, (403, 404))
        self.assert_no_group_b_leak(resp)

    def test_cannot_update_other_group_record(self):
        resp = self.client.patch(
            f"/api/v1/records/{self.record_b.id}/",
            {"what": "Hackeado pelo grupo A"},
            format="json",
        )
        self.assertIn(resp.status_code, (403, 404))
        self.record_b.refresh_from_db()
        self.assertEqual(self.record_b.what, "Pressao arterial confidencial B")

    def test_cannot_delete_other_group_record(self):
        resp = self.client.delete(f"/api/v1/records/{self.record_b.id}/")
        self.assertIn(resp.status_code, (403, 404))
        self.assertTrue(CareRecord.objects.filter(pk=self.record_b.id).exists())

    def test_admin_of_group_a_cannot_delete_record_of_group_b(self):
        """
        Um admin/staff pertence apenas ao Grupo A; a permissao de admin
        NAO deve conceder acesso a registros de outros grupos.
        """
        admin_a = User.objects.create_user(
            "admin-a", password="pass1234", is_staff=True
        )
        GroupMembership.objects.create(
            user=admin_a, group=self.group_a, relation_to_patient="FAMILY"
        )
        self.client.force_authenticate(user=admin_a)

        resp = self.client.delete(f"/api/v1/records/{self.record_b.id}/")

        self.assertIn(
            resp.status_code, (403, 404),
            f"admin do grupo A conseguiu excluir registro do grupo B (status={resp.status_code})",
        )
        self.assertTrue(CareRecord.objects.filter(pk=self.record_b.id).exists())

    def test_cannot_set_status_of_other_group_record(self):
        now = timezone.localtime()
        resp = self.client.post(
            f"/api/v1/records/{self.record_b.id}/set_status/",
            {
                "status": "done",
                "date": now.date().isoformat(),
                "time": now.strftime("%H:%M"),
            },
            format="json",
        )
        self.assertIn(resp.status_code, (403, 404))
        self.record_b.refresh_from_db()
        self.assertEqual(self.record_b.status, "pending")

    def test_cannot_react_to_other_group_record(self):
        resp = self.client.post(
            f"/api/v1/records/{self.record_b.id}/react/",
            {"reaction": "heart"},
            format="json",
        )
        self.assertIn(resp.status_code, (403, 404))

    def test_cannot_list_comments_of_other_group_record(self):
        resp = self.client.get(f"/api/v1/records/{self.record_b.id}/comments/")
        self.assertIn(resp.status_code, (403, 404))

    def test_cannot_post_comment_on_other_group_record(self):
        resp = self.client.post(
            f"/api/v1/records/{self.record_b.id}/comments/",
            {"text": "Comentario indevido"},
            format="json",
        )
        self.assertIn(resp.status_code, (403, 404))

    def test_cannot_cancel_following_of_other_group_record(self):
        resp = self.client.post(
            f"/api/v1/records/{self.record_b.id}/cancel_following/"
        )
        self.assertIn(resp.status_code, (403, 404))
        self.assertTrue(CareRecord.objects.filter(pk=self.record_b.id).exists())


class CareRecordBulkAndRescheduleCrossGroupTests(TwoGroupsTestMixin, TestCase):
    """Actions de lista (/records/bulk_set_status/, /records/reschedule/)."""

    def test_bulk_set_status_never_returns_200_for_other_group_ids(self):
        resp = self.client.post(
            "/api/v1/records/bulk_set_status/",
            {"ids": [self.record_b.id], "status": "missed"},
            format="json",
        )
        self.assertIn(
            resp.status_code, (403, 404),
            f"bulk_set_status aceitou ids de outro grupo silenciosamente (status={resp.status_code}, body={resp.content})",
        )
        self.record_b.refresh_from_db()
        self.assertEqual(self.record_b.status, "pending")

    def test_bulk_set_status_mixed_ids_does_not_touch_other_group_record(self):
        resp = self.client.post(
            "/api/v1/records/bulk_set_status/",
            {"ids": [self.record_a.id, self.record_b.id], "status": "missed", "reason": "x"},
            format="json",
        )
        # Mesmo se o registro do proprio grupo for aceito, o de outro
        # grupo jamais pode ser afetado nem citado como atualizado.
        self.record_b.refresh_from_db()
        self.assertEqual(self.record_b.status, "pending")
        if resp.status_code == 200:
            updated_ids = resp.data.get("updated", [])
            self.assertNotIn(self.record_b.id, updated_ids)

    def test_reschedule_other_group_record_not_found(self):
        resp = self.client.post(
            "/api/v1/records/reschedule/",
            {
                "id": self.record_b.id,
                "date": (date.today() + timedelta(days=2)).isoformat(),
                "time": "11:00",
            },
            format="json",
        )
        self.assertIn(resp.status_code, (403, 404))
        self.record_b.refresh_from_db()
        self.assertEqual(self.record_b.date, date.today() + timedelta(days=1))
        self.assertEqual(self.record_b.time, time(9, 0))


class StandaloneEndpointsCrossGroupTests(TwoGroupsTestMixin, TestCase):
    """
    dashboard_data, calendar_data, upcoming_data, upcoming_buckets e
    export_csv nao recebem um id de registro de outro grupo diretamente,
    mas devem sempre ficar restritos ao patient do usuario autenticado
    e jamais expor dados do Grupo B.
    """

    def test_dashboard_does_not_leak_other_group_data(self):
        resp = self.client.get("/api/v1/dashboard/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assert_no_group_b_leak(resp)

    def test_calendar_does_not_leak_other_group_data(self):
        target_month = (date.today() + timedelta(days=1)).replace(day=1)
        resp = self.client.get("/api/v1/calendar/", {"m": target_month.isoformat()})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assert_no_group_b_leak(resp)

    def test_upcoming_does_not_leak_other_group_data(self):
        resp = self.client.get("/api/v1/upcoming/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assert_no_group_b_leak(resp)

    def test_upcoming_buckets_does_not_leak_other_group_data(self):
        resp = self.client.get("/api/v1/upcoming/buckets/", {
            "from": date.today().isoformat(),
            "to": (date.today() + timedelta(days=7)).isoformat(),
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assert_no_group_b_leak(resp)

    def test_export_csv_does_not_leak_other_group_data(self):
        resp = self.client.get("/api/v1/export/csv/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        content = resp.content.decode("utf-8-sig")
        self.assertNotIn("Pressao arterial confidencial B", content)
        self.assertNotIn("Cuidador B", content)


class NoGroupUserCannotAccessCareEndpointsTests(TwoGroupsTestMixin, TestCase):
    """Usuario autenticado mas sem GroupMembership nao acessa nada de care/."""

    def setUp(self):
        super().setUp()
        self.orphan_user = User.objects.create_user("orphan", password="pass1234")
        self.client.force_authenticate(user=self.orphan_user)

    def test_cannot_list_records(self):
        resp = self.client.get("/api/v1/records/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_read_any_record_detail(self):
        resp = self.client.get(f"/api/v1/records/{self.record_a.id}/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_access_dashboard(self):
        resp = self.client.get("/api/v1/dashboard/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_access_calendar(self):
        resp = self.client.get("/api/v1/calendar/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_access_upcoming(self):
        resp = self.client.get("/api/v1/upcoming/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_access_upcoming_buckets(self):
        resp = self.client.get("/api/v1/upcoming/buckets/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_export_csv(self):
        resp = self.client.get("/api/v1/export/csv/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_reschedule(self):
        resp = self.client.post("/api/v1/records/reschedule/", {
            "id": self.record_a.id, "date": date.today().isoformat(), "time": "10:00",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_bulk_set_status(self):
        resp = self.client.post("/api/v1/records/bulk_set_status/", {
            "ids": [self.record_a.id], "status": "done",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_list_medications(self):
        resp = self.client.get("/api/v1/medications/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class MedicationCrossGroupTests(TwoGroupsTestMixin, TestCase):
    """MedicationViewSet: registros de estoque/medicamentos de outro grupo."""

    def test_cannot_read_other_group_medication_detail(self):
        resp = self.client.get(f"/api/v1/medications/{self.medication_b.id}/")
        self.assertIn(resp.status_code, (403, 404))
        self.assert_no_group_b_leak(resp)

    def test_cannot_update_other_group_medication(self):
        resp = self.client.patch(
            f"/api/v1/medications/{self.medication_b.id}/",
            {"dosage": "0mg"},
            format="json",
        )
        self.assertIn(resp.status_code, (403, 404))
        self.medication_b.refresh_from_db()
        self.assertEqual(self.medication_b.dosage, "999mg")

    def test_cannot_delete_other_group_medication(self):
        resp = self.client.delete(f"/api/v1/medications/{self.medication_b.id}/")
        self.assertIn(resp.status_code, (403, 404))
        self.assertTrue(Medication.objects.filter(pk=self.medication_b.id).exists())

    def test_cannot_add_stock_to_other_group_medication(self):
        resp = self.client.post(
            f"/api/v1/medications/{self.medication_b.id}/add_stock/",
            {"quantity": 100},
            format="json",
        )
        self.assertIn(resp.status_code, (403, 404))
        self.assertEqual(
            MedicationStockEntry.objects.filter(medication=self.medication_b).count(), 1,
        )

    def test_medication_list_does_not_include_other_group_items(self):
        resp = self.client.get("/api/v1/medications/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = [item["name"] for item in resp.data["results"]]
        self.assertNotIn("RemedioSigilosoB", names)

    def test_stock_overview_does_not_leak_other_group_medication(self):
        resp = self.client.get("/api/v1/medications/stock_overview/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assert_no_group_b_leak(resp)
