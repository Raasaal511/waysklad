from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.domain.debts.entities import snapshot_as_of
from app.domain.identity.permissions import Permission, require_warehouse
from app.presentation.audit.schemas import AuditEntryResponse
from app.presentation.debts.schemas import (
    CreateInstallmentRequest,
    DebtResponse,
    DebtsFilterParams,
    DebtsOverviewResponse,
    DebtsSummaryResponse,
    ExtendDebtRequest,
    IssueDebtRequest,
    IssueSupplierDebtRequest,
    RepayDebtRequest,
)
from app.presentation.deps import (
    ActorDep,
    CreateInstallmentDep,
    ExtendDebtDep,
    IssueDebtDep,
    IssueSupplierDebtDep,
    RepayDebtDep,
    UowDep,
)
from app.presentation.deps.auth import require_permission

router = APIRouter(prefix="/debts", tags=["debts"])
_view = require_permission(Permission.DEBTS_VIEW)


def _scoped(actor, debts: list) -> list:
    """Оставляет только долги складов актора, если он warehouse-scoped."""
    if not actor.is_warehouse_scoped:
        return debts
    allowed = set(actor.warehouse_ids)
    return [d for d in debts if d.warehouse_id in allowed]


@router.post("", status_code=201)
async def issue_debt(
    body: IssueDebtRequest, actor: ActorDep, use_case: IssueDebtDep
) -> DebtResponse:
    return DebtResponse.from_entity(await use_case.execute(actor, body.to_command()))


@router.post("/suppliers", status_code=201)
async def issue_supplier_debt(
    body: IssueSupplierDebtRequest, actor: ActorDep, use_case: IssueSupplierDebtDep
) -> DebtResponse:
    return DebtResponse.from_entity(await use_case.execute(actor, body.to_command()))


@router.get("", dependencies=[_view])
async def list_active_debts(
    response: Response, actor: ActorDep, uow: UowDep, params: Annotated[DebtsFilterParams, Depends()],
) -> list[DebtResponse]:
    async with uow:
        raw_params = {**params.to_raw_params(), "balance__gt": 0, "order_by": params.order_by or "-severity"}
        if actor.is_warehouse_scoped:
            raw_params["warehouse_id__in"] = actor.warehouse_ids
        debts, total = await uow.debts.list_filtered(raw_params)
        response.headers["X-Total-Count"] = str(total)
        return [DebtResponse.from_entity(d) for d in debts]


@router.get("/closed", dependencies=[_view])
async def list_closed_debts(
    response: Response, actor: ActorDep, uow: UowDep, params: Annotated[DebtsFilterParams, Depends()],
) -> list[DebtResponse]:
    async with uow:
        raw_params = {**params.to_raw_params(), "balance__lte": 0, "order_by": params.order_by or "-issued_at"}
        if actor.is_warehouse_scoped:
            raw_params["warehouse_id__in"] = actor.warehouse_ids
        debts, total = await uow.debts.list_filtered(raw_params)
        response.headers["X-Total-Count"] = str(total)
        return [DebtResponse.from_entity(d) for d in debts]


@router.get("/overview", dependencies=[_view])
async def get_debts_overview(actor: ActorDep, uow: UowDep) -> DebtsOverviewResponse:
    async with uow:
        debts = _scoped(actor, await uow.debts.list_active())
        clients = await uow.clients.search("", include_inactive=True)
        suppliers = await uow.suppliers.list()
        counterparty_name = {("client", c.id): c.name for c in clients}
        counterparty_name.update({("supplier", s.id): s.name for s in suppliers})
        return DebtsOverviewResponse.from_active_debts(debts, counterparty_name)


@router.get("/due", dependencies=[_view])
async def list_due_debts(
    actor: ActorDep, uow: UowDep, on: date | None = None
) -> list[DebtResponse]:
    async with uow:
        debts = _scoped(actor, await uow.debts.list_due(on or date.today()))
        return [DebtResponse.from_entity(d) for d in debts]


@router.get("/client/{client_id}", dependencies=[_view])
async def list_client_debts(
    client_id: int, actor: ActorDep, uow: UowDep, on: date | None = None
) -> DebtsSummaryResponse:
    async with uow:
        debts = _scoped(actor, await uow.debts.list_by_client(client_id))
        if on is not None:
            debts = snapshot_as_of(debts, on)
        return DebtsSummaryResponse.from_debts(debts)


@router.get("/supplier/{supplier_id}", dependencies=[_view])
async def list_supplier_debts(
    supplier_id: int, actor: ActorDep, uow: UowDep, on: date | None = None
) -> DebtsSummaryResponse:
    async with uow:
        debts = _scoped(actor, await uow.debts.list_by_supplier(supplier_id))
        if on is not None:
            debts = snapshot_as_of(debts, on)
        return DebtsSummaryResponse.from_debts(debts)


@router.get("/{debt_id}", dependencies=[_view])
async def get_debt(debt_id: int, actor: ActorDep, uow: UowDep) -> DebtResponse:
    async with uow:
        debt = await uow.debts.get(debt_id)
        require_warehouse(actor, debt.warehouse_id)
        return DebtResponse.from_entity(debt)


@router.get("/{debt_id}/history", dependencies=[_view])
async def get_debt_history(
    debt_id: int, actor: ActorDep, uow: UowDep
) -> list[AuditEntryResponse]:
    async with uow:
        require_warehouse(actor, (await uow.debts.get(debt_id)).warehouse_id)
        entries = await uow.audit.list_by_entity("debt", debt_id)
        return [AuditEntryResponse.from_entity(e) for e in entries]


@router.post("/{debt_id}/repayments")
async def repay_debt(
    debt_id: int, body: RepayDebtRequest, actor: ActorDep, use_case: RepayDebtDep
) -> DebtResponse:
    return DebtResponse.from_entity(await use_case.execute(actor, body.to_command(debt_id)))


@router.post("/{debt_id}/installments")
async def create_installment(
    debt_id: int,
    body: CreateInstallmentRequest,
    actor: ActorDep,
    use_case: CreateInstallmentDep,
) -> DebtResponse:
    return DebtResponse.from_entity(await use_case.execute(actor, body.to_command(debt_id)))


@router.post("/{debt_id}/extend")
async def extend_debt(
    debt_id: int, body: ExtendDebtRequest, actor: ActorDep, use_case: ExtendDebtDep
) -> DebtResponse:
    return DebtResponse.from_entity(await use_case.execute(actor, body.to_command(debt_id)))
