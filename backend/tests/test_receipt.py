from decimal import Decimal

from app.domain.common.money import Money
from app.domain.common.phone import Phone
from app.domain.common.quantity import Quantity, Unit
from app.domain.sales.entities import Sale, SaleLine
from app.domain.sales.payment import PaymentMethod
from app.domain.sales.receipt import build_whatsapp_link, render_receipt_text

PCS = Unit("pcs", "шт")


def _sale(**overrides) -> Sale:
    fields = dict(
        id=1,
        warehouse_id=1,
        seller_id=1,
        payment_method=PaymentMethod.CASH,
        lines=[
            SaleLine(id=10, product_id=100, quantity=Quantity(Decimal("2"), PCS), price=Money.of("250")),
        ],
    )
    fields.update(overrides)
    return Sale(**fields)


def test_receipt_text_includes_shop_items_and_total():
    text = render_receipt_text("Магазин Беркат", _sale(), {100: "Духи масляные 6мл"})
    assert "Магазин Беркат" in text
    assert "Чек №1" in text
    assert "Духи масляные 6мл — 2 x 250 ₽ = 500 ₽" in text
    assert "Итого: 500 ₽" in text
    assert "наличные" in text


def test_receipt_text_includes_client_name_and_discount():
    sale = _sale(discount=Money.of("50"))
    text = render_receipt_text("Магазин Беркат", sale, {100: "Товар"}, client_name="Ахмед")
    assert "Клиент: Ахмед" in text
    assert "Скидка: 50 ₽" in text
    assert "Итого: 450 ₽" in text


def test_receipt_text_labels_credit_payment():
    sale = _sale(payment_method=PaymentMethod.CREDIT, client_id=5)
    text = render_receipt_text("Магазин Беркат", sale, {100: "Товар"})
    assert "в долг" in text


def test_whatsapp_link_strips_plus_and_encodes_text():
    link = build_whatsapp_link(Phone("+79280001122"), "Привет! Ваш чек")
    assert link.startswith("https://wa.me/79280001122?text=")
    assert "+" not in link.split("?text=")[0]
    assert "%D0%9F%D1%80%D0%B8%D0%B2%D0%B5%D1%82" in link  # url-encoded «Привет»
