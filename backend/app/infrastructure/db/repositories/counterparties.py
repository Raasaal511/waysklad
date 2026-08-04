from sqlalchemy import or_, select

from app.domain.common.exceptions import NotFoundError
from app.domain.counterparties.entities import Client, Supplier
from app.domain.counterparties.repository import IClientRepository, ISupplierRepository
from app.infrastructure.db.mappers.counterparties import ClientMapper, SupplierMapper
from app.infrastructure.db.models.counterparties import ClientModel, SupplierModel
from app.infrastructure.db.repositories.base import SqlAlchemyRepository


class SqlAlchemyClientRepository(SqlAlchemyRepository, IClientRepository):
    async def add(self, client: Client) -> Client:
        model = ClientMapper.to_orm(client, self._tenant)
        self._session.add(model)
        await self._session.flush()
        client.id = model.id
        return client

    async def get(self, client_id: int) -> Client:
        model = (
            await self._session.execute(
                select(ClientModel).where(
                    ClientModel.tenant_id == self._tenant, ClientModel.id == client_id
                )
            )
        ).scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"Клиент {client_id} не найден")
        return ClientMapper.to_entity(model)

    async def search(self, query: str) -> list[Client]:
        pattern = f"%{query}%"
        models = (
            await self._session.execute(
                select(ClientModel)
                .where(
                    ClientModel.tenant_id == self._tenant,
                    or_(ClientModel.name.ilike(pattern), ClientModel.phone.ilike(pattern)),
                )
                .order_by(ClientModel.name)
                .limit(50)
            )
        ).scalars().all()
        return [ClientMapper.to_entity(m) for m in models]


class SqlAlchemySupplierRepository(SqlAlchemyRepository, ISupplierRepository):
    async def add(self, supplier: Supplier) -> Supplier:
        model = SupplierMapper.to_orm(supplier, self._tenant)
        self._session.add(model)
        await self._session.flush()
        supplier.id = model.id
        return supplier

    async def list(self) -> list[Supplier]:
        models = (
            await self._session.execute(
                select(SupplierModel)
                .where(SupplierModel.tenant_id == self._tenant)
                .order_by(SupplierModel.name)
            )
        ).scalars()
        return [SupplierMapper.to_entity(m) for m in models]
