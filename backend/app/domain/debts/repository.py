from datetime import date
from typing import Protocol

from app.domain.debts.entities import Debt


class IDebtRepository(Protocol):
    async def add(self, debt: Debt) -> Debt: ...

    async def save(self, debt: Debt) -> Debt:
        """Дописывает новые погашения и заменяет график рассрочки."""
        ...

    async def get(self, debt_id: int) -> Debt: ...
    async def list_by_client(self, client_id: int) -> list[Debt]: ...
    async def list_by_supplier(self, supplier_id: int) -> list[Debt]: ...

    async def list_due(self, on: date) -> list[Debt]:
        """Долги со сроком на дату — для напоминаний «сегодня должны вернуть»."""
        ...

    async def list_active(self) -> list[Debt]:
        """Все незакрытые долги арендатора (клиентские и поставщические) — для общего списка."""
        ...
