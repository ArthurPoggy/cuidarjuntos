"""Utilities to export care records to multiple formats."""
from __future__ import annotations

import csv
import re
import textwrap
import zipfile
from dataclasses import dataclass
import math
from datetime import date
from io import BytesIO
from typing import Iterable, Sequence
from xml.sax.saxutils import escape as xml_escape

from django.http import HttpResponse
from django.utils import timezone
from django.utils.text import slugify


class ExportDependencyError(RuntimeError):
    """Raised when an export format is unavailable due to missing deps."""


@dataclass(slots=True)
class ExportMetadata:
    start: date | None
    end: date | None
    period_label: str
    patient_name: str | None
    records_total: int

    @property
    def range_slug(self) -> str:
        start = self.start.isoformat() if self.start else "inicio"
        end = self.end.isoformat() if self.end else "agora"
        if not self.start and not self.end:
            return "todos"
        return f"{start}_{end}"

    @property
    def patient_slug(self) -> str:
        if not self.patient_name:
            return "todos"
        return slugify(self.patient_name) or "paciente"

    def describe(self) -> str:
        parts: list[str] = [f"Período: {self.period_label}"]
        if self.start and self.end:
            parts.append(f"De {self.start.strftime('%d/%m/%Y')} até {self.end.strftime('%d/%m/%Y')}")
        elif self.start and not self.end:
            parts.append(f"A partir de {self.start.strftime('%d/%m/%Y')}")
        elif not self.start and self.end:
            parts.append(f"Até {self.end.strftime('%d/%m/%Y')}")
        if self.patient_name:
            parts.append(f"Paciente: {self.patient_name}")
        parts.append(f"Total de registros: {self.records_total}")
        return " | ".join(parts)

    def summary_rows(self) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = [("Período selecionado", self.period_label)]
        if self.start and self.end:
            rows.append(("Intervalo", f"{self.start.strftime('%d/%m/%Y')} – {self.end.strftime('%d/%m/%Y')}"))
        elif self.start and not self.end:
            rows.append(("Intervalo", f"Desde {self.start.strftime('%d/%m/%Y')}"))
        elif not self.start and self.end:
            rows.append(("Intervalo", f"Até {self.end.strftime('%d/%m/%Y')}"))
        rows.append(("Paciente", self.patient_name or "Todos os pacientes"))
        rows.append(("Total de registros", str(self.records_total)))
        rows.append(("Gerado em", timezone.localtime().strftime("%d/%m/%Y %H:%M")))
        return rows


def _clean_text(value: str | None) -> str:
    return (value or "").replace("\r", " ").replace("\n", " ").strip()


COLUMNS: Sequence[tuple[str, str]] = (
    ("date", "Data"),
    ("time", "Hora"),
    ("category", "Categoria"),
    ("what", "O que"),
    ("description", "Observações"),
    ("caregiver", "Cuidador"),
    ("patient", "Paciente"),
    ("status", "Status"),
    ("progress", "Classificação"),
    ("exception", "Exceção?"),
    ("timestamp", "Criado em"),
    ("author", "Criado por"),
)

MEDICATION_COLUMNS: Sequence[tuple[str, str]] = (
    ("created_date", "Data"),
    ("created_time", "Horário"),
    ("recurrence", "Recorrência"),
    ("medication", "Medicamento"),
    ("patient", "Paciente"),
    ("caregiver", "Cuidador"),
)

DEFAULT_COL_WIDTH_UNITS = 11
CREATED_COL_WIDTH_UNITS = 15
DEFAULT_COL_WIDTH_PX = 82
CREATED_COL_WIDTH_PX = 110


def _column_width_units(columns: Sequence[tuple[str, str]]) -> list[int]:
    widths: list[int] = []
    for _, label in columns:
        if label == "Criado em":
            widths.append(CREATED_COL_WIDTH_UNITS)
        else:
            widths.append(DEFAULT_COL_WIDTH_UNITS)
    return widths


def _column_width_px(columns: Sequence[tuple[str, str]]) -> list[int]:
    widths: list[int] = []
    for _, label in columns:
        if label == "Criado em":
            widths.append(CREATED_COL_WIDTH_PX)
        else:
            widths.append(DEFAULT_COL_WIDTH_PX)
    return widths


