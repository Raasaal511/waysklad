from dataclasses import dataclass

from app.application.sales.create_sale import CreateSaleCommand, CreateSaleUseCase
from app.domain.common.exceptions import DomainError
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor
from app.domain.sales.entities import Sale


@dataclass(frozen=True)
class ApplyOfflineSalesCommand:
    sales: list[CreateSaleCommand]


@dataclass(frozen=True)
class OfflineOpError:
    client_op_id: str | None
    message: str


@dataclass(frozen=True)
class ApplyOfflineSalesResult:
    applied: list[Sale]
    errors: list[OfflineOpError]


class ApplyOfflineSalesUseCase:
    """Накат офлайн-очереди продаж: сервер прав, каждая продажа применяется
    независимо — ошибка одной (например, недостаточно остатка) не блокирует
    остальные. Идемпотентность — по client_op_id (CreateSaleUseCase)."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: ApplyOfflineSalesCommand) -> ApplyOfflineSalesResult:
        applied: list[Sale] = []
        errors: list[OfflineOpError] = []
        for sale_cmd in cmd.sales:
            try:
                result = await CreateSaleUseCase(self._uow).execute(actor, sale_cmd)
                applied.append(result.sale)
            except DomainError as exc:
                errors.append(OfflineOpError(client_op_id=sale_cmd.client_op_id, message=str(exc)))
        return ApplyOfflineSalesResult(applied=applied, errors=errors)
