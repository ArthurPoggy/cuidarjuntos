"""Testes do template de email do relatorio semanal.

Cobrem os criterios de aceitacao do card #63:
- cabecalho com nome do paciente
- saudacao personalizada
- periodo do relatorio (DD/MM a DD/MM)
- resumo por categoria
- tabela Data/Tipo/O que aconteceu/Cuidador
- rodape com data de geracao e aviso de confidencialidade
- largura maxima de 600px, sem CSS externo
"""
from datetime import date, datetime

from django.template.loader import render_to_string
from django.test import SimpleTestCase


def _sample_context():
    return {
        "patient_name": "Vovó Maria",
        "recipient_name": "Alice",
        "period_start": date(2026, 5, 4),
        "period_end": date(2026, 5, 10),
        "category_summary": [
            {"label": "Medicação", "count": 5},
            {"label": "Alimentação", "count": 3},
            {"label": "Sinais Vitais", "count": 2},
        ],
        "records": [
            {
                "date": date(2026, 5, 4),
                "type_display": "Medicação",
                "what": "Losartana 50mg",
                "caregiver": "Bob",
            },
            {
                "date": date(2026, 5, 5),
                "type_display": "Alimentação",
                "what": "Almoço completo",
                "caregiver": "Carol",
            },
        ],
        "generated_at": datetime(2026, 5, 11, 8, 30),
    }


class WeeklyReportEmailTemplateTests(SimpleTestCase):
    """Renderiza templates/emails/weekly_report.html com um contexto de exemplo."""

    def _render(self, **overrides):
        context = _sample_context()
        context.update(overrides)
        return render_to_string("emails/weekly_report.html", context)

    def test_header_contains_patient_name(self):
        html = self._render()
        self.assertIn("Vovó Maria", html)

    def test_personalized_greeting(self):
        html = self._render()
        self.assertIn("Alice", html)
        # saudacao deve conter alguma forma de "Ola"/"Oi" junto do nome
        self.assertRegex(html, r"(?i)(ol[áa]|oi),?\s+Alice")

    def test_period_formatted_ddmm_to_ddmm(self):
        html = self._render()
        self.assertIn("04/05", html)
        self.assertIn("10/05", html)

    def test_category_summary_present(self):
        html = self._render()
        self.assertIn("Medicação", html)
        self.assertIn("Alimentação", html)
        self.assertIn("Sinais Vitais", html)
        self.assertIn("5", html)
        self.assertIn("3", html)

    def test_table_headers_present(self):
        html = self._render()
        self.assertIn("Data", html)
        self.assertIn("Tipo", html)
        self.assertIn("O que aconteceu", html)
        self.assertIn("Cuidador", html)

    def test_table_rows_render_record_fields(self):
        html = self._render()
        self.assertIn("Losartana 50mg", html)
        self.assertIn("Bob", html)
        self.assertIn("Almoço completo", html)
        self.assertIn("Carol", html)
        self.assertIn("04/05", html)

    def test_footer_has_generation_date(self):
        html = self._render()
        self.assertIn("11/05/2026", html)

    def test_footer_has_confidentiality_notice(self):
        html = self._render()
        self.assertRegex(html, r"(?i)confidencia")

    def test_max_width_600px(self):
        html = self._render()
        self.assertIn("600px", html)

    def test_no_external_stylesheet_or_script(self):
        html = self._render()
        self.assertNotIn("<link", html.lower())
        self.assertNotRegex(html, r"<script[^>]*src=")

    def test_no_empty_records_still_renders(self):
        html = self._render(records=[], category_summary=[])
        self.assertIn("Vovó Maria", html)
