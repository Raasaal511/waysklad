from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.analytics.repository import IAnalyticsRepository
    from app.domain.audit.repository import IAuditRepository
    from app.domain.catalog.repository import (
        ICategoryRepository,
        IProductRepository,
        IUnitRepository,
    )
    from app.domain.counterparties.repository import IClientRepository, ISupplierRepository
    from app.domain.customers.repository import (
        ICustomerLoginLinkRepository,
        ICustomerRepository,
    )
    from app.domain.debts.repository import IDebtRepository
    from app.domain.identity.repository import (
        ITenantRepository,
        IUserRepository,
        IWarehouseRepository,
    )
    from app.domain.inventory.repository import IStockDocumentRepository, IStockRepository
    from app.domain.marketplace.repository import IMarketplaceProductRepository
    from app.domain.notifications.repository import INotificationRepository
    from app.domain.orders.repository import IOrderRepository
    from app.domain.sales.repository import ISaleRepository, ISaleReturnRepository
    from app.domain.storefront.repository import (
        IStorefrontMessageRepository,
        IStorefrontRequestRepository,
    )
    from app.domain.tasks.repository import ITaskRepository


class IUnitOfWork(ABC):
    """Одна бизнес-операция = одна транзакция.

    Реализация (infrastructure/db/uow.py) открывает сессию и отдаёт
    репозитории, уже привязанные к текущему tenant_id.
    tenant_id = None допустим только для регистрации магазина.
    """

    tenant_id: int | None

    tenants: ITenantRepository
    users: IUserRepository
    warehouses: IWarehouseRepository
    products: IProductRepository
    units: IUnitRepository
    categories: ICategoryRepository
    clients: IClientRepository
    suppliers: ISupplierRepository
    customers: ICustomerRepository
    customer_login_links: ICustomerLoginLinkRepository
    stock: IStockRepository
    stock_documents: IStockDocumentRepository
    sales: ISaleRepository
    sale_returns: ISaleReturnRepository
    debts: IDebtRepository
    orders: IOrderRepository
    storefront_requests: IStorefrontRequestRepository
    storefront_messages: IStorefrontMessageRepository
    tasks: ITaskRepository
    notifications: INotificationRepository
    audit: IAuditRepository
    analytics: IAnalyticsRepository
    marketplace_products: IMarketplaceProductRepository

    async def __aenter__(self) -> IUnitOfWork:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            await self.rollback()

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...
