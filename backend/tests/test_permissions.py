import pytest

from app.domain.common.exceptions import AccessDeniedError
from app.domain.identity.entities import Role
from app.domain.identity.permissions import (
    ROLE_PERMISSIONS,
    Actor,
    Permission,
    has_permission,
    require,
)


def test_owner_has_all_permissions():
    assert ROLE_PERMISSIONS[Role.OWNER] == frozenset(Permission)


def test_seller_cannot_manage_products_or_see_purchase_prices():
    assert not has_permission(Role.SELLER, Permission.PRODUCTS_MANAGE)
    assert not has_permission(Role.SELLER, Permission.PURCHASE_PRICES_VIEW)
    assert not has_permission(Role.SELLER, Permission.ANALYTICS_VIEW)
    assert has_permission(Role.SELLER, Permission.SALES_CREATE)
    assert has_permission(Role.SELLER, Permission.DEBTS_MANAGE)


def test_manager_has_no_profit_reports():
    assert not has_permission(Role.MANAGER, Permission.ANALYTICS_VIEW)
    assert not has_permission(Role.MANAGER, Permission.AUDIT_VIEW)
    assert has_permission(Role.MANAGER, Permission.PRODUCTS_MANAGE)
    assert has_permission(Role.MANAGER, Permission.USERS_MANAGE)


def test_storekeeper_manages_stock_but_not_sales():
    assert has_permission(Role.STOREKEEPER, Permission.STOCK_RECEIVE)
    assert has_permission(Role.STOREKEEPER, Permission.STOCK_TAKE)
    assert not has_permission(Role.STOREKEEPER, Permission.SALES_CREATE)


def test_analyst_is_read_only():
    for permission in ROLE_PERMISSIONS[Role.ANALYST]:
        assert permission.value.endswith(".view"), f"{permission} — не read-only"


def test_require_raises_for_missing_permission():
    seller = Actor(id=1, role=Role.SELLER)
    with pytest.raises(AccessDeniedError):
        require(seller, Permission.PRODUCTS_MANAGE)
    require(seller, Permission.SALES_CREATE)  # не бросает


def test_storekeeper_cannot_manage_debts_clients_or_orders():
    assert not has_permission(Role.STOREKEEPER, Permission.DEBTS_MANAGE)
    assert not has_permission(Role.STOREKEEPER, Permission.ORDERS_MANAGE)
    assert not has_permission(Role.STOREKEEPER, Permission.CLIENTS_MANAGE)


def test_manager_is_superset_of_seller_and_storekeeper():
    combined = ROLE_PERMISSIONS[Role.SELLER] | ROLE_PERMISSIONS[Role.STOREKEEPER]
    assert combined <= ROLE_PERMISSIONS[Role.MANAGER]


@pytest.mark.parametrize("role", list(Role))
def test_require_never_raises_for_permissions_the_role_has(role):
    actor = Actor(id=1, role=role)
    for permission in ROLE_PERMISSIONS[role]:
        require(actor, permission)  # не должно бросать ни для одного разрешённого права
