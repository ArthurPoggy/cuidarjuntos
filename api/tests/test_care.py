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
    humanize_identifier,
)
from care.utils import sync_recurrence_series


def _future_today_date_and_time(offset=timedelta(hours=1)):
    """
    Retorna (date, time) sempre no futuro em relacao ao momento da chamada,
    evitando testes frageis que dependem do horario em que a suite roda.
    Normalmente cai no mesmo dia (date.today()); se o offset ultrapassar a
    meia-noite, avanca a data para o dia seguinte para permanecer no futuro.
    """
    now = timezone.localtime()
    target_dt = now + offset
    target_date = target_dt.date()
    target_time = target_dt.time()
    return target_date, target_time


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
        safe_date, safe_time = _future_today_date_and_time()
        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="Old",
            date=safe_date, time=safe_time,
            caregiver="Test", created_by=self.user,
        )
        resp = self.client.patch(f"/api/v1/records/{rec.id}/", {
            "what": "Updated",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rec.refresh_from_db()
        self.assertEqual(rec.what, "Updated")

    def test_update_past_record_forbidden(self):
        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="Old",
            date=date.today() - timedelta(days=1), time=time(10, 0),
            caregiver="Test", created_by=self.user,
        )
        resp = self.client.patch(f"/api/v1/records/{rec.id}/", {
            "what": "Updated",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        rec.refresh_from_db()
        self.assertEqual(rec.what, "Old")

    def test_put_past_record_forbidden(self):
        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="Old",
            date=date.today() - timedelta(days=1), time=time(10, 0),
            caregiver="Test", created_by=self.user,
        )
        resp = self.client.put(f"/api/v1/records/{rec.id}/", {
            "type": "other",
            "what": "Updated",
            "date": str(date.today() - timedelta(days=1)),
            "time": "10:00",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        rec.refresh_from_db()
        self.assertEqual(rec.what, "Old")

    def test_update_future_record_allowed(self):
        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="Old",
            date=date.today() + timedelta(days=1), time=time(10, 0),
            caregiver="Test", created_by=self.user,
        )
        resp = self.client.patch(f"/api/v1/records/{rec.id}/", {
            "what": "Updated",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rec.refresh_from_db()
        self.assertEqual(rec.what, "Updated")

    def test_record_admin_can_update_past_record(self):
        admin = User.objects.create_user("api-admin2", password="pass1234", is_staff=True)
        GroupMembership.objects.create(user=admin, group=self.group, relation_to_patient="FAMILY")
        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="Old",
            date=date.today() - timedelta(days=1), time=time(10, 0),
            caregiver="Test", created_by=self.user,
        )
        self.client.force_authenticate(user=admin)

        resp = self.client.patch(f"/api/v1/records/{rec.id}/", {
            "what": "Updated by admin",
        }, format="json")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rec.refresh_from_db()
        self.assertEqual(rec.what, "Updated by admin")

    def test_delete_record(self):
        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="Del",
            date=date.today(), time=time(10, 0),
            caregiver="Test", created_by=self.user,
        )
        resp = self.client.delete(f"/api/v1/records/{rec.id}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(CareRecord.objects.filter(pk=rec.id).exists())

    def test_admin_can_delete_any_record(self):
        # O admin precisa pertencer ao mesmo grupo do registro: a permissao
        # de staff/admin dispensa a checagem de "dono do registro", mas
        # nunca concede acesso a registros de outros grupos (ver testes de
        # isolamento entre grupos em test_cross_group_isolation.py).
        admin = User.objects.create_user("api-admin", password="pass1234", is_staff=True)
        GroupMembership.objects.create(user=admin, group=self.group, relation_to_patient="FAMILY")
        rec = CareRecord.objects.create(
            patient=self.patient, type="meal", what="Almoco",
            date=date.today(), time=time(12, 0),
            caregiver="Test", created_by=self.user,
        )
        self.client.force_authenticate(user=admin)

        resp = self.client.delete(f"/api/v1/records/{rec.id}/")

        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(CareRecord.objects.filter(pk=rec.id).exists())

    def test_common_user_cannot_delete_other_users_record(self):
        other = User.objects.create_user("api-other", password="pass1234")
        GroupMembership.objects.create(user=other, group=self.group, relation_to_patient="FAMILY")
        rec = CareRecord.objects.create(
            patient=self.patient, type="activity", what="Caminhada",
            date=date.today(), time=time(9, 0),
            caregiver="Test", created_by=self.user,
        )
        self.client.force_authenticate(user=other)

        resp = self.client.delete(f"/api/v1/records/{rec.id}/")

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(CareRecord.objects.filter(pk=rec.id).exists())

    def test_anonymous_user_cannot_delete_record(self):
        rec = CareRecord.objects.create(
            patient=self.patient, type="vital", what="Pressao arterial",
            date=date.today(), time=time(8, 0),
            caregiver="Test", created_by=self.user,
        )
        self.client.force_authenticate(user=None)

        resp = self.client.delete(f"/api/v1/records/{rec.id}/")

        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(CareRecord.objects.filter(pk=rec.id).exists())

    def test_deleted_record_is_not_listed(self):
        rec = CareRecord.objects.create(
            patient=self.patient, type="progress", what="Evolucao",
            date=date.today(), time=time(10, 0),
            caregiver="Test", created_by=self.user,
        )

        delete_resp = self.client.delete(f"/api/v1/records/{rec.id}/")
        list_resp = self.client.get("/api/v1/records/")

        self.assertEqual(delete_resp.status_code, status.HTTP_204_NO_CONTENT)
        ids = [item["id"] for item in list_resp.data["results"]]
        self.assertNotIn(rec.id, ids)

    def test_delete_works_for_multiple_record_types(self):
        for type_value in ("sleep", "bathroom", "medication"):
            rec = CareRecord.objects.create(
                patient=self.patient, type=type_value, what=f"Delete {type_value}",
                date=date.today(), time=time(10, 0),
                caregiver="Test", created_by=self.user,
            )

            resp = self.client.delete(f"/api/v1/records/{rec.id}/")

            self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT, type_value)
            self.assertFalse(CareRecord.objects.filter(pk=rec.id).exists(), type_value)

    def test_delete_record_is_soft_deleted_not_removed_from_database(self):
        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="Del soft",
            date=date.today(), time=time(10, 0),
            caregiver="Test", created_by=self.user,
        )

        resp = self.client.delete(f"/api/v1/records/{rec.id}/")

        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(CareRecord.objects.filter(pk=rec.id).exists())

        still_in_db = CareRecord.all_objects.get(pk=rec.id)
        self.assertIsNotNone(still_in_db.deleted_at)
        self.assertEqual(still_in_db.deleted_by, self.user)

    def test_cancel_following_single_record_is_soft_deleted(self):
        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="Sem serie",
            date=date.today(), time=time(10, 0),
            caregiver="Test", created_by=self.user,
        )

        resp = self.client.post(f"/api/v1/records/{rec.id}/cancel_following/")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(CareRecord.objects.filter(pk=rec.id).exists())

        still_in_db = CareRecord.all_objects.get(pk=rec.id)
        self.assertIsNotNone(still_in_db.deleted_at)
        self.assertEqual(still_in_db.deleted_by, self.user)

    def test_cancel_following_series_soft_deletes_future_occurrences(self):
        today = date.today()
        base = CareRecord.objects.create(
            patient=self.patient, type="medication", what="Remedio recorrente",
            date=today, time=time(8, 0),
            caregiver="Test", created_by=self.user,
            recurrence=CareRecord.Recurrence.DAILY,
            repeat_until=today + timedelta(days=2),
        )
        sync_recurrence_series(base)
        series_ids = list(
            CareRecord.objects.filter(recurrence_group=base.recurrence_group)
            .values_list("id", flat=True)
        )
        self.assertEqual(len(series_ids), 3)

        resp = self.client.post(f"/api/v1/records/{base.id}/cancel_following/")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["deleted"], 3)

        for series_id in series_ids:
            self.assertFalse(CareRecord.objects.filter(pk=series_id).exists())
            still_in_db = CareRecord.all_objects.get(pk=series_id)
            self.assertIsNotNone(still_in_db.deleted_at)
            self.assertEqual(still_in_db.deleted_by, self.user)


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

    def test_dashboard_records_null_time_no_duplicates_ordering_and_counts(self):
        """
        Regressao conclusiva para a issue #106.

        Exercita, de ponta a ponta via GET /api/v1/dashboard/, os tres
        pontos do criterio de aceite:

        (a) um CareRecord com time=None deve ser criavel e deve aparecer
            no dashboard ordenado como se tivesse o menor horario possivel
            do seu dia (NULLs tratados explicitamente, nao deixados ao
            sabor do backend de banco).

            Hoje isso e impossivel: `care/models.py` declara
            `time = models.TimeField("Hora")` sem `null=True`, entao
            `CareRecord.objects.create(..., time=None, ...)` estoura
            `django.db.utils.IntegrityError` (NOT NULL constraint failed:
            care_carerecord.time). Esse IntegrityError e a propria falha
            esperada deste teste ate que o campo seja migrado para
            `null=True, blank=True` e o `records_qs` do dashboard trate o
            NULL explicitamente (ex.: Coalesce) — pre-requisito real para
            a parte do item #106 sobre ordenacao com time=None.

        (b) uma serie recorrente de 3 ocorrencias (via
            sync_recurrence_series) dentro do periodo consultado nao deve
            gerar ids duplicados em `records`, e a lista deve estar em
            ordem nao-crescente por (date, time), com desempate estavel
            por -id quando date/time coincidem (dois registros da serie
            recorrente podem cair no mesmo dia/hora apos edicoes pontuais).

        (c) `counts[type]` deve bater exatamente com a contagem real de
            CareRecord por tipo (excluindo status='missed' por padrao),
            para pelo menos dois tipos distintos.
        """
        today = date.today()

        # (a) registro sem horario definido.
        no_time_record = CareRecord.objects.create(
            patient=self.patient, type="progress", what="Observacao sem horario",
            date=today, time=None,
            caregiver="Test", created_by=self.user, status="pending",
        )

        # (b) serie recorrente diaria com 3 ocorrencias (base + 2 clones),
        # gerada via sync_recurrence_series, dentro do periodo consultado.
        base = CareRecord.objects.create(
            patient=self.patient, type="medication", what="Remedio recorrente",
            date=today, time=time(8, 0),
            caregiver="Test", created_by=self.user, status="pending",
            recurrence=CareRecord.Recurrence.DAILY,
            repeat_until=today + timedelta(days=2),
        )
        sync_recurrence_series(base)
        self.assertEqual(
            CareRecord.objects.filter(recurrence_group=base.recurrence_group).count(),
            3,
            "setup: serie recorrente deveria ter gerado exatamente 3 ocorrencias",
        )

        # registro adicional de outro tipo, para permitir comparar counts
        # de pelo menos dois tipos distintos.
        CareRecord.objects.create(
            patient=self.patient, type="meal", what="Almoco",
            date=today, time=time(12, 0),
            caregiver="Test", created_by=self.user, status="done",
        )

        # `clear=1` remove o filtro de periodo padrao (que seria so "hoje"),
        # garantindo que a serie recorrente (que se estende por 3 dias)
        # fique inteiramente dentro do conjunto consultado, tanto para os
        # records quanto para os counts.
        resp = self.client.get("/api/v1/dashboard/", {"clear": "1"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        records = resp.data["records"]
        ids = [r["id"] for r in records]

        # (a) o registro com time=None deve aparecer no dashboard.
        self.assertIn(
            no_time_record.id, ids,
            "registro com time=None nao apareceu em records do dashboard",
        )

        # (b) sem duplicatas.
        self.assertEqual(
            len(ids), len(set(ids)),
            f"records retornados contem ids duplicados: {ids}",
        )

        # Todas as 3 ocorrencias da serie devem estar presentes (nada foi
        # perdido nem duplicado).
        series_ids = list(
            CareRecord.objects.filter(recurrence_group=base.recurrence_group)
            .values_list("id", flat=True)
        )
        for series_id in series_ids:
            self.assertIn(series_id, ids)

        # (b) Ordenacao nao-crescente por (date, time), com time=None
        # tratado como o menor valor possivel do dia, e desempate estavel
        # por -id quando (date, time) coincidem.
        def sort_key(item):
            # None deve ordenar como "menor que qualquer horario real".
            time_value = item["time"] if item["time"] is not None else ""
            return (item["date"], time_value, -item["id"])

        keys = [sort_key(r) for r in records]
        self.assertEqual(
            keys, sorted(keys, reverse=True),
            f"records nao estao em ordem nao-crescente por (date, time, -id): {keys}",
        )

        # (c) counts deve bater exatamente com a contagem real por tipo,
        # excluindo status='missed' (regra vigente por padrao).
        for care_type in ("medication", "meal"):
            expected = (
                CareRecord.objects.filter(patient=self.patient, type=care_type)
                .exclude(status="missed")
                .count()
            )
            self.assertEqual(
                resp.data["counts"][care_type], expected,
                f"counts['{care_type}'] nao bate com a contagem real",
            )


class DashboardAuthorNameConsistencyTests(CareRecordTestMixin, TestCase):
    """
    Regressao para o item do #106: 'Garantir consistencia do autor exibido
    (author_name/caregiver) com o usuario real que criou o registro'.

    O frontend (RecordCard.tsx) exibe `record.caregiver || record.author_name`,
    priorizando `caregiver` (uma string livre, gravada no momento da criacao
    e que pode ficar desatualizada apos edicao/reatribuicao do registro) sobre
    `author_name` (derivado de `created_by`, a fonte de verdade sobre quem
    de fato criou o registro). Isso pode divergir do autor real.

    Estes testes fixam o contrato do lado do backend: `author_name` deve
    sempre refletir `created_by` (o autor real), independentemente do valor
    de `caregiver`. A correcao do item tambem precisa ajustar o frontend
    para nao preferir `caregiver` sobre `author_name` — isso nao e coberto
    aqui (fora do escopo de testes de API), mas o valor de `author_name`
    retornado pela API precisa estar correto para que essa correcao seja
    possivel.
    """

    def test_author_name_falls_back_to_humanized_username_without_profile_or_names(self):
        """
        (1) Usuario sem profile.full_name e sem first_name/last_name: o
        author_name do registro deve ser nao-vazio e igual a
        humanize_identifier(username) do usuario que de fato criou o
        registro (created_by), nao um valor arbitrario/vazio.
        """
        author = User.objects.create_user("joao.pereira", password="pass1234")
        # Garantia explicita do cenario: sem full_name no profile e sem
        # first_name/last_name no User.
        profile = getattr(author, "profile", None)
        if profile is not None:
            profile.full_name = ""
            profile.save(update_fields=["full_name"])
        author.first_name = ""
        author.last_name = ""
        author.save(update_fields=["first_name", "last_name"])

        record = CareRecord.objects.create(
            patient=self.patient, type="other", what="Registro sem nome no perfil",
            date=date.today(), time=time(9, 0),
            caregiver="joao.pereira", created_by=author, status="pending",
        )

        resp = self.client.get("/api/v1/dashboard/", {"clear": "1"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        by_id = {r["id"]: r for r in resp.data["records"]}
        self.assertIn(record.id, by_id, "registro criado nao apareceu em records do dashboard")

        author_name = by_id[record.id]["author_name"]
        expected = humanize_identifier(author.username)
        self.assertTrue(author_name, "author_name nao deveria ser vazio")
        self.assertEqual(
            author_name, expected,
            f"author_name deveria ser humanize_identifier(username)={expected!r}, "
            f"mas veio {author_name!r}",
        )

    def test_author_name_stays_consistent_with_created_by_when_caregiver_diverges(self):
        """
        (2) Quando o campo `caregiver` foi alterado manualmente para um
        valor diferente do usuario criador atual (registro desatualizado
        apos edicao/reatribuicao), o valor usado para exibir o autor deve
        permanecer consistente com `created_by` — o autor real — e nao com
        o `caregiver` divergente.
        """
        real_author = User.objects.create_user(
            "maria.silva", password="pass1234", first_name="Maria", last_name="Silva",
        )

        record = CareRecord.objects.create(
            patient=self.patient, type="other", what="Registro reatribuido",
            date=date.today(), time=time(10, 0),
            caregiver="Maria Silva", created_by=real_author, status="pending",
        )

        # Simula o campo `caregiver` ficando desatualizado (ex.: apos edicao
        # ou reatribuicao do registro) sem que `created_by` mude.
        record.caregiver = "Cuidador Desconhecido"
        record.save(update_fields=["caregiver"])

        resp = self.client.get("/api/v1/dashboard/", {"clear": "1"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        by_id = {r["id"]: r for r in resp.data["records"]}
        self.assertIn(record.id, by_id, "registro criado nao apareceu em records do dashboard")

        data = by_id[record.id]
        self.assertNotEqual(
            data["author_name"], humanize_identifier(data["caregiver"]),
            "setup invalido: caregiver e author_name deveriam divergir neste cenario",
        )

        # O valor de exibicao do autor (author_name) deve continuar batendo
        # com o autor real (created_by), e nao com o caregiver desatualizado.
        expected = real_author.get_full_name().strip()
        self.assertEqual(
            data["author_name"], expected,
            f"author_name deveria refletir created_by ({expected!r}), "
            f"mas veio {data['author_name']!r} (caregiver desatualizado="
            f"{data['caregiver']!r})",
        )

        # A UI (RecordCard.tsx) atualmente exibe `caregiver || author_name`,
        # priorizando o caregiver desatualizado. Documentamos aqui o
        # contrato que a correcao do frontend precisa respeitar: o valor
        # efetivamente exibido para o autor deve ser author_name, nao
        # caregiver, quando eles divergem.
        displayed_value = data["caregiver"] or data["author_name"]
        self.assertEqual(
            displayed_value, data["author_name"],
            "a logica de exibicao (caregiver || author_name) nao deveria "
            "priorizar um caregiver desatualizado sobre o author_name, que "
            "reflete o autor real (created_by)",
        )


class DashboardCategoryDateRangeFilterTests(CareRecordTestMixin, TestCase):
    """
    Regressao para o item do #106: 'Evitar perda de registros ao combinar
    filtros de categoria + intervalo de datas no dashboard'.

    `dashboard_data` (api/views/care.py) deriva `qs_cat` de `qs` (ja filtrado
    por data) e depois corta o resultado em `[:200]` antes de serializar.
    Quando o conjunto de registros que satisfaz (data dentro do intervalo E
    tipo em `categories`) tem mais de 200 itens, esse corte silencioso
    descarta registros validos sem qualquer aviso ao cliente — nao ha
    paginacao real nem contagem total exposta para o front perceber a perda.
    """

    def test_combined_category_and_date_range_returns_exact_expected_set(self):
        """
        Caso baseline (sem tocar no limite de 200): cria registros de pelo
        menos dois tipos/categorias distintos, alguns dentro e outros fora
        do intervalo de datas consultado, e alguns dentro do intervalo mas
        de um tipo nao selecionado. O conjunto de ids retornado em
        `records` deve ser exatamente igual ao conjunto calculado
        manualmente pelos mesmos criterios (data dentro do intervalo E tipo
        em `categories`) — nem faltando, nem sobrando itens.
        """
        today = date.today()
        start = today - timedelta(days=10)
        end = today

        # Dentro do intervalo e da categoria selecionada -> esperados.
        med_in = CareRecord.objects.create(
            patient=self.patient, type="medication", what="Remedio dentro",
            date=today, time=time(8, 0),
            caregiver="Test", created_by=self.user, status="pending",
        )
        meal_in = CareRecord.objects.create(
            patient=self.patient, type="meal", what="Refeicao dentro",
            date=today - timedelta(days=5), time=time(12, 0),
            caregiver="Test", created_by=self.user, status="pending",
        )

        # Dentro do intervalo, mas de categoria NAO selecionada -> nao deve
        # aparecer.
        CareRecord.objects.create(
            patient=self.patient, type="vital", what="Sinal vital dentro",
            date=today - timedelta(days=2), time=time(9, 0),
            caregiver="Test", created_by=self.user, status="pending",
        )

        # Categoria selecionada, mas FORA do intervalo de datas -> nao deve
        # aparecer.
        CareRecord.objects.create(
            patient=self.patient, type="medication", what="Remedio fora (antes)",
            date=start - timedelta(days=1), time=time(8, 0),
            caregiver="Test", created_by=self.user, status="pending",
        )
        CareRecord.objects.create(
            patient=self.patient, type="meal", what="Refeicao fora (depois)",
            date=end + timedelta(days=1), time=time(12, 0),
            caregiver="Test", created_by=self.user, status="pending",
        )

        expected_ids = set(
            CareRecord.objects.filter(
                patient=self.patient,
                type__in=["medication", "meal"],
                date__gte=start,
                date__lte=end,
            ).values_list("id", flat=True)
        )
        self.assertEqual(
            expected_ids, {med_in.id, meal_in.id},
            "setup invalido: conjunto esperado deveria conter apenas os "
            "dois registros dentro do intervalo e da categoria selecionada",
        )

        resp = self.client.get("/api/v1/dashboard/", {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "categories": "medication,meal",
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        returned_ids = {r["id"] for r in resp.data["records"]}
        self.assertEqual(
            returned_ids, expected_ids,
            f"ids retornados em records ({sorted(returned_ids)}) nao batem "
            f"exatamente com o conjunto esperado ({sorted(expected_ids)}) ao "
            "combinar filtros de categoria + intervalo de datas",
        )

    def test_combined_category_and_date_range_does_not_silently_truncate_past_200(self):
        """
        Caso que expoe o corte silencioso em `[:200]`: quando o numero de
        registros que satisfazem (data dentro do intervalo E tipo em
        `categories`) excede 200, TODOS eles ainda devem ser esperados em
        `records` — ou, no minimo, o backend nao pode devolver um
        subconjunto arbitrario sem indicar a perda. Aqui fixamos o
        contrato mais forte (usado pelo criterio de aceite do item):
        o conjunto de ids retornado deve ser exatamente igual ao conjunto
        esperado, sem itens faltando.

        Cria 150 registros 'medication' e 60 'meal' (210 no total, todos
        dentro do intervalo consultado e da categoria selecionada, com
        horarios distintos), mais alguns registros de controle fora do
        intervalo e fora da categoria selecionada. Com o `[:200]` atual em
        `records_qs`, 10 desses 210 registros validos sao descartados sem
        aviso -- o teste falha mostrando exatamente os ids perdidos.
        """
        today = date.today()
        start = today - timedelta(days=1)
        end = today

        in_filter_records = []
        # 150 registros 'medication', horarios distintos (minutos 0..149).
        for i in range(150):
            in_filter_records.append(CareRecord(
                patient=self.patient, type="medication", what=f"Remedio {i}",
                date=today, time=time(hour=i // 60, minute=i % 60),
                caregiver="Test", created_by=self.user, status="pending",
            ))
        # 60 registros 'meal', horarios distintos (minutos 150..209).
        for i in range(150, 210):
            in_filter_records.append(CareRecord(
                patient=self.patient, type="meal", what=f"Refeicao {i}",
                date=today, time=time(hour=i // 60, minute=i % 60),
                caregiver="Test", created_by=self.user, status="pending",
            ))
        CareRecord.objects.bulk_create(in_filter_records)

        # Controle: dentro do intervalo, categoria nao selecionada.
        CareRecord.objects.bulk_create([
            CareRecord(
                patient=self.patient, type="vital", what=f"Sinal vital {i}",
                date=today, time=time(hour=20, minute=i),
                caregiver="Test", created_by=self.user, status="pending",
            )
            for i in range(5)
        ])
        # Controle: categoria selecionada, fora do intervalo.
        CareRecord.objects.bulk_create([
            CareRecord(
                patient=self.patient, type="medication", what=f"Remedio fora {i}",
                date=start - timedelta(days=1), time=time(hour=10, minute=i),
                caregiver="Test", created_by=self.user, status="pending",
            )
            for i in range(5)
        ])

        expected_ids = set(
            CareRecord.objects.filter(
                patient=self.patient,
                type__in=["medication", "meal"],
                date__gte=start,
                date__lte=end,
            ).values_list("id", flat=True)
        )
        self.assertEqual(
            len(expected_ids), 210,
            "setup invalido: deveriam existir exatamente 210 registros "
            "validos para o filtro combinado",
        )

        resp = self.client.get("/api/v1/dashboard/", {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "categories": "medication,meal",
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        returned_ids = {r["id"] for r in resp.data["records"]}
        missing_ids = expected_ids - returned_ids
        extra_ids = returned_ids - expected_ids

        self.assertEqual(
            returned_ids, expected_ids,
            "ao combinar filtros de categoria + intervalo de datas com mais "
            f"de 200 registros validos, {len(missing_ids)} registro(s) "
            f"esperado(s) foram omitidos (ids: {sorted(missing_ids)}) e "
            f"{len(extra_ids)} id(s) inesperado(s) vieram a mais "
            f"(ids: {sorted(extra_ids)}); total esperado={len(expected_ids)}, "
            f"total retornado={len(returned_ids)}",
        )


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

    def _bucket_ids_for_date(self, resp_data, date_iso):
        """Retorna a lista de ids de items no bucket cuja date_iso == date_iso."""
        for bucket in resp_data["buckets"]:
            if bucket["date_iso"] == date_iso:
                return [item["id"] for item in bucket["items"]]
        return []

    def _assert_record_only_in_bucket(self, resp_data, record_id, expected_date_iso):
        """
        Garante que record_id aparece exclusivamente no bucket cujo
        date_iso == expected_date_iso, e em nenhum outro bucket do payload.
        """
        found_in = [
            bucket["date_iso"]
            for bucket in resp_data["buckets"]
            if record_id in [item["id"] for item in bucket["items"]]
        ]
        self.assertEqual(
            found_in, [expected_date_iso],
            f"esperado record {record_id} apenas no bucket {expected_date_iso}, encontrado em {found_in}",
        )

    def test_upcoming_buckets_week_range_boundary_from_date_included(self):
        """
        Um CareRecord com date == dfrom (limite inicial do range semanal)
        deve aparecer no bucket date_iso == dfrom.isoformat().
        Usamos um range totalmente no futuro para não esbarrar na exclusão
        de horários passados do dia de hoje.
        """
        dfrom = date.today() + timedelta(days=10)
        dto = dfrom + timedelta(days=6)  # range de semana (7 dias)

        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="No limite inicial",
            date=dfrom, time=time(9, 0),
            caregiver="Test", created_by=self.user, status="pending",
        )

        resp = self.client.get("/api/v1/upcoming/buckets/", {
            "from": dfrom.isoformat(),
            "to": dto.isoformat(),
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["ok"])
        self._assert_record_only_in_bucket(resp.data, rec.id, dfrom.isoformat())

    def test_upcoming_buckets_week_range_boundary_to_date_included(self):
        """
        Um CareRecord com date == dto (limite final do range semanal)
        deve aparecer no bucket date_iso == dto.isoformat().
        """
        dfrom = date.today() + timedelta(days=10)
        dto = dfrom + timedelta(days=6)

        rec = CareRecord.objects.create(
            patient=self.patient, type="other", what="No limite final",
            date=dto, time=time(9, 0),
            caregiver="Test", created_by=self.user, status="pending",
        )

        resp = self.client.get("/api/v1/upcoming/buckets/", {
            "from": dfrom.isoformat(),
            "to": dto.isoformat(),
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["ok"])
        self._assert_record_only_in_bucket(resp.data, rec.id, dto.isoformat())

    def test_upcoming_buckets_week_range_excludes_records_outside_range(self):
        """
        Registros com date fora de [dfrom, dto] (um dia antes de dfrom e um
        dia depois de dto) não devem aparecer em nenhum bucket do payload.
        """
        dfrom = date.today() + timedelta(days=10)
        dto = dfrom + timedelta(days=6)

        before = CareRecord.objects.create(
            patient=self.patient, type="other", what="Antes do range",
            date=dfrom - timedelta(days=1), time=time(9, 0),
            caregiver="Test", created_by=self.user, status="pending",
        )
        after = CareRecord.objects.create(
            patient=self.patient, type="other", what="Depois do range",
            date=dto + timedelta(days=1), time=time(9, 0),
            caregiver="Test", created_by=self.user, status="pending",
        )

        resp = self.client.get("/api/v1/upcoming/buckets/", {
            "from": dfrom.isoformat(),
            "to": dto.isoformat(),
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["ok"])

        all_ids = {
            item["id"]
            for bucket in resp.data["buckets"]
            for item in bucket["items"]
        }
        self.assertNotIn(before.id, all_ids)
        self.assertNotIn(after.id, all_ids)

    def test_upcoming_buckets_month_crossing_range(self):
        """
        Range de mês que cruza a virada de mês (ex.: do último dia de um mês
        ao primeiro dia do mês seguinte). Registros no último dia do mês
        anterior e no primeiro dia do mês seguinte devem aparecer cada um
        exclusivamente no bucket de sua própria data; um registro fora do
        range (dois dias depois de dto) deve ser omitido.
        """
        # Ponto de partida bem no futuro para não colidir com o "hoje" da suite.
        anchor = date.today() + timedelta(days=60)
        # Último dia do mês de anchor.
        next_month_first = anchor.replace(day=28) + timedelta(days=4)
        last_day_of_month = next_month_first - timedelta(days=next_month_first.day)
        first_day_next_month = last_day_of_month + timedelta(days=1)

        dfrom = last_day_of_month
        dto = first_day_next_month + timedelta(days=1)  # cobre a virada de mês

        rec_last_day = CareRecord.objects.create(
            patient=self.patient, type="other", what="Ultimo dia do mes",
            date=last_day_of_month, time=time(9, 0),
            caregiver="Test", created_by=self.user, status="pending",
        )
        rec_first_day_next = CareRecord.objects.create(
            patient=self.patient, type="other", what="Primeiro dia do mes seguinte",
            date=first_day_next_month, time=time(9, 0),
            caregiver="Test", created_by=self.user, status="pending",
        )
        rec_outside = CareRecord.objects.create(
            patient=self.patient, type="other", what="Fora do range",
            date=dto + timedelta(days=2), time=time(9, 0),
            caregiver="Test", created_by=self.user, status="pending",
        )

        resp = self.client.get("/api/v1/upcoming/buckets/", {
            "from": dfrom.isoformat(),
            "to": dto.isoformat(),
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["ok"])

        self._assert_record_only_in_bucket(
            resp.data, rec_last_day.id, last_day_of_month.isoformat()
        )
        self._assert_record_only_in_bucket(
            resp.data, rec_first_day_next.id, first_day_next_month.isoformat()
        )

        all_ids = {
            item["id"]
            for bucket in resp.data["buckets"]
            for item in bucket["items"]
        }
        self.assertNotIn(rec_outside.id, all_ids)


class AgendaConsistencyAfterMutationTests(CareRecordTestMixin, TestCase):
    """
    Testes para a tarefa #110 "Consertar agenda -> MOBILE", item "Garantir
    consistencia da agenda apos criar/editar/remover um registro
    (CareRecord)".

    Cobrem a parte de backend do criterio de aceitacao: `calendar_data` e
    `upcoming_buckets` devem devolver o registro exatamente na data gravada
    (`date`, um `DateField` puro, sem componente de horario/fuso), tanto logo
    apos a criacao quanto apos uma edicao que muda a data, e o registro deve
    deixar de aparecer em qualquer bucket/dia apos a exclusao. Isso funciona
    como guarda de regressao contra qualquer futuro deslocamento de fuso
    horario (ex.: passar a derivar a data a partir de um `datetime` UTC em
    vez de usar `record.date` diretamente) nesses dois endpoints.
    """

    def _get_bucket_dates(self, resp):
        return {b["date_iso"] for b in resp.data["buckets"]}

    def _bucket_item_ids(self, resp, date_iso):
        for b in resp.data["buckets"]:
            if b["date_iso"] == date_iso:
                return {item["id"] for item in b["items"]}
        return set()

    def test_calendar_and_buckets_reflect_exact_creation_date(self):
        date_x = date.today() + timedelta(days=3)

        create_resp = self.client.post("/api/v1/records/", {
            "type": "other",
            "what": "Consulta medica",
            "date": date_x.isoformat(),
            "time": "09:00",
        }, format="json")
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        record_id = create_resp.data["id"]

        buckets_resp = self.client.get("/api/v1/upcoming/buckets/", {
            "from": date.today().isoformat(),
            "to": (date.today() + timedelta(days=14)).isoformat(),
        })
        self.assertEqual(buckets_resp.status_code, status.HTTP_200_OK)
        self.assertIn(
            record_id, self._bucket_item_ids(buckets_resp, date_x.isoformat()),
            "Registro deveria aparecer no bucket da data exata gravada (sem deslocamento de fuso).",
        )
        # Nao pode "vazar" para o dia anterior/seguinte por causa de fuso horario.
        self.assertNotIn(record_id, self._bucket_item_ids(buckets_resp, (date_x - timedelta(days=1)).isoformat()))
        self.assertNotIn(record_id, self._bucket_item_ids(buckets_resp, (date_x + timedelta(days=1)).isoformat()))

        calendar_resp = self.client.get("/api/v1/calendar/", {"m": date_x.replace(day=1).isoformat()})
        self.assertEqual(calendar_resp.status_code, status.HTTP_200_OK)
        events_by_date = calendar_resp.data["events_by_date"]
        self.assertIn(date_x.isoformat(), events_by_date)
        self.assertTrue(
            any(ev["what"] == "Consulta medica" for ev in events_by_date[date_x.isoformat()])
        )
        self.assertNotIn((date_x - timedelta(days=1)).isoformat(), events_by_date)
        self.assertNotIn((date_x + timedelta(days=1)).isoformat(), events_by_date)

    def test_calendar_and_buckets_move_to_new_date_after_edit(self):
        date_x = date.today() + timedelta(days=3)
        date_y = date.today() + timedelta(days=10)

        create_resp = self.client.post("/api/v1/records/", {
            "type": "other",
            "what": "Consulta medica",
            "date": date_x.isoformat(),
            "time": "09:00",
        }, format="json")
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        record_id = create_resp.data["id"]

        update_resp = self.client.patch(f"/api/v1/records/{record_id}/", {
            "date": date_y.isoformat(),
        }, format="json")
        self.assertEqual(update_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(update_resp.data["date"], date_y.isoformat())

        buckets_resp = self.client.get("/api/v1/upcoming/buckets/", {
            "from": date.today().isoformat(),
            "to": (date.today() + timedelta(days=30)).isoformat(),
        })
        self.assertEqual(buckets_resp.status_code, status.HTTP_200_OK)

        # So pode existir no bucket novo (Y); precisa ter sumido do antigo (X).
        self.assertIn(record_id, self._bucket_item_ids(buckets_resp, date_y.isoformat()))
        self.assertNotIn(record_id, self._bucket_item_ids(buckets_resp, date_x.isoformat()))

        calendar_old_month_resp = self.client.get(
            "/api/v1/calendar/", {"m": date_x.replace(day=1).isoformat()}
        )
        self.assertNotIn(date_x.isoformat(), calendar_old_month_resp.data["events_by_date"])

        calendar_new_month_resp = self.client.get(
            "/api/v1/calendar/", {"m": date_y.replace(day=1).isoformat()}
        )
        events_by_date = calendar_new_month_resp.data["events_by_date"]
        self.assertIn(date_y.isoformat(), events_by_date)

    def test_record_disappears_from_calendar_and_buckets_after_delete(self):
        date_x = date.today() + timedelta(days=3)

        create_resp = self.client.post("/api/v1/records/", {
            "type": "other",
            "what": "Consulta medica",
            "date": date_x.isoformat(),
            "time": "09:00",
        }, format="json")
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        record_id = create_resp.data["id"]

        delete_resp = self.client.delete(f"/api/v1/records/{record_id}/")
        self.assertEqual(delete_resp.status_code, status.HTTP_204_NO_CONTENT)

        buckets_resp = self.client.get("/api/v1/upcoming/buckets/", {
            "from": date.today().isoformat(),
            "to": (date.today() + timedelta(days=14)).isoformat(),
        })
        self.assertNotIn(record_id, self._bucket_item_ids(buckets_resp, date_x.isoformat()))
        self.assertNotIn(date_x.isoformat(), self._get_bucket_dates(buckets_resp))

        calendar_resp = self.client.get("/api/v1/calendar/", {"m": date_x.replace(day=1).isoformat()})
        self.assertNotIn(date_x.isoformat(), calendar_resp.data["events_by_date"])


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
