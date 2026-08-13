from decimal import Decimal
from typing import Protocol

from app.domain.inventory.entities import StockDocument, StockItem


class IStockRepository(Protocol):
    async def get(self, product_id: int, warehouse_id: int, variant_id: int | None = None) -> Decimal: ...

    async def change(
        self, product_id: int, warehouse_id: int, delta: Decimal, variant_id: int | None = None
    ) -> Decimal:
        """Изменить остаток, вернуть новое значение. Отрицательный итог допустим
        только при накате офлайн-очереди («сервер прав, продажи докатываются»)."""
        ...

    async def list_all(self) -> list[StockItem]:
        """Все ненулевые остатки по всем складам/товарам — для экрана «Остатки»."""
        ...


class IStockDocumentRepository(Protocol):
    async def add(self, document: StockDocument) -> StockDocument: ...

    async def list_all(self, warehouse_ids: list[int] | None = None) -> list[StockDocument]:
        """История документов движения, новые сначала. warehouse_ids=None — без
        ограничения по складу (owner/analyst); иначе — только документы, где склад
        документа (источник или получатель при перемещении) входит в список."""
        ...
