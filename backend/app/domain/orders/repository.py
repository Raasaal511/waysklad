from typing import Protocol

from app.domain.orders.entities import Order


class IOrderRepository(Protocol):
    async def add(self, order: Order) -> Order: ...

    async def save(self, order: Order) -> Order:
        """Обновляет статус, дату готовности, предоплату, заметку (не строки)."""
        ...

    async def get(self, order_id: int) -> Order: ...
    async def list_active(self) -> list[Order]: ...
