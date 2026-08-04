from typing import Protocol

from app.domain.sales.entities import Sale


class ISaleRepository(Protocol):
    async def add(self, sale: Sale) -> Sale: ...
    async def get(self, sale_id: int) -> Sale: ...
