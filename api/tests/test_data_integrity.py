# api/tests/test_data_integrity.py
"""
Testes de integridade CRUD e concorrência (tarefa #111).

Cobrem três cenários de segurança/integridade de dados de saúde:

(a) bulk_set_status com select_for_update não deve duplicar notificação nem
    perder registros quando duas requisições concorrentes competem pelo
    mesmo conjunto de IDs. Como o backend de testes é SQLite (sem suporte
    real a locking em `SELECT ... FOR UPDATE` -- Django simplesmente omite
    a cláusula), o `select_for_update()` do código de produção não protege
    de fato contra a corrida entre duas threads reais concorrendo pela
    mesma leitura "ainda não MISSED".

(b) sync_recurrence_series deve manter a consistência da série recorrente
    ao editar/excluir um registro, sem apagar registros de OUTRO paciente
    que por colisão de UUID compartilhe o mesmo recurrence_group.

(c) Constraints de unicidade (unique_medication_per_group,
    unique_user_group_membership -- renomeada na tarefa #38 a partir da
    antiga unique_user_one_group) devem ser respeitadas via API
    retornando 400, nunca vazando um IntegrityError como 500 para o
    cliente.
"""
import threading
import uuid
from datetime import date, time
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models.query import QuerySet
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from care.models import CareGroup, CareRecord, GroupMembership, Medication, Patient
from care.signals import queue_missed_notification
from care.utils import sync_recurrence_series


# ---------------------------------------------------------------------------
# (a) bulk_set_status: corrida entre leituras concorrentes (determinística)
# ---------------------------------------------------------------------------

@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class BulkSetStatusConcurrencyTest(TestCase):
    """
    Duas requisições concorrentes chamando bulk_set_status(status="missed")
    para o MESMO conjunto de ids não podem notificar o mesmo registro duas
    vezes nem deixar o estado final inconsistente.

    Em vez de disparar threads reais via HTTP (frágil aqui: o banco de
    testes é um SQLite em memória com shared cache, que levanta
    "database table is locked" sob escrita concorrente real, um problema
    de infraestrutura de teste independente do bug de negócio), este teste
    reproduz a corrida de forma determinística: intercala manualmente, na
    MESMA thread, os dois passos que duas requisições concorrentes fariam
    -- ambas leem "quais registros ainda não estão MISSED" ANTES de
    qualquer uma escrever. É exatamente essa janela que o
    `select_for_update()` do código de produção deveria fechar (e não
    fecha: o backend SQLite não suporta locking real em
    `SELECT ... FOR UPDATE`, e Django simplesmente omite a cláusula).
    """

    def setUp(self):
        self.user = User.objects.create_user("alice", password="pass1234")
        self.patient = Patient.objects.create(name="Vovo")
        self.group = CareGroup.objects.create(name="Familia", patient=self.patient)
        GroupMembership.objects.create(
            user=self.user, group=self.group, relation_to_patient="FAMILY"
        )
        self.r1 = CareRecord.objects.create(
            patient=self.patient, type="medication", what="Remedio A",
            date=date(2026, 1, 1), time=time(9, 0),
            caregiver="Cuidador", status=CareRecord.Status.PENDING,
        )
        self.r2 = CareRecord.objects.create(
            patient=self.patient, type="medication", what="Remedio B",
            date=date(2026, 1, 1), time=time(10, 0),
            caregiver="Cuidador", status=CareRecord.Status.PENDING,
        )

    def test_two_concurrent_reads_before_any_write_duplicate_notification(self):
        ids = [self.r1.id, self.r2.id]
        qs = CareRecord.objects.filter(pk__in=ids, patient=self.patient)

        with patch("api.services.push.send_push") as mock_send:
            with self.captureOnCommitCallbacks(execute=True):
                # Requisição 1 lê o conjunto "ainda não MISSED" -- mesmo
                # código usado por api/views/care.py::bulk_set_status.
                to_notify_1 = list(
                    qs.select_for_update().exclude(status=CareRecord.Status.MISSED)
                )
                # Requisição 2, concorrente, lê o MESMO conjunto antes de
                # a requisição 1 ter escrito nada.
                to_notify_2 = list(
                    qs.select_for_update().exclude(status=CareRecord.Status.MISSED)
                )

                with transaction.atomic():
                    qs.update(status=CareRecord.Status.MISSED)
                    for record in to_notify_1:
                        queue_missed_notification(record)

                with transaction.atomic():
                    qs.update(status=CareRecord.Status.MISSED)
                    for record in to_notify_2:
                        queue_missed_notification(record)

        # Cada um dos 2 registros só pode transitar para MISSED (e
        # notificar) uma única vez no total, mesmo com 2 leituras
        # concorrentes do mesmo conjunto "ainda não MISSED".
        self.assertEqual(
            mock_send.call_count, 2,
            f"esperado exatamente 2 notificacoes no total (uma por "
            f"registro), obtido {mock_send.call_count} -- select_for_update "
            f"nao impediu notificacao duplicada quando duas leituras "
            f"concorrentes veem o mesmo conjunto 'ainda nao MISSED'."
        )

        # Estado final do banco: os 2 registros existem e estao MISSED --
        # nenhum foi perdido nem duplicado.
        self.assertEqual(CareRecord.objects.filter(pk__in=ids).count(), 2)
        self.r1.refresh_from_db()
        self.r2.refresh_from_db()
        self.assertEqual(self.r1.status, CareRecord.Status.MISSED)
        self.assertEqual(self.r2.status, CareRecord.Status.MISSED)


