import re
from dataclasses import dataclass
from decimal import Decimal

from app.domain.audit.entities import AuditEntry
from app.domain.common.cache import ICache
from app.domain.common.exceptions import DomainError
from app.domain.common.money import Money
from app.domain.common.phone import Phone
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Tenant
from app.domain.identity.permissions import Actor, Permission, require
from app.domain.platform.cities import is_valid_city
from app.infrastructure.cache.cache_aside import invalidate_shop_cache

# username Telegram: 5-32 символа, латиница/цифры/подчёркивание, начинается
# с буквы — то же правило, что использует сам Telegram при регистрации ника.
# Без "@" — фронт добавляет его сам при построении t.me-ссылки (промпт B2 п.1)
_TELEGRAM_USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")


@dataclass(frozen=True)
class UpdateShopCommand:
    name: str
    summary_daily_enabled: bool | None = None
    summary_weekly_enabled: bool | None = None
    summary_monthly_enabled: bool | None = None
    summary_daily_hour_msk: int | None = None
    storefront_enabled: bool | None = None
    # как и остальные Optional-поля здесь — None значит «не трогать» (тот же
    # PATCH-принцип, что у summary_*/storefront_enabled); явного способа
    # сбросить уже выбранный город на null сейчас нет — не было в промпте
    city: str | None = None
    storefront_show_stock_qty: bool | None = None
    storefront_description: str | None = None
    contact_phone: str | None = None
    contact_whatsapp: str | None = None
    contact_telegram: str | None = None
    # явный флаг сброса на null — Decimal-поле не может использовать "не
    # передано" (None) и одновременно "сбросить в null" одинаково, поэтому
    # отдельно от storefront_min_order_total (см. UpdateShopRequest)
    clear_min_order_total: bool = False
    storefront_min_order_total: Decimal | None = None
    policy_refund_money: str | None = None
    policy_payment: str | None = None
    policy_delivery: str | None = None
    policy_returns: str | None = None


class UpdateShopUseCase:
    """Владелец меняет название магазина и настройки Telegram-сводки."""

    def __init__(self, uow: IUnitOfWork, cache: ICache | None = None):
        self._uow = uow
        self._cache = cache

    async def execute(self, actor: Actor, cmd: UpdateShopCommand) -> Tenant:
        require(actor, Permission.SETTINGS_MANAGE)
        if not cmd.name.strip():
            raise DomainError("Название магазина не может быть пустым")
        if cmd.summary_daily_hour_msk is not None and not (0 <= cmd.summary_daily_hour_msk <= 23):
            raise DomainError("Час рассылки должен быть от 0 до 23")
        if cmd.city is not None and not is_valid_city(cmd.city):
            raise DomainError(f"Неизвестный город: «{cmd.city}»")
        if cmd.storefront_description is not None and len(cmd.storefront_description) > 500:
            raise DomainError("Описание магазина — не более 500 символов")
        if cmd.contact_phone:
            Phone(cmd.contact_phone)  # бросит DomainError сам, формат тот же, что у User.phone
        if cmd.contact_whatsapp:
            Phone(cmd.contact_whatsapp)
        if cmd.contact_telegram and not _TELEGRAM_USERNAME_RE.match(cmd.contact_telegram.lstrip("@")):
            raise DomainError(
                f"Некорректный username Telegram: «{cmd.contact_telegram}» "
                "(5-32 символа, латиница/цифры/подчёркивание, без «@»)"
            )
        if cmd.storefront_min_order_total is not None and cmd.storefront_min_order_total < 0:
            raise DomainError("Минимальная сумма заказа не может быть отрицательной")
        for label, text in (
            ("Возврат денег", cmd.policy_refund_money),
            ("Оплата", cmd.policy_payment),
            ("Доставка", cmd.policy_delivery),
            ("Возврат товаров", cmd.policy_returns),
        ):
            if text is not None and len(text) > 5000:
                raise DomainError(f"«{label}» — не более 5000 символов")

        async with self._uow as uow:
            tenant = await uow.tenants.get(uow.tenant_id)
            tenant.name = cmd.name.strip()
            if cmd.summary_daily_enabled is not None:
                tenant.summary_daily_enabled = cmd.summary_daily_enabled
            if cmd.summary_weekly_enabled is not None:
                tenant.summary_weekly_enabled = cmd.summary_weekly_enabled
            if cmd.summary_monthly_enabled is not None:
                tenant.summary_monthly_enabled = cmd.summary_monthly_enabled
            if cmd.summary_daily_hour_msk is not None:
                tenant.summary_daily_hour_msk = cmd.summary_daily_hour_msk
            if cmd.storefront_enabled is not None:
                tenant.storefront_enabled = cmd.storefront_enabled
            if cmd.city is not None:
                tenant.city = cmd.city
            if cmd.storefront_show_stock_qty is not None:
                tenant.storefront_show_stock_qty = cmd.storefront_show_stock_qty
            if cmd.storefront_description is not None:
                tenant.storefront_description = cmd.storefront_description.strip()
            if cmd.contact_phone is not None:
                tenant.contact_phone = str(Phone(cmd.contact_phone)) if cmd.contact_phone else ""
            if cmd.contact_whatsapp is not None:
                tenant.contact_whatsapp = (
                    str(Phone(cmd.contact_whatsapp)) if cmd.contact_whatsapp else ""
                )
            if cmd.contact_telegram is not None:
                tenant.contact_telegram = cmd.contact_telegram.lstrip("@")
            if cmd.clear_min_order_total:
                tenant.storefront_min_order_total = None
            elif cmd.storefront_min_order_total is not None:
                # квантуем до копеек тем же правилом, что Money — иначе значение,
                # введённое как "1000", отдавалось бы обратно как "1000" вместо
                # "1000.00" (несогласованно с retail_price и остальными деньгами)
                tenant.storefront_min_order_total = Money.of(cmd.storefront_min_order_total).amount
            if cmd.policy_refund_money is not None:
                tenant.policy_refund_money = cmd.policy_refund_money.strip()
            if cmd.policy_payment is not None:
                tenant.policy_payment = cmd.policy_payment.strip()
            if cmd.policy_delivery is not None:
                tenant.policy_delivery = cmd.policy_delivery.strip()
            if cmd.policy_returns is not None:
                tenant.policy_returns = cmd.policy_returns.strip()
            tenant = await uow.tenants.save(tenant)
            await uow.audit.add(AuditEntry.record(actor, "shop.update", tenant.id))
            await uow.commit()
            await invalidate_shop_cache(self._cache, uow)
            return tenant
