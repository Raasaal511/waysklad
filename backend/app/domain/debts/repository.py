from __future__ import annotations

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

    async def list_closed(self) -> list[Debt]:
        """Все погашенные долги арендатора — для вкладки «Погашен» в общем списке."""
        ...

    async def list_filtered(self, raw_params: dict) -> tuple[list[Debt], int]:
        """Список долгов по декларативным фильтрам (см. app/infrastructure/db/filtering) —
        для страницы «Долги» с направлением/статусом/поиском/сортировкой на сервере."""
        ...
