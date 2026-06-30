from datetime import date, time, timedelta
from io import BytesIO
import zipfile

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .exporters import (
    COLUMNS,
    ConsolidatedExportSection,
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
from .utils import sync_recurrence_series


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
