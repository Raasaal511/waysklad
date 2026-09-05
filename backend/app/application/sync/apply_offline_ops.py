from dataclasses import dataclass, field

from sqlalchemy.exc import IntegrityError

from app.application.inventory.receive_goods import ReceiveGoodsCommand, ReceiveGoodsUseCase
from app.application.inventory.write_off import WriteOffCommand, WriteOffUseCase
from app.application.sales.create_sale import CreateSaleCommand, CreateSaleUseCase
from app.application.sales.return_sale import ReturnSaleCommand, ReturnSaleUseCase
from app.domain.common.exceptions import DomainError
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor
from app.domain.inventory.entities import StockDocument
from app.domain.sales.entities import Sale, SaleReturn

_CONFLICT_MESSAGE = "Конфликт при сохранении — попробуйте повторить синхронизацию"


@dataclass(frozen=True)
class ApplyOfflineSalesCommand:
    sales: list[CreateSaleCommand] = field(default_factory=list)
    returns: list[ReturnSaleCommand] = field(default_factory=list)
    receipts: list[ReceiveGoodsCommand] = field(default_factory=list)
    writeoffs: list[WriteOffCommand] = field(default_factory=list)


@dataclass(frozen=True)
class OfflineOpError:
    op_type: str  # "sale" | "return" | "receipt" | "writeoff"
    client_op_id: str | None
    code: str  # имя класса исключения (DomainError.__class__.__name__), "IntegrityConflict" — нерезолвящийся дубль
    message: str


@dataclass(frozen=True)
class ApplyOfflineSalesResult:
    applied: list[Sale] = field(default_factory=list)
    applied_returns: list[SaleReturn] = field(default_factory=list)
    applied_receipts: list[StockDocument] = field(default_factory=list)
    applied_writeoffs: list[StockDocument] = field(default_factory=list)
    errors: list[OfflineOpError] = field(default_factory=list)


class ApplyOfflineSalesUseCase:
    """Накат офлайн-очереди (продажи/возвраты/приёмки/списания): сервер прав,
    каждая операция применяется независимо — ошибка одной (например,
    недостаточно остатка) не блокирует остальные, в том числе других типов.
    Идемпотентность — по client_op_id (см. соответствующий use case каждого
    типа): при гонке (повторная отправка той же пачки до получения ответа с
    двух вкладок/устройств) UNIQUE(tenant_id, client_op_id) в БД ловится
    здесь же, чтобы не оборвать обработку оставшихся операций пачки
    необработанным IntegrityError."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: ApplyOfflineSalesCommand) -> ApplyOfflineSalesResult:
        applied: list[Sale] = []
        applied_returns: list[SaleReturn] = []
        applied_receipts: list[StockDocument] = []
        applied_writeoffs: list[StockDocument] = []
        errors: list[OfflineOpError] = []

        for sale_cmd in cmd.sales:
            try:
                result = await CreateSaleUseCase(self._uow).execute(actor, sale_cmd)
                applied.append(result.sale)
            except DomainError as exc:
                errors.append(
                    OfflineOpError(
                        op_type="sale", client_op_id=sale_cmd.client_op_id,
                        code=type(exc).__name__, message=str(exc),
                    )
                )
            except IntegrityError:
                existing = await self._resolve_conflict(sale_cmd.client_op_id, "sales")
                if existing is not None:
                    applied.append(existing)
                else:
                    errors.append(
                        OfflineOpError(
                            op_type="sale", client_op_id=sale_cmd.client_op_id,
                            code="IntegrityConflict", message=_CONFLICT_MESSAGE,
                        )
                    )

        for return_cmd in cmd.returns:
            try:
                result = await ReturnSaleUseCase(self._uow).execute(actor, return_cmd)
                applied_returns.append(result.sale_return)
            except DomainError as exc:
                errors.append(
                    OfflineOpError(
                        op_type="return", client_op_id=return_cmd.client_op_id,
                        code=type(exc).__name__, message=str(exc),
                    )
                )
            except IntegrityError:
                existing = await self._resolve_conflict(return_cmd.client_op_id, "sale_returns")
                if existing is not None:
                    applied_returns.append(existing)
                else:
                    errors.append(
                        OfflineOpError(
                            op_type="return", client_op_id=return_cmd.client_op_id,
                            code="IntegrityConflict", message=_CONFLICT_MESSAGE,
                        )
                    )

        for receipt_cmd in cmd.receipts:
            try:
                document = await ReceiveGoodsUseCase(self._uow).execute(actor, receipt_cmd)
                applied_receipts.append(document)
            except DomainError as exc:
                errors.append(
                    OfflineOpError(
                        op_type="receipt", client_op_id=receipt_cmd.client_op_id,
                        code=type(exc).__name__, message=str(exc),
                    )
                )
            except IntegrityError:
                existing = await self._resolve_conflict(
                    receipt_cmd.client_op_id, "stock_documents"
                )
                if existing is not None:
                    applied_receipts.append(existing)
                else:
                    errors.append(
                        OfflineOpError(
                            op_type="receipt", client_op_id=receipt_cmd.client_op_id,
                            code="IntegrityConflict", message=_CONFLICT_MESSAGE,
                        )
                    )

        for writeoff_cmd in cmd.writeoffs:
            try:
                document = await WriteOffUseCase(self._uow).execute(actor, writeoff_cmd)
                applied_writeoffs.append(document)
            except DomainError as exc:
                errors.append(
                    OfflineOpError(
                        op_type="writeoff", client_op_id=writeoff_cmd.client_op_id,
                        code=type(exc).__name__, message=str(exc),
                    )
                )
            except IntegrityError:
                existing = await self._resolve_conflict(
                    writeoff_cmd.client_op_id, "stock_documents"
                )
                if existing is not None:
                    applied_writeoffs.append(existing)
                else:
                    errors.append(
                        OfflineOpError(
                            op_type="writeoff", client_op_id=writeoff_cmd.client_op_id,
                            code="IntegrityConflict", message=_CONFLICT_MESSAGE,
                        )
                    )

        return ApplyOfflineSalesResult(
            applied=applied, applied_returns=applied_returns,
            applied_receipts=applied_receipts, applied_writeoffs=applied_writeoffs,
            errors=errors,
        )

    async def _resolve_conflict(self, client_op_id: str | None, repo_name: str):
        """Дубль client_op_id внутри одной пачки (клиент отправил повторно ту же
        операцию, не дождавшись ответа) бьётся об UNIQUE(tenant_id, client_op_id)
        — резолвим в уже применённую операцию вместо того, чтобы ронять пачку."""
        if client_op_id is None:
            return None
        async with self._uow as uow:
            repo = getattr(uow, repo_name)
            return await repo.get_by_client_op_id(client_op_id)
