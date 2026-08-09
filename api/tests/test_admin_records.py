# api/tests/test_admin_records.py
"""
Testes para a tarefa #90 (subtask 90-1-backend-endpoint-registros):

Endpoint administrativo GET /api/v1/admin/records/ deve:
- Ser protegido por api.permissions.IsSuperUser (401/403 para anonimo,
  403 para usuario comum ou staff nao-superuser).
- Retornar 200 com uma lista paginada de CareRecord de MULTIPLOS
  grupos/pacientes (nao restrita ao grupo do proprio superuser) quando
  acessado por um superuser.
- Cada item deve incluir: id, type/label, status, date, patient (nome),
  group (nome), author_name/caregiver.
- Suportar filtros de busca (q) e status.
"""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from care.models import CareGroup, CareRecord, GroupMembership, Patient


class AdminRecordsPermissionTest(TestCase):
    """GET /api/v1/admin/records/ eh protegido por IsSuperUser."""

    url = "/api/v1/admin/records/"

    def setUp(self):
        self.client = APIClient()

        self.regular_user = User.objects.create_user(
            "regularrec", password="pass1234"
        )
        self.staff_non_super = User.objects.create_user(
            "staffrec", password="pass1234", is_staff=True
        )
        self.superuser = User.objects.create_superuser(
            "bossrec", email="bossrec@test.com", password="pass1234"
        )

        self.patient = Patient.objects.create(name="Paciente Um")
        self.group = CareGroup.objects.create(name="Grupo Um", patient=self.patient)
        GroupMembership.objects.create(
            user=self.regular_user, group=self.group, relation_to_patient="FAMILY"
        )

    def test_anonymous_cannot_access_admin_records(self):
        resp = self.client.get(self.url)
        self.assertIn(
            resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
            f"usuario anonimo deveria ser barrado do endpoint admin/records, "
            f"obtido {resp.status_code}",
        )

    def test_regular_user_gets_403(self):
        self.client.force_authenticate(user=self.regular_user)
        resp = self.client.get(self.url)
        self.assertEqual(
            resp.status_code, status.HTTP_403_FORBIDDEN,
            f"usuario comum deveria receber 403 do endpoint admin/records, "
            f"obtido {resp.status_code} (corpo: {resp.content!r})",
        )

    def test_staff_non_superuser_gets_403(self):
        self.client.force_authenticate(user=self.staff_non_super)
        resp = self.client.get(self.url)
        self.assertEqual(
            resp.status_code, status.HTTP_403_FORBIDDEN,
            f"usuario staff (nao superuser) deveria receber 403 do endpoint "
            f"admin/records, obtido {resp.status_code} (corpo: {resp.content!r})",
        )

    def test_superuser_can_access_admin_records(self):
        self.client.force_authenticate(user=self.superuser)
        resp = self.client.get(self.url)
        self.assertEqual(
            resp.status_code, status.HTTP_200_OK,
            f"superuser deveria conseguir acessar admin/records, obtido "
            f"{resp.status_code} (corpo: {resp.content!r})",
        )


