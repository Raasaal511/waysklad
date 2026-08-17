from typing import Protocol

from app.domain.orders.entities import Order


class IOrderRepository(Protocol):
    async def add(self, order: Order) -> Order: ...

    async def save(self, order: Order) -> Order:
        """Обновляет статус, дату готовности, предоплату, заметку, источник, sale_id
        и строки (полная замена — используется при редактировании состава заказа)."""
        ...

    async def get(self, order_id: int) -> Order: ...
    async def list_active(self) -> list[Order]: ...
    async def list_completed(self) -> list[Order]:
        """Завершённые заказы (issued/cancelled) — история, новые сначала."""
        ...
