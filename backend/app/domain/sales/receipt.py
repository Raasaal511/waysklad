from urllib.parse import quote

from app.domain.common.phone import Phone
from app.domain.sales.entities import Sale
from app.domain.sales.payment import PaymentMethod

_PAYMENT_LABELS = {
    PaymentMethod.CASH: "наличные",
    PaymentMethod.TRANSFER: "перевод",
    PaymentMethod.CREDIT: "в долг",
}


def render_receipt_text(
    shop_name: str, sale: Sale, product_names: dict[int, str], client_name: str | None = None
) -> str:
    """Товарная квитанция (не фискальный чек) — текст для отправки клиенту в WhatsApp."""
    lines = [shop_name, f"Чек №{sale.id} от {sale.created_at:%d.%m.%Y %H:%M}"]
    if client_name:
        lines.append(f"Клиент: {client_name}")
    lines.append("")
    for line in sale.lines:
        name = product_names.get(line.product_id, f"Товар #{line.product_id}")
        lines.append(f"{name} — {line.quantity.formatted} x {line.price.amount} = {line.total.amount}")
    lines.append("")
    if sale.discount.amount:
        lines.append(f"Скидка: {sale.discount.amount}")
    lines.append(f"Итого: {sale.total.amount} ₽")
    lines.append(f"Оплата: {_PAYMENT_LABELS[sale.payment_method]}")
    lines.append("Спасибо за покупку!")
    return "\n".join(lines)


def build_whatsapp_link(phone: Phone, text: str) -> str:
    """Ссылка wa.me с готовым текстом квитанции — открывает чат с клиентом одним нажатием."""
    digits = phone.value.lstrip("+")
    return f"https://wa.me/{digits}?text={quote(text)}"
