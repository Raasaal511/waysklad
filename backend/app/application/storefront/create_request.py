import secrets
from dataclasses import dataclass, field
from decimal import Decimal

from app.application.storefront.reservation import reserve_request_stock
from app.application.tasks.notify import notify_user
from app.domain.catalog.entities import Product
from app.domain.common.exceptions import DomainError
from app.domain.common.money import format_rub
from app.domain.identity.entities import Role
from app.domain.notifications.entities import NotificationKind
from app.domain.storefront.entities import StorefrontRequest, StorefrontRequestLine
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

# защита от заспамливания списка заявок владельца — не более этого числа
# ещё не обработанных заявок одновременно с одного телефона на один магазин
_MAX_PENDING_REQUESTS_PER_PHONE = 5


def _goods_count(n: int) -> str:
    """«1 товар», «3 товара», «11 товаров» — текст уведомления видно на экране
    блокировки, «1 товаров» там режет глаз."""
    if n % 10 == 1 and n % 100 != 11:
        word = "товар"
    elif n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        word = "товара"
    else:
        word = "товаров"
    return f"{n} {word}"


def _line_unit_price(product: Product, variant_id: int | None) -> Decimal:
    """Цена строки заявки — цена варианта, если задана, иначе retail_price
    товара (тот же приоритет, что у StorefrontProductVariantResponse.price
    на витрине). До промпта B2 сумма заявки везде считалась по retail_price
    товара, игнорируя цену варианта — расхождение с тем, что видит покупатель
    на карточке товара, исправлено попутно вместе с проверкой минимальной суммы."""
    if variant_id is not None:
        variant = next((v for v in product.variants if v.id == variant_id), None)
        if variant is not None and variant.price is not None:
            return variant.price.amount
    return product.retail_price.amount


def _validate_storefront_quantity(product: Product, quantity: Decimal) -> None:
    """Мин. количество и шаг заказа — ограничения только для заявки с витрины
    (Product.storefront_min_qty/step_qty), обычная продажа/заказ их не знают."""
    min_qty = product.storefront_min_qty
    step_qty = product.storefront_step_qty
    if min_qty is not None and quantity < min_qty:
        raise DomainError(f"«{product.name}»: минимальное количество для заказа — {min_qty}")
    if step_qty is not None:
        base = min_qty or Decimal("0")
        if (quantity - base) % step_qty != 0:
            raise DomainError(f"«{product.name}»: количество должно кратно увеличиваться на {step_qty}")


@dataclass(frozen=True)
class StorefrontRequestItemInput:
    product_id: int
    quantity: Decimal
    variant_id: int | None = None


@dataclass(frozen=True)
class CreateStorefrontRequestCommand:
    slug: str
    customer_id: int  # авторизованный покупатель — см. CurrentCustomerDep
    customer_name: str
    items: list[StorefrontRequestItemInput] = field(default_factory=list)
    note: str = ""
    customer_telegram_chat_id: str = ""  # заполнено, только если заявка из Telegram-бота витрины


