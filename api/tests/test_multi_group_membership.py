"""
Testes da tarefa #38 (mudanca de cardinalidade de GroupMembership.user).

GroupMembership.user deixa de ser OneToOneField (1 grupo por usuario) e
passa a ser ForeignKey (N grupos por usuario), com unique_together
(user, group) no lugar do antigo unique(user).

Cobre tres cenarios, na ordem de importancia da tarefa:

(a) um usuario PODE ter memberships em 2+ grupos diferentes (isso hoje
    falha com IntegrityError, porque `unique_user_one_group` bloqueia).
(b) um usuario NAO PODE duplicar membership no MESMO grupo (a nova
    constraint unique_together(user, group) deve continuar bloqueando
    isso com IntegrityError).
(c) MAIS IMPORTANTE: o isolamento de dados de saude entre grupos
    continua intacto depois da mudanca de cardinalidade -- inclusive no
    caso novo (um usuario com 2 memberships), o fallback transitorio
    (primeiro grupo) nunca mistura dados de CareRecord de um grupo que
    nao e o resolvido para a request.
"""
from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from care.models import CareGroup, CareRecord, GroupMembership, Patient


class UserCanHaveMultipleGroupsTests(TestCase):
    """(a) e (b): cardinalidade nova de GroupMembership.user."""

    def setUp(self):
        self.user = User.objects.create_user("multi", password="pass1234")
        self.patient1 = Patient.objects.create(name="Paciente 1")
        self.group1 = CareGroup.objects.create(name="Grupo 1", patient=self.patient1)
        self.patient2 = Patient.objects.create(name="Paciente 2")
        self.group2 = CareGroup.objects.create(name="Grupo 2", patient=self.patient2)

    def test_user_can_belong_to_two_different_groups(self):
        GroupMembership.objects.create(
            user=self.user, group=self.group1, relation_to_patient="FAMILY"
        )
        # Antes da mudanca de schema, isto levanta IntegrityError por causa
        # de `unique_user_one_group`. Depois da mudanca, deve funcionar.
        GroupMembership.objects.create(
            user=self.user, group=self.group2, relation_to_patient="CAREGIVER"
        )

        memberships = GroupMembership.objects.filter(user=self.user)
        self.assertEqual(memberships.count(), 2)
        self.assertCountEqual(
            memberships.values_list("group_id", flat=True),
            [self.group1.id, self.group2.id],
        )

    def test_user_cannot_duplicate_membership_in_same_group(self):
        GroupMembership.objects.create(
            user=self.user, group=self.group1, relation_to_patient="FAMILY"
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                GroupMembership.objects.create(
                    user=self.user, group=self.group1, relation_to_patient="OTHER"
                )
        # a membership original continua intacta, so uma linha.
        self.assertEqual(
            GroupMembership.objects.filter(user=self.user, group=self.group1).count(), 1,
        )


class MultiGroupUserDataIsolationTests(TestCase):
    """
    (c) O teste mais importante: isolamento de dados de saude entre
    grupos continua intacto depois da mudanca de cardinalidade.
    """

    def setUp(self):
        self.client = APIClient()

        # Usuario A: um unico grupo (caso comum, hoje ja existente).
        self.user_a = User.objects.create_user("usera38", password="pass1234")
        self.patient_a = Patient.objects.create(name="Paciente A38")
        self.group_a = CareGroup.objects.create(name="GrupoA38", patient=self.patient_a)
        GroupMembership.objects.create(
            user=self.user_a, group=self.group_a, relation_to_patient="FAMILY"
        )
        self.record_a = CareRecord.objects.create(
            patient=self.patient_a, type="other", what="Registro sigiloso A38",
            description="Dado de saude do paciente A38",
            date=date.today() + timedelta(days=1), time=time(9, 0),
            caregiver="Cuidador A38", created_by=self.user_a, status="pending",
        )

        # Usuario B: um unico grupo, totalmente independente do A.
        self.user_b = User.objects.create_user("userb38", password="pass1234")
        self.patient_b = Patient.objects.create(name="Paciente B38")
        self.group_b = CareGroup.objects.create(name="GrupoB38", patient=self.patient_b)
        GroupMembership.objects.create(
            user=self.user_b, group=self.group_b, relation_to_patient="FAMILY"
        )
        self.record_b = CareRecord.objects.create(
            patient=self.patient_b, type="other", what="Registro sigiloso B38",
            description="Dado de saude do paciente B38",
            date=date.today() + timedelta(days=1), time=time(9, 0),
            caregiver="Cuidador B38", created_by=self.user_b, status="pending",
        )

    def test_user_a_never_sees_record_of_user_b_group(self):
        """Caso base (1 grupo por usuario): isolamento continua intacto."""
        self.client.force_authenticate(user=self.user_a)

        resp = self.client.get(f"/api/v1/records/{self.record_b.id}/")
        self.assertIn(resp.status_code, (403, 404))

        resp = self.client.get("/api/v1/records/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [r["id"] for r in resp.data["results"]]
        self.assertNotIn(str(self.record_b.id), [str(i) for i in ids])

    def test_user_in_two_groups_still_isolated_from_a_third_groups_data(self):
        """
        Usuario A agora TAMBEM pertence a um segundo grupo (Grupo C, seu
        proprio, dele mesmo) -- cenario so possivel depois da mudanca de
        cardinalidade desta tarefa. Mesmo assim, o usuario A jamais pode
        enxergar dados do Grupo B (que ele nunca integrou).
        """
        patient_c = Patient.objects.create(name="Paciente C38")
        group_c = CareGroup.objects.create(name="GrupoC38", patient=patient_c)
        GroupMembership.objects.create(
            user=self.user_a, group=group_c, relation_to_patient="CAREGIVER"
        )
        record_c = CareRecord.objects.create(
            patient=patient_c, type="other", what="Registro sigiloso C38",
            date=date.today() + timedelta(days=1), time=time(10, 0),
            caregiver="Cuidador C38", created_by=self.user_a, status="pending",
        )

        self.client.force_authenticate(user=self.user_a)

        # Nunca acessa dado do Grupo B, mesmo tendo 2 memberships agora.
        resp = self.client.get(f"/api/v1/records/{self.record_b.id}/")
        self.assertIn(resp.status_code, (403, 404))

        resp = self.client.get("/api/v1/records/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = str(resp.content)
        self.assertNotIn("Registro sigiloso B38", body)
        self.assertNotIn("Dado de saude do paciente B38", body)

        # O fallback transitorio (primeiro grupo) e deterministico: o
        # usuario ve consistentemente o mesmo grupo (A ou C) em requests
        # sucessivas -- nunca alterna aleatoriamente entre eles.
        first_resp_ids = {r["id"] for r in resp.data["results"]}
        resp2 = self.client.get("/api/v1/records/")
        second_resp_ids = {r["id"] for r in resp2.data["results"]}
        self.assertEqual(first_resp_ids, second_resp_ids)

    def test_user_b_never_sees_record_of_user_a_group(self):
        self.client.force_authenticate(user=self.user_b)

        resp = self.client.get(f"/api/v1/records/{self.record_a.id}/")
        self.assertIn(resp.status_code, (403, 404))

        resp = self.client.get("/api/v1/records/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = str(resp.content)
        self.assertNotIn("Registro sigiloso A38", body)
