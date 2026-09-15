from decimal import Decimal

from app.domain.catalog.entities import Product


def catalog_page_text(shop_name: str, offset: int, total: int) -> str:
    if total == 0:
        return f"<b>{shop_name}</b>\n\nПока нет товаров в каталоге."
    shown_from = offset + 1
    shown_to = min(offset + 8, total)
    return f"<b>{shop_name}</b>\n\nТовары {shown_from}–{shown_to} из {total}:"


def product_card_text(product: Product, in_stock: bool) -> str:
    lines = [f"<b>{product.name}</b>", f"Цена: {product.retail_price.amount} ₽"]
    if product.sku:
        lines.append(f"Артикул: {product.sku}")
    lines.append("В наличии" if in_stock else "Сейчас нет в наличии")
    if product.storefront_min_qty:
        lines.append(f"Минимальный заказ: {product.storefront_min_qty}")
    if product.storefront_step_qty:
        lines.append(f"Шаг заказа: {product.storefront_step_qty}")
    return "\n".join(lines)


def quantity_prompt_text(product_name: str, quantity: Decimal) -> str:
    return f"«{product_name}» — количество: <b>{quantity}</b>"


def confirmation_text(product_name: str, quantity: Decimal, name: str, phone: str) -> str:
    phone_line = phone or "не указан"
    return (
        f"Проверьте заявку:\n\n"
        f"Товар: <b>{product_name}</b>\n"
        f"Количество: <b>{quantity}</b>\n"
        f"Имя: {name}\n"
        f"Телефон: {phone_line}"
    )
