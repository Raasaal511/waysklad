from decimal import Decimal
from io import BytesIO, StringIO
import csv

import openpyxl
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.domain.inventory.entities import StockDocType, StockDocument
from app.infrastructure.export.pdf_fonts import register_fonts

_TYPE_LABELS = {
    StockDocType.RECEIPT: "Приёмка",
    StockDocType.WRITE_OFF: "Списание",
    StockDocType.TRANSFER: "Перемещение",
    StockDocType.STOCKTAKE: "Инвентаризация",
}

_COLUMNS = [
    "№", "Дата", "Тип", "Склад", "Склад-получатель", "Автор", "Товар", "Кол-во", "Цена", "Примечание",
]


def _format_quantity(value: Decimal, fractional: bool) -> str:
    if not fractional:
        return str(int(value))
    normalized = value.normalize()
    return format(normalized, "f") if "E" in str(normalized) else str(normalized)


def _rows(
    documents: list[StockDocument],
    warehouse_names: dict[int, str],
    product_names: dict[int, str],
    product_fractional: dict[int, bool],
    author_names: dict[int, str],
) -> list[list[str]]:
    rows = []
    for doc in documents:
        for line in doc.lines:
            rows.append([
                str(doc.number),
                doc.created_at.strftime("%d.%m.%Y %H:%M") if doc.created_at else "",
                _TYPE_LABELS.get(doc.type, doc.type.value),
                warehouse_names.get(doc.warehouse_id, f"#{doc.warehouse_id}"),
                warehouse_names.get(doc.to_warehouse_id, "") if doc.to_warehouse_id else "",
                author_names.get(doc.author_id, f"#{doc.author_id}"),
                product_names.get(line.product_id, f"#{line.product_id}"),
                _format_quantity(line.quantity.value, product_fractional.get(line.product_id, True)),
                str(line.cost.amount) if line.cost else "",
                doc.note,
            ])
    return rows


def render_documents_xlsx(
    documents: list[StockDocument],
    warehouse_names: dict[int, str],
    product_names: dict[int, str],
    product_fractional: dict[int, bool],
    author_names: dict[int, str],
) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Остатки"
    sheet.append(_COLUMNS)
    for row in _rows(documents, warehouse_names, product_names, product_fractional, author_names):
        sheet.append(row)

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def render_documents_csv(
    documents: list[StockDocument],
    warehouse_names: dict[int, str],
    product_names: dict[int, str],
    product_fractional: dict[int, bool],
    author_names: dict[int, str],
) -> bytes:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_COLUMNS)
    for row in _rows(documents, warehouse_names, product_names, product_fractional, author_names):
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8-sig")


def render_documents_pdf(
    shop_name: str,
    documents: list[StockDocument],
    warehouse_names: dict[int, str],
    product_names: dict[int, str],
    product_fractional: dict[int, bool],
    author_names: dict[int, str],
) -> bytes:
    font, font_bold = register_fonts()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    title_style = ParagraphStyle("Title", fontName=font_bold, fontSize=15, leading=18)
    meta_style = ParagraphStyle(
        "Meta", fontName=font, fontSize=9.5, leading=13, textColor=colors.HexColor("#444444")
    )
    cell_style = ParagraphStyle("Cell", fontName=font, fontSize=7.5, leading=10)
    header_style = ParagraphStyle("Header", fontName=font_bold, fontSize=7.5, leading=10)

    row_values = _rows(documents, warehouse_names, product_names, product_fractional, author_names)
    story = [
        Paragraph(shop_name, title_style),
        Spacer(1, 2 * mm),
        Paragraph(f"История движения товара · {len(row_values)} позиций", meta_style),
        Spacer(1, 5 * mm),
    ]

    rows = [[Paragraph(c, header_style) for c in _COLUMNS]]
    for row in row_values:
        rows.append([Paragraph(str(v), cell_style) for v in row])

    col_widths = [10 * mm, 25 * mm, 24 * mm, 28 * mm, 28 * mm, 26 * mm, 45 * mm, 18 * mm, 18 * mm, 30 * mm]
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
                ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#333333")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (7, 0), (8, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)

    doc.build(story)
    return buffer.getvalue()
