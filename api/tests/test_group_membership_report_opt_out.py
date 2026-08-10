from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from care.models import Patient, CareGroup, GroupMembership


class GroupMembershipReceiveWeeklyReportTests(TestCase):
    """
    Card #61: membro pode optar por receber ou nao o relatorio semanal
    por email. Campo receive_weekly_report em GroupMembership deve:
    - existir com default True;
    - ser exposto (leitura) pelo serializer;
    - ser editavel via PATCH em /api/v1/group-memberships/{id}/.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("alice", password="pass1234")
        self.other_user = User.objects.create_user("bob", password="pass1234")

        self.patient = Patient.objects.create(name="Paciente")
        self.group = CareGroup.objects.create(name="Grupo", patient=self.patient)

        self.membership = GroupMembership.objects.create(
            user=self.user, group=self.group, relation_to_patient="FAMILY"
        )
        self.other_membership = GroupMembership.objects.create(
            user=self.other_user, group=self.group, relation_to_patient="CAREGIVER"
        )

        self.client.force_authenticate(user=self.user)

    def test_model_default_is_true(self):
        self.assertTrue(self.membership.receive_weekly_report)

    def test_field_is_exposed_on_retrieve(self):
        resp = self.client.get(f"/api/v1/group-memberships/{self.membership.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("receive_weekly_report", resp.data)
        self.assertTrue(resp.data["receive_weekly_report"])

    def test_patch_updates_receive_weekly_report(self):
        resp = self.client.patch(
            f"/api/v1/group-memberships/{self.membership.id}/",
            {"receive_weekly_report": False},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["receive_weekly_report"])

        self.membership.refresh_from_db()
        self.assertFalse(self.membership.receive_weekly_report)

    def test_cannot_patch_other_users_membership(self):
        resp = self.client.patch(
            f"/api/v1/group-memberships/{self.other_membership.id}/",
            {"receive_weekly_report": False},
            format="json",
        )
        self.assertIn(
            resp.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )
        self.other_membership.refresh_from_db()
        self.assertTrue(self.other_membership.receive_weekly_report)
