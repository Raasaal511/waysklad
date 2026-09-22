from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle

from app.domain.common.money import format_rub
from app.domain.sales.entities import Sale
from app.domain.sales.payment import PaymentMethod

_FONT_PATHS = {
    "DejaVu": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "DejaVu-Bold": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
}
_FALLBACK_FONT = "Helvetica"
_FALLBACK_FONT_BOLD = "Helvetica-Bold"

_PAYMENT_LABELS = {
    PaymentMethod.CASH: "наличные",
    PaymentMethod.TRANSFER: "перевод",
    PaymentMethod.CREDIT: "в долг",
}

_registered = False


def _register_fonts() -> tuple[str, str]:
    """Пытается зарегистрировать DejaVu (кириллица); если шрифтов нет — Helvetica (только латиница)."""
    global _registered
    if not _registered:
        try:
            pdfmetrics.registerFont(TTFont("DejaVu", _FONT_PATHS["DejaVu"]))
            pdfmetrics.registerFont(TTFont("DejaVu-Bold", _FONT_PATHS["DejaVu-Bold"]))
        except Exception:
            pass
        _registered = True
    if "DejaVu" in pdfmetrics.getRegisteredFontNames():
        return "DejaVu", "DejaVu-Bold"
    return _FALLBACK_FONT, _FALLBACK_FONT_BOLD


def render_receipt_pdf(
    shop_name: str,
    sale: Sale,
    product_names: dict[int, str],
    client_name: str | None = None,
) -> bytes:
    """Товарная квитанция PDF-документом (не фискальный чек) — для отправки клиенту."""
    font, font_bold = _register_fonts()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A5,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    title_style = ParagraphStyle("Title", fontName=font_bold, fontSize=15, leading=18)
    meta_style = ParagraphStyle("Meta", fontName=font, fontSize=9.5, leading=13, textColor=colors.HexColor("#444444"))
    cell_style = ParagraphStyle("Cell", fontName=font, fontSize=9, leading=12)
    header_style = ParagraphStyle("Header", fontName=font_bold, fontSize=9, leading=12)
    total_style = ParagraphStyle("Total", fontName=font_bold, fontSize=12, leading=16)

    story = [
        Paragraph(shop_name, title_style),
        Spacer(1, 2 * mm),
        Paragraph(f"Товарная квитанция №{sale.id} от {sale.created_at:%d.%m.%Y %H:%M}", meta_style),
    ]
    if client_name:
        story.append(Paragraph(f"Покупатель: {client_name}", meta_style))
    story.append(Spacer(1, 5 * mm))

    header_row = [
        Paragraph("№", header_style),
        Paragraph("Наименование", header_style),
        Paragraph("Кол-во", header_style),
        Paragraph("Цена", header_style),
        Paragraph("Сумма", header_style),
    ]
    rows = [header_row]
    for i, line in enumerate(sale.lines, start=1):
        name = product_names.get(line.product_id, f"Товар #{line.product_id}")
        rows.append([
            Paragraph(str(i), cell_style),
            Paragraph(name, cell_style),
            Paragraph(line.quantity.formatted, cell_style),
            Paragraph(f"{line.price.amount}", cell_style),
            Paragraph(f"{line.total.amount}", cell_style),
        ])

    col_widths = [9 * mm, 63 * mm, 18 * mm, 24 * mm, 24 * mm]
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
                ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#333333")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 6 * mm))

    if sale.discount.amount:
        story.append(Paragraph(f"Скидка: {format_rub(sale.discount)}", meta_style))
        story.append(Spacer(1, 1.5 * mm))
    story.append(Paragraph(f"Итого: {format_rub(sale.total)}", total_style))
    story.append(Spacer(1, 1.5 * mm))
    story.append(Paragraph(f"Оплата: {_PAYMENT_LABELS[sale.payment_method]}", meta_style))
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("Спасибо за покупку!", meta_style))

    doc.build(story)
    return buffer.getvalue()
