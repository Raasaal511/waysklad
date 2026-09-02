from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

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
    остальные. Идемпотентность — по client_op_id (CreateSaleUseCase): при
    гонке (повторная отправка той же пачки до получения ответа с двух вкладок
    /устройств) UNIQUE(tenant_id, client_op_id) в БД ловится здесь же, чтобы
    не оборвать обработку оставшихся продаж пачки необработанным IntegrityError."""

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
            except IntegrityError:
                existing = None
                if sale_cmd.client_op_id is not None:
                    async with self._uow as uow:
                        existing = await uow.sales.get_by_client_op_id(sale_cmd.client_op_id)
                if existing is not None:
                    applied.append(existing)
                else:
                    errors.append(
                        OfflineOpError(
                            client_op_id=sale_cmd.client_op_id,
                            message="Конфликт при сохранении — попробуйте повторить синхронизацию",
                        )
                    )
        return ApplyOfflineSalesResult(applied=applied, errors=errors)
