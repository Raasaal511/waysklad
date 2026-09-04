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

    async def reserve(
        self, product_id: int, warehouse_id: int, delta: Decimal, variant_id: int | None = None
    ) -> Decimal:
        """Изменить резерв (под заказ) на delta, вернуть новый reserved. Отрицательный
        delta — снять резерв (отмена/выдача/редактирование заказа). Как и change(),
        сам не проверяет превышение quantity — это делает вызывающий use case,
        сверяя результат с uow.stock.get(...) (см. CreateOrderUseCase)."""
        ...

    async def get_reserved(
        self, product_id: int, warehouse_id: int, variant_id: int | None = None
    ) -> Decimal:
        """Текущий резерв позиции — для проверки, что списание (продажа/списание/
        перемещение) не уходит в товар, уже обещанный по заказу."""
        ...


class IStockDocumentRepository(Protocol):
    async def add(self, document: StockDocument) -> StockDocument: ...

    async def list_all(self, warehouse_ids: list[int] | None = None) -> list[StockDocument]:
        """История документов движения, новые сначала. warehouse_ids=None — без
        ограничения по складу (owner/analyst); иначе — только документы, где склад
        документа (источник или получатель при перемещении) входит в список."""
        ...

    async def get(self, document_id: int) -> StockDocument:
        """Один документ по id. NotFoundError, если не найден в текущем tenant."""
        ...
