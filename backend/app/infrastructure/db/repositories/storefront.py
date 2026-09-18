from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.domain.common.exceptions import NotFoundError
from app.domain.storefront.entities import (
    StorefrontMessage,
    StorefrontRequest,
    StorefrontRequestStatus,
)
from app.domain.storefront.repository import (
    IProductViewRepository,
    IStorefrontMessageRepository,
    IStorefrontRequestRepository,
)
from app.infrastructure.db.mappers.storefront import (
    StorefrontMessageMapper,
    StorefrontRequestMapper,
)
from app.infrastructure.db.models.storefront import (
    ProductViewDailyModel,
    StorefrontMessageModel,
    StorefrontRequestModel,
)
from app.infrastructure.db.repositories.base import SqlAlchemyRepository


class SqlAlchemyStorefrontRequestRepository(SqlAlchemyRepository, IStorefrontRequestRepository):
    async def add(self, request: StorefrontRequest) -> StorefrontRequest:
        model = StorefrontRequestMapper.to_orm(request, self._tenant)
        self._session.add(model)
        await self._session.flush()
        request.id = model.id
        return request

    async def save(self, request: StorefrontRequest) -> StorefrontRequest:
        model = await self._get_model(request.id)
        if model is None:
            raise NotFoundError(f"Заявка {request.id} не найдена")
        model.status = request.status
        model.order_id = request.order_id
        model.insufficient_stock_at_request = request.insufficient_stock_at_request
        model.reservation_released = request.reservation_released
        await self._session.flush()
        return request

    async def get(self, request_id: int) -> StorefrontRequest:
        model = await self._get_model(request_id)
        if model is None:
            raise NotFoundError(f"Заявка {request_id} не найдена")
        return StorefrontRequestMapper.to_entity(model)

    async def get_by_token(self, access_token: str) -> StorefrontRequest | None:
        # без tenant-фильтра: вызывается анонимным покупателем ДО того, как
        # известен tenant — токен сам по себе доказательство владения заявкой,
        # как и Tenant.slug при резолве магазина
        model = (
            await self._session.execute(
                select(StorefrontRequestModel).where(
                    StorefrontRequestModel.access_token == access_token
                )
            )
        ).scalar_one_or_none()
        if model is None:
            return None
        entity = StorefrontRequestMapper.to_entity(model)
        entity.tenant_id = model.tenant_id
        return entity

    async def list_by_customer(self, customer_id: int) -> list[StorefrontRequest]:
        # без tenant-фильтра: покупатель — сущность платформы, его заявки
        # могут лежать в разных магазинах разом (тот же смысл, что у
        # get_by_token — доступ доказан не принадлежностью к tenant'у сессии)
        models = (
            await self._session.execute(
                select(StorefrontRequestModel)
                .where(StorefrontRequestModel.customer_id == customer_id)
                .order_by(StorefrontRequestModel.created_at.desc())
            )
        ).scalars().all()
        entities = []
        for m in models:
            entity = StorefrontRequestMapper.to_entity(m)
            entity.tenant_id = m.tenant_id
            entities.append(entity)
        return entities

    async def list_new(self) -> list[StorefrontRequest]:
        models = (
            await self._session.execute(
                select(StorefrontRequestModel)
                .where(
                    StorefrontRequestModel.tenant_id == self._tenant,
                    StorefrontRequestModel.status == StorefrontRequestStatus.NEW,
                )
                .order_by(StorefrontRequestModel.created_at)
            )
        ).scalars().all()
        return [StorefrontRequestMapper.to_entity(m) for m in models]

    async def list_stale_reserved(self, older_than: datetime) -> list[StorefrontRequest]:
        models = (
            await self._session.execute(
                select(StorefrontRequestModel).where(
                    StorefrontRequestModel.tenant_id == self._tenant,
                    StorefrontRequestModel.status == StorefrontRequestStatus.NEW,
                    StorefrontRequestModel.reservation_released.is_(False),
                    StorefrontRequestModel.created_at < older_than,
                )
            )
        ).scalars().all()
        return [StorefrontRequestMapper.to_entity(m) for m in models]

    async def count_new_by_phone(self, phone: str) -> int:
        return (
            await self._session.execute(
                select(func.count())
                .select_from(StorefrontRequestModel)
                .where(
                    StorefrontRequestModel.tenant_id == self._tenant,
                    StorefrontRequestModel.customer_phone == phone,
                    StorefrontRequestModel.status == StorefrontRequestStatus.NEW,
                )
            )
        ).scalar_one()

    async def count_accepted(self) -> int:
        return (
            await self._session.execute(
                select(func.count())
                .select_from(StorefrontRequestModel)
                .where(
                    StorefrontRequestModel.tenant_id == self._tenant,
                    StorefrontRequestModel.status == StorefrontRequestStatus.ACCEPTED,
                )
            )
        ).scalar_one()

    async def _get_model(self, request_id: int) -> StorefrontRequestModel | None:
        return (
            await self._session.execute(
                select(StorefrontRequestModel).where(
                    StorefrontRequestModel.tenant_id == self._tenant,
                    StorefrontRequestModel.id == request_id,
                )
            )
        ).scalar_one_or_none()


class SqlAlchemyStorefrontMessageRepository(SqlAlchemyRepository, IStorefrontMessageRepository):
    async def add(self, message: StorefrontMessage) -> StorefrontMessage:
        model = StorefrontMessageMapper.to_orm(message, self._tenant)
        self._session.add(model)
        await self._session.flush()
        message.id = model.id
        message.created_at = model.created_at
        return message

    async def list_by_request(self, request_id: int) -> list[StorefrontMessage]:
        models = (
            await self._session.execute(
                select(StorefrontMessageModel)
                .where(
                    StorefrontMessageModel.tenant_id == self._tenant,
                    StorefrontMessageModel.request_id == request_id,
                )
                .order_by(StorefrontMessageModel.created_at)
            )
        ).scalars().all()
        return [StorefrontMessageMapper.to_entity(m) for m in models]


class SqlAlchemyProductViewRepository(SqlAlchemyRepository, IProductViewRepository):
    async def record_view(self, product_id: int, day: date) -> None:
        stmt = pg_insert(ProductViewDailyModel).values(
            tenant_id=self._tenant, product_id=product_id, day=day, count=1
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["tenant_id", "product_id", "day"],
            set_={"count": ProductViewDailyModel.count + 1},
        )
        await self._session.execute(stmt)

    async def views_since(self, product_id: int, since: date) -> int:
        total = (
            await self._session.execute(
                select(func.coalesce(func.sum(ProductViewDailyModel.count), 0)).where(
                    ProductViewDailyModel.tenant_id == self._tenant,
                    ProductViewDailyModel.product_id == product_id,
                    ProductViewDailyModel.day >= since,
                )
            )
        ).scalar_one()
        return int(total)
