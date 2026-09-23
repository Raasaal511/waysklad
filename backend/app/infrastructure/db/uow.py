from __future__ import annotations

from app.domain.common.uow import IUnitOfWork
from app.infrastructure.db.repositories.analytics import SqlAlchemyAnalyticsRepository
from app.infrastructure.db.repositories.audit import SqlAlchemyAuditRepository
from app.infrastructure.db.repositories.catalog import (
    SqlAlchemyCategoryRepository,
    SqlAlchemyProductRepository,
    SqlAlchemyUnitRepository,
)
from app.infrastructure.db.repositories.counterparties import (
    SqlAlchemyClientRepository,
    SqlAlchemySupplierRepository,
)
from app.infrastructure.db.repositories.customers import (
    SqlAlchemyCustomerLoginLinkRepository,
    SqlAlchemyCustomerRepository,
    SqlAlchemyPhoneVerificationCodeRepository,
)
from app.infrastructure.db.repositories.debts import SqlAlchemyDebtRepository
from app.infrastructure.db.repositories.feedback import SqlAlchemyFeedbackRepository
from app.infrastructure.db.repositories.identity import (
    SqlAlchemyTenantRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyWarehouseRepository,
)
from app.infrastructure.db.repositories.inventory import (
    SqlAlchemyStockDocumentRepository,
    SqlAlchemyStockRepository,
)
from app.infrastructure.db.repositories.marketplace import SqlAlchemyMarketplaceProductRepository
from app.infrastructure.db.repositories.notifications import SqlAlchemyNotificationRepository
from app.infrastructure.db.repositories.orders import SqlAlchemyOrderRepository
from app.infrastructure.db.repositories.platform import (
    SqlAlchemyPlatformBannerRepository,
    SqlAlchemyPlatformCategoryRepository,
)
from app.infrastructure.db.repositories.reviews import (
    SqlAlchemyReviewRepository,
    SqlAlchemyReviewUploadRepository,
    SqlAlchemyReviewVoteRepository,
)
from app.infrastructure.db.repositories.sales import (
    SqlAlchemySaleRepository,
    SqlAlchemySaleReturnRepository,
)
from app.infrastructure.db.repositories.storefront import (
    SqlAlchemyProductViewRepository,
    SqlAlchemyStorefrontMessageRepository,
    SqlAlchemyStorefrontRequestRepository,
)
from app.infrastructure.db.repositories.tasks import SqlAlchemyTaskRepository
from app.infrastructure.db.session import SessionLocal


class SqlAlchemyUnitOfWork(IUnitOfWork):
    """Транзакция + репозитории, привязанные к tenant_id текущего пользователя.

    tenant_id = None допустим только для регистрации магазина: после
    uow.tenants.add(...) сценарий обязан выставить uow.tenant_id = tenant.id.
    """

    def __init__(self, tenant_id: int | None, session_factory=SessionLocal):
        self.tenant_id = tenant_id
        self._session_factory = session_factory

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        self.session = self._session_factory()
        self.tenants = SqlAlchemyTenantRepository(self)
        self.users = SqlAlchemyUserRepository(self)
        self.warehouses = SqlAlchemyWarehouseRepository(self)
        self.products = SqlAlchemyProductRepository(self)
        self.units = SqlAlchemyUnitRepository(self)
        self.categories = SqlAlchemyCategoryRepository(self)
        self.clients = SqlAlchemyClientRepository(self)
        self.suppliers = SqlAlchemySupplierRepository(self)
        self.customers = SqlAlchemyCustomerRepository(self)
        self.customer_login_links = SqlAlchemyCustomerLoginLinkRepository(self)
        self.customer_phone_codes = SqlAlchemyPhoneVerificationCodeRepository(self)
        self.stock = SqlAlchemyStockRepository(self)
        self.stock_documents = SqlAlchemyStockDocumentRepository(self)
        self.sales = SqlAlchemySaleRepository(self)
        self.sale_returns = SqlAlchemySaleReturnRepository(self)
        self.debts = SqlAlchemyDebtRepository(self)
        self.orders = SqlAlchemyOrderRepository(self)
        self.storefront_requests = SqlAlchemyStorefrontRequestRepository(self)
        self.storefront_messages = SqlAlchemyStorefrontMessageRepository(self)
        self.product_views = SqlAlchemyProductViewRepository(self)
        self.reviews = SqlAlchemyReviewRepository(self)
        self.review_uploads = SqlAlchemyReviewUploadRepository(self)
        self.review_votes = SqlAlchemyReviewVoteRepository(self)
        self.tasks = SqlAlchemyTaskRepository(self)
        self.notifications = SqlAlchemyNotificationRepository(self)
        self.audit = SqlAlchemyAuditRepository(self)
        self.analytics = SqlAlchemyAnalyticsRepository(self)
        self.marketplace_products = SqlAlchemyMarketplaceProductRepository(self.session)
        self.platform_categories = SqlAlchemyPlatformCategoryRepository(self.session)
        self.platform_banners = SqlAlchemyPlatformBannerRepository(self.session)
        self.feedback = SqlAlchemyFeedbackRepository(self.session)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await super().__aexit__(exc_type, exc, tb)
        await self.session.close()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
