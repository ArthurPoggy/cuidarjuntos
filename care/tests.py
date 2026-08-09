from datetime import date, time, timedelta
from io import BytesIO, StringIO
from unittest.mock import patch
import csv
import uuid
import zipfile

from datetime import datetime as dt_datetime

from django.contrib.auth.models import User
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .exporters import (
    COLUMNS,
    ConsolidatedExportSection,
    EXPORTERS,
    ExportMetadata,
    MEDICATION_COLUMNS,
    build_bathroom_export_layout,
    build_activity_export_layout,
    build_meal_export_layout,
    build_progress_export_layout,
    build_medication_export_layout,
    build_sleep_export_layout,
    build_vital_export_layout,
    export_consolidated_as_docx,
    export_consolidated_as_pdf,
    export_as_docx,
    export_as_pdf,
)
from .models import CareGroup, CareRecord, GroupMembership, Patient
from .utils import can_edit_record, sync_recurrence_series
from .views import admin_export_db, display_name, _resolve_export_period

from docx import Document as DocxDocument


class ExportPeriodFilterTests(TestCase):
    def test_last_7_days_covers_exactly_seven_days(self):
        today = timezone.localdate()
        start, end, _label = _resolve_export_period("last_7_days", None, None)
        self.assertEqual(end, today)
        self.assertEqual(start, today - timedelta(days=6))
        self.assertEqual((end - start).days + 1, 7)

    def test_last_30_days_covers_exactly_thirty_days(self):
        today = timezone.localdate()
        start, end, _label = _resolve_export_period("last_30_days", None, None)
        self.assertEqual(end, today)
        self.assertEqual(start, today - timedelta(days=29))
        self.assertEqual((end - start).days + 1, 30)

    def test_last_90_days_covers_exactly_ninety_days(self):
        today = timezone.localdate()
        start, end, _label = _resolve_export_period("last_90_days", None, None)
        self.assertEqual(end, today)
        self.assertEqual(start, today - timedelta(days=89))
        self.assertEqual((end - start).days + 1, 90)

    def test_last_year_covers_exactly_365_days(self):
        today = timezone.localdate()
        start, end, _label = _resolve_export_period("last_year", None, None)
        self.assertEqual(end, today)
        self.assertEqual(start, today - timedelta(days=364))
        self.assertEqual((end - start).days + 1, 365)

    def test_custom_period_uses_given_dates_without_swapping_when_ordered(self):
        start, end, label = _resolve_export_period(
            "custom", "2026-01-10", "2026-01-20"
        )
        self.assertEqual(start, date(2026, 1, 10))
        self.assertEqual(end, date(2026, 1, 20))
        self.assertEqual(label, "Período personalizado")

    def test_custom_period_swaps_inverted_dates(self):
        start, end, _label = _resolve_export_period(
            "custom", "2026-01-20", "2026-01-10"
        )
        self.assertEqual(start, date(2026, 1, 10))
        self.assertEqual(end, date(2026, 1, 20))

    def test_all_period_has_no_bounds(self):
        start, end, label = _resolve_export_period("all", None, None)
        self.assertIsNone(start)
        self.assertIsNone(end)
        self.assertEqual(label, "Todos os tempos")


class RecurrenceUtilsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="Senha123!")
        self.patient = Patient.objects.create(name="Paciente Teste")

    def test_daily_recurrence_generates_future_records(self):
        start = date.today() + timedelta(days=1)
        record = CareRecord.objects.create(
            patient=self.patient,
            caregiver="Tester",
            type=CareRecord.Type.MEDICATION,
            what="Remédio",
            date=start,
            time=time(9, 0),
            recurrence=CareRecord.Recurrence.DAILY,
            repeat_until=start + timedelta(days=2),
            created_by=self.user,
        )

        sync_recurrence_series(record)

        series_qs = CareRecord.objects.filter(recurrence_group=record.recurrence_group)
        self.assertEqual(series_qs.count(), 3)  # registro base + 2 futuras ocorrências
        future_dates = sorted(series_qs.values_list("date", flat=True))
        self.assertEqual(future_dates[0], start)
        self.assertEqual(future_dates[-1], start + timedelta(days=2))

    def test_clearing_recurrence_removes_clones(self):
        start = date.today() + timedelta(days=1)
        record = CareRecord.objects.create(
            patient=self.patient,
            caregiver="Tester",
            type=CareRecord.Type.MEAL,
            what="Lanche",
            date=start,
            time=time(15, 30),
            recurrence=CareRecord.Recurrence.WEEKLY,
            repeat_until=start + timedelta(weeks=2),
            created_by=self.user,
        )

        sync_recurrence_series(record)
        self.assertTrue(CareRecord.objects.filter(recurrence_group=record.recurrence_group).count() > 1)

        previous_group = record.recurrence_group
        record.recurrence = CareRecord.Recurrence.NONE
        record.repeat_until = None
        sync_recurrence_series(record, previous_group=previous_group)

        record.refresh_from_db()
        self.assertIsNone(record.recurrence_group)
        self.assertFalse(
            CareRecord.objects.exclude(pk=record.pk).filter(recurrence_group=previous_group).exists()
        )


class RecordDeletionPermissionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pass1234")
        self.other = User.objects.create_user(username="other", password="pass1234")
        self.admin = User.objects.create_user(username="admin", password="pass1234", is_staff=True)
        self.patient = Patient.objects.create(name="Paciente Exclusao")
        self.group = CareGroup.objects.create(name="Grupo Exclusao", patient=self.patient)
        GroupMembership.objects.create(user=self.owner, group=self.group, relation_to_patient="FAMILY")
        GroupMembership.objects.create(user=self.other, group=self.group, relation_to_patient="FAMILY")

    def _record(self, *, created_by=None, type_value=CareRecord.Type.OTHER, what="Registro"):
        return CareRecord.objects.create(
            patient=self.patient,
            caregiver="Cuidador",
            type=type_value,
            what=what,
            date=date.today(),
            time=time(10, 0),
            created_by=created_by or self.owner,
        )

    def _delete_url(self, record):
        return reverse("care:record-delete", args=[record.pk])

    def test_creator_can_delete_own_record(self):
        record = self._record()
        self.client.login(username="owner", password="pass1234")

        response = self.client.delete(self._delete_url(record), HTTP_ACCEPT="application/json")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(CareRecord.objects.filter(pk=record.pk).exists())

    def test_staff_admin_can_delete_any_record(self):
        record = self._record()
        self.client.login(username="admin", password="pass1234")

        response = self.client.delete(self._delete_url(record), HTTP_ACCEPT="application/json")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(CareRecord.objects.filter(pk=record.pk).exists())

    def test_common_user_cannot_delete_record_created_by_another_user(self):
        record = self._record(created_by=self.owner)
        self.client.login(username="other", password="pass1234")

        response = self.client.delete(self._delete_url(record), HTTP_ACCEPT="application/json")

        self.assertEqual(response.status_code, 403)
        self.assertTrue(CareRecord.objects.filter(pk=record.pk).exists())

    def test_anonymous_user_cannot_delete_record(self):
        record = self._record()

        response = self.client.delete(self._delete_url(record), HTTP_ACCEPT="application/json")

        self.assertEqual(response.status_code, 401)
        self.assertTrue(CareRecord.objects.filter(pk=record.pk).exists())

    def test_deleted_record_no_longer_appears_in_list(self):
        record = self._record(what="Registro removido")
        self.client.login(username="owner", password="pass1234")

        response = self.client.post(
            self._delete_url(record),
            {"scope": "single"},
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 204)
        list_response = self.client.get(reverse("care:record-list"))
        self.assertNotContains(list_response, "Registro removido")

    def test_delete_works_for_different_record_types(self):
        for type_value, _label in CareRecord.Type.choices:
            record = self._record(type_value=type_value, what=f"Excluir {type_value}")
            self.client.login(username="owner", password="pass1234")

            response = self.client.delete(self._delete_url(record), HTTP_ACCEPT="application/json")

            self.assertEqual(response.status_code, 204, type_value)
            self.assertFalse(CareRecord.objects.filter(pk=record.pk).exists(), type_value)

    def test_single_delete_soft_deletes_record_instead_of_removing_it(self):
        record = self._record(what="Registro para soft delete")
        self.client.login(username="owner", password="pass1234")

        response = self.client.delete(self._delete_url(record), HTTP_ACCEPT="application/json")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(CareRecord.objects.filter(pk=record.pk).exists())

        still_in_db = CareRecord.all_objects.get(pk=record.pk)
        self.assertIsNotNone(still_in_db.deleted_at)
        self.assertEqual(still_in_db.deleted_by, self.owner)

    def test_future_scope_delete_soft_deletes_series_records(self):
        group_id = uuid.uuid4()
        base = self._record(what="Serie base")
        base.recurrence_group = group_id
        base.save(update_fields=["recurrence_group"])
        future = CareRecord.objects.create(
            patient=self.patient,
            caregiver="Cuidador",
            type=CareRecord.Type.OTHER,
            what="Serie futura",
            date=date.today() + timedelta(days=1),
            time=time(10, 0),
            created_by=self.owner,
            recurrence_group=group_id,
        )
        self.client.login(username="owner", password="pass1234")

        response = self.client.post(
            self._delete_url(base),
            {"scope": "future"},
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(CareRecord.objects.filter(pk=base.pk).exists())
        self.assertFalse(CareRecord.objects.filter(pk=future.pk).exists())

        base_in_db = CareRecord.all_objects.get(pk=base.pk)
        future_in_db = CareRecord.all_objects.get(pk=future.pk)
        self.assertIsNotNone(base_in_db.deleted_at)
        self.assertEqual(base_in_db.deleted_by, self.owner)
        self.assertIsNotNone(future_in_db.deleted_at)
        self.assertEqual(future_in_db.deleted_by, self.owner)

    def test_cancel_following_soft_deletes_base_and_future_series_records(self):
        group_id = uuid.uuid4()
        base = self._record(what="Serie base cancel")
        base.recurrence_group = group_id
        base.save(update_fields=["recurrence_group"])
        future = CareRecord.objects.create(
            patient=self.patient,
            caregiver="Cuidador",
            type=CareRecord.Type.OTHER,
            what="Serie futura cancel",
            date=date.today() + timedelta(days=1),
            time=time(10, 0),
            created_by=self.owner,
            recurrence_group=group_id,
        )
        self.client.login(username="owner", password="pass1234")

        response = self.client.post(
            reverse("care:record-cancel-following", args=[base.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(CareRecord.objects.filter(pk=base.pk).exists())
        self.assertFalse(CareRecord.objects.filter(pk=future.pk).exists())

        base_in_db = CareRecord.all_objects.get(pk=base.pk)
        future_in_db = CareRecord.all_objects.get(pk=future.pk)
        self.assertIsNotNone(base_in_db.deleted_at)
        self.assertEqual(base_in_db.deleted_by, self.owner)
        self.assertIsNotNone(future_in_db.deleted_at)
        self.assertEqual(future_in_db.deleted_by, self.owner)

    def test_cancel_following_without_series_soft_deletes_single_record(self):
        record = self._record(what="Sem serie cancel")
        self.client.login(username="owner", password="pass1234")

        response = self.client.post(
            reverse("care:record-cancel-following", args=[record.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(CareRecord.objects.filter(pk=record.pk).exists())

        still_in_db = CareRecord.all_objects.get(pk=record.pk)
        self.assertIsNotNone(still_in_db.deleted_at)
        self.assertEqual(still_in_db.deleted_by, self.owner)

    def test_export_pdf_and_docx_still_generate_after_deletion(self):
        deleted = self._record(what="Registro excluido")
        remaining = self._record(type_value=CareRecord.Type.MEAL, what="Almoco")
        self.client.login(username="owner", password="pass1234")
        self.client.delete(self._delete_url(deleted), HTTP_ACCEPT="application/json")

        rows = [
            {
                "date": remaining.date.isoformat(),
                "time": remaining.time.strftime("%H:%M"),
                "category": remaining.get_type_display(),
                "what": remaining.what,
                "description": remaining.description,
                "caregiver": remaining.caregiver,
                "patient": str(remaining.patient),
                "status": remaining.get_status_display(),
                "exception": "Nao",
            }
        ]
        meta = ExportMetadata(
            start=None,
            end=None,
            period_label="Todos os tempos",
            patient_name=str(self.patient),
            records_total=len(rows),
            record_types_label="Alimentacao",
        )

        pdf_response = export_as_pdf(rows, meta, columns=COLUMNS)
        docx_response = export_as_docx(rows, meta, columns=COLUMNS)

        self.assertEqual(pdf_response["Content-Type"], "application/pdf")
        self.assertEqual(
            docx_response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )


class SleepRecordExportLayoutTests(TestCase):
    def _sleep_rows(self):
        return [
            {
                "date": "2026-06-01",
                "time": "22:00",
                "category": "Sono",
                "what": "Dormiu",
                "description": "Adormeceu sem intercorrencias.",
                "caregiver": "Dra Ana",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "exception": "Nao",
            },
            {
                "date": "2026-06-02",
                "time": "06:30",
                "category": "Sono",
                "what": "Acordou",
                "description": "Acordou bem.",
                "caregiver": "Dra Ana",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "exception": "Nao",
            },
            {
                "date": "2026-06-02",
                "time": "14:00",
                "category": "Sono",
                "what": "Dormiu",
                "description": "Cochilo sem registro de despertar.",
                "caregiver": "Dra Ana",
                "patient": "Paciente Teste",
                "status": "Pendente",
                "exception": "Nao",
            },
        ]

    def _sleep_meta(self):
        return ExportMetadata(
            start=date(2026, 6, 1),
            end=date(2026, 6, 2),
            period_label="Periodo personalizado",
            patient_name="Paciente Teste",
            patient_identifier="ID interno: 1",
            records_total=3,
            group_name="Unidade Norte",
            record_types_label="Sono",
            professional_name="Dra Ana",
            unit_name="Unidade Norte",
        )

    def test_sleep_layout_consolidates_sessions_for_pdf_and_docx(self):
        layout = build_sleep_export_layout(self._sleep_rows(), self._sleep_meta())

        self.assertEqual(layout.title, "Relatório de Sono")
        self.assertEqual(layout.summary_cards[0], ("Média Horas Dormidas", "8,5 h"))
        self.assertEqual(layout.summary_cards[1], ("Períodos Completos", "1"))
        self.assertEqual(layout.summary_cards[2], ("Maior Duração", "8,5 h"))
        self.assertEqual(layout.summary_cards[3], ("Menor Duração", "8,5 h"))
        self.assertEqual(layout.start_count, 2)
        self.assertEqual(layout.end_count, 1)
        self.assertEqual(layout.total_count, 3)
        self.assertEqual(layout.history_rows[0]["duration"], "8h 30min")
        self.assertEqual(layout.history_rows[1]["duration"], "Registro incompleto")
        self.assertEqual(layout.history_rows[1]["status"], "PENDENTE")
        self.assertIn("Adormeceu sem intercorrencias.", layout.clinical_observations)

    def test_sleep_docx_uses_contextual_sleep_layout(self):
        response = export_as_docx(self._sleep_rows(), self._sleep_meta(), columns=COLUMNS)

        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        with zipfile.ZipFile(BytesIO(response.content)) as docx:
            document_xml = docx.read("word/document.xml").decode("utf-8")

        self.assertIn("Relatório de Sono", document_xml)
        self.assertIn("Resumo do Sono", document_xml)
        self.assertIn("Histórico Detalhado", document_xml)
        self.assertIn("Média Horas Dormidas", document_xml)
        self.assertIn("Períodos Completos", document_xml)
        self.assertIn("8h 30min", document_xml)
        self.assertIn("Registro incompleto", document_xml)
        self.assertIn("Resp: Dra Ana", document_xml)
        self.assertIn("Informações Técnicas", document_xml)

    def test_sleep_pdf_returns_pdf_with_sleep_filename(self):
        response = export_as_pdf(self._sleep_rows(), self._sleep_meta(), columns=COLUMNS)

        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-"))
        self.assertIn("registros_2026-06-01_2026-06-02_paciente-teste", response["Content-Disposition"])

    def test_non_sleep_docx_keeps_generic_export_layout(self):
        rows = [
            {
                "date": "2026-06-01",
                "time": "12:00",
                "category": "Outros",
                "what": "Almoco",
                "description": "Aceitou bem.",
                "caregiver": "Cuidador",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "exception": "Nao",
            }
        ]
        meta = ExportMetadata(
            start=None,
            end=None,
            period_label="Todos os tempos",
            patient_name="Paciente Teste",
            records_total=1,
            record_types_label="Outros",
        )

        response = export_as_docx(rows, meta, columns=COLUMNS)
        with zipfile.ZipFile(BytesIO(response.content)) as docx:
            document_xml = docx.read("word/document.xml").decode("utf-8")

        self.assertIn("Relatório de registros de cuidado", document_xml)
        self.assertNotIn("Resumo do Sono", document_xml)


class BathroomRecordExportLayoutTests(TestCase):
    def _bathroom_rows(self):
        return [
            {
                "date": "2026-06-01",
                "time": "08:00",
                "category": "Banheiro",
                "what": "Higienização oral",
                "description": "Realizada após o café.",
                "caregiver": "Enf Maria",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Diariamente",
                "exception": "Nao",
            },
            {
                "date": "2026-06-01",
                "time": "10:30",
                "category": "Banheiro",
                "what": "Urina",
                "description": "Volume habitual.",
                "caregiver": "Enf Maria",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Não se repete",
                "exception": "Nao",
            },
            {
                "date": "2026-06-01",
                "time": "11:00",
                "category": "Banheiro",
                "what": "Evacuação",
                "description": "Sem dor.",
                "caregiver": "Enf Maria",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Não se repete",
                "exception": "Nao",
            },
            {
                "date": "2026-06-01",
                "time": "12:15",
                "category": "Banheiro",
                "what": "Vômito",
                "description": "Episódio após almoço.\nAvisar equipe.",
                "caregiver": "Enf Maria",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Não se repete",
                "exception": "Sim",
            },
        ]

    def _bathroom_meta(self):
        return ExportMetadata(
            start=date(2026, 6, 1),
            end=date(2026, 6, 1),
            period_label="Periodo personalizado",
            patient_name="Paciente Teste",
            records_total=4,
            group_name="Unidade Norte",
            record_types_label="Banheiro",
            professional_name="Enf Maria",
            unit_name="Unidade Norte",
        )

    def test_bathroom_layout_calculates_summary_and_tags(self):
        layout = build_bathroom_export_layout(self._bathroom_rows(), self._bathroom_meta())

        self.assertEqual(layout.title, "Relatório de Banheiro e Higiene")
        self.assertEqual(layout.summary_cards[0], ("Total de Registros", "4"))
        self.assertEqual(layout.summary_cards[1], ("Higiene & Banho", "1"))
        self.assertEqual(layout.summary_cards[2], ("Eliminações (Urina/Evac.)", "2"))
        self.assertEqual(layout.summary_cards[3], ("Intercorrências (Vômito)", "1"))
        self.assertEqual(layout.history_rows[0]["tag_kind"], "hygiene")
        self.assertEqual(layout.history_rows[1]["tag_kind"], "elimination")
        self.assertEqual(layout.history_rows[3]["tag_kind"], "alert")

    def test_bathroom_docx_uses_bathroom_layout(self):
        response = export_as_docx(self._bathroom_rows(), self._bathroom_meta(), columns=COLUMNS)

        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        with zipfile.ZipFile(BytesIO(response.content)) as docx:
            document_xml = docx.read("word/document.xml").decode("utf-8")

        self.assertIn("Relatório de Banheiro e Higiene", document_xml)
        self.assertIn("Resumo das Ocorrências", document_xml)
        self.assertIn("Higiene &amp; Banho", document_xml)
        self.assertIn("Intercorrências (Vômito)", document_xml)
        self.assertIn("HIGIENIZAÇÃO ORAL", document_xml)
        self.assertIn("VÔMITO", document_xml)
        self.assertNotIn("Resumo do Sono", document_xml)

    def test_bathroom_pdf_returns_pdf_with_bathroom_layout(self):
        response = export_as_pdf(self._bathroom_rows(), self._bathroom_meta(), columns=COLUMNS)

        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-"))
        self.assertIn("registros_2026-06-01_2026-06-01_paciente-teste", response["Content-Disposition"])

    def test_non_bathroom_docx_keeps_existing_non_bathroom_layout(self):
        rows = [
            {
                "date": "2026-06-01",
                "time": "12:00",
                "category": "Outros",
                "what": "Almoco",
                "description": "Aceitou bem.",
                "caregiver": "Cuidador",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "exception": "Nao",
            }
        ]
        meta = ExportMetadata(
            start=None,
            end=None,
            period_label="Todos os tempos",
            patient_name="Paciente Teste",
            records_total=1,
            record_types_label="Outros",
        )

        response = export_as_docx(rows, meta, columns=COLUMNS)
        with zipfile.ZipFile(BytesIO(response.content)) as docx:
            document_xml = docx.read("word/document.xml").decode("utf-8")

        self.assertIn("Relatório de registros de cuidado", document_xml)
        self.assertNotIn("Relatório de Banheiro e Higiene", document_xml)


class VitalRecordExportLayoutTests(TestCase):
    def _vital_rows(self):
        return [
            {
                "date": "2026-06-15",
                "time": "08:00",
                "category": "Sinais Vitais",
                "what": "Pressão arterial (PA) • Normal",
                "description": "Medido em repouso.",
                "caregiver": "Enf Carla",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "3x ao dia",
                "exception": "Nao",
            },
            {
                "date": "2026-06-15",
                "time": "08:05",
                "category": "Sinais Vitais",
                "what": "Frequência cardíaca (FrC) • Taquicardia",
                "description": "Após caminhada leve.",
                "caregiver": "Enf Carla",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Contínua",
                "exception": "Nao",
            },
            {
                "date": "2026-06-15",
                "time": "11:15",
                "category": "Sinais Vitais",
                "what": "SpO2 (Oxímetro) • Baixa Saturação",
                "description": "91% em ar ambiente.\nIniciado protocolo.",
                "caregiver": "Enf Carla",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Sob demanda",
                "exception": "Sim",
            },
        ]

    def _vital_meta(self, total=3):
        return ExportMetadata(
            start=date(2026, 6, 15),
            end=date(2026, 6, 15),
            period_label="Periodo personalizado",
            patient_name="Paciente Teste",
            records_total=total,
            group_name="Unidade Norte",
            record_types_label="Sinais Vitais",
            professional_name="Enf Carla",
            unit_name="Unidade Norte",
        )

    def test_vital_layout_calculates_summary_and_status_levels(self):
        layout = build_vital_export_layout(self._vital_rows(), self._vital_meta())

        self.assertEqual(layout.title, "Relatório de Sinais Vitais")
        self.assertEqual(layout.summary_cards[0], ("Total Medições", "3", "main"))
        self.assertEqual(layout.summary_cards[1], ("Status Normal", "1", "normal"))
        self.assertEqual(layout.summary_cards[2], ("Atenção (Febre/Taquic.)", "1", "warning"))
        self.assertEqual(layout.summary_cards[3], ("Alerta Crítico", "1", "alert"))
        self.assertEqual(layout.history_rows[0]["status_level"], "normal")
        self.assertEqual(layout.history_rows[1]["status_level"], "warning")
        self.assertEqual(layout.history_rows[2]["status_level"], "alert")

    def test_vital_docx_uses_vital_layout(self):
        response = export_as_docx(self._vital_rows(), self._vital_meta(), columns=COLUMNS)

        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        with zipfile.ZipFile(BytesIO(response.content)) as docx:
            document_xml = docx.read("word/document.xml").decode("utf-8")

        self.assertIn("Relatório de Sinais Vitais", document_xml)
        self.assertIn("Resumo de Alertas Clínicos", document_xml)
        self.assertIn("Total Medições", document_xml)
        self.assertIn("STATUS CLÍNICO", document_xml)
        self.assertIn("BAIXA SATURAÇÃO", document_xml)
        self.assertIn("Informações Técnicas", document_xml)
        self.assertNotIn("Relatório de Banheiro e Higiene", document_xml)
        self.assertNotIn("Resumo do Sono", document_xml)

    def test_vital_pdf_returns_pdf_and_supports_many_rows(self):
        rows = self._vital_rows() * 18
        response = export_as_pdf(rows, self._vital_meta(total=len(rows)), columns=COLUMNS)

        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-"))
        self.assertIn("registros_2026-06-15_2026-06-15_paciente-teste", response["Content-Disposition"])

    def test_non_vital_docx_keeps_existing_non_vital_layout(self):
        rows = [
            {
                "date": "2026-06-01",
                "time": "12:00",
                "category": "Outros",
                "what": "Almoco",
                "description": "Aceitou bem.",
                "caregiver": "Cuidador",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "exception": "Nao",
            }
        ]
        meta = ExportMetadata(
            start=None,
            end=None,
            period_label="Todos os tempos",
            patient_name="Paciente Teste",
            records_total=1,
            record_types_label="Outros",
        )

        response = export_as_docx(rows, meta, columns=COLUMNS)
        with zipfile.ZipFile(BytesIO(response.content)) as docx:
            document_xml = docx.read("word/document.xml").decode("utf-8")

        self.assertIn("Relatório de registros de cuidado", document_xml)
        self.assertNotIn("Relatório de Sinais Vitais", document_xml)


class MedicationRecordExportLayoutTests(TestCase):
    def _medication_rows(self):
        return [
            {
                "date": "2026-06-15",
                "time": "06:00",
                "category": "Medicação",
                "created_date": "2026-06-15",
                "created_time": "06:01",
                "medication": "Omeprazol 20 mg",
                "medication_name": "Omeprazol",
                "dose": "20 mg",
                "quantity": "1",
                "quantity_unit": "Cápsulas",
                "description": "Administrado em jejum.",
                "caregiver": "Enf Paula",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Diária",
                "exception": "Não",
                "missed_reason": "",
            },
            {
                "date": "2026-06-15",
                "time": "08:00",
                "category": "Medicação",
                "created_date": "2026-06-15",
                "created_time": "08:01",
                "medication": "Losartana Potássica 50 mg",
                "medication_name": "Losartana Potássica",
                "dose": "50 mg",
                "quantity": "2",
                "quantity_unit": "Comprimidos",
                "description": "Sem reações adversas.",
                "caregiver": "Enf Paula",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "A cada 12h",
                "exception": "Não",
                "missed_reason": "",
            },
            {
                "date": "2026-06-15",
                "time": "12:00",
                "category": "Medicação",
                "created_date": "2026-06-15",
                "created_time": "12:01",
                "medication": "Dipirona Monoidratada 500 mg/mL",
                "medication_name": "Dipirona Monoidratada",
                "dose": "500 mg/mL",
                "quantity": "20",
                "quantity_unit": "Gotas",
                "description": "Diluído em água.",
                "caregiver": "Enf Paula",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Se necessário",
                "exception": "Não",
                "missed_reason": "",
            },
            {
                "date": "2026-06-15",
                "time": "18:00",
                "category": "Medicação",
                "created_date": "2026-06-15",
                "created_time": "18:01",
                "medication": "Vitamina D 2000 UI",
                "medication_name": "Vitamina D",
                "dose": "2000 UI",
                "quantity": "1",
                "quantity_unit": "Cápsulas",
                "description": "Recusa do paciente registrada.",
                "caregiver": "Enf Paula",
                "patient": "Paciente Teste",
                "status": "Não realizado",
                "recurrence": "Diária",
                "exception": "Sim",
                "missed_reason": "Recusa do paciente",
            },
        ]

    def _medication_meta(self, total=4):
        return ExportMetadata(
            start=date(2026, 6, 15),
            end=date(2026, 6, 15),
            period_label="Periodo personalizado",
            patient_name="Paciente Teste",
            records_total=total,
            group_name="Unidade Norte",
            record_types_label="Medicação",
            professional_name="Enf Paula",
            unit_name="Unidade Norte",
        )

    def test_medication_layout_calculates_summary_and_rows(self):
        layout = build_medication_export_layout(self._medication_rows(), self._medication_meta())

        self.assertEqual(layout.title, "Relatório de Medicação")
        self.assertEqual(layout.summary_cards[0], ("Total de Ministrações", "4", "main"))
        self.assertEqual(layout.summary_cards[1], ("Via Oral (Cápsulas)", "3", "blue"))
        self.assertEqual(layout.summary_cards[2], ("Via Oral (Gotas)", "1", "blue"))
        self.assertEqual(layout.summary_cards[3], ("Intercorrências / Recusas", "1", "neutral"))
        self.assertEqual(layout.history_rows[0]["medication_name"], "Omeprazol")
        self.assertEqual(layout.history_rows[0]["dose"], "20 mg")
        self.assertEqual(layout.history_rows[2]["quantity"], "20 Gotas")

    def test_medication_docx_uses_medication_layout(self):
        response = export_as_docx(self._medication_rows(), self._medication_meta(), columns=COLUMNS)

        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        with zipfile.ZipFile(BytesIO(response.content)) as docx:
            document_xml = docx.read("word/document.xml").decode("utf-8")

        self.assertIn("Relatório de Medicação", document_xml)
        self.assertIn("Resumo de Ministrações", document_xml)
        self.assertIn("Via Oral (Cápsulas)", document_xml)
        self.assertIn("Intercorrências / Recusas", document_xml)
        self.assertIn("Omeprazol", document_xml)
        self.assertIn("20 mg", document_xml)
        self.assertIn("20 Gotas", document_xml)
        self.assertNotIn("Relatório de Sinais Vitais", document_xml)
        self.assertNotIn("Relatório de Banheiro e Higiene", document_xml)
        self.assertNotIn("Resumo do Sono", document_xml)

    def test_medication_pdf_returns_pdf_and_supports_many_rows(self):
        rows = self._medication_rows() * 18
        response = export_as_pdf(rows, self._medication_meta(total=len(rows)), columns=COLUMNS)

        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-"))
        self.assertIn("registros_2026-06-15_2026-06-15_paciente-teste", response["Content-Disposition"])

    def test_non_medication_docx_keeps_existing_non_medication_layout(self):
        rows = [
            {
                "date": "2026-06-01",
                "time": "12:00",
                "category": "Outros",
                "what": "Almoco",
                "description": "Aceitou bem.",
                "caregiver": "Cuidador",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "exception": "Nao",
            }
        ]
        meta = ExportMetadata(
            start=None,
            end=None,
            period_label="Todos os tempos",
            patient_name="Paciente Teste",
            records_total=1,
            record_types_label="Outros",
        )

        response = export_as_docx(rows, meta, columns=COLUMNS)
        with zipfile.ZipFile(BytesIO(response.content)) as docx:
            document_xml = docx.read("word/document.xml").decode("utf-8")

        self.assertIn("Relatório de registros de cuidado", document_xml)
        self.assertNotIn("Relatório de Medicação", document_xml)


class ActivityRecordExportLayoutTests(TestCase):
    def _activity_rows(self):
        return [
            {
                "date": "2026-06-13",
                "time": "16:30",
                "category": "Atividade",
                "what": "Caminhada Leve",
                "description": "Realizada em ambiente plano.\nPaciente relatou leve cansaço ao final.",
                "caregiver": "Fisio Lara",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Diária",
                "exception": "Não",
                "missed_reason": "",
            },
            {
                "date": "2026-06-14",
                "time": "10:00",
                "category": "Atividade",
                "what": "Exercício de Fisioterapia Motora",
                "description": "Fortalecimento de quadríceps com caneleira leve.",
                "caregiver": "Fisio Lara",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "3x por semana",
                "exception": "Não",
                "missed_reason": "",
            },
            {
                "date": "2026-06-15",
                "time": "09:00",
                "category": "Atividade",
                "what": "Bicicleta Ergométrica",
                "description": "Boa tolerância ao esforço.",
                "caregiver": "Fisio Lara",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Semanalmente",
                "exception": "Não",
                "missed_reason": "",
            },
            {
                "date": "2026-06-15",
                "time": "16:00",
                "category": "Atividade",
                "what": "Alongamento Passivo",
                "description": "Atividade recusada por dor persistente.",
                "caregiver": "Fisio Lara",
                "patient": "Paciente Teste",
                "status": "Não realizado",
                "recurrence": "Diária",
                "exception": "Sim",
                "missed_reason": "Recusa do paciente",
            },
        ]

    def _activity_meta(self, total=4):
        return ExportMetadata(
            start=date(2026, 6, 13),
            end=date(2026, 6, 15),
            period_label="Periodo personalizado",
            patient_name="Paciente Teste",
            records_total=total,
            group_name="Unidade Norte",
            record_types_label="Atividade",
            professional_name="Fisio Lara",
            unit_name="Unidade Norte",
        )

    def test_activity_layout_calculates_summary_and_classifications(self):
        layout = build_activity_export_layout(self._activity_rows(), self._activity_meta())

        self.assertEqual(layout.title, "Relatório de Atividade Física")
        self.assertEqual(layout.summary_cards[0], ("Total de Exercícios", "4", "main"))
        self.assertEqual(layout.summary_cards[1], ("Cardiovascular", "2", "blue"))
        self.assertEqual(layout.summary_cards[2], ("Mobilidade/Alongamento", "2", "blue"))
        self.assertEqual(layout.summary_cards[3], ("Recusas ou Suspensões", "1", "neutral"))
        self.assertEqual(layout.history_rows[0]["activity_name"], "Caminhada Leve")
        self.assertIn("\n", layout.history_rows[0]["observation"])

    def test_activity_docx_uses_activity_layout(self):
        response = export_as_docx(self._activity_rows(), self._activity_meta(), columns=COLUMNS)

        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        with zipfile.ZipFile(BytesIO(response.content)) as docx:
            document_xml = docx.read("word/document.xml").decode("utf-8")

        self.assertIn("Relatório de Atividade Física", document_xml)
        self.assertIn("Resumo do Período", document_xml)
        self.assertIn("Total de Exercícios", document_xml)
        self.assertIn("Cardiovascular", document_xml)
        self.assertIn("Mobilidade/Alongamento", document_xml)
        self.assertIn("Recusas ou Suspensões", document_xml)
        self.assertIn("ATIVIDADE (NOME)", document_xml)
        self.assertIn("Caminhada Leve", document_xml)
        self.assertIn("Bicicleta Ergométrica", document_xml)
        self.assertIn("Informações Técnicas", document_xml)
        self.assertNotIn("Relatório de Sono", document_xml)
        self.assertNotIn("Relatório de Banheiro e Higiene", document_xml)
        self.assertNotIn("Relatório de Sinais Vitais", document_xml)
        self.assertNotIn("Relatório de Medicação", document_xml)

    def test_activity_pdf_returns_pdf_and_supports_many_rows(self):
        rows = self._activity_rows() * 18
        response = export_as_pdf(rows, self._activity_meta(total=len(rows)), columns=COLUMNS)

        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-"))
        self.assertIn("registros_2026-06-13_2026-06-15_paciente-teste", response["Content-Disposition"])

    def test_non_activity_docx_keeps_existing_non_activity_layout(self):
        rows = [
            {
                "date": "2026-06-01",
                "time": "22:00",
                "category": "Sono",
                "what": "Dormiu",
                "description": "Adormeceu bem.",
                "caregiver": "Cuidador",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "exception": "Não",
            }
        ]
        meta = ExportMetadata(
            start=None,
            end=None,
            period_label="Todos os tempos",
            patient_name="Paciente Teste",
            records_total=1,
            record_types_label="Sono",
        )

        response = export_as_docx(rows, meta, columns=COLUMNS)
        with zipfile.ZipFile(BytesIO(response.content)) as docx:
            document_xml = docx.read("word/document.xml").decode("utf-8")

        self.assertIn("Relatório de Sono", document_xml)
        self.assertNotIn("Relatório de Atividade Física", document_xml)


class MealRecordExportLayoutTests(TestCase):
    def _meal_rows(self):
        return [
            {
                "date": "2026-06-15",
                "time": "08:30",
                "category": "Alimentação",
                "what": "Café da manhã • Boa aceitação",
                "description": "Consumiu toda a porção de frutas.\nSem engasgos.",
                "caregiver": "Nutri Rosa",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Diária",
                "exception": "Não",
            },
            {
                "date": "2026-06-15",
                "time": "12:30",
                "category": "Alimentação",
                "what": "Almoço • Ruim aceitação",
                "description": "Ingeriu pouca quantidade da proteína.",
                "caregiver": "Nutri Rosa",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Diária",
                "exception": "Não",
            },
            {
                "date": "2026-06-15",
                "time": "16:00",
                "category": "Alimentação",
                "what": "Lanche da tarde • Boa aceitação",
                "description": "Aceitou bem o chá e a torrada.",
                "caregiver": "Nutri Rosa",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Diária",
                "exception": "Não",
            },
            {
                "date": "2026-06-15",
                "time": "19:30",
                "category": "Alimentação",
                "what": "Ceia da noite • Outro",
                "description": "Dieta ajustada pela família.",
                "caregiver": "Nutri Rosa",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Não se repete",
                "exception": "Não",
            },
        ]

    def _meal_meta(self, total=4):
        return ExportMetadata(
            start=date(2026, 6, 15),
            end=date(2026, 6, 15),
            period_label="Periodo personalizado",
            patient_name="Paciente Teste",
            records_total=total,
            group_name="Unidade Norte",
            record_types_label="Alimentação",
            professional_name="Nutri Rosa",
            unit_name="Unidade Norte",
        )

    def test_meal_layout_calculates_summary_and_acceptance_tags(self):
        layout = build_meal_export_layout(self._meal_rows(), self._meal_meta())

        self.assertEqual(layout.title, "Relatório de Alimentação")
        self.assertEqual(layout.summary_cards[0], ("Refeições Registradas", "4", "main"))
        self.assertEqual(layout.summary_cards[1], ("Boa Aceitação", "2", "good"))
        self.assertEqual(layout.summary_cards[2], ("Ruim Aceitação", "1", "poor"))
        self.assertEqual(layout.summary_cards[3], ("Outras Ocorrências", "1", "blue"))
        self.assertEqual(layout.history_rows[0]["meal_name"], "Café da manhã")
        self.assertEqual(layout.history_rows[0]["acceptance_kind"], "good")
        self.assertEqual(layout.history_rows[1]["acceptance_kind"], "poor")
        self.assertEqual(layout.history_rows[3]["acceptance_kind"], "other")
        self.assertIn("\n", layout.history_rows[0]["observation"])

    def test_meal_docx_uses_meal_layout_and_acceptance_tags(self):
        response = export_as_docx(self._meal_rows(), self._meal_meta(), columns=COLUMNS)

        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        with zipfile.ZipFile(BytesIO(response.content)) as docx:
            document_xml = docx.read("word/document.xml").decode("utf-8")

        self.assertIn("Relatório de Alimentação", document_xml)
        self.assertIn("Resumo Nutricional", document_xml)
        self.assertIn("Refeições Registradas", document_xml)
        self.assertIn("Boa Aceitação", document_xml)
        self.assertIn("Ruim Aceitação", document_xml)
        self.assertIn("Outras Ocorrências", document_xml)
        self.assertIn("ACEITAÇÃO", document_xml)
        self.assertIn("BOA ACEITAÇÃO", document_xml)
        self.assertIn("RUIM ACEITAÇÃO", document_xml)
        self.assertIn("OUTRO", document_xml)
        self.assertIn("Café da manhã", document_xml)
        self.assertIn("Informações Técnicas", document_xml)
        self.assertNotIn("Relatório de Atividade Física", document_xml)
        self.assertNotIn("Relatório de Sono", document_xml)
        self.assertNotIn("Relatório de Banheiro e Higiene", document_xml)
        self.assertNotIn("Relatório de Sinais Vitais", document_xml)
        self.assertNotIn("Relatório de Medicação", document_xml)

    def test_meal_pdf_returns_pdf_and_supports_many_rows(self):
        rows = self._meal_rows() * 18
        response = export_as_pdf(rows, self._meal_meta(total=len(rows)), columns=COLUMNS)

        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-"))
        self.assertIn("registros_2026-06-15_2026-06-15_paciente-teste", response["Content-Disposition"])

    def test_non_meal_docx_keeps_existing_non_meal_layout(self):
        rows = [
            {
                "date": "2026-06-15",
                "time": "09:00",
                "category": "Atividade",
                "what": "Caminhada Leve",
                "description": "Boa tolerância ao esforço.",
                "caregiver": "Cuidador",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Diária",
                "exception": "Não",
            }
        ]
        meta = ExportMetadata(
            start=None,
            end=None,
            period_label="Todos os tempos",
            patient_name="Paciente Teste",
            records_total=1,
            record_types_label="Atividade",
        )

        response = export_as_docx(rows, meta, columns=COLUMNS)
        with zipfile.ZipFile(BytesIO(response.content)) as docx:
            document_xml = docx.read("word/document.xml").decode("utf-8")

        self.assertIn("Relatório de Atividade Física", document_xml)
        self.assertNotIn("Relatório de Alimentação", document_xml)


class ProgressRecordExportLayoutTests(TestCase):
    def _progress_rows(self):
        return [
            {
                "date": "2026-06-14",
                "time": "18:00",
                "category": "Evolução/Regressão",
                "what": "",
                "description": "Melhora significativa na interação social.\nRespondeu aos estímulos cognitivos.",
                "caregiver": "Terapeuta Lia",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Sob demanda",
                "exception": "Não",
                "progress_trend": "Evolução",
            },
            {
                "date": "2026-06-15",
                "time": "10:00",
                "category": "Evolução/Regressão",
                "what": "",
                "description": "Realizou higiene oral sem auxílio do cuidador.",
                "caregiver": "Terapeuta Lia",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Sob demanda",
                "exception": "Não",
                "progress_trend": "Evolução",
            },
            {
                "date": "2026-06-15",
                "time": "15:30",
                "category": "Evolução/Regressão",
                "what": "",
                "description": "Desorientação têmporo-espacial durante a tarde.",
                "caregiver": "Terapeuta Lia",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Esporádica",
                "exception": "Sim",
                "progress_trend": "Regressão",
            },
            {
                "date": "2026-06-16",
                "time": "09:10",
                "category": "Evolução/Regressão",
                "what": "",
                "description": "Observação clínica sem classificação conclusiva.",
                "caregiver": "Terapeuta Lia",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Não se repete",
                "exception": "Não",
                "progress_trend": "Outro",
            },
        ]

    def _progress_meta(self, total=4):
        return ExportMetadata(
            start=date(2026, 6, 14),
            end=date(2026, 6, 16),
            period_label="Periodo personalizado",
            patient_name="Paciente Teste",
            records_total=total,
            group_name="Unidade Norte",
            record_types_label="Evolução/Regressão",
            professional_name="Terapeuta Lia",
            unit_name="Unidade Norte",
        )

    def test_progress_layout_calculates_summary_and_classification_tags(self):
        layout = build_progress_export_layout(self._progress_rows(), self._progress_meta())

        self.assertEqual(layout.title, "Relatório de Evolução / Regressão")
        self.assertEqual(layout.summary_cards[0], ("Total de Registros", "4", "main"))
        self.assertEqual(layout.summary_cards[1], ("Eventos de Evolução", "2", "evolution"))
        self.assertEqual(layout.summary_cards[2], ("Eventos de Regressão", "1", "regression"))
        self.assertEqual(layout.summary_cards[3], ("Outras Ocorrências", "1", "neutral"))
        self.assertEqual(layout.history_rows[0]["classification_kind"], "evolution")
        self.assertEqual(layout.history_rows[2]["classification_kind"], "regression")
        self.assertEqual(layout.history_rows[3]["classification_kind"], "other")
        self.assertIn("\n", layout.history_rows[0]["observation"])

    def test_progress_docx_uses_progress_layout_and_tags(self):
        response = export_as_docx(self._progress_rows(), self._progress_meta(), columns=COLUMNS)

        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        with zipfile.ZipFile(BytesIO(response.content)) as docx:
            document_xml = docx.read("word/document.xml").decode("utf-8")

        self.assertIn("Relatório de Evolução / Regressão", document_xml)
        self.assertIn("Resumo de Quadros Observados", document_xml)
        self.assertIn("Eventos de Evolução", document_xml)
        self.assertIn("Eventos de Regressão", document_xml)
        self.assertIn("Outras Ocorrências", document_xml)
        self.assertIn("CLASSIFICAÇÃO", document_xml)
        self.assertIn("EVOLUÇÃO", document_xml)
        self.assertIn("REGRESSÃO", document_xml)
        self.assertIn("OUTRO", document_xml)
        self.assertIn("OBSERVAÇÕES / NOTAS CLÍNICAS", document_xml)
        self.assertIn("Informações Técnicas", document_xml)
        self.assertNotIn("Relatório de Alimentação", document_xml)
        self.assertNotIn("Relatório de Atividade Física", document_xml)
        self.assertNotIn("Relatório de Sono", document_xml)
        self.assertNotIn("Relatório de Banheiro e Higiene", document_xml)
        self.assertNotIn("Relatório de Sinais Vitais", document_xml)
        self.assertNotIn("Relatório de Medicação", document_xml)

    def test_progress_pdf_returns_pdf_and_supports_many_rows(self):
        rows = self._progress_rows() * 18
        response = export_as_pdf(rows, self._progress_meta(total=len(rows)), columns=COLUMNS)

        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-"))
        self.assertIn("registros_2026-06-14_2026-06-16_paciente-teste", response["Content-Disposition"])

    def test_non_progress_docx_keeps_existing_non_progress_layout(self):
        rows = [
            {
                "date": "2026-06-15",
                "time": "08:30",
                "category": "Alimentação",
                "what": "Café da manhã • Boa aceitação",
                "description": "Consumiu toda a porção.",
                "caregiver": "Cuidador",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Diária",
                "exception": "Não",
            }
        ]
        meta = ExportMetadata(
            start=None,
            end=None,
            period_label="Todos os tempos",
            patient_name="Paciente Teste",
            records_total=1,
            record_types_label="Alimentação",
        )

        response = export_as_docx(rows, meta, columns=COLUMNS)
        with zipfile.ZipFile(BytesIO(response.content)) as docx:
            document_xml = docx.read("word/document.xml").decode("utf-8")

        self.assertIn("Relatório de Alimentação", document_xml)
        self.assertNotIn("Relatório de Evolução / Regressão", document_xml)


class ConsolidatedRecordExportTests(TestCase):
    def _meta(self, labels="Sono, Atividade"):
        return ExportMetadata(
            start=date(2026, 6, 14),
            end=date(2026, 6, 16),
            period_label="Periodo personalizado",
            patient_name="Paciente Teste",
            records_total=0,
            group_name="Unidade Norte",
            record_types_label=labels,
            professional_name="Equipe Integrada",
            unit_name="Unidade Norte",
        )

    def _section(self, type_value, label, rows, columns=COLUMNS):
        return ConsolidatedExportSection(
            type_value=type_value,
            label=label,
            rows=rows,
            columns=columns,
        )

    def _sleep_rows(self):
        return [
            {
                "date": "2026-06-14",
                "time": "22:00",
                "category": "Sono",
                "what": "Dormiu",
                "description": "Adormeceu bem.",
                "caregiver": "Equipe Integrada",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "exception": "Não",
            },
            {
                "date": "2026-06-15",
                "time": "06:00",
                "category": "Sono",
                "what": "Acordou",
                "description": "Acordou orientado.",
                "caregiver": "Equipe Integrada",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "exception": "Não",
            },
        ]

    def _activity_rows(self):
        return [
            {
                "date": "2026-06-15",
                "time": "09:00",
                "category": "Atividade",
                "what": "Caminhada Leve",
                "description": "Boa tolerância ao esforço.",
                "caregiver": "Equipe Integrada",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Diária",
                "exception": "Não",
                "missed_reason": "",
            }
        ]

    def _bathroom_rows(self):
        return [
            {
                "date": "2026-06-15",
                "time": "10:30",
                "category": "Banheiro",
                "what": "Urina",
                "description": "Volume habitual.",
                "caregiver": "Equipe Integrada",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Não se repete",
                "exception": "Não",
            }
        ]

    def _vital_rows(self):
        return [
            {
                "date": "2026-06-15",
                "time": "08:00",
                "category": "Sinais Vitais",
                "what": "Pressão arterial (PA) • Normal",
                "description": "Medido em repouso.",
                "caregiver": "Equipe Integrada",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Sob demanda",
                "exception": "Não",
            }
        ]

    def _medication_rows(self):
        return [
            {
                "date": "2026-06-15",
                "time": "08:00",
                "category": "Medicação",
                "created_date": "2026-06-15",
                "created_time": "08:01",
                "medication": "Losartana 50 mg",
                "medication_name": "Losartana",
                "dose": "50 mg",
                "quantity": "1",
                "quantity_unit": "Comprimidos",
                "description": "Sem intercorrências.",
                "caregiver": "Equipe Integrada",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Diária",
                "exception": "Não",
                "missed_reason": "",
            }
        ]

    def _meal_rows(self):
        return [
            {
                "date": "2026-06-15",
                "time": "12:30",
                "category": "Alimentação",
                "what": "Almoço • Boa aceitação",
                "description": "Aceitou bem.",
                "caregiver": "Equipe Integrada",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Diária",
                "exception": "Não",
            }
        ]

    def _progress_rows(self):
        return [
            {
                "date": "2026-06-15",
                "time": "15:30",
                "category": "Evolução/Regressão",
                "what": "",
                "description": "Melhora de autonomia.",
                "caregiver": "Equipe Integrada",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "recurrence": "Sob demanda",
                "exception": "Não",
                "progress_trend": "Evolução",
            }
        ]

    def test_consolidated_docx_with_two_types_keeps_each_section_layout(self):
        sections = [
            self._section("sleep", "Sono", self._sleep_rows()),
            self._section("activity", "Atividade", self._activity_rows()),
        ]
        meta = self._meta(labels="Sono, Atividade")
        meta.records_total = sum(len(section.rows) for section in sections)

        response = export_consolidated_as_docx(sections, meta)

        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        with zipfile.ZipFile(BytesIO(response.content)) as docx:
            document_xml = docx.read("word/document.xml").decode("utf-8")

        self.assertEqual(document_xml.count("Relatório Consolidado de Cuidados"), 1)
        self.assertIn("Resumo Geral da Exportação", document_xml)
        self.assertIn("Sono", document_xml)
        self.assertIn("Resumo do Sono", document_xml)
        self.assertIn("Atividade Física", document_xml)
        self.assertIn("Resumo do Período", document_xml)
        self.assertIn("Caminhada Leve", document_xml)
        self.assertIn('w:type="page"', document_xml)
        self.assertNotIn("Relatório de Atividade Física", document_xml)

    def test_consolidated_pdf_with_three_types_returns_pdf(self):
        sections = [
            self._section("medication", "Medicação", self._medication_rows(), MEDICATION_COLUMNS),
            self._section("vital", "Sinais Vitais", self._vital_rows()),
            self._section("progress", "Evolução/Regressão", self._progress_rows()),
        ]
        meta = self._meta(labels="Medicação, Sinais Vitais, Evolução/Regressão")
        meta.records_total = sum(len(section.rows) for section in sections)

        response = export_consolidated_as_pdf(sections, meta)

        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-"))
        self.assertIn("registros_2026-06-14_2026-06-16_paciente-teste", response["Content-Disposition"])

    def test_consolidated_docx_with_all_types_and_empty_section(self):
        sections = [
            self._section("sleep", "Sono", self._sleep_rows()),
            self._section("bathroom", "Banheiro", self._bathroom_rows()),
            self._section("vital", "Sinais Vitais", self._vital_rows()),
            self._section("medication", "Medicação", self._medication_rows(), MEDICATION_COLUMNS),
            self._section("activity", "Atividade", self._activity_rows()),
            self._section("meal", "Alimentação", self._meal_rows()),
            self._section("progress", "Evolução/Regressão", self._progress_rows()),
            self._section("other", "Outros", []),
        ]
        meta = self._meta(labels="Sono, Banheiro, Sinais Vitais, Medicação, Atividade, Alimentação, Evolução/Regressão, Outros")
        meta.records_total = sum(len(section.rows) for section in sections)

        response = export_consolidated_as_docx(sections, meta)

        with zipfile.ZipFile(BytesIO(response.content)) as docx:
            document_xml = docx.read("word/document.xml").decode("utf-8")

        self.assertIn("Banheiro e Higiene", document_xml)
        self.assertIn("Sinais Vitais", document_xml)
        self.assertIn("Medicação", document_xml)
        self.assertIn("Alimentação", document_xml)
        self.assertIn("Evolução / Regressão", document_xml)
        self.assertIn("Outros", document_xml)
        self.assertIn("Nenhum registro encontrado para outros no período analisado.", document_xml)
        self.assertIn("BOA ACEITAÇÃO", document_xml)
        self.assertIn("EVOLUÇÃO", document_xml)


class DailyCaregiverReportTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user("ana", password="pass")
        self.bruno = User.objects.create_user("bruno", password="pass")
        self.viewer = User.objects.create_user("viewer", password="pass")

        self.ana.profile.full_name = "Ana Responsavel"
        self.ana.profile.save(update_fields=["full_name"])
        self.bruno.profile.full_name = "Bruno Auditor"
        self.bruno.profile.save(update_fields=["full_name"])
        self.viewer.profile.full_name = "Pessoa Visualizadora"
        self.viewer.profile.save(update_fields=["full_name"])

        self.patient = Patient.objects.create(name="Paciente Relatorio")
        self.group = CareGroup.objects.create(name="Grupo Relatorio", patient=self.patient)
        GroupMembership.objects.create(
            user=self.ana, group=self.group, relation_to_patient="CAREGIVER"
        )
        GroupMembership.objects.create(
            user=self.bruno, group=self.group, relation_to_patient="CAREGIVER"
        )
        GroupMembership.objects.create(
            user=self.viewer, group=self.group, relation_to_patient="FAMILY"
        )
        self.day = date(2026, 6, 1)
        self.client.force_login(self.viewer)

    def _url(self, **params):
        url = reverse("care:daily-caregiver-report")
        if not params:
            return url
        query = "&".join(f"{key}={value}" for key, value in params.items())
        return f"{url}?{query}"

    def _record(self, *, assigned_to, caregiver="Bruno Auditor", created_by=None, what="Banho assistido", status=None):
        return CareRecord.objects.create(
            patient=self.patient,
            caregiver=caregiver,
            type=CareRecord.Type.ACTIVITY,
            what=what,
            description="Observacao do registro",
            date=self.day,
            time=time(9, 0),
            assigned_to=assigned_to,
            created_by=created_by if created_by is not None else self.bruno,
            status=status or CareRecord.Status.PENDING,
        )

    def test_report_groups_records_by_assigned_to(self):
        self._record(assigned_to=self.ana, what="Atividade da Ana")
        self._record(assigned_to=self.bruno, caregiver="Ana Responsavel", created_by=self.ana, what="Atividade do Bruno")

        response = self.client.get(self._url(date=self.day.isoformat()))

        self.assertEqual(response.status_code, 200)
        section_titles = [section["title"] for section in response.context["sections"]]
        self.assertEqual(section_titles, ["Ana Responsavel", "Bruno Auditor"])

    def test_report_does_not_use_caregiver_as_responsible(self):
        self._record(
            assigned_to=self.ana,
            caregiver="Bruno Auditor",
            created_by=self.bruno,
            what="Medicacao atribuida a Ana",
            status=CareRecord.Status.DONE,
        )

        response = self.client.get(self._url(date=self.day.isoformat()))

        section = response.context["sections"][0]
        item = section["records"][0]
        self.assertEqual(section["title"], "Ana Responsavel")
        self.assertEqual(item["assigned_name"], "Ana Responsavel")
        self.assertEqual(item["author_name"], "Bruno Auditor")

    def test_filter_by_assigned_caregiver_works(self):
        self._record(
            assigned_to=self.ana,
            caregiver="Bruno Auditor",
            created_by=self.bruno,
            what="Mostrar para Ana",
        )
        self._record(
            assigned_to=self.bruno,
            caregiver="Ana Responsavel",
            created_by=self.ana,
            what="Nao mostrar pelo caregiver Ana",
        )

        response = self.client.get(self._url(date=self.day.isoformat(), caregiver=self.ana.pk))
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mostrar para Ana")
        self.assertNotIn("Nao mostrar pelo caregiver Ana", content)
        self.assertEqual([section["title"] for section in response.context["sections"]], ["Ana Responsavel"])

    def test_unassigned_records_appear_in_separate_section(self):
        self._record(assigned_to=None, what="Sem responsavel definido")

        response = self.client.get(self._url(date=self.day.isoformat()))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["sections"][0]["title"], "Sem cuidador atribuído")
        self.assertContains(response, "Sem cuidador atribuído")

    def test_csv_uses_assigned_to_and_author_columns(self):
        self._record(
            assigned_to=self.ana,
            caregiver="Bruno Auditor",
            created_by=self.bruno,
            what="Medicacao atribuida a Ana",
            status=CareRecord.Status.DONE,
        )

        response = self.client.get(self._url(date=self.day.isoformat(), format="csv"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
        rows = list(csv.DictReader(StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(rows[0]["Cuidador atribuído"], "Ana Responsavel")
        self.assertEqual(rows[0]["Registrado/Concluído por"], "Bruno Auditor")
        self.assertEqual(rows[0]["O que"], "Medicacao atribuida a Ana")


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class WebBulkMissedNotificationTests(TestCase):
    """Endpoint web (care:record-bulk-set-status) também deve notificar em lote.

    Cobre o mesmo cenário de BulkMissedNotificationTests (em
    api/tests/test_signals.py), mas para o fluxo web, que reimplementa a
    marcação em lote via QuerySet.update separadamente do endpoint da API.
    """

    def setUp(self):
        self.user1 = User.objects.create_user("alice", password="pass")
        self.user2 = User.objects.create_user("bob", password="pass")
        self.patient = Patient.objects.create(name="Vovó")
        self.group = CareGroup.objects.create(name="Família", patient=self.patient)
        GroupMembership.objects.create(
            user=self.user1, group=self.group, relation_to_patient="FAMILY"
        )
        GroupMembership.objects.create(
            user=self.user2, group=self.group, relation_to_patient="CAREGIVER"
        )
        self.client.force_login(self.user1)

    def _pending(self):
        return CareRecord.objects.create(
            patient=self.patient, type="medication", what="Remédio",
            date=date(2026, 6, 1), time=time(9, 0),
            caregiver="Cuidador", status=CareRecord.Status.PENDING,
        )

    @patch("api.services.push.send_push")
    def test_bulk_missed_notifies_each_record(self, mock_send):
        r1 = self._pending()
        r2 = self._pending()

        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post(
                reverse("care:record-bulk-set-status"),
                {"ids": f"{r1.id},{r2.id}", "status": "missed"},
            )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(mock_send.call_count, 2)
        r1.refresh_from_db()
        self.assertEqual(r1.status, CareRecord.Status.MISSED)

    @patch("api.services.push.send_push")
    def test_bulk_missed_skips_already_missed(self, mock_send):
        already = self._pending()
        already.status = CareRecord.Status.MISSED
        already.save(update_fields=["status"])
        mock_send.reset_mock()

        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post(
                reverse("care:record-bulk-set-status"),
                {"ids": str(already.id), "status": "missed"},
            )

        self.assertEqual(resp.status_code, 200)
        mock_send.assert_not_called()


class CanEditRecordTests(TestCase):
    """Testa a regra única de elegibilidade de edição em care.utils.can_edit_record.

    Regra: um CareRecord "anterior" (date/time já passados) só pode ser
    editado por um record-admin (superuser, staff ou Profile.role == ADMIN).
    Registros não-anteriores (hoje com horário futuro, ou data futura) podem
    ser editados pelo próprio criador comum.
    """

    def setUp(self):
        self.owner = User.objects.create_user(username="owner_edit", password="pass1234")
        self.superuser = User.objects.create_user(
            username="super_edit", password="pass1234", is_superuser=True
        )
        self.staff = User.objects.create_user(
            username="staff_edit", password="pass1234", is_staff=True
        )
        self.profile_admin = User.objects.create_user(
            username="profile_admin_edit", password="pass1234"
        )
        self.profile_admin.profile.role = "ADMIN"
        self.profile_admin.profile.save(update_fields=["role"])

        self.patient = Patient.objects.create(name="Paciente CanEdit")

        self.today = timezone.localdate()
        self.now_time = timezone.localtime().time()

    def _record(self, *, record_date, record_time, created_by=None):
        return CareRecord.objects.create(
            patient=self.patient,
            caregiver="Cuidador",
            type=CareRecord.Type.OTHER,
            what="Registro",
            date=record_date,
            time=record_time,
            created_by=created_by or self.owner,
        )

    def _past_time(self):
        # horário anterior a "agora" no mesmo dia, evitando cruzar a meia-noite
        combined = dt_datetime.combine(self.today, self.now_time)
        past = combined - timedelta(hours=1)
        if past.date() != self.today:
            # se "agora" é muito cedo, usa o começo do dia
            return time(0, 0)
        return past.time()

    def _future_time(self):
        combined = dt_datetime.combine(self.today, self.now_time)
        future = combined + timedelta(hours=1)
        if future.date() != self.today:
            return time(23, 59)
        return future.time()

    # (a) registro passado + usuário criador comum -> False
    def test_past_date_common_creator_cannot_edit(self):
        record = self._record(
            record_date=self.today - timedelta(days=1),
            record_time=time(10, 0),
            created_by=self.owner,
        )

        self.assertFalse(can_edit_record(self.owner, record))

    def test_today_past_time_common_creator_cannot_edit(self):
        record = self._record(
            record_date=self.today,
            record_time=self._past_time(),
            created_by=self.owner,
        )

        self.assertFalse(can_edit_record(self.owner, record))

    # (b) registro futuro (hoje c/ horário futuro, ou data futura) + criador comum -> True
    def test_today_future_time_common_creator_can_edit(self):
        record = self._record(
            record_date=self.today,
            record_time=self._future_time(),
            created_by=self.owner,
        )

        self.assertTrue(can_edit_record(self.owner, record))

    def test_future_date_common_creator_can_edit(self):
        record = self._record(
            record_date=self.today + timedelta(days=1),
            record_time=time(10, 0),
            created_by=self.owner,
        )

        self.assertTrue(can_edit_record(self.owner, record))

    # (b.1) registro de hoje sem horario definido (time=None) + criador comum -> True
    # Regressao: `record.time < timezone.localtime().time()` quebrava com
    # TypeError quando time=None, derrubando (HTTP 500) qualquer tela que
    # calculasse can_edit para um registro de hoje sem horario agendado.
    def test_today_none_time_common_creator_can_edit(self):
        record = self._record(
            record_date=self.today,
            record_time=None,
            created_by=self.owner,
        )

        self.assertTrue(can_edit_record(self.owner, record))

    # (c) registro passado + staff/superuser/profile-admin -> True
    def test_past_record_superuser_can_edit(self):
        record = self._record(
            record_date=self.today - timedelta(days=1),
            record_time=time(10, 0),
            created_by=self.owner,
        )

        self.assertTrue(can_edit_record(self.superuser, record))

    def test_past_record_staff_can_edit(self):
        record = self._record(
            record_date=self.today - timedelta(days=1),
            record_time=time(10, 0),
            created_by=self.owner,
        )

        self.assertTrue(can_edit_record(self.staff, record))

    def test_past_record_profile_admin_can_edit(self):
        record = self._record(
            record_date=self.today - timedelta(days=1),
            record_time=time(10, 0),
            created_by=self.owner,
        )

        self.assertTrue(can_edit_record(self.profile_admin, record))


class RecordUpdateViewPermissionTests(TestCase):
    """Testa que a view server-rendered RecordUpdate (care:record-update)
    respeita a mesma regra de care.utils.can_edit_record: um registro
    "anterior" (date/time já passados) não pode ser editado via POST pelo
    próprio criador comum, mesmo que ele seja o dono do registro.
    """

    def setUp(self):
        self.owner = User.objects.create_user(username="owner_update", password="pass1234")
        self.patient = Patient.objects.create(name="Paciente RecordUpdate")
        self.group = CareGroup.objects.create(name="Grupo RecordUpdate", patient=self.patient)
        GroupMembership.objects.create(
            user=self.owner, group=self.group, relation_to_patient="FAMILY"
        )

        self.today = timezone.localdate()
        self.now_time = timezone.localtime().time()

    def _record(self, *, record_date, record_time, what="Registro original"):
        return CareRecord.objects.create(
            patient=self.patient,
            caregiver="Cuidador",
            type=CareRecord.Type.OTHER,
            what=what,
            date=record_date,
            time=record_time,
            created_by=self.owner,
        )

    def _past_time(self):
        combined = dt_datetime.combine(self.today, self.now_time)
        past = combined - timedelta(hours=1)
        if past.date() != self.today:
            return time(0, 0)
        return past.time()

    def _future_time(self):
        combined = dt_datetime.combine(self.today, self.now_time)
        future = combined + timedelta(hours=1)
        if future.date() != self.today:
            return time(23, 59)
        return future.time()

    def _update_url(self, record):
        return reverse("care:record-update", args=[record.pk])

    def _payload(self, record, *, what):
        return {
            "patient": str(record.patient_id),
            "type": CareRecord.Type.OTHER,
            "what": what,
            "description": "",
            "missed_reason": "",
            "date": record.date.isoformat(),
            "time": record.time.strftime("%H:%M"),
            "recurrence": CareRecord.Recurrence.NONE,
        }

    def test_cannot_edit_past_record_via_post(self):
        record = self._record(
            record_date=self.today - timedelta(days=1),
            record_time=time(10, 0),
            what="Registro passado original",
        )
        self.client.login(username="owner_update", password="pass1234")

        response = self.client.post(
            self._update_url(record),
            self._payload(record, what="Tentativa de edicao indevida"),
        )

        self.assertNotEqual(response.status_code, 200)
        record.refresh_from_db()
        self.assertEqual(record.what, "Registro passado original")

    def test_cannot_edit_today_past_time_record_via_post(self):
        record = self._record(
            record_date=self.today,
            record_time=self._past_time(),
            what="Registro de hoje ja passado",
        )
        self.client.login(username="owner_update", password="pass1234")

        response = self.client.post(
            self._update_url(record),
            self._payload(record, what="Tentativa de edicao indevida"),
        )

        self.assertNotEqual(response.status_code, 200)
        record.refresh_from_db()
        self.assertEqual(record.what, "Registro de hoje ja passado")

    def test_cannot_get_edit_form_for_past_record(self):
        record = self._record(
            record_date=self.today - timedelta(days=1),
            record_time=time(10, 0),
        )
        self.client.login(username="owner_update", password="pass1234")

        response = self.client.get(self._update_url(record))

        self.assertIn(response.status_code, (403, 404))

    def test_can_edit_today_future_time_record_via_post_regression(self):
        record = self._record(
            record_date=self.today,
            record_time=self._future_time(),
            what="Registro futuro original",
        )
        self.client.login(username="owner_update", password="pass1234")

        response = self.client.post(
            self._update_url(record),
            self._payload(record, what="Edicao valida"),
        )

        self.assertEqual(response.status_code, 302)
        record.refresh_from_db()
        self.assertEqual(record.what, "Edicao valida")

    def test_can_edit_future_date_record_via_post_regression(self):
        record = self._record(
            record_date=self.today + timedelta(days=1),
            record_time=time(10, 0),
            what="Registro futuro original",
        )
        self.client.login(username="owner_update", password="pass1234")

        response = self.client.post(
            self._update_url(record),
            self._payload(record, what="Edicao valida"),
        )

        self.assertEqual(response.status_code, 302)
        record.refresh_from_db()
        self.assertEqual(record.what, "Edicao valida")


class RecordListEditLinkVisibilityTests(TestCase):
    """Testa que a tela server-rendered de listagem/historico (care:record-list)
    so exibe o link/botao 'Editar' quando care.utils.can_edit_record permite a
    edicao do registro pelo usuario autenticado.

    Hoje o template exibe 'Editar' para qualquer registro do dono (ou
    superuser), independente do registro ser "anterior" (bloqueado no
    backend pela subtask 2). Isso gera UX inconsistente: o usuario clica em
    Editar e recebe erro/403. Estes testes devem falhar contra o codigo
    atual ate que o contexto da view inclua um flag por registro (ex.
    'can_edit') e o template condicione a exibicao do link a esse flag.
    """

    def setUp(self):
        self.owner = User.objects.create_user(username="owner_list", password="pass1234")
        self.patient = Patient.objects.create(name="Paciente RecordList")
        self.group = CareGroup.objects.create(name="Grupo RecordList", patient=self.patient)
        GroupMembership.objects.create(
            user=self.owner, group=self.group, relation_to_patient="FAMILY"
        )

        self.today = timezone.localdate()
        self.now_time = timezone.localtime().time()

    def _record(self, *, record_date, record_time, what):
        return CareRecord.objects.create(
            patient=self.patient,
            caregiver="Cuidador",
            type=CareRecord.Type.OTHER,
            what=what,
            date=record_date,
            time=record_time,
            created_by=self.owner,
        )

    def _past_time(self):
        combined = dt_datetime.combine(self.today, self.now_time)
        past = combined - timedelta(hours=1)
        if past.date() != self.today:
            return time(0, 0)
        return past.time()

    def _future_time(self):
        combined = dt_datetime.combine(self.today, self.now_time)
        future = combined + timedelta(hours=1)
        if future.date() != self.today:
            return time(23, 59)
        return future.time()

    def _edit_url(self, record):
        return reverse("care:record-update", args=[record.pk])

    def test_edit_link_hidden_for_past_record_shown_for_future_record(self):
        """Registro anterior (bloqueado) nao deve exibir link de Editar; registro
        futuro do mesmo dono deve exibir o link normalmente."""
        past_record = self._record(
            record_date=self.today - timedelta(days=1),
            record_time=time(10, 0),
            what="Registro anterior",
        )
        future_record = self._record(
            record_date=self.today + timedelta(days=1),
            record_time=time(10, 0),
            what="Registro futuro",
        )

        self.client.login(username="owner_list", password="pass1234")
        response = self.client.get(reverse("care:record-list"))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()

        past_edit_url = self._edit_url(past_record)
        future_edit_url = self._edit_url(future_record)

        self.assertNotIn(
            past_edit_url, html,
            "Link de Editar nao deveria aparecer para um registro anterior "
            "(edicao bloqueada no backend)."
        )
        self.assertIn(
            future_edit_url, html,
            "Link de Editar deveria aparecer para um registro futuro editavel."
        )

    def test_edit_link_hidden_for_today_past_time_record(self):
        """Registro de hoje com horario ja passado tambem conta como
        'anterior' e nao deve exibir o link de Editar."""
        record = self._record(
            record_date=self.today,
            record_time=self._past_time(),
            what="Registro de hoje ja passado",
        )

        self.client.login(username="owner_list", password="pass1234")
        response = self.client.get(reverse("care:record-list"))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()

        self.assertNotIn(self._edit_url(record), html)

    def test_edit_link_shown_for_today_future_time_record(self):
        """Registro de hoje com horario futuro continua editavel e deve
        exibir o link de Editar."""
        record = self._record(
            record_date=self.today,
            record_time=self._future_time(),
            what="Registro de hoje ainda nao chegou",
        )

        self.client.login(username="owner_list", password="pass1234")
        response = self.client.get(reverse("care:record-list"))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()

        self.assertIn(self._edit_url(record), html)

    def test_edit_link_shown_for_today_none_time_record(self):
        """Registro de hoje sem horario definido (time=None) nao pode ser
        tratado como "ja passado": a view precisa exibir a listagem (sem
        estourar 500) e mostrar o link de Editar normalmente.

        Regressao: care.utils.can_edit_record comparava record.time
        diretamente com a hora atual sem checar None, e essa view calcula
        can_edit para cada registro da listagem (care/views.py RecordList).
        """
        record = self._record(
            record_date=self.today,
            record_time=None,
            what="Registro de hoje sem horario",
        )

        self.client.login(username="owner_list", password="pass1234")
        response = self.client.get(reverse("care:record-list"))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()

        self.assertIn(self._edit_url(record), html)

    def test_context_records_expose_can_edit_flag(self):
        """A view deve anexar um flag por registro (ex. 'can_edit') no
        contexto, calculado com care.utils.can_edit_record, para permitir
        que o template condicione a exibicao do link de Editar."""
        past_record = self._record(
            record_date=self.today - timedelta(days=1),
            record_time=time(10, 0),
            what="Registro anterior",
        )
        future_record = self._record(
            record_date=self.today + timedelta(days=1),
            record_time=time(10, 0),
            what="Registro futuro",
        )

        self.client.login(username="owner_list", password="pass1234")
        response = self.client.get(reverse("care:record-list"))

        self.assertEqual(response.status_code, 200)

        records_by_id = {r.pk: r for r in response.context["records"]}

        self.assertIn(past_record.pk, records_by_id)
        self.assertIn(future_record.pk, records_by_id)

        past_ctx_record = records_by_id[past_record.pk]
        future_ctx_record = records_by_id[future_record.pk]

        self.assertTrue(
            hasattr(past_ctx_record, "can_edit"),
            "Cada registro no contexto deveria expor um atributo 'can_edit'."
        )
        self.assertFalse(
            past_ctx_record.can_edit,
            "Registro anterior nao deveria ter can_edit=True."
        )
        self.assertTrue(
            future_ctx_record.can_edit,
            "Registro futuro/atual deveria ter can_edit=True."
        )


class DashboardEditLinkVisibilityTests(TestCase):
    """Testa que a tela server-rendered do dashboard (care:dashboard) so
    exibe o link/botao 'Editar' quando care.utils.can_edit_record permite a
    edicao do registro pelo usuario autenticado.

    O dashboard renderiza registros em dois blocos de template distintos
    (templates/care/dashboard.html): o bloco de "range" (agrupado por dia,
    usado quando ha filtro de periodo via ?start=/&end=) e o bloco
    "schedule" (lista simples, usado quando o filtro de data e limpo via
    ?clear=1). Ambos hoje exibem 'Editar' para qualquer registro do dono,
    independente do registro estar bloqueado no backend por ser "anterior".
    Estes testes devem falhar contra o codigo atual.
    """

    def setUp(self):
        self.owner = User.objects.create_user(username="owner_dash", password="pass1234")
        self.patient = Patient.objects.create(name="Paciente Dashboard")
        self.group = CareGroup.objects.create(name="Grupo Dashboard", patient=self.patient)
        GroupMembership.objects.create(
            user=self.owner, group=self.group, relation_to_patient="FAMILY"
        )

        self.today = timezone.localdate()
        self.now_time = timezone.localtime().time()

    def _record(self, *, record_date, record_time, what):
        return CareRecord.objects.create(
            patient=self.patient,
            caregiver="Cuidador",
            type=CareRecord.Type.OTHER,
            what=what,
            date=record_date,
            time=record_time,
            created_by=self.owner,
        )

    def _past_time(self):
        combined = dt_datetime.combine(self.today, self.now_time)
        past = combined - timedelta(hours=1)
        if past.date() != self.today:
            return time(0, 0)
        return past.time()

    def _edit_url(self, record):
        return reverse("care:record-update", args=[record.pk])

    def test_range_block_hides_edit_link_for_past_record(self):
        """Bloco de periodo (?start=/&end=): registro anterior nao deve
        exibir link de Editar; registro futuro do mesmo dono deve exibir."""
        past_record = self._record(
            record_date=self.today - timedelta(days=2),
            record_time=time(10, 0),
            what="Registro anterior (range)",
        )
        future_record = self._record(
            record_date=self.today + timedelta(days=2),
            record_time=time(10, 0),
            what="Registro futuro (range)",
        )

        self.client.login(username="owner_dash", password="pass1234")
        response = self.client.get(
            reverse("care:dashboard"),
            {
                "start": (self.today - timedelta(days=3)).isoformat(),
                "end": (self.today + timedelta(days=3)).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()

        self.assertNotIn(
            self._edit_url(past_record), html,
            "Link de Editar nao deveria aparecer para um registro anterior "
            "no bloco de periodo do dashboard."
        )
        self.assertIn(
            self._edit_url(future_record), html,
            "Link de Editar deveria aparecer para um registro futuro editavel "
            "no bloco de periodo do dashboard."
        )

    def test_schedule_block_hides_edit_link_for_past_record(self):
        """Bloco 'schedule' (?clear=1, sem filtro de periodo): registro
        anterior nao deve exibir link de Editar; registro futuro deve."""
        past_record = self._record(
            record_date=self.today - timedelta(days=1),
            record_time=self._past_time(),
            what="Registro anterior (schedule)",
        )
        future_record = self._record(
            record_date=self.today + timedelta(days=1),
            record_time=time(10, 0),
            what="Registro futuro (schedule)",
        )

        self.client.login(username="owner_dash", password="pass1234")
        response = self.client.get(reverse("care:dashboard"), {"clear": "1"})

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()

        self.assertNotIn(
            self._edit_url(past_record), html,
            "Link de Editar nao deveria aparecer para um registro anterior "
            "no bloco 'schedule' do dashboard."
        )
        self.assertIn(
            self._edit_url(future_record), html,
            "Link de Editar deveria aparecer para um registro futuro editavel "
            "no bloco 'schedule' do dashboard."
        )


class RecordCreateHistoryEditLinkVisibilityTests(TestCase):
    """Testa que o historico recente exibido em care:record-create
    (templates/care/record_quick.html, secao 'Historico recente') so
    exibe o link/botao 'Editar' quando care.utils.can_edit_record permite a
    edicao do registro pelo usuario autenticado.

    Hoje o template exibe 'Editar' para qualquer registro do dono,
    independente do registro estar bloqueado no backend por ser "anterior".
    Este teste deve falhar contra o codigo atual.
    """

    def setUp(self):
        self.owner = User.objects.create_user(username="owner_quick", password="pass1234")
        self.patient = Patient.objects.create(name="Paciente RecordQuick")
        self.group = CareGroup.objects.create(name="Grupo RecordQuick", patient=self.patient)
        GroupMembership.objects.create(
            user=self.owner, group=self.group, relation_to_patient="FAMILY"
        )

        self.today = timezone.localdate()

    def _record(self, *, record_date, record_time, what):
        return CareRecord.objects.create(
            patient=self.patient,
            caregiver="Cuidador",
            type=CareRecord.Type.OTHER,
            what=what,
            date=record_date,
            time=record_time,
            created_by=self.owner,
        )

    def _edit_url(self, record):
        return reverse("care:record-update", args=[record.pk])

    def test_history_hides_edit_link_for_past_record_shows_for_future(self):
        past_record = self._record(
            record_date=self.today - timedelta(days=1),
            record_time=time(10, 0),
            what="Registro anterior (historico)",
        )
        future_record = self._record(
            record_date=self.today + timedelta(days=1),
            record_time=time(10, 0),
            what="Registro futuro (historico)",
        )

        self.client.login(username="owner_quick", password="pass1234")
        response = self.client.get(reverse("care:record-create"))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()

        self.assertNotIn(
            self._edit_url(past_record), html,
            "Link de Editar nao deveria aparecer para um registro anterior "
            "no historico recente de record-create."
        )
        self.assertIn(
            self._edit_url(future_record), html,
            "Link de Editar deveria aparecer para um registro futuro editavel "
            "no historico recente de record-create."
        )


class ExportMetadataGeneratedByTests(TestCase):
    """Cobre a subtask 84-A: campo generated_by em ExportMetadata."""

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            "admin_exportador", password="pass1234"
        )
        self.superuser.profile.full_name = "Administradora Fulana"
        self.superuser.profile.save(update_fields=["full_name"])

        self.patient = Patient.objects.create(name="Paciente Export")
        self.group = CareGroup.objects.create(name="Grupo Export", patient=self.patient)
        CareRecord.objects.create(
            patient=self.patient,
            caregiver="Cuidador Export",
            type=CareRecord.Type.OTHER,
            what="Registro qualquer",
            date=date(2026, 6, 15),
            time=time(12, 0),
            created_by=self.superuser,
        )
        self.factory = RequestFactory()

    def test_export_metadata_accepts_optional_generated_by_field(self):
        meta = ExportMetadata(
            start=None,
            end=None,
            period_label="Todos os tempos",
            patient_name="Paciente Teste",
            records_total=0,
        )
        self.assertIsNone(meta.generated_by)

        meta_com_autor = ExportMetadata(
            start=None,
            end=None,
            period_label="Todos os tempos",
            patient_name="Paciente Teste",
            records_total=0,
            generated_by="Administradora Fulana",
        )
        self.assertEqual(meta_com_autor.generated_by, "Administradora Fulana")

    def test_single_type_export_populates_generated_by_with_logged_user_display_name(self):
        request = self.factory.get("/care/admin/export/", {"format": "csv"})
        request.user = self.superuser

        captured = {}
        original_csv_exporter = EXPORTERS["csv"]

        def fake_csv_exporter(rows, meta, columns=None):
            captured["meta"] = meta
            return original_csv_exporter(rows, meta, columns=columns)

        with patch.dict(EXPORTERS, {"csv": fake_csv_exporter}):
            response = admin_export_db(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("meta", captured)
        self.assertEqual(
            captured["meta"].generated_by,
            display_name(self.superuser),
        )

    def test_consolidated_multi_type_export_populates_generated_by_with_logged_user_display_name(self):
        CareRecord.objects.create(
            patient=self.patient,
            caregiver="Cuidador Export",
            type=CareRecord.Type.MEDICATION,
            what="Dipirona 500mg",
            date=date(2026, 6, 15),
            time=time(13, 0),
            created_by=self.superuser,
        )
        request = self.factory.get(
            "/care/admin/export/",
            {
                "format": "docx",
                "record_type": ["other", "medication"],
            },
        )
        request.user = self.superuser

        captured = {}

        def fake_consolidated_docx(sections, meta):
            captured["meta"] = meta
            return HttpResponse(
                content_type=(
                    "application/vnd.openxmlformats-officedocument"
                    ".wordprocessingml.document"
                )
            )

        with patch("care.views.export_consolidated_as_docx", fake_consolidated_docx):
            response = admin_export_db(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("meta", captured)
        self.assertEqual(
            captured["meta"].generated_by,
            display_name(self.superuser),
        )


class DocxPageFooterMetadataTests(TestCase):
    """Cobre a subtask 84-B: rodape real de pagina (section.footer) nos DOCX."""

    def _generic_rows(self):
        return [
            {
                "date": "2026-06-15",
                "time": "12:00",
                "category": "Outros",
                "what": "Almoco",
                "description": "Aceitou bem.",
                "caregiver": "Cuidador",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "exception": "Nao",
            }
        ]

    def _generic_meta(self, generated_by=None):
        return ExportMetadata(
            start=None,
            end=None,
            period_label="Todos os tempos",
            patient_name="Paciente Teste",
            records_total=1,
            record_types_label="Outros",
            generated_by=generated_by,
        )

    def _footer_text(self, docx_bytes):
        document = DocxDocument(BytesIO(docx_bytes))
        return "\n".join(
            paragraph.text for paragraph in document.sections[0].footer.paragraphs
        )

    def test_single_type_docx_page_footer_contains_generation_datetime_and_generated_by(self):
        rows = self._generic_rows()
        meta = self._generic_meta(generated_by="Administradora Fulana")

        fixed_now = timezone.make_aware(dt_datetime(2026, 6, 15, 14, 30))
        with patch("care.exporters.timezone.localtime", return_value=fixed_now):
            response = export_as_docx(rows, meta, columns=COLUMNS)

        footer_text = self._footer_text(response.content)

        self.assertIn("15/06/2026 14:30", footer_text)
        self.assertIn("Administradora Fulana", footer_text)

    def test_single_type_docx_page_footer_falls_back_to_sistema_when_generated_by_is_none(self):
        rows = self._generic_rows()
        meta = self._generic_meta(generated_by=None)

        response = export_as_docx(rows, meta, columns=COLUMNS)

        footer_text = self._footer_text(response.content)

        self.assertIn("Sistema", footer_text)

    def test_sleep_docx_page_footer_contains_generation_datetime_and_generated_by(self):
        rows = [
            {
                "date": "2026-06-01",
                "time": "22:00",
                "category": "Sono",
                "what": "Dormiu",
                "description": "Adormeceu sem intercorrencias.",
                "caregiver": "Dra Ana",
                "patient": "Paciente Teste",
                "status": "Realizada",
                "exception": "Nao",
            }
        ]
        meta = ExportMetadata(
            start=date(2026, 6, 1),
            end=date(2026, 6, 1),
            period_label="Periodo personalizado",
            patient_name="Paciente Teste",
            records_total=1,
            record_types_label="Sono",
            generated_by="Enfermeiro Beto",
        )

        fixed_now = timezone.make_aware(dt_datetime(2026, 6, 1, 23, 0))
        with patch("care.exporters.timezone.localtime", return_value=fixed_now):
            response = export_as_docx(rows, meta, columns=COLUMNS)

        footer_text = self._footer_text(response.content)

        self.assertIn("01/06/2026 23:00", footer_text)
        self.assertIn("Enfermeiro Beto", footer_text)

    def test_consolidated_docx_page_footer_contains_generation_datetime_and_generated_by(self):
        section = ConsolidatedExportSection(
            type_value="other",
            label="Outros",
            rows=self._generic_rows(),
            columns=COLUMNS,
        )
        meta = ExportMetadata(
            start=date(2026, 6, 14),
            end=date(2026, 6, 16),
            period_label="Periodo personalizado",
            patient_name="Paciente Teste",
            records_total=1,
            record_types_label="Outros",
            generated_by="Coordenadora Clinica",
        )

        fixed_now = timezone.make_aware(dt_datetime(2026, 6, 16, 9, 5))
        with patch("care.exporters.timezone.localtime", return_value=fixed_now):
            response = export_consolidated_as_docx([section], meta)

        footer_text = self._footer_text(response.content)

        self.assertIn("16/06/2026 09:05", footer_text)
        self.assertIn("Coordenadora Clinica", footer_text)


class CareRecordSoftDeleteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="soft_delete_user", password="pass1234")
        self.patient = Patient.objects.create(name="Paciente Soft Delete")

    def _create_record(self):
        return CareRecord.objects.create(
            patient=self.patient,
            caregiver="Cuidador",
            type=CareRecord.Type.OTHER,
            what="Registro para exclusao logica",
            date=date.today(),
            time=time(9, 0),
            created_by=self.user,
        )

    def test_carerecord_has_soft_delete_fields_with_pt_br_verbose_name(self):
        deleted_at_field = CareRecord._meta.get_field("deleted_at")
        deleted_by_field = CareRecord._meta.get_field("deleted_by")

        self.assertEqual(deleted_at_field.verbose_name, "Removido em")
        self.assertTrue(deleted_at_field.null)
        self.assertTrue(deleted_at_field.blank)
        self.assertTrue(deleted_at_field.db_index)

        self.assertEqual(deleted_by_field.verbose_name, "Removido por")
        self.assertTrue(deleted_by_field.null)
        self.assertTrue(deleted_by_field.blank)
        self.assertEqual(deleted_by_field.remote_field.on_delete.__name__, "SET_NULL")

    def test_default_manager_excludes_soft_deleted_records(self):
        record = self._create_record()

        record.deleted_at = timezone.now()
        record.deleted_by = self.user
        record.save(update_fields=["deleted_at", "deleted_by"])

        self.assertNotIn(record, CareRecord.objects.all())
        self.assertFalse(CareRecord.objects.filter(pk=record.pk).exists())

    def test_all_objects_manager_returns_soft_deleted_records(self):
        record = self._create_record()

        record.deleted_at = timezone.now()
        record.deleted_by = self.user
        record.save(update_fields=["deleted_at", "deleted_by"])

        deleted_record = CareRecord.all_objects.get(pk=record.pk)
        self.assertEqual(deleted_record.deleted_by, self.user)
        self.assertIsNotNone(deleted_record.deleted_at)

    def test_default_manager_still_returns_non_deleted_records(self):
        record = self._create_record()

        self.assertIn(record, CareRecord.objects.all())
        self.assertIn(record, CareRecord.all_objects.all())

    def test_admin_queryset_includes_soft_deleted_records_for_audit(self):
        from care.admin import CareRecordAdmin
        from django.contrib import admin as django_admin

        record = self._create_record()
        record.deleted_at = timezone.now()
        record.deleted_by = self.user
        record.save(update_fields=["deleted_at", "deleted_by"])

        model_admin = CareRecordAdmin(CareRecord, django_admin.site)
        request = type("Request", (), {"user": self.user})()

        queryset = model_admin.get_queryset(request)

        self.assertIn(record, queryset)
        self.assertIn("deleted_at", model_admin.list_display)
        self.assertIn("deleted_by", model_admin.list_display)
        self.assertIn("deleted_at", model_admin.readonly_fields)
        self.assertIn("deleted_by", model_admin.readonly_fields)

    def test_admin_disallows_physical_deletion(self):
        from care.admin import CareRecordAdmin
        from django.contrib import admin as django_admin

        record = self._create_record()

        model_admin = CareRecordAdmin(CareRecord, django_admin.site)
        request = type("Request", (), {"user": self.user})()

        self.assertFalse(model_admin.has_delete_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request, record))
