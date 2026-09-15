from dataclasses import dataclass

from app.domain.common.uow import IUnitOfWork
from app.domain.debts.entities import Debt
from app.domain.identity.permissions import Actor


@dataclass(frozen=True)
class ListDebtsCommand:
    raw_params: dict
    balance_filter: str  # "gt" — активные (баланс > 0), "lte" — закрытые (баланс <= 0)
    default_order_by: str


@dataclass(frozen=True)
class ListDebtsResult:
    debts: list[Debt]
    total: int


class ListDebtsUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: ListDebtsCommand) -> ListDebtsResult:
        raw_params = {
            **cmd.raw_params,
            "order_by": cmd.raw_params.get("order_by") or cmd.default_order_by,
        }
        if cmd.balance_filter == "gt":
            raw_params["balance__gt"] = 0
        else:
            raw_params["balance__lte"] = 0
        if actor.is_warehouse_scoped:
            raw_params["warehouse_id__in"] = actor.warehouse_ids

        async with self._uow as uow:
            debts, total = await uow.debts.list_filtered(raw_params)
            return ListDebtsResult(debts=debts, total=total)