def serialize_records(records: Iterable) -> list[dict[str, str]]:
    """Return a normalized list of dictionaries ready for export."""
    serialized: list[dict[str, str]] = []
    for record in records:
        serialized.append(
            {
                "date": record.date.strftime("%Y-%m-%d"),
                "time": record.time.strftime("%H:%M") if record.time else "",
                "category": record.get_type_display(),
                "what": _clean_text(record.what),
                "description": _clean_text(record.description),
                "caregiver": _clean_text(record.caregiver),
                "patient": str(record.patient),
                "status": record.get_status_display(),
                "progress": record.get_progress_trend_display() if record.progress_trend else "",
                "exception": "Sim" if record.is_exception else "Não",
                "timestamp": timezone.localtime(record.timestamp).strftime("%Y-%m-%d %H:%M"),
                "author": _clean_text(record.author_name),
            }
        )
    return serialized


def serialize_medication_export(records: Iterable, patient_name: str | None) -> list[dict[str, str]]:
    """Return rows for the medication export table."""
    serialized: list[dict[str, str]] = []
    for record in records:
        created_at = timezone.localtime(record.timestamp)
        serialized.append(
            {
                "created_date": created_at.strftime("%Y-%m-%d"),
                "created_time": created_at.strftime("%H:%M"),
                "recurrence": record.get_recurrence_display() if record.recurrence else "",
                "medication": _clean_text(record.what),
                "patient": patient_name or str(record.patient),
                "caregiver": _clean_text(record.author_name),
            }
        )
    return serialized


def _default_filename(meta: ExportMetadata, ext: str) -> str:
    timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
    return f"registros_{meta.range_slug}_{meta.patient_slug}_{timestamp}.{ext}"


def export_as_csv(
    rows: list[dict[str, str]],
    meta: ExportMetadata,
    columns: Sequence[tuple[str, str]] = COLUMNS,
) -> HttpResponse:
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f"attachment; filename=\"{_default_filename(meta, 'csv')}\""
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow([label for _, label in columns])
    for row in rows:
        writer.writerow([row[key] for key, _ in columns])
    return response


def export_as_xlsx(
    rows: list[dict[str, str]],
    meta: ExportMetadata,
    columns: Sequence[tuple[str, str]] = COLUMNS,
) -> HttpResponse:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        return _export_xlsx_inline(rows, meta)

    wb = Workbook()
    ws = wb.active
    ws.title = "Registros"

    total_columns = len(columns)
    header_row = 1
    header_font = Font(bold=True, color="000000")
    thin_side = Side(style="thin", color="D1D5DB")
    header_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
    cell_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
    for col_idx, (_, label) in enumerate(columns, start=1):
        cell = ws.cell(row=header_row, column=col_idx, value=label)
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = header_border

    column_widths = _column_width_units(columns)
    for data_idx, row in enumerate(rows, start=1):
        excel_row = header_row + data_idx
        for col_idx, (key, _) in enumerate(columns, start=1):
            value = _xlsx_sanitize(row.get(key, ""))
            cell = ws.cell(row=excel_row, column=col_idx, value=value)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = cell_border

    ws.freeze_panes = ws.cell(row=2, column=1)
    ws.row_dimensions[1].height = 22
    for idx, width in enumerate(column_widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width

    buffer = BytesIO()
    wb.save(buffer)
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f"attachment; filename=\"{_default_filename(meta, 'xlsx')}\""
    return response


def export_as_docx(rows: list[dict[str, str]], meta: ExportMetadata) -> HttpResponse:
    try:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from docx.shared import Inches
    except ImportError as exc:
        return _export_docx_inline(rows, meta)

    def set_cell_shading(cell, color: str) -> None:
        shading = OxmlElement("w:shd")
        shading.set(qn("w:fill"), color)
        cell._tc.get_or_add_tcPr().append(shading)

    document = Document()
    table = document.add_table(rows=1, cols=len(columns))
    table.autofit = False
    table.style = "Table Grid"
    col_widths_px = _column_width_px(columns)
    col_widths_in = [Inches(px / 96) for px in col_widths_px]
    for idx, width in enumerate(col_widths_in):
        table.columns[idx].width = width
    header_cells = table.rows[0].cells
    for idx, (_, label) in enumerate(columns):
        header_cells[idx].text = label
        if header_cells[idx].paragraphs and header_cells[idx].paragraphs[0].runs:
            header_cells[idx].paragraphs[0].runs[0].bold = True
        if header_cells[idx].paragraphs:
            header_cells[idx].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        header_cells[idx].width = col_widths_in[idx]

    for row in rows:
        cells = table.add_row().cells
        for idx, (key, _) in enumerate(columns):
            cells[idx].text = row[key]
            cells[idx].width = col_widths_in[idx]
            for paragraph in cells[idx].paragraphs:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

    buffer = BytesIO()
    document.save(buffer)
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    response["Content-Disposition"] = f"attachment; filename=\"{_default_filename(meta, 'docx')}\""
    return response


def export_as_pdf(
    rows: list[dict[str, str]],
    meta: ExportMetadata,
    columns: Sequence[tuple[str, str]] = COLUMNS,
) -> HttpResponse:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        return _export_pdf_inline(rows, meta)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title="Registros exportados")
    styles = getSampleStyleSheet()
    story: list[object] = []

    grid_gray = colors.HexColor("#D1D5DB")

    data: list[list[str]] = [[label for _, label in columns]]
    data.extend([[row[key] for key, _ in columns] for row in rows])

    col_units = _column_width_units(columns)
    unit_total = sum(col_units) or 1
    col_widths = [(doc.width * unit / unit_total) for unit in col_units]
    table = Table(data, repeatRows=1, colWidths=col_widths)
    table.setStyle(
        TableStyle(
            [
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, grid_gray),
            ]
        )
    )
    story.append(table)

    doc.build(story)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f"attachment; filename=\"{_default_filename(meta, 'pdf')}\""
    return response


