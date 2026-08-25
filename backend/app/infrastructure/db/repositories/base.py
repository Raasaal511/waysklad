from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.domain.common.exceptions import DomainError
from app.domain.common.quantity import UNITS, Unit
from app.infrastructure.db.models.catalog import ProductModel, UnitModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


class SqlAlchemyRepository:
    """База: сессия и tenant_id берутся из UnitOfWork в момент вызова,
    поэтому регистрация магазина может выставить tenant_id после создания tenant'а."""

    def __init__(self, uow: SqlAlchemyUnitOfWork):
        self._uow = uow

    @property
    def _session(self) -> AsyncSession:
        return self._uow.session

    @property
    def _tenant(self) -> int:
        if self._uow.tenant_id is None:
            raise DomainError("Операция требует контекста магазина (tenant)")
        return self._uow.tenant_id

    async def _next_number(self, model) -> int:
        """Сквозной номер документа в пределах магазина."""
        stmt = select(func.coalesce(func.max(model.number), 0) + 1).where(
            model.tenant_id == self._tenant
        )
        return (await self._session.execute(stmt)).scalar_one()

    async def _units_map(self) -> dict[str, Unit]:
        rows = (
            await self._session.execute(
                select(UnitModel).where(UnitModel.tenant_id == self._tenant)
            )
        ).scalars()
        units = {u.code: Unit(u.code, u.name, u.fractional) for u in rows}
        return {**UNITS, **units}

    async def _product_unit_by_id(self, product_ids: set[int]) -> dict[int, Unit]:
        """Единицы измерения товаров — для восстановления Quantity в строках документов."""
        if not product_ids:
            return {}
        units = await self._units_map()
        rows = (
            await self._session.execute(
                select(ProductModel.id, ProductModel.unit_code).where(
                    ProductModel.tenant_id == self._tenant,
                    ProductModel.id.in_(product_ids),
                )
            )
        ).all()
        fallback = Unit("pcs", "шт")
        return {pid: units.get(code, fallback) for pid, code in rows}
