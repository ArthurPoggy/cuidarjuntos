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


class FirstGroupFallbackTests(TestCase):
    """(d) O fallback transitorio "primeiro grupo por id" e uma DECISAO, nao
    um acidente -- estes testes a afirmam explicitamente.

    Enquanto o conceito de grupo ativo (`Profile.active_group`, cards
    #32/#33) nao existe, todo ponto que antes lia `user.group_membership`
    resolve para `group_memberships.order_by("id").first()`. Se alguem
    trocar essa regra sem substituir o conceito, estes testes quebram --
    que e exatamente o sinal desejado.
    """

    def setUp(self):
        self.user = User.objects.create_user("fallback38", password="pass1234")
        self.patient_primeiro = Patient.objects.create(name="Paciente Primeiro")
        self.group_primeiro = CareGroup.objects.create(
            name="Grupo Primeiro", patient=self.patient_primeiro
        )
        self.patient_segundo = Patient.objects.create(name="Paciente Segundo")
        self.group_segundo = CareGroup.objects.create(
            name="Grupo Segundo", patient=self.patient_segundo
        )
        # Ordem de criacao define os ids: o "primeiro" e o de menor id.
        self.mem_primeiro = GroupMembership.objects.create(
            user=self.user, group=self.group_primeiro, relation_to_patient="FAMILY"
        )
        self.mem_segundo = GroupMembership.objects.create(
            user=self.user, group=self.group_segundo, relation_to_patient="CAREGIVER"
        )
        self.assertLess(self.mem_primeiro.id, self.mem_segundo.id)

    def test_api_get_patient_resolve_para_o_primeiro_grupo(self):
        from api.views.care import _get_patient

        self.assertEqual(_get_patient(self.user), self.patient_primeiro)

    def test_api_get_group_das_medicacoes_resolve_para_o_primeiro_grupo(self):
        from api.views.medications import _get_group

        self.assertEqual(_get_group(self.user), self.group_primeiro)

    def test_endpoint_group_current_devolve_o_primeiro_grupo(self):
        client = APIClient()
        client.force_authenticate(user=self.user)

        resp = client.get("/api/v1/groups/current/")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["group"]["name"], "Grupo Primeiro")

    def test_context_processor_devolve_o_primeiro_grupo(self):
        from django.test import RequestFactory

        from care.context_processors import current_group

        request = RequestFactory().get("/")
        request.user = self.user

        ctx = current_group(request)

        self.assertEqual(ctx["current_group"], self.group_primeiro)
        self.assertEqual(ctx["current_group_membership"], self.mem_primeiro)

    def test_serializer_de_auth_devolve_o_primeiro_grupo(self):
        client = APIClient()
        client.force_authenticate(user=self.user)

        resp = client.get("/api/v1/auth/me/")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["membership"]["group_id"], self.group_primeiro.id)
        self.assertEqual(resp.data["membership"]["group_name"], "Grupo Primeiro")

    def test_leave_sai_do_primeiro_grupo_e_o_segundo_vira_o_atual(self):
        client = APIClient()
        client.force_authenticate(user=self.user)

        resp = client.post("/api/v1/groups/leave/")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(
            GroupMembership.objects.filter(pk=self.mem_primeiro.pk).exists()
        )
        # Consequencia direta do fallback: sair "do grupo" promove o proximo.
        resp = client.get("/api/v1/groups/current/")
        self.assertEqual(resp.data["group"]["name"], "Grupo Segundo")


class ApiStillEnforcesOneGroupAtATimeTests(TestCase):
    """A remocao da constraint `unique_user_one_group` NAO deve abrir a API.

    Enquanto nao existe tela de troca de grupo, entrar num segundo grupo
    deixaria o usuario presoo ao primeiro (ver FirstGroupFallbackTests).
    A politica de "1 grupo por vez" passou a ser responsabilidade da view
    -- estes testes garantem que ela nao se perdeu junto com a constraint.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("umgrupo38", password="pass1234")
        self.patient = Patient.objects.create(name="Paciente Existente")
        self.group_atual = CareGroup.objects.create(
            name="Grupo Atual", patient=self.patient
        )
        GroupMembership.objects.create(
            user=self.user, group=self.group_atual, relation_to_patient="FAMILY"
        )

        self.outro_patient = Patient.objects.create(name="Paciente Outro")
        self.outro_group = CareGroup.objects.create(
            name="Grupo Outro", patient=self.outro_patient
        )
        self.outro_group.set_join_code("4321")
        self.outro_group.save(update_fields=["join_code_hash"])

        self.client.force_authenticate(user=self.user)

    def test_join_em_segundo_grupo_e_recusado_com_400(self):
        resp = self.client.post(
            "/api/v1/groups/join/",
            {
                "group_id": self.outro_group.id,
                "relation_to_patient": "CAREGIVER",
                "pin": "4321",
            },
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(GroupMembership.objects.filter(user=self.user).count(), 1)

    def test_create_de_segundo_grupo_e_recusado_com_400(self):
        resp = self.client.post(
            "/api/v1/groups/create/",
            {
                "group_name": "Grupo Novo",
                "group_pin": "1234",
                "patient_name": "Paciente Novo",
                "relation_to_patient": "FAMILY",
            },
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(GroupMembership.objects.filter(user=self.user).count(), 1)
