"""Права по ролям.

Матрица — единственный источник правды о том, кому что можно.
Use case проверяет право первой строкой: require(actor, Permission.X).
"""

from dataclasses import dataclass
from enum import StrEnum

from app.domain.common.exceptions import AccessDeniedError
from app.domain.identity.entities import Role


class Permission(StrEnum):
    PRODUCTS_VIEW = "products.view"
    PRODUCTS_MANAGE = "products.manage"
    PURCHASE_PRICES_VIEW = "purchase_prices.view"  # закупочные цены и наценка

    STOCK_VIEW = "stock.view"
    STOCK_RECEIVE = "stock.receive"
    STOCK_WRITE_OFF = "stock.write_off"
    STOCK_TRANSFER = "stock.transfer"
    STOCK_TAKE = "stock.take"  # инвентаризация

    SALES_CREATE = "sales.create"
    SALES_RETURN = "sales.return"
    SALES_EDIT = "sales.edit"  # правка клиента/заметки задним числом
    SALES_DELETE = "sales.delete"  # полный возврат + аннулирование долга — только владелец/управляющий

    DEBTS_VIEW = "debts.view"
    DEBTS_MANAGE = "debts.manage"

    ORDERS_VIEW = "orders.view"
    ORDERS_MANAGE = "orders.manage"

    TASKS_VIEW = "tasks.view"
    TASKS_MANAGE = "tasks.manage"  # свои задачи ведёт каждый сотрудник; чужие — owner/manager

    CLIENTS_VIEW = "clients.view"
    CLIENTS_MANAGE = "clients.manage"
    SUPPLIERS_MANAGE = "suppliers.manage"

    WAREHOUSES_MANAGE = "warehouses.manage"
    USERS_MANAGE = "users.manage"

    ANALYTICS_VIEW = "analytics.view"  # дашборд, прибыль — «отчёты о прибыли»
    AUDIT_VIEW = "audit.view"
    SETTINGS_MANAGE = "settings.manage"  # настройки магазина (Telegram-сводка и т.п.) — только владелец


_SELLER = {
    Permission.PRODUCTS_VIEW,
    Permission.STOCK_VIEW,
    Permission.SALES_CREATE,
    Permission.SALES_RETURN,
    Permission.DEBTS_VIEW,
    Permission.DEBTS_MANAGE,      # записывает долг и принимает погашения
    Permission.ORDERS_VIEW,
    Permission.ORDERS_MANAGE,     # принимает заказы из переписки
    Permission.CLIENTS_VIEW,
    Permission.CLIENTS_MANAGE,    # заводит клиента при продаже
    Permission.TASKS_VIEW,
    Permission.TASKS_MANAGE,      # ведёт свои задачи на доске
}

_STOREKEEPER = {
    Permission.PRODUCTS_VIEW,
    Permission.PURCHASE_PRICES_VIEW,  # приёмка требует закупочных цен
    Permission.STOCK_VIEW,
    Permission.STOCK_RECEIVE,
    Permission.STOCK_WRITE_OFF,
    Permission.STOCK_TRANSFER,
    Permission.STOCK_TAKE,
    Permission.SUPPLIERS_MANAGE,
    Permission.TASKS_VIEW,
    Permission.TASKS_MANAGE,      # ведёт свои задачи на доске (в т.ч. дозаказ)
}

_ANALYST = {
    Permission.PRODUCTS_VIEW,
    Permission.PURCHASE_PRICES_VIEW,
    Permission.STOCK_VIEW,
    Permission.DEBTS_VIEW,
    Permission.ORDERS_VIEW,
    Permission.CLIENTS_VIEW,
    Permission.ANALYTICS_VIEW,
    Permission.AUDIT_VIEW,
    Permission.TASKS_VIEW,        # видит доску, но не ведёт задачи (read-only роль)
}

# управляющий = продавец + кладовщик + управление товарами/складами/сотрудниками + аналитика
# (данные и аналитика ограничены складами, к которым привязан управляющий)
_MANAGER = _SELLER | _STOREKEEPER | {
    Permission.PRODUCTS_MANAGE,
    Permission.WAREHOUSES_MANAGE,
    Permission.USERS_MANAGE,  # но создавать может только продавцов/кладовщиков/аналитиков
    Permission.SALES_EDIT,
    Permission.SALES_DELETE,
    Permission.ANALYTICS_VIEW,
}

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OWNER: frozenset(Permission),
    Role.MANAGER: frozenset(_MANAGER),
    Role.SELLER: frozenset(_SELLER),
    Role.STOREKEEPER: frozenset(_STOREKEEPER),
    Role.ANALYST: frozenset(_ANALYST),
}


@dataclass(frozen=True, slots=True)
class Actor:
    """Кто выполняет действие — передаётся в каждый use case."""

    id: int
    role: Role
    # склады, к которым привязан актор (manager/seller/storekeeper) — данные фильтруются
    # по этому списку; None — без ограничения (owner/analyst, видят весь tenant)
    warehouse_ids: list[int] | None = None

    @property
    def is_warehouse_scoped(self) -> bool:
        """True, если данные актора нужно фильтровать по его складам."""
        return self.warehouse_ids is not None


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS[role]


def require(actor: Actor, permission: Permission) -> None:
    if not has_permission(actor.role, permission):
        raise AccessDeniedError(f"Роль «{actor.role}» не имеет права «{permission}»")


def require_warehouse(actor: Actor, warehouse_id: int) -> None:
    """Проверка, что документ/склад входит в зону видимости актора."""
    if actor.is_warehouse_scoped and warehouse_id not in actor.warehouse_ids:
        raise AccessDeniedError("Этот склад вам не назначен")
