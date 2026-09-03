from sqlalchemy import select

from app.domain.common.exceptions import NotFoundError
from app.domain.storefront.entities import StorefrontRequest, StorefrontRequestStatus
from app.domain.storefront.repository import IStorefrontRequestRepository
from app.infrastructure.db.mappers.storefront import StorefrontRequestMapper
from app.infrastructure.db.models.storefront import StorefrontRequestModel
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
        await self._session.flush()
        return request

    async def get(self, request_id: int) -> StorefrontRequest:
        model = await self._get_model(request_id)
        if model is None:
            raise NotFoundError(f"Заявка {request_id} не найдена")
        return StorefrontRequestMapper.to_entity(model)

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

    async def _get_model(self, request_id: int) -> StorefrontRequestModel | None:
        return (
            await self._session.execute(
                select(StorefrontRequestModel).where(
                    StorefrontRequestModel.tenant_id == self._tenant,
                    StorefrontRequestModel.id == request_id,
                )
            )
        ).scalar_one_or_none()