# ---------------------------------------------------------------------------
# (b) sync_recurrence_series: isolamento entre pacientes com mesmo recurrence_group
# ---------------------------------------------------------------------------

class SyncRecurrenceSeriesCrossPatientIsolationTest(TestCase):
    """
    _clear_series / sync_recurrence_series filtram apenas por
    `recurrence_group=group_id`, sem restringir por paciente. Se, por
    colisao de UUID (ou por um bug em outro ponto que reutilize um id),
    dois pacientes diferentes tiverem registros com o MESMO
    recurrence_group, editar/excluir a serie de um paciente NAO PODE
    apagar os registros do outro paciente.
    """

    def setUp(self):
        self.user = User.objects.create_user("caregiver", password="pass1234")
        self.patient_a = Patient.objects.create(name="Paciente A")
        self.patient_b = Patient.objects.create(name="Paciente B")
        self.shared_group_id = uuid.uuid4()

    def _record(self, patient, d, recurrence=CareRecord.Recurrence.NONE, repeat_until=None):
        return CareRecord.objects.create(
            patient=patient,
            caregiver="Cuidador",
            type=CareRecord.Type.MEDICATION,
            what="Remedio",
            date=d,
            time=time(8, 0),
            recurrence=recurrence,
            repeat_until=repeat_until,
            recurrence_group=self.shared_group_id,
            created_by=self.user,
        )

    def test_editing_series_of_patient_a_does_not_delete_patient_b_records(self):
        start = date(2026, 1, 1)
        # Serie do paciente A (o "base" que sera editado).
        base_a = self._record(
            self.patient_a, start,
            recurrence=CareRecord.Recurrence.DAILY,
            repeat_until=start,
        )
        # Registro futuro do paciente B que colide no mesmo recurrence_group.
        other_b = self._record(self.patient_b, start)

        # Editar a serie do paciente A (ex.: desativando a recorrencia) nao
        # pode apagar o registro do paciente B, mesmo compartilhando o
        # mesmo recurrence_group.
        base_a.recurrence = CareRecord.Recurrence.NONE
        base_a.repeat_until = None
        sync_recurrence_series(base_a, previous_group=self.shared_group_id)

        self.assertTrue(
            CareRecord.objects.filter(pk=other_b.pk).exists(),
            "registro do PACIENTE B foi apagado ao sincronizar a serie "
            "recorrente do PACIENTE A -- vazamento de dados entre pacientes "
            "por colisao de recurrence_group.",
        )

    def test_recreating_series_of_patient_a_does_not_delete_patient_b_records(self):
        start = date(2026, 2, 1)
        base_a = self._record(
            self.patient_a, start,
            recurrence=CareRecord.Recurrence.DAILY,
            repeat_until=start,
        )
        other_b = self._record(self.patient_b, start)

        # Estende a recorrencia do paciente A -- isso recria a serie
        # (delete + bulk_create) usando o mesmo recurrence_group.
        base_a.repeat_until = start.replace(day=3)
        sync_recurrence_series(base_a)

        self.assertTrue(
            CareRecord.objects.filter(pk=other_b.pk).exists(),
            "registro do PACIENTE B foi apagado ao recriar a serie "
            "recorrente do PACIENTE A.",
        )
        self.assertEqual(
            CareRecord.objects.filter(patient=self.patient_b).count(), 1,
            "contagem final de registros do PACIENTE B mudou apos operacao "
            "restrita a serie do PACIENTE A.",
        )


# ---------------------------------------------------------------------------
# (c) Constraints de unicidade via API: 400, nunca 500
# ---------------------------------------------------------------------------

