from sqlalchemy import exists, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.domain.common.exceptions import NotFoundError
from app.domain.counterparties.entities import Client, Supplier
from app.domain.counterparties.repository import IClientRepository, ISupplierRepository
from app.infrastructure.db.mappers.counterparties import ClientMapper, SupplierMapper
from app.infrastructure.db.models.counterparties import (
    ClientModel,
    SupplierModel,
    WarehouseClientLinkModel,
    WarehouseSupplierLinkModel,
)
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

    async def search(
        self,
        query: str,
        include_inactive: bool = False,
        warehouse_ids: list[int] | None = None,
    ) -> list[Client]:
        pattern = f"%{query}%"
        conditions = [
            ClientModel.tenant_id == self._tenant,
            or_(ClientModel.name.ilike(pattern), ClientModel.phone.ilike(pattern)),
        ]
        if not include_inactive:
            conditions.append(ClientModel.is_active.is_(True))
        if warehouse_ids is not None:
            conditions.append(
                exists().where(
                    WarehouseClientLinkModel.client_id == ClientModel.id,
                    WarehouseClientLinkModel.warehouse_id.in_(warehouse_ids),
                )
            )
        models = (
            await self._session.execute(
                select(ClientModel).where(*conditions).order_by(ClientModel.name).limit(50)
            )
        ).scalars().all()
        return [ClientMapper.to_entity(m) for m in models]

    async def save(self, client: Client) -> Client:
        model = (
            await self._session.execute(
                select(ClientModel).where(
                    ClientModel.tenant_id == self._tenant, ClientModel.id == client.id
                )
            )
        ).scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"Клиент {client.id} не найден")
        model.name = client.name
        model.phone = str(client.phone) if client.phone else ""
        model.whatsapp = str(client.whatsapp) if client.whatsapp else ""
        model.city = client.city
        model.debt_limit = client.debt_limit.amount if client.debt_limit else None
        model.is_active = client.is_active
        await self._session.flush()
        return client

    async def get_by_phone(self, phone: str) -> Client | None:
        if not phone:
            return None
        model = (
            await self._session.execute(
                select(ClientModel).where(
                    ClientModel.tenant_id == self._tenant, ClientModel.phone == phone
                )
            )
        ).scalar_one_or_none()
        return ClientMapper.to_entity(model) if model else None

    async def link_to_warehouse(self, client_id: int, warehouse_id: int) -> None:
        # tenant-изоляция транзитивна через warehouse_id/client_id (как и в
        # WarehouseAssignmentModel) — caller уже провалидировал оба id в своём tenant
        stmt = (
            pg_insert(WarehouseClientLinkModel)
            .values(warehouse_id=warehouse_id, client_id=client_id)
            .on_conflict_do_nothing(index_elements=["warehouse_id", "client_id"])
        )
        await self._session.execute(stmt)


class SqlAlchemySupplierRepository(SqlAlchemyRepository, ISupplierRepository):
    async def add(self, supplier: Supplier) -> Supplier:
        model = SupplierMapper.to_orm(supplier, self._tenant)
        self._session.add(model)
        await self._session.flush()
        supplier.id = model.id
        return supplier

    async def get(self, supplier_id: int) -> Supplier:
        model = (
            await self._session.execute(
                select(SupplierModel).where(
                    SupplierModel.tenant_id == self._tenant, SupplierModel.id == supplier_id
                )
            )
        ).scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"Поставщик {supplier_id} не найден")
        return SupplierMapper.to_entity(model)

    async def list(self, warehouse_ids: list[int] | None = None) -> list[Supplier]:
        conditions = [SupplierModel.tenant_id == self._tenant]
        if warehouse_ids is not None:
            conditions.append(
                exists().where(
                    WarehouseSupplierLinkModel.supplier_id == SupplierModel.id,
                    WarehouseSupplierLinkModel.warehouse_id.in_(warehouse_ids),
                )
            )
        models = (
            await self._session.execute(
                select(SupplierModel).where(*conditions).order_by(SupplierModel.name)
            )
        ).scalars()
        return [SupplierMapper.to_entity(m) for m in models]

    async def link_to_warehouse(self, supplier_id: int, warehouse_id: int) -> None:
        stmt = (
            pg_insert(WarehouseSupplierLinkModel)
            .values(warehouse_id=warehouse_id, supplier_id=supplier_id)
            .on_conflict_do_nothing(index_elements=["warehouse_id", "supplier_id"])
        )
        await self._session.execute(stmt)
