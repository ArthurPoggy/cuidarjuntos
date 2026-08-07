import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from care.models import (
    Patient, CareGroup, GroupMembership,
    Medication, MedicationStockEntry, CareRecord,
)


class MedicationTestMixin:
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("meduser", password="pass1234")
        self.patient = Patient.objects.create(name="Paciente")
        self.group = CareGroup.objects.create(name="Grupo", patient=self.patient)
        GroupMembership.objects.create(user=self.user, group=self.group, relation_to_patient="FAMILY")
        self.client.force_authenticate(user=self.user)


class MedicationCRUDTests(MedicationTestMixin, TestCase):
    def test_create_medication(self):
        resp = self.client.post("/api/v1/medications/", {
            "name": "Paracetamol",
            "dosage": "500mg",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["name"], "Paracetamol")

    def test_list_medications(self):
        Medication.objects.create(group=self.group, name="Med1", dosage="10mg")
        resp = self.client.get("/api/v1/medications/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data["results"]), 1)

    def test_update_medication(self):
        med = Medication.objects.create(group=self.group, name="Med1", dosage="10mg")
        resp = self.client.patch(f"/api/v1/medications/{med.id}/", {
            "dosage": "20mg",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        med.refresh_from_db()
        self.assertEqual(med.dosage, "20mg")

    def test_delete_medication(self):
        med = Medication.objects.create(group=self.group, name="Med1", dosage="10mg")
        resp = self.client.delete(f"/api/v1/medications/{med.id}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)


class StockTests(MedicationTestMixin, TestCase):
    def test_add_stock(self):
        med = Medication.objects.create(group=self.group, name="Med1", dosage="10mg")
        resp = self.client.post(f"/api/v1/medications/{med.id}/add_stock/", {
            "quantity": 30,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(MedicationStockEntry.objects.filter(medication=med).count(), 1)

    def test_stock_overview(self):
        med = Medication.objects.create(group=self.group, name="Med1", dosage="10mg")
        MedicationStockEntry.objects.create(medication=med, quantity=10, created_by=self.user)
        resp = self.client.get("/api/v1/medications/stock_overview/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("sections", resp.data)

    def test_stock_overview_danger(self):
        med = Medication.objects.create(group=self.group, name="Med1", dosage="10mg")
        # No stock added = danger
        resp = self.client.get("/api/v1/medications/stock_overview/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        sections = resp.data["sections"]
        if sections:
            self.assertEqual(sections[0]["key"], "danger")


class StockOverviewNextDoseTests(MedicationTestMixin, TestCase):
    """
    Critério de aceitação: stock_overview deve retornar, para cada
    medicamento, um campo `next_dose` com a data/hora do CareRecord
    pendente mais próximo (status=pending) vinculado a ele, ou null
    quando não houver nenhum CareRecord pendente.

    Formato de `next_dose`: segue a convenção já usada no restante da
    API para combinar data e hora (ver api/views/care.py, action
    `reschedule`, que responde com campos separados `date` e `time`,
    respectivamente ISO (YYYY-MM-DD) e HH:MM). Aqui `next_dose` é um
    objeto `{"date": "YYYY-MM-DD", "time": "HH:MM"}` (ou `null`),
    seguindo o mesmo padrão em vez de uma string concatenada.
    """

    def _find_item(self, resp, medication_id):
        for section in resp.data["sections"]:
            for item in section["items"]:
                if item["id"] == medication_id:
                    return item
        return None

    def test_next_dose_is_null_when_no_pending_record(self):
        med = Medication.objects.create(group=self.group, name="Med1", dosage="10mg")
        MedicationStockEntry.objects.create(medication=med, quantity=10, created_by=self.user)

        resp = self.client.get("/api/v1/medications/stock_overview/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        item = self._find_item(resp, med.id)
        self.assertIsNotNone(item, "medicamento deveria aparecer em alguma seção")
        self.assertIn("next_dose", item)
        self.assertIsNone(item["next_dose"])

    def test_next_dose_returns_nearest_pending_care_record(self):
        med = Medication.objects.create(group=self.group, name="Med2", dosage="20mg")
        MedicationStockEntry.objects.create(medication=med, quantity=10, created_by=self.user)

        today = timezone.localdate()

        # CareRecord pendente mais distante
        far_record = CareRecord.objects.create(
            patient=self.patient,
            caregiver="Cuidador",
            type=CareRecord.Type.MEDICATION,
            what="Tomar Med2",
            medication=med,
            date=today + datetime.timedelta(days=5),
            time=datetime.time(8, 0),
            status=CareRecord.Status.PENDING,
        )
        # CareRecord pendente mais próximo (esse deve ser retornado)
        near_record = CareRecord.objects.create(
            patient=self.patient,
            caregiver="Cuidador",
            type=CareRecord.Type.MEDICATION,
            what="Tomar Med2",
            medication=med,
            date=today + datetime.timedelta(days=1),
            time=datetime.time(9, 30),
            status=CareRecord.Status.PENDING,
        )
        # CareRecord já concluído: não deve interferir mesmo estando mais próximo
        CareRecord.objects.create(
            patient=self.patient,
            caregiver="Cuidador",
            type=CareRecord.Type.MEDICATION,
            what="Tomar Med2",
            medication=med,
            date=today,
            time=datetime.time(7, 0),
            status=CareRecord.Status.DONE,
        )

        resp = self.client.get("/api/v1/medications/stock_overview/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        item = self._find_item(resp, med.id)
        self.assertIsNotNone(item)
        self.assertIn("next_dose", item)
        self.assertIsNotNone(item["next_dose"])

        next_dose = item["next_dose"]
        self.assertIsInstance(next_dose, dict)
        self.assertIn("date", next_dose)
        self.assertIn("time", next_dose)

        expected_date = near_record.date.isoformat()
        expected_time = near_record.time.strftime("%H:%M")
        self.assertEqual(next_dose["date"], expected_date)
        self.assertEqual(next_dose["time"], expected_time)

        # garante que não pegou o registro mais distante
        far_date = far_record.date.isoformat()
        self.assertNotEqual(next_dose["date"], far_date)

    def test_next_dose_picks_earliest_time_when_same_date(self):
        med = Medication.objects.create(group=self.group, name="Med3", dosage="30mg")
        MedicationStockEntry.objects.create(medication=med, quantity=10, created_by=self.user)

        today = timezone.localdate()
        target_date = today + datetime.timedelta(days=2)

        later_today_record = CareRecord.objects.create(
            patient=self.patient,
            caregiver="Cuidador",
            type=CareRecord.Type.MEDICATION,
            what="Tomar Med3",
            medication=med,
            date=target_date,
            time=datetime.time(20, 0),
            status=CareRecord.Status.PENDING,
        )
        earlier_today_record = CareRecord.objects.create(
            patient=self.patient,
            caregiver="Cuidador",
            type=CareRecord.Type.MEDICATION,
            what="Tomar Med3",
            medication=med,
            date=target_date,
            time=datetime.time(6, 0),
            status=CareRecord.Status.PENDING,
        )

        resp = self.client.get("/api/v1/medications/stock_overview/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        item = self._find_item(resp, med.id)
        self.assertIsNotNone(item)
        next_dose = item["next_dose"]
        self.assertIsNotNone(next_dose)
        self.assertEqual(next_dose["date"], target_date.isoformat())
        self.assertEqual(next_dose["time"], earlier_today_record.time.strftime("%H:%M"))
        self.assertNotEqual(next_dose["time"], later_today_record.time.strftime("%H:%M"))

    def test_next_dose_ignores_records_of_other_medications(self):
        med_a = Medication.objects.create(group=self.group, name="Med4", dosage="40mg")
        med_b = Medication.objects.create(group=self.group, name="Med5", dosage="50mg")
        MedicationStockEntry.objects.create(medication=med_a, quantity=10, created_by=self.user)
        MedicationStockEntry.objects.create(medication=med_b, quantity=10, created_by=self.user)

        today = timezone.localdate()

        # Pending record belongs only to med_b
        CareRecord.objects.create(
            patient=self.patient,
            caregiver="Cuidador",
            type=CareRecord.Type.MEDICATION,
            what="Tomar Med5",
            medication=med_b,
            date=today + datetime.timedelta(days=1),
            time=datetime.time(10, 0),
            status=CareRecord.Status.PENDING,
        )

        resp = self.client.get("/api/v1/medications/stock_overview/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        item_a = self._find_item(resp, med_a.id)
        item_b = self._find_item(resp, med_b.id)
        self.assertIsNotNone(item_a)
        self.assertIsNotNone(item_b)
        self.assertIsNone(item_a["next_dose"])
        self.assertIsNotNone(item_b["next_dose"])
