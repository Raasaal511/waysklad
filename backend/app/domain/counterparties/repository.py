from typing import Protocol

from app.domain.counterparties.entities import Client, Supplier


class IClientRepository(Protocol):
    async def add(self, client: Client) -> Client: ...
    async def get(self, client_id: int) -> Client: ...

    async def search(
        self,
        query: str,
        include_inactive: bool = False,
        warehouse_ids: list[int] | None = None,
    ) -> list[Client]:
        """warehouse_ids=None — без ограничения (owner/analyst); иначе — только
        клиенты, засветившиеся (продажа/заказ/долг) на одном из этих складов."""
        ...

    async def save(self, client: Client) -> Client: ...
    async def get_by_phone(self, phone: str) -> Client | None: ...

    async def link_to_warehouse(self, client_id: int, warehouse_id: int) -> None:
        """Индексная связка для видимости клиента warehouse-scoped сотрудникам —
        не бизнес-правило, просто фиксирует «клиент засветился на этом складе»."""
        ...


class ISupplierRepository(Protocol):
    async def add(self, supplier: Supplier) -> Supplier: ...
    async def get(self, supplier_id: int) -> Supplier: ...

    async def list(self, warehouse_ids: list[int] | None = None) -> list[Supplier]:
        """warehouse_ids=None — без ограничения; иначе — только поставщики,
        засветившиеся (приёмка/долг) на одном из этих складов."""
        ...

    async def link_to_warehouse(self, supplier_id: int, warehouse_id: int) -> None:
        """Аналог IClientRepository.link_to_warehouse для поставщиков."""
        ...
