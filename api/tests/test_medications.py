from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from care.models import (
    Patient, CareGroup, GroupMembership,
    Medication, MedicationStockEntry,
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
