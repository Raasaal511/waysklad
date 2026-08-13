"""Общая логика привязки сотрудника к складам — используется при создании и
редактировании (CreateEmployeeUseCase/UpdateEmployeeUseCase)."""

from app.domain.common.exceptions import DomainError
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Role

# роли, для которых обязательна привязка минимум к одному складу
WAREHOUSE_SCOPED_ROLES = (Role.MANAGER, Role.SELLER, Role.STOREKEEPER)


async def resolve_warehouse_ids(
    uow: IUnitOfWork, role: Role, warehouse_ids: list[int] | None
) -> list[int]:
    """Определяет итоговый список складов сотрудника с учётом бизнес-правил:

    - owner — без привязки, список игнорируется;
    - если магазин имеет ровно один склад — сотрудник привязывается к нему
      автоматически, вне зависимости от того, что прислал фронт (типичный
      случай «один магазин = один склад» не должен требовать выбора);
    - иначе для manager/seller/storekeeper нужен хотя бы один переданный
      склад, и все они должны существовать и принадлежать текущему tenant.
    """
    if role not in WAREHOUSE_SCOPED_ROLES:
        return []

    all_warehouses = await uow.warehouses.list()
    if len(all_warehouses) == 1:
        return [all_warehouses[0].id]

    if not warehouse_ids:
        raise DomainError(
            "Для этой роли нужно выбрать хотя бы один склад"
        )

    existing_ids = {w.id for w in all_warehouses}
    unknown = set(warehouse_ids) - existing_ids
    if unknown:
        raise DomainError("Указан несуществующий склад")

    return list(dict.fromkeys(warehouse_ids))  # без дублей, сохраняя порядок