def _export_xlsx_inline(
    rows: list[dict[str, str]],
    meta: ExportMetadata,
    columns: Sequence[tuple[str, str]] = COLUMNS,
) -> HttpResponse:
    headers = [label for _, label in columns]
    column_widths = _column_width_units(columns)
    width = len(headers)

    all_rows: list[list[str]] = []
    all_rows.append(headers)
    all_rows.extend([[row.get(key, "") for key, _ in columns] for row in rows])

    last_col = _excel_column_letter(len(headers) - 1)
    last_row = len(all_rows)
    dimension = f"A1:{last_col}{last_row}"

    sheet_rows: list[str] = []
    for row_index, values in enumerate(all_rows, start=1):
        cells = []
        for col_index, value in enumerate(values):
            cell_ref = f"{_excel_column_letter(col_index)}{row_index}"
            safe_value = _xlsx_escape(value)
            cells.append(
                f'<c r="{cell_ref}" t="inlineStr"><is><t xml:space="preserve">{safe_value}</t></is></c>'
            )
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    cols_xml = "".join(
        f'<col min="{idx}" max="{idx}" width="{column_widths[idx - 1]}" customWidth="1"/>'
        for idx in range(1, len(headers) + 1)
    )
    sheet_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n""" + (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<dimension ref="{dimension}"/>'
        '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
        '<sheetFormatPr defaultRowHeight="15"/>'
        f"<cols>{cols_xml}</cols>"
        f"<sheetData>{''.join(sheet_rows)}</sheetData>"
        "</worksheet>"
    )

    created = timezone.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    with BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "[Content_Types].xml",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>"""
                "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
                "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
                "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
                "<Override PartName=\"/xl/workbook.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/>"
                "<Override PartName=\"/xl/worksheets/sheet1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/>"
                "<Override PartName=\"/docProps/core.xml\" ContentType=\"application/vnd.openxmlformats-package.core-properties+xml\"/>"
                "<Override PartName=\"/docProps/app.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.extended-properties+xml\"/>"
                "<Override PartName=\"/xl/styles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml\"/>"
                "</Types>",
            )
            zf.writestr(
                "_rels/.rels",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>"""
                "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
                "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"xl/workbook.xml\"/>"
                "<Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties\" Target=\"docProps/app.xml\"/>"
                "<Relationship Id=\"rId3\" Type=\"http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties\" Target=\"docProps/core.xml\"/>"
                "</Relationships>",
            )
            zf.writestr(
                "docProps/app.xml",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>"""
                "<Properties xmlns=\"http://schemas.openxmlformats.org/officeDocument/2006/extended-properties\" "
                "xmlns:vt=\"http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes\">"
                "<Application>Cuidar Juntos</Application>"
                "<TotalTime>0</TotalTime>"
                "</Properties>",
            )
            zf.writestr(
                "docProps/core.xml",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>"""
                "<cp:coreProperties xmlns:cp=\"http://schemas.openxmlformats.org/package/2006/metadata/core-properties\" "
                "xmlns:dc=\"http://purl.org/dc/elements/1.1/\" "
                "xmlns:dcterms=\"http://purl.org/dc/terms/\" "
                "xmlns:dcmitype=\"http://purl.org/dc/dcmitype/\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\">"
                f"<dc:title>Registros exportados</dc:title><cp:category>{xml_escape(meta.period_label)}</cp:category>"
                f"<dcterms:created xsi:type=\"dcterms:W3CDTF\">{created}</dcterms:created>"
                "</cp:coreProperties>",
            )
            zf.writestr(
                "xl/workbook.xml",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>"""
                "<workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" "
                "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">"
                "<bookViews><workbookView/></bookViews>"
                "<sheets><sheet name=\"Registros\" sheetId=\"1\" r:id=\"rId1\"/></sheets>"
                "</workbook>",
            )
            zf.writestr(
                "xl/_rels/workbook.xml.rels",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>"""
                "<Relationships xmlns=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">"
                "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet1.xml\"/>"
                "<Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles\" Target=\"styles.xml\"/>"
                "</Relationships>",
            )
            zf.writestr(
                "xl/styles.xml",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>"""
                "<styleSheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">"
                "<fonts count=\"1\"><font><name val=\"Calibri\"/><family val=\"2\"/><sz val=\"11\"/></font></fonts>"
                "<fills count=\"1\"><fill><patternFill patternType=\"none\"/></fill></fills>"
                "<borders count=\"1\"><border><left/><right/><top/><bottom/><diagonal/></border></borders>"
                "<cellStyleXfs count=\"1\"><xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\"/></cellStyleXfs>"
                "<cellXfs count=\"1\"><xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\" xfId=\"0\"/></cellXfs>"
                "<cellStyles count=\"1\"><cellStyle name=\"Normal\" xfId=\"0\" builtinId=\"0\"/></cellStyles>"
                "</styleSheet>",
            )
            zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)

        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    response["Content-Disposition"] = f"attachment; filename=\"{_default_filename(meta, 'xlsx')}\""
    return response


