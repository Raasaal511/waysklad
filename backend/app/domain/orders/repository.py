from typing import Protocol

from app.domain.orders.entities import Order


class IOrderRepository(Protocol):
    async def add(self, order: Order) -> Order: ...

    async def save(self, order: Order) -> Order:
        """Обновляет статус, дату готовности, предоплату, заметку, источник, sale_id
        и строки (полная замена — используется при редактировании состава заказа)."""
        ...

    async def get(self, order_id: int) -> Order: ...

    async def list_active(self, warehouse_ids: list[int] | None = None) -> list[Order]:
        """warehouse_ids=None — без ограничения по складу (owner/analyst); иначе —
        только заказы, где склад заказа входит в список."""
        ...

    async def list_completed(self, warehouse_ids: list[int] | None = None) -> list[Order]:
        """Завершённые заказы (issued/cancelled) — история, новые сначала."""
        ...

    async def list_by_client(self, client_id: int) -> list[Order]:
        """Все заказы (любого статуса) клиента — для ленты событий клиента."""
        ...
