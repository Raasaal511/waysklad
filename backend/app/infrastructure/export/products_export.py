from io import BytesIO, StringIO
import csv

import openpyxl
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from decimal import Decimal

from app.domain.catalog.entities import Product
from app.infrastructure.pdf_fonts import register_fonts

_COLUMNS = [
    "Название",
    "Артикул",
    "Штрихкод",
    "Ед.изм.",
    "Категория",
    "Закупочная цена",
    "Розничная цена",
    "Маржа",
    "Мин.остаток",
]


def _format_stock(value: Decimal, fractional: bool) -> str:
    """Целые единицы (шт, упаковка…) — без дробной части; дробные (кг, л…) — без хвостовых нулей."""
    if not fractional:
        return str(int(value))
    normalized = value.normalize()
    return format(normalized, "f") if "E" in str(normalized) else str(normalized)


def _row(product: Product, category_names: dict[int, str], show_purchase: bool) -> list[str]:
    category = category_names.get(product.category_id, "") if product.category_id else ""
    return [
        product.name,
        product.sku,
        product.barcode.value if product.barcode else "",
        product.unit.name,
        category,
        str(product.purchase_price.amount) if show_purchase else "",
        str(product.retail_price.amount),
        str(product.margin.amount) if show_purchase else "",
        _format_stock(product.min_stock, product.unit.fractional),
    ]


def render_products_xlsx(
    products: list[Product], category_names: dict[int, str], show_purchase: bool
) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Товары"
    sheet.append(_COLUMNS)
    for product in products:
        sheet.append(_row(product, category_names, show_purchase))

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def render_products_csv(
    products: list[Product], category_names: dict[int, str], show_purchase: bool
) -> bytes:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_COLUMNS)
    for product in products:
        writer.writerow(_row(product, category_names, show_purchase))
    return buffer.getvalue().encode("utf-8-sig")


def render_products_pdf(
    shop_name: str,
    products: list[Product],
    category_names: dict[int, str],
    show_purchase: bool,
) -> bytes:
    font, font_bold = register_fonts()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    title_style = ParagraphStyle("Title", fontName=font_bold, fontSize=15, leading=18)
    meta_style = ParagraphStyle(
        "Meta", fontName=font, fontSize=9.5, leading=13, textColor=colors.HexColor("#444444")
    )
    cell_style = ParagraphStyle("Cell", fontName=font, fontSize=8.5, leading=11)
    header_style = ParagraphStyle("Header", fontName=font_bold, fontSize=8.5, leading=11)

    story = [
        Paragraph(shop_name, title_style),
        Spacer(1, 2 * mm),
        Paragraph(f"Список товаров · {len(products)} шт.", meta_style),
        Spacer(1, 5 * mm),
    ]

    rows = [[Paragraph(c, header_style) for c in _COLUMNS]]
    for product in products:
        rows.append(
            [Paragraph(str(v), cell_style) for v in _row(product, category_names, show_purchase)]
        )

    col_widths = [55 * mm, 28 * mm, 30 * mm, 18 * mm, 30 * mm, 28 * mm, 28 * mm, 24 * mm, 22 * mm]
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
                ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#333333")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (5, 0), (-1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(table)

    doc.build(story)
    return buffer.getvalue()
