from dataclasses import dataclass

from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import User


@dataclass(frozen=True)
class EmployeeListItem:
    user: User
    warehouse_ids: list[int]


class ListEmployeesUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self) -> list[EmployeeListItem]:
        async with self._uow as uow:
            employees = await uow.users.list_by_tenant()
            warehouses = await uow.warehouses.list()
            by_user: dict[int, list[int]] = {}
            for warehouse in warehouses:
                for user_id in warehouse.assigned_user_ids:
                    by_user.setdefault(user_id, []).append(warehouse.id)
            return [
                EmployeeListItem(user=u, warehouse_ids=by_user.get(u.id, []))
                for u in employees
            ]