class CreateStorefrontRequestUseCase:
    """Публичная (без авторизации) заявка с витрины — без даты готовности и
    привязки к конкретному складу (склад выбирает владелец при принятии), но
    сразу мягко резервирует остаток на видимых складах, чтобы товар не ушёл
    другому покупателю, пока заявка ждёт ответа. Резерв снимается принятием/
    отклонением или авто-освобождением через 72ч (см. app/infrastructure/scheduler.py)."""

    def __init__(self, session_factory, notifier=None):
        self._session_factory = session_factory
        self._notifier = notifier

    async def execute(self, cmd: CreateStorefrontRequestCommand) -> StorefrontRequest | None:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as public_uow:
            tenant = await public_uow.tenants.get_by_slug(cmd.slug)
            customer = await public_uow.customers.get(cmd.customer_id)
        if tenant is None or not tenant.storefront_enabled:
            return None

        phone = customer.phone

        async with SqlAlchemyUnitOfWork(tenant.id, session_factory=self._session_factory) as uow:
            pending = await uow.storefront_requests.count_new_by_phone(str(phone))
            if pending >= _MAX_PENDING_REQUESTS_PER_PHONE:
                raise DomainError(
                    "У вас уже есть необработанные заявки — дождитесь ответа магазина"
                )

            products_by_id: dict[int, Product] = {}
            quantity_by_product: dict[int, Decimal] = {}
            for item in cmd.items:
                product = products_by_id.get(item.product_id) or await uow.products.get(item.product_id)
                if not product.show_on_storefront:
                    raise DomainError(f"Товар «{product.name}» недоступен на витрине")
                if item.variant_id is not None and not any(
                    v.id == item.variant_id for v in product.variants
                ):
                    raise DomainError(f"«{product.name}»: указанный вариант не найден")
                products_by_id[item.product_id] = product
                quantity_by_product[item.product_id] = (
                    quantity_by_product.get(item.product_id, Decimal("0")) + item.quantity
                )
            # мин.кол-во и шаг — суммарно по товару, а не по каждой строке
            # (варианту) отдельно: заказ 5 шт размера M + 5 шт размера L —
            # это 10 штук одной модели, а не два заказа по 5
            for product_id, total_quantity in quantity_by_product.items():
                _validate_storefront_quantity(products_by_id[product_id], total_quantity)

            # сумма по серверным ценам, с учётом цены варианта (промпт B2 п.4) —
            # считаем до создания заявки, чтобы не резервировать остаток впустую,
            # если сумма всё равно не пройдёт проверку минимального заказа
            total_amount = sum(
                (
                    _line_unit_price(products_by_id[item.product_id], item.variant_id) * item.quantity
                    for item in cmd.items
                ),
                Decimal("0"),
            )
            if (
                tenant.storefront_min_order_total is not None
                and total_amount < tenant.storefront_min_order_total
            ):
                # normalize() без формата "f" даёт экспоненциальную запись для
                # круглых чисел (Decimal("1000").normalize() -> "1E+3") — используем
                # ":f", как и остальные денежные DomainError в проекте (без
                # разделителя тысяч, общего хелпера форматирования денег в
                # кодовой базе нет, не изобретаем его здесь)
                min_total = tenant.storefront_min_order_total.normalize()
                raise DomainError(f"Минимальная сумма заказа в этом магазине — {format_rub(min_total)}")

            request = StorefrontRequest(
                id=None,
                customer_name=cmd.customer_name.strip(),
                customer_id=cmd.customer_id,
                customer_phone=str(phone),
                customer_telegram_chat_id=cmd.customer_telegram_chat_id,
                note=cmd.note.strip(),
                access_token=secrets.token_urlsafe(32),
                lines=[
                    StorefrontRequestLine(
                        product_id=item.product_id,
                        variant_id=item.variant_id,
                        quantity=item.quantity,
                    )
                    for item in cmd.items
                ],
            )
            request.validate()

            visible_warehouse_ids = {
                w.id for w in await uow.warehouses.list() if w.show_on_storefront
            }
            request.insufficient_stock_at_request = not await reserve_request_stock(
                uow, request.lines, visible_warehouse_ids
            )

            await uow.storefront_requests.add(request)

            recipients = [
                u for u in await uow.users.list_by_tenant() if u.role in (Role.OWNER, Role.MANAGER)
            ]
            for user in recipients:
                await notify_user(
                    uow, self._notifier,
                    user_id=user.id,
                    kind=NotificationKind.STOREFRONT_REQUEST_NEW,
                    text=(
                        f"Новая заявка с витрины: {request.customer_name}, "
                        f"{_goods_count(len(request.lines))} на сумму {format_rub(total_amount)}"
                    ),
                    link="/orders/storefront-requests",
                    entity_id=request.id,
                )

            await uow.commit()
            return request