class AdminRecordsDataTest(TestCase):
    """Dados retornados por GET /api/v1/admin/records/ devem cruzar
    multiplos grupos/pacientes e trazer os campos necessarios para a
    tela; filtros de busca e status devem funcionar."""

    url = "/api/v1/admin/records/"

    def setUp(self):
        self.client = APIClient()

        self.superuser = User.objects.create_superuser(
            "bossdata", email="bossdata@test.com", password="pass1234"
        )
        # Superuser tambem tem seu proprio grupo/paciente, para garantir
        # que o endpoint nao filtra apenas pelo grupo do proprio superuser.
        self.own_patient = Patient.objects.create(name="Paciente Do Boss")
        self.own_group = CareGroup.objects.create(
            name="Grupo Do Boss", patient=self.own_patient
        )
        GroupMembership.objects.create(
            user=self.superuser, group=self.own_group, relation_to_patient="FAMILY"
        )

        self.author_a = User.objects.create_user("autora", password="pass1234")
        self.author_b = User.objects.create_user("autorb", password="pass1234")

        self.patient_a = Patient.objects.create(name="Paciente Alfa")
        self.group_a = CareGroup.objects.create(name="Grupo Alfa", patient=self.patient_a)
        GroupMembership.objects.create(
            user=self.author_a, group=self.group_a, relation_to_patient="FAMILY"
        )

        self.patient_b = Patient.objects.create(name="Paciente Beta")
        self.group_b = CareGroup.objects.create(name="Grupo Beta", patient=self.patient_b)
        GroupMembership.objects.create(
            user=self.author_b, group=self.group_b, relation_to_patient="FAMILY"
        )

        self.record_a = CareRecord.objects.create(
            patient=self.patient_a,
            caregiver="Autora",
            type=CareRecord.Type.MEDICATION,
            what="Dipirona",
            date=date(2026, 8, 1),
            status=CareRecord.Status.PENDING,
            created_by=self.author_a,
        )
        self.record_b = CareRecord.objects.create(
            patient=self.patient_b,
            caregiver="Autorb",
            type=CareRecord.Type.MEAL,
            what="Almoco",
            date=date(2026, 8, 2),
            status=CareRecord.Status.DONE,
            created_by=self.author_b,
        )

        self.client.force_authenticate(user=self.superuser)

    def _get_results(self, resp):
        data = resp.json()
        # Aceita tanto lista simples quanto paginacao estilo DRF
        # ({"results": [...], "count": N}).
        if isinstance(data, dict) and "results" in data:
            return data["results"]
        return data

    def test_returns_records_from_multiple_groups_and_patients(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._get_results(resp)

        record_ids = {item["id"] for item in results}
        self.assertIn(
            self.record_a.id, record_ids,
            "registro do Grupo Alfa deveria aparecer na listagem cross-group",
        )
        self.assertIn(
            self.record_b.id, record_ids,
            "registro do Grupo Beta deveria aparecer na listagem cross-group",
        )

        groups_seen = {item.get("group") for item in results}
        self.assertGreaterEqual(
            len(groups_seen), 2,
            f"a listagem deveria conter registros de multiplos grupos, "
            f"obtido apenas {groups_seen!r} -- endpoint parece restrito "
            f"ao grupo do proprio superuser",
        )

    def test_result_item_has_required_fields(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._get_results(resp)
        self.assertTrue(results, "esperava ao menos um registro na listagem")

        item = next(r for r in results if r["id"] == self.record_a.id)

        self.assertIn("id", item)
        self.assertIn("status", item)
        self.assertIn("date", item)
        self.assertEqual(item["status"], CareRecord.Status.PENDING)
        self.assertEqual(item["date"], "2026-08-01")

        self.assertTrue(
            "type" in item or "label" in item,
            f"item deveria incluir tipo/label do registro, obtido chaves {list(item.keys())}",
        )

        self.assertIn("patient", item)
        self.assertEqual(item["patient"], "Paciente Alfa")

        self.assertIn("group", item)
        self.assertEqual(item["group"], "Grupo Alfa")

        self.assertTrue(
            "author_name" in item or "caregiver" in item,
            f"item deveria incluir autor/cuidador, obtido chaves {list(item.keys())}",
        )

    def test_search_filter_reduces_results(self):
        resp = self.client.get(self.url, {"q": "Alfa"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._get_results(resp)

        ids = {item["id"] for item in results}
        self.assertIn(self.record_a.id, ids)
        self.assertNotIn(
            self.record_b.id, ids,
            "busca por 'Alfa' nao deveria retornar registro do paciente/grupo Beta",
        )

    def test_status_filter_reduces_results(self):
        resp = self.client.get(self.url, {"status": CareRecord.Status.DONE})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._get_results(resp)

        ids = {item["id"] for item in results}
        self.assertIn(self.record_b.id, ids)
        self.assertNotIn(
            self.record_a.id, ids,
            "filtro status=done nao deveria retornar registro pendente",
        )
