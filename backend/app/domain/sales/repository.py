from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Protocol

from app.domain.sales.entities import Sale, SaleReturn
from app.domain.sales.payment import PaymentMethod


class ISaleRepository(Protocol):
    async def add(self, sale: Sale) -> Sale: ...
    async def get(self, sale_id: int) -> Sale: ...
    async def get_by_client_op_id(self, client_op_id: str) -> Sale | None: ...
    async def list(
        self,
        limit: int = 50,
        offset: int = 0,
        client_id: int | None = None,
        product_id: int | None = None,
        warehouse_id: int | None = None,
        warehouse_ids: list[int] | None = None,
        payment_method: PaymentMethod | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        sort: str = "date_desc",
    ) -> tuple[list[Sale], int]: ...

    async def summary_by_payment_method(
        self,
        warehouse_id: int | None = None,
        warehouse_ids: list[int] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[PaymentMethod, tuple[int, Decimal]]:
        """Кол-во и сумма продаж за период по каждому способу оплаты — для сводной
        панели «Итого», которая показывает все способы одновременно вне зависимости
        от того, какой способ выбран в фильтре списка."""
        ...

    async def save(self, sale: Sale) -> None: ...


class ISaleReturnRepository(Protocol):
    async def add(self, sale_return: SaleReturn) -> SaleReturn: ...
    async def list_by_sale(self, sale_id: int) -> list[SaleReturn]: ...
