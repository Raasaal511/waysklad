from dataclasses import dataclass

from app.domain.audit.entities import AuditEntry
from app.domain.common.cache import ICache
from app.domain.common.exceptions import DomainError
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Tenant
from app.domain.identity.permissions import Actor, Permission, require
from app.domain.platform.cities import is_valid_city
from app.infrastructure.cache.cache_aside import invalidate_shop_cache


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
            tenant = await uow.tenants.save(tenant)
            await uow.audit.add(AuditEntry.record(actor, "shop.update", tenant.id))
            await uow.commit()
            await invalidate_shop_cache(self._cache, uow)
            return tenant
