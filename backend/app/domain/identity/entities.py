from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.common.phone import Phone


class Role(StrEnum):
    """Права уточняются в use case'ах; здесь — базовое разделение."""

    OWNER = "owner"              # владелец: всё, включая закупочные цены и прибыль
    MANAGER = "manager"          # управляющий: товары, приёмки, заказы, продавцы; без отчётов о прибыли
    SELLER = "seller"            # продавец: продажи, остатки; не видит закупочные цены
    STOREKEEPER = "storekeeper"  # кладовщик: приёмка, списание, перемещение, инвентаризация
    ANALYST = "analyst"          # аналитик/бухгалтер: отчёты и журналы, только чтение


@dataclass
class Tenant:
    """Магазин — единица изоляции данных."""

    id: int | None
    name: str
    # публичный URL витрины (waysklad.ru/<slug>); None — пока не сгенерирован
    slug: str | None = None
    storefront_enabled: bool = False
    owner_telegram_chat_id: str | None = None
    summary_daily_enabled: bool = True
    summary_weekly_enabled: bool = False
    summary_monthly_enabled: bool = False
    summary_daily_hour_msk: int = 20


@dataclass
class Warehouse:
    """Точка/склад внутри магазина."""

    id: int | None
    name: str
    address: str = ""
    # сотрудники (manager/seller/storekeeper), которым разрешена работа с этим складом —
    # данные (продажи, остатки, аналитика) для них фильтруются по этому списку;
    # owner имеет доступ ко всем складам магазина вне зависимости от списка
    assigned_user_ids: list[int] = field(default_factory=list)
    show_on_storefront: bool = False  # видимость на публичной витрине — по умолчанию скрыт

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "assigned_user_ids": self.assigned_user_ids,
            "show_on_storefront": self.show_on_storefront,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Warehouse":
        return cls(
            id=d["id"],
            name=d["name"],
            address=d["address"],
            assigned_user_ids=d["assigned_user_ids"],
            show_on_storefront=d["show_on_storefront"],
        )


@dataclass
class User:
    id: int | None
    name: str
    phone: Phone
    role: Role
    password_hash: str = ""
    is_active: bool = True
    # identity — единственный контекст, знающий о tenant: без этого логин
    # не может определить, в какой магазин входит пользователь
    tenant_id: int | None = None
    # инкрементируется при смене пароля/разлогине со всех устройств — токены
    # с прежним значением перестают проходить проверку
    token_version: int = 0
