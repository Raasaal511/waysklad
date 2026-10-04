from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
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
        IPhoneVerificationCodeRepository,
    )
    from app.domain.debts.repository import IDebtRepository
    from app.domain.feedback.repository import IFeedbackRepository
    from app.domain.identity.telegram_verification import ITelegramVerificationRepository
    from app.domain.identity.repository import (
        ITenantRepository,
        IUserRepository,
        IWarehouseRepository,
    )
    from app.domain.inventory.repository import IStockDocumentRepository, IStockRepository
    from app.domain.marketplace.repository import IMarketplaceProductRepository
    from app.domain.notifications.push import IPushSubscriptionRepository
    from app.domain.notifications.repository import INotificationRepository
    from app.domain.orders.repository import IOrderRepository
    from app.domain.platform.repository import IPlatformBannerRepository, IPlatformCategoryRepository
    from app.domain.reviews.repository import (
        IReviewRepository,
        IReviewUploadRepository,
        IReviewVoteRepository,
    )
    from app.domain.sales.repository import ISaleRepository, ISaleReturnRepository
    from app.domain.storefront.repository import (
        IProductViewRepository,
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
    customer_phone_codes: IPhoneVerificationCodeRepository
    stock: IStockRepository
    stock_documents: IStockDocumentRepository
    sales: ISaleRepository
    sale_returns: ISaleReturnRepository
    debts: IDebtRepository
    orders: IOrderRepository
    storefront_requests: IStorefrontRequestRepository
    storefront_messages: IStorefrontMessageRepository
    product_views: IProductViewRepository
    reviews: IReviewRepository
    review_uploads: IReviewUploadRepository
    review_votes: IReviewVoteRepository
    tasks: ITaskRepository
    notifications: INotificationRepository
    push_subscriptions: IPushSubscriptionRepository
    audit: IAuditRepository
    analytics: IAnalyticsRepository
    marketplace_products: IMarketplaceProductRepository
    platform_categories: IPlatformCategoryRepository
    platform_banners: IPlatformBannerRepository
    feedback: IFeedbackRepository
    telegram_verifications: ITelegramVerificationRepository

    async def __aenter__(self) -> IUnitOfWork:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            await self.rollback()

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...

    @abstractmethod
    def after_commit(self, action: Callable[[], Awaitable[None]]) -> None:
        """Выполнить после успешного commit() в фоне, вне транзакции: внешние
        вызовы (push на телефон) не держат блокировки строк, не задерживают
        ответ и не уходят, если операция откатилась."""
        ...

    @abstractmethod
    def fork(self) -> IUnitOfWork:
        """Новый UoW того же магазина и той же БД — для фоновой работы после
        commit, когда исходная сессия уже закрыта."""
        ...
