from dataclasses import dataclass
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


@dataclass
class Warehouse:
    """Точка/склад внутри магазина."""

    id: int | None
    name: str
    address: str = ""


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