def _export_docx_inline(
    rows: list[dict[str, str]],
    meta: ExportMetadata,
    columns: Sequence[tuple[str, str]] = COLUMNS,
) -> HttpResponse:
    def paragraph(text: str) -> str:
        if not text:
            return "<w:p/>"
        escaped = xml_escape(text)
        escaped = escaped.replace("\n", "<w:br/>")
        return f"<w:p><w:r><w:t xml:space=\"preserve\">{escaped}</w:t></w:r></w:p>"

    table_rows = []
    headers = [label for _, label in columns]
    widths_twips = [px * 15 for px in _column_width_px(columns)]
    table_rows.append(_docx_table_row(headers, widths_twips, bold=True))
    for row in rows:
        values = [row.get(key, "") for key, _ in columns]
        table_rows.append(_docx_table_row(values, widths_twips))

    table_xml = (
        "<w:tbl>"
        "<w:tblPr>"
        "<w:tblStyle w:val=\"TableGrid\"/><w:tblW w:w=\"0\" w:type=\"auto\"/>"
        "<w:tblBorders>"
        "<w:top w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "<w:left w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "<w:bottom w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "<w:right w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "<w:insideH w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "<w:insideV w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "</w:tblBorders>"
        "</w:tblPr>"
        "<w:tblGrid>"
        f"{''.join(f'<w:gridCol w:w=\"{width}\"/>' for width in widths_twips)}"
        "</w:tblGrid>"
        f"{''.join(table_rows)}"
        "</w:tbl>"
    )

    document_xml = (
        """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>"""
        "<w:document xmlns:wpc=\"http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas\" "
        "xmlns:mc=\"http://schemas.openxmlformats.org/markup-compatibility/2006\" "
        "xmlns:o=\"urn:schemas-microsoft-com:office:office\" "
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" "
        "xmlns:m=\"http://schemas.openxmlformats.org/officeDocument/2006/math\" "
        "xmlns:v=\"urn:schemas-microsoft-com:vml\" "
        "xmlns:wp14=\"http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing\" "
        "xmlns:wp=\"http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing\" "
        "xmlns:w10=\"urn:schemas-microsoft-com:office:word\" "
        "xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\" "
        "xmlns:w14=\"http://schemas.microsoft.com/office/word/2010/wordml\" "
        "xmlns:wpg=\"http://schemas.microsoft.com/office/word/2010/wordprocessingGroup\" "
        "xmlns:wpi=\"http://schemas.microsoft.com/office/word/2010/wordprocessingInk\" "
        "xmlns:wne=\"http://schemas.microsoft.com/office/word/2006/wordml\" "
        "xmlns:wps=\"http://schemas.microsoft.com/office/word/2010/wordprocessingShape\" mc:Ignorable=\"w14 wp14\">"
        "<w:body>"
        f"{table_xml}"
        "<w:sectPr>"
        "<w:pgSz w:w=\"12240\" w:h=\"15840\"/><w:pgMar w:top=\"1440\" w:right=\"1440\" w:bottom=\"1440\" w:left=\"1440\"/>"
        "</w:sectPr>"
        "</w:body>"
        "</w:document>"
    )

    created = timezone.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    with BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "[Content_Types].xml",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>"""
                "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
                "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
                "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
                "<Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>"
                "<Override PartName=\"/word/styles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml\"/>"
                "<Override PartName=\"/docProps/core.xml\" ContentType=\"application/vnd.openxmlformats-package.core-properties+xml\"/>"
                "<Override PartName=\"/docProps/app.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.extended-properties+xml\"/>"
                "</Types>",
            )
            zf.writestr(
                "_rels/.rels",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>"""
                "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
                "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/>"
                "<Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties\" Target=\"docProps/app.xml\"/>"
                "<Relationship Id=\"rId3\" Type=\"http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties\" Target=\"docProps/core.xml\"/>"
                "</Relationships>",
            )
            zf.writestr(
                "docProps/app.xml",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>"""
                "<Properties xmlns=\"http://schemas.openxmlformats.org/officeDocument/2006/extended-properties\" "
                "xmlns:vt=\"http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes\">"
                "<Application>Cuidar Juntos</Application>"
                "<DocSecurity>0</DocSecurity>"
                "</Properties>",
            )
            zf.writestr(
                "docProps/core.xml",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>"""
                "<cp:coreProperties xmlns:cp=\"http://schemas.openxmlformats.org/package/2006/metadata/core-properties\" "
                "xmlns:dc=\"http://purl.org/dc/elements/1.1/\" "
                "xmlns:dcterms=\"http://purl.org/dc/terms/\" "
                "xmlns:dcmitype=\"http://purl.org/dc/dcmitype/\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\">"
                "<dc:title>Registros exportados</dc:title>"
                f"<dc:subject>{xml_escape(meta.period_label)}</dc:subject>"
                f"<dcterms:created xsi:type=\"dcterms:W3CDTF\">{created}</dcterms:created>"
                "</cp:coreProperties>",
            )
            zf.writestr("word/document.xml", document_xml)
            zf.writestr(
                "word/styles.xml",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>"""
                "<w:styles xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
                "<w:style w:type=\"paragraph\" w:default=\"1\" w:styleId=\"Normal\">"
                "<w:name w:val=\"Normal\"/><w:qFormat/>"
                "<w:rPr><w:lang w:val=\"pt-BR\"/></w:rPr>"
                "</w:style>"
                "<w:style w:type=\"table\" w:styleId=\"TableGrid\">"
                "<w:name w:val=\"Table Grid\"/>"
                "<w:tblPr><w:tblBorders>"
                "<w:top w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
                "<w:left w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
                "<w:bottom w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
                "<w:right w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
                "<w:insideH w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
                "<w:insideV w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
                "</w:tblBorders></w:tblPr>"
                "</w:style>"
                "</w:styles>",
            )

        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    response["Content-Disposition"] = f"attachment; filename=\"{_default_filename(meta, 'docx')}\""
    return response


def _export_pdf_inline(
    rows: list[dict[str, str]],
    meta: ExportMetadata,
    columns: Sequence[tuple[str, str]] = COLUMNS,
) -> HttpResponse:
    lines: list[str] = []
    header = " | ".join(label for _, label in columns)
    lines.append(header)
    lines.append("-" * len(header))

    for row in rows:
        text = " | ".join((row.get(key, "") or "-") for key, _ in columns)
        wrapped = textwrap.wrap(text, width=100) or [""]
        lines.extend(wrapped)
        lines.append("")

    if not rows:
        lines.append("Nenhum registro encontrado para os filtros selecionados.")

    pdf_bytes = _build_simple_pdf(lines)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f"attachment; filename=\"{_default_filename(meta, 'pdf')}\""
    return response


def _build_simple_pdf(lines: list[str]) -> bytes:
    pages: list[list[str]] = []
    page: list[str] = []
    max_lines = 45
    for line in lines:
        if len(page) >= max_lines:
            pages.append(page)
            page = []
        page.append(line)
    if page:
        pages.append(page)
    if not pages:
        pages = [[""]]

    num_pages = len(pages)
    total_objects = 2 + num_pages * 2 + 1  # catalog + pages + (page+content)*n + font
    objects: list[bytes | None] = [None] * (total_objects + 1)

    catalog_obj = 1
    pages_obj = 2
    page_objs = list(range(3, 3 + num_pages))
    content_objs = list(range(3 + num_pages, 3 + (num_pages * 2)))
    font_obj = total_objects

    objects[font_obj] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    for idx, page_lines in enumerate(pages):
        content_stream = _pdf_page_stream(page_lines)
        content_obj = content_objs[idx]
        objects[content_obj] = content_stream
        page_obj = page_objs[idx]
        objects[page_obj] = (
            f"<< /Type /Page /Parent {pages_obj} 0 R /MediaBox [0 0 595 842] "
            f"/Contents {content_obj} 0 R /Resources << /Font << /F1 {font_obj} 0 R >> >> >>"
        ).encode("utf-8")

    kids = " ".join(f"{num} 0 R" for num in page_objs)
    objects[pages_obj] = f"<< /Type /Pages /Count {num_pages} /Kids [{kids}] >>".encode("utf-8")
    objects[catalog_obj] = f"<< /Type /Catalog /Pages {pages_obj} 0 R >>".encode("utf-8")

    buffer = BytesIO()
    buffer.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    offsets = [0] * (total_objects + 1)
    for obj_num in range(1, total_objects + 1):
        offsets[obj_num] = buffer.tell()
        buffer.write(f"{obj_num} 0 obj\n".encode("utf-8"))
        data = objects[obj_num]
        if isinstance(data, str):
            data = data.encode("utf-8")
        buffer.write(data or b"")
        buffer.write(b"\nendobj\n")

    xref_pos = buffer.tell()
    buffer.write(f"xref\n0 {total_objects + 1}\n".encode("utf-8"))
    buffer.write(b"0000000000 65535 f \n")
    for obj_num in range(1, total_objects + 1):
        buffer.write(f"{offsets[obj_num]:010d} 00000 n \n".encode("utf-8"))
    buffer.write(
        f"trailer\n<< /Size {total_objects + 1} /Root {catalog_obj} 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode(
            "utf-8"
        )
    )
    return buffer.getvalue()


def _pdf_page_stream(lines: list[str]) -> bytes:
    ops = ["BT", "/F1 11 Tf", "14 TL", "50 800 Td"]
    for line in lines:
        text = _pdf_escape(line)
        ops.append(f"({text}) Tj")
        ops.append("T*")
    ops.append("ET")
    content = "\n".join(ops).encode("utf-8")
    return b"<< /Length " + str(len(content)).encode("utf-8") + b" >>\nstream\n" + content + b"\nendstream"


def _pdf_escape(value: str) -> str:
    return (
        (value or "")
        .replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def _docx_table_row(
    values: list[str],
    widths_twips: Sequence[int],
    bold: bool | Sequence[bool] = False,
) -> str:
    if isinstance(bold, bool):
        bold_flags = [bold] * len(values)
    else:
        bold_flags = list(bold) + [False] * max(0, len(values) - len(bold))  # type: ignore[arg-type]
        bold_flags = bold_flags[: len(values)]

    cells = []
    for idx, value in enumerate(values):
        escaped = xml_escape(value or "")
        run_props = "<w:rPr><w:b/></w:rPr>" if bold_flags[idx] else ""
        width = widths_twips[idx] if idx < len(widths_twips) else widths_twips[-1]
        cells.append(
            "<w:tc><w:tcPr>"
            f"<w:tcW w:w=\"{width}\" w:type=\"dxa\"/>"
            "</w:tcPr>"
            "<w:p><w:pPr><w:jc w:val=\"center\"/></w:pPr>"
            f"<w:r>{run_props}<w:t xml:space=\"preserve\">{escaped}</w:t></w:r></w:p></w:tc>"
        )
    return f"<w:tr>{''.join(cells)}</w:tr>"


def _xlsx_escape(value: str) -> str:
    return (xml_escape(_xlsx_sanitize(value))).replace("\n", "&#10;")


_XLSX_ILLEGAL_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")


def _xlsx_sanitize(value: str | None) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return _XLSX_ILLEGAL_CHARS_RE.sub("", value)


def _excel_column_letter(index: int) -> str:
    result = ""
    while index >= 0:
        index, remainder = divmod(index, 26)
        result = chr(65 + remainder) + result
        index -= 1
    return result


def export_sleep_chart(sessions: Sequence[dict[str, object]], meta: ExportMetadata) -> HttpResponse:
    width = 960
    height = 620
    margin_left = 70
    margin_right = 24
    margin_top = 70
    margin_bottom = 150

    chart_width = width - margin_left - margin_right
    chart_height = height - margin_top - margin_bottom

    if not sessions:
        svg = (
            f"<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{width}\" height=\"{height}\">"
            "<rect width=\"100%\" height=\"100%\" fill=\"#FFFFFF\"/>"
            f"<text x=\"{width/2}\" y=\"{height/2}\" text-anchor=\"middle\" "
            "font-family=\"Arial\" font-size=\"16\" fill=\"#334155\">"
            "Nenhum dado de sono para o período selecionado."
            "</text></svg>"
        )
        response = HttpResponse(svg, content_type="image/svg+xml")
        response["Content-Disposition"] = (
            f"attachment; filename=sono_grafico_{meta.range_slug}_{meta.patient_slug}.svg"
        )
        return response

    date_map = {session["date"]: session["date_label"] for session in sessions}
    dates = sorted(date_map.keys())
    max_hours = max(float(session["hours"]) for session in sessions)
    max_y = max(1, math.ceil(max_hours))

    if max_y <= 6:
        y_step = 1
    elif max_y <= 12:
        y_step = 2
    else:
        y_step = 3

    by_patient: dict[str, list[dict[str, object]]] = {}
    for session in sessions:
        patient = str(session["patient"])
        by_patient.setdefault(patient, []).append(session)

    colors = ["#2563EB", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#14B8A6"]

    def y_for(hours: float) -> float:
        return margin_top + chart_height * (1 - (hours / max_y))

    svg_parts = [
        f"<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{width}\" height=\"{height}\">",
        "<rect width=\"100%\" height=\"100%\" fill=\"#FFFFFF\"/>",
        f"<text x=\"{margin_left}\" y=\"32\" font-family=\"Arial\" font-size=\"18\" "
        "fill=\"#0F172A\" font-weight=\"bold\">Gráfico de Sono</text>",
        f"<text x=\"{margin_left}\" y=\"52\" font-family=\"Arial\" font-size=\"12\" "
        "fill=\"#475569\">"
        f"{xml_escape(meta.describe())}"
        "</text>",
    ]

    for tick in range(0, max_y + 1, y_step):
        y = y_for(float(tick))
        svg_parts.append(
            f"<line x1=\"{margin_left}\" y1=\"{y}\" x2=\"{width - margin_right}\" "
            f"y2=\"{y}\" stroke=\"#E2E8F0\" stroke-width=\"1\"/>"
        )
        svg_parts.append(
            f"<text x=\"{margin_left - 8}\" y=\"{y + 4}\" text-anchor=\"end\" "
            "font-family=\"Arial\" font-size=\"11\" fill=\"#64748B\">"
            f"{tick}</text>"
        )

    svg_parts.append(
        f"<line x1=\"{margin_left}\" y1=\"{margin_top}\" x2=\"{margin_left}\" "
        f"y2=\"{height - margin_bottom}\" stroke=\"#0F172A\" stroke-width=\"1\"/>"
    )
    svg_parts.append(
        f"<line x1=\"{margin_left}\" y1=\"{height - margin_bottom}\" "
        f"x2=\"{width - margin_right}\" y2=\"{height - margin_bottom}\" "
        "stroke=\"#0F172A\" stroke-width=\"1\"/>"
    )

    date_positions: dict[object, float] = {}
    group_width = chart_width / max(1, len(dates))
    for idx, label in enumerate(dates):
        group_start = margin_left + idx * group_width
        date_positions[label] = group_start + group_width / 2

    max_labels = 10
    x_label_step = max(1, math.ceil(len(dates) / max_labels))
    for idx, label in enumerate(dates):
        if idx % x_label_step != 0:
            continue
        x = date_positions[label]
        svg_parts.append(
            f"<text x=\"{x}\" y=\"{height - margin_bottom + 18}\" text-anchor=\"middle\" "
            "font-family=\"Arial\" font-size=\"10\" fill=\"#64748B\">"
            f"{xml_escape(str(date_map[label]))}</text>"
        )

    svg_parts.append(
        f"<text x=\"{margin_left}\" y=\"{height - margin_bottom + 30}\" font-family=\"Arial\" "
        "font-size=\"12\" fill=\"#475569\">Data do registro (Dormiu)</text>"
    )
    svg_parts.append(
        f"<text x=\"20\" y=\"{margin_top - 12}\" font-family=\"Arial\" "
        "font-size=\"12\" fill=\"#475569\">Horas de sono</text>"
    )

    legend_y = margin_top - 8
    legend_x = width - margin_right - 150
    patient_names = [name for name, _ in sorted(by_patient.items())]
    patient_count = max(1, len(patient_names))
    bar_gap = 6
    inner_padding = 0.12
    bar_slot_width = group_width * (1 - inner_padding * 2)
    bar_width = max(6, (bar_slot_width - (patient_count - 1) * bar_gap) / patient_count)

    hours_by_date_patient: dict[object, dict[str, float]] = {label: {} for label in dates}
    for patient, items in by_patient.items():
        for item in items:
            hours_by_date_patient[item["date"]][patient] = float(item["hours"])

    for patient_index, patient in enumerate(patient_names):
        color = colors[patient_index % len(colors)]
        y = legend_y + patient_index * 16
        svg_parts.append(
            f"<rect x=\"{legend_x}\" y=\"{y - 10}\" width=\"10\" height=\"10\" "
            f"fill=\"{color}\"/>"
        )
        svg_parts.append(
            f"<text x=\"{legend_x + 14}\" y=\"{y - 1}\" font-family=\"Arial\" "
            "font-size=\"10\" fill=\"#475569\">"
            f"{xml_escape(patient)}</text>"
        )

        for date_index, label in enumerate(dates):
            hours = hours_by_date_patient[label].get(patient)
            if hours is None:
                continue
            bar_height = chart_height * (hours / max_y)
            x = margin_left + date_index * group_width + (group_width - bar_slot_width) / 2
            x += patient_index * (bar_width + bar_gap)
            y_top = margin_top + chart_height - bar_height
            svg_parts.append(
                f"<rect x=\"{x:.2f}\" y=\"{y_top:.2f}\" width=\"{bar_width:.2f}\" "
                f"height=\"{bar_height:.2f}\" rx=\"3\" ry=\"3\" fill=\"{color}\"/>"
            )

    svg_parts.append("</svg>")
    svg = "".join(svg_parts)

    total_hours = sum(float(session["hours"]) for session in sessions)
    avg_hours = total_hours / len(sessions)
    max_session = max(sessions, key=lambda row: float(row["hours"]))
    min_session = min(sessions, key=lambda row: float(row["hours"]))
    summary_lines = [
        f"Media de horas dormidas: {avg_hours:.2f} h",
        f"Maior sono: {max_session['date_label']} - {float(max_session['hours']):.2f} h ({max_session['patient']})",
        f"Menor sono: {min_session['date_label']} - {float(min_session['hours']):.2f} h ({min_session['patient']})",
    ]
    summary_y_start = height - margin_bottom + 60
    summary_svg = []
    for idx, line in enumerate(summary_lines):
        y = summary_y_start + idx * 18
        summary_svg.append(
            f"<text x=\"{margin_left}\" y=\"{y}\" font-family=\"Arial\" "
            "font-size=\"12\" fill=\"#0F172A\">"
            f"{xml_escape(line)}</text>"
        )
    svg = svg.replace("</svg>", "".join(summary_svg) + "</svg>")

    response = HttpResponse(svg, content_type="image/svg+xml")
    response["Content-Disposition"] = (
        f"attachment; filename=sono_grafico_{meta.range_slug}_{meta.patient_slug}.svg"
    )
    return response




EXPORTERS = {
    "csv": export_as_csv,
    "xlsx": export_as_xlsx,
    "docx": export_as_docx,
    "pdf": export_as_pdf,
    "sleep_chart": export_sleep_chart,
}
