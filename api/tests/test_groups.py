from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from care.models import Patient, CareGroup, GroupMembership


class GroupCreateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("alice", password="pass1234")
        self.client.force_authenticate(user=self.user)

    def test_create_group(self):
        resp = self.client.post("/api/v1/groups/create/", {
            "group_name": "Familia Silva",
            "patient_name": "Joao Silva",
            "patient_birth_date": "1950-03-20",
            "relation_to_patient": "FAMILY",
            "health_data": "Diabetes tipo 2",
            "group_pin": "1234",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["name"], "Familia Silva")
        self.assertTrue(GroupMembership.objects.filter(user=self.user).exists())
        self.assertTrue(Patient.objects.filter(name="Joao Silva").exists())

    def test_create_group_already_in_group(self):
        patient = Patient.objects.create(name="P1")
        group = CareGroup.objects.create(name="G1", patient=patient)
        GroupMembership.objects.create(user=self.user, group=group, relation_to_patient="FAMILY")

        resp = self.client.post("/api/v1/groups/create/", {
            "group_name": "G2",
            "patient_name": "P2",
            "relation_to_patient": "FAMILY",
            "group_pin": "5678",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_group_invalid_pin(self):
        resp = self.client.post("/api/v1/groups/create/", {
            "group_name": "G1",
            "patient_name": "P1",
            "relation_to_patient": "FAMILY",
            "group_pin": "abc",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class GroupJoinTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("bob", password="pass1234")
        self.client.force_authenticate(user=self.user)

        self.patient = Patient.objects.create(name="Paciente")
        self.group = CareGroup.objects.create(name="Grupo1", patient=self.patient)
        self.group.set_join_code("4321")
        self.group.save()

    def test_join_group(self):
        resp = self.client.post("/api/v1/groups/join/", {
            "group_id": self.group.id,
            "relation_to_patient": "CAREGIVER",
            "pin": "4321",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(GroupMembership.objects.filter(user=self.user, group=self.group).exists())

    def test_join_wrong_pin(self):
        resp = self.client.post("/api/v1/groups/join/", {
            "group_id": self.group.id,
            "relation_to_patient": "CAREGIVER",
            "pin": "0000",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class GroupLeaveTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("carol", password="pass1234")
        self.client.force_authenticate(user=self.user)

        self.patient = Patient.objects.create(name="P")
        self.group = CareGroup.objects.create(name="G", patient=self.patient)
        GroupMembership.objects.create(user=self.user, group=self.group, relation_to_patient="FAMILY")

    def test_leave_group(self):
        resp = self.client.post("/api/v1/groups/leave/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(GroupMembership.objects.filter(user=self.user).exists())

    def test_leave_no_group(self):
        GroupMembership.objects.filter(user=self.user).delete()
        resp = self.client.post("/api/v1/groups/leave/")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class GroupCurrentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("dave", password="pass1234")
        self.client.force_authenticate(user=self.user)

    def test_current_no_group(self):
        resp = self.client.get("/api/v1/groups/current/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNone(resp.data["group"])

    def test_current_with_group(self):
        patient = Patient.objects.create(name="P")
        group = CareGroup.objects.create(name="G", patient=patient)
        GroupMembership.objects.create(user=self.user, group=group, relation_to_patient="DOCTOR")

        resp = self.client.get("/api/v1/groups/current/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["group"]["name"], "G")