class MedicationUniqueConstraintAPITest(TestCase):
    """unique_medication_per_group deve virar 400 pela API, nunca um 500
    de IntegrityError vazando (o MedicationSerializer nao inclui o campo
    "group" e por isso o UniqueTogetherValidator automatico do DRF nao
    e' gerado para essa constraint)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("meduser", password="pass1234")
        self.patient = Patient.objects.create(name="Paciente")
        self.group = CareGroup.objects.create(name="Grupo", patient=self.patient)
        GroupMembership.objects.create(
            user=self.user, group=self.group, relation_to_patient="FAMILY"
        )
        self.client.force_authenticate(user=self.user)

    def test_duplicate_medication_via_api_returns_400_not_500(self):
        Medication.objects.create(group=self.group, name="Paracetamol", dosage="500mg")

        # Neste ambiente local (Python 3.14), uma resposta 500 real quebra
        # ao tentar renderizar o template de erro (incompatibilidade do
        # Context.__copy__ do Django com 3.14 -- ver memoria
        # test-env-py314), mascarando a excecao original com um
        # AttributeError espurio. Isso NAO e uma regressao deste teste: o
        # test client (raise_request_exception=True, padrao) propaga a
        # excecao nao tratada da view diretamente para o teste, o que por
        # si so ja comprova que a API nao converteu a violacao de
        # constraint em uma resposta 400 tratada.
        try:
            resp = self.client.post("/api/v1/medications/", {
                "name": "Paracetamol",
                "dosage": "500mg",
            }, format="json")
        except Exception as exc:  # noqa: BLE001 - é exatamente o que queremos flagrar
            self.fail(
                f"duplicata de medicamento nao deveria propagar uma excecao "
                f"nao tratada (IntegrityError vazando como 500): {exc!r}"
            )

        self.assertEqual(
            resp.status_code, status.HTTP_400_BAD_REQUEST,
            f"duplicata de medicamento deveria retornar 400, retornou "
            f"{resp.status_code} (corpo: {resp.content!r})",
        )
        self.assertEqual(
            Medication.objects.filter(
                group=self.group, name="Paracetamol", dosage="500mg"
            ).count(),
            1,
        )


class GroupMembershipUniqueConstraintConcurrencyTest(TransactionTestCase):
    """
    unique_user_group_membership (tarefa #38: renomeada a partir da antiga
    unique_user_one_group, que so permitia 1 grupo por usuario -- agora um
    usuario PODE estar em varios grupos, mas nao pode duplicar membership
    no MESMO grupo): duas requisicoes concorrentes do MESMO usuario
    tentando entrar no MESMO grupo ao mesmo tempo (dois cliques, duas
    abas) disputam a checagem
    `GroupMembership.objects.filter(user=...).exists()` seguida de
    `.create()`. Nenhuma delas pode vazar um 500 de IntegrityError, e ao
    final deve existir exatamente 1 GroupMembership para o usuario nesse
    grupo (a corrida nao pode duplicar a linha).

    Nota: como agora o usuario pode pertencer a varios grupos, entrar
    concorrentemente em DOIS GRUPOS DIFERENTES nao é mais barrado pelo
    banco (nao ha mais nada de errado nisso -- é exatamente o
    comportamento que esta tarefa passou a permitir). Esta race
    especifica (mesmo grupo, duas vezes) e o cenario que continua
    precisando de protecao.
    """

    def setUp(self):
        self.user = User.objects.create_user("carol", password="pass1234")

        self.patient1 = Patient.objects.create(name="Paciente 1")
        self.group1 = CareGroup.objects.create(name="Grupo 1", patient=self.patient1)
        self.group1.set_join_code("1111")
        self.group1.save(update_fields=["join_code_hash"])

    def _client(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        return client

    def test_concurrent_group_join_never_returns_500_and_creates_single_membership(self):
        barrier = threading.Barrier(2, timeout=10)
        original_exists = QuerySet.exists

        def synced_exists(self_qs, *args, **kwargs):
            if self_qs.model is GroupMembership:
                try:
                    barrier.wait()
                except threading.BrokenBarrierError:
                    pass
            return original_exists(self_qs, *args, **kwargs)

        results = {}

        def worker(name, group_id, pin):
            client = self._client()
            client.raise_request_exception = False
            try:
                with patch.object(QuerySet, "exists", synced_exists):
                    resp = client.post("/api/v1/groups/join/", {
                        "group_id": group_id,
                        "relation_to_patient": "FAMILY",
                        "pin": pin,
                    }, format="json")
                results[name] = resp.status_code
            except Exception as exc:  # noqa: BLE001 - queremos flagrar qualquer vazamento
                # Neste ambiente (Python 3.14) uma resposta 500 real quebra
                # ao renderizar o template de erro (ver memoria
                # test-env-py314), entao a excecao nao tratada da view
                # (IntegrityError) acaba se manifestando aqui como uma
                # excecao de renderizacao. De um jeito ou de outro, chegar
                # nesse except comprova que a violacao da constraint nao
                # foi convertida numa resposta 400 tratada pela view.
                results[name] = f"EXC:{exc!r}"

        t1 = threading.Thread(target=worker, args=("t1", self.group1.id, "1111"))
        t2 = threading.Thread(target=worker, args=("t2", self.group1.id, "1111"))
        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)

        self.assertFalse(t1.is_alive(), "thread t1 nao terminou (deadlock?)")
        self.assertFalse(t2.is_alive(), "thread t2 nao terminou (deadlock?)")

        for name, code in results.items():
            self.assertIn(
                code, (200, 400),
                f"{name}: IntegrityError vazou como excecao/500 em vez de "
                f"ser tratada como uma resposta 400 (obtido: {code!r}).",
            )

        self.assertEqual(
            GroupMembership.objects.filter(user=self.user).count(), 1,
            "usuario deveria terminar com exatamente 1 GroupMembership "
            "apos a corrida entre as duas requisicoes.",
        )
