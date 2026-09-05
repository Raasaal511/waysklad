from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.application.debts.list_debts import ListDebtsCommand
from app.domain.identity.permissions import Permission
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
    GetDebtDep,
    GetDebtHistoryDep,
    GetDebtsOverviewDep,
    IssueDebtDep,
    IssueSupplierDebtDep,
    ListClientDebtsDep,
    ListDebtsDep,
    ListDueDebtsDep,
    ListSupplierDebtsDep,
    RepayDebtDep,
)
from app.presentation.deps.auth import require_permission

router = APIRouter(prefix="/debts", tags=["debts"])
_view = require_permission(Permission.DEBTS_VIEW)


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
    response: Response,
    actor: ActorDep,
    use_case: ListDebtsDep,
    params: Annotated[DebtsFilterParams, Depends()],
) -> list[DebtResponse]:
    cmd = ListDebtsCommand(
        raw_params=params.to_raw_params(), balance_filter="gt", default_order_by="-severity"
    )
    result = await use_case.execute(actor, cmd)
    response.headers["X-Total-Count"] = str(result.total)
    return [DebtResponse.from_entity(d) for d in result.debts]


@router.get("/closed", dependencies=[_view])
async def list_closed_debts(
    response: Response,
    actor: ActorDep,
    use_case: ListDebtsDep,
    params: Annotated[DebtsFilterParams, Depends()],
) -> list[DebtResponse]:
    cmd = ListDebtsCommand(
        raw_params=params.to_raw_params(), balance_filter="lte", default_order_by="-issued_at"
    )
    result = await use_case.execute(actor, cmd)
    response.headers["X-Total-Count"] = str(result.total)
    return [DebtResponse.from_entity(d) for d in result.debts]


@router.get("/overview", dependencies=[_view])
async def get_debts_overview(actor: ActorDep, use_case: GetDebtsOverviewDep) -> DebtsOverviewResponse:
    debts, counterparty_name = await use_case.execute(actor)
    return DebtsOverviewResponse.from_active_debts(debts, counterparty_name)


@router.get("/due", dependencies=[_view])
async def list_due_debts(
    actor: ActorDep, use_case: ListDueDebtsDep, on: date | None = None
) -> list[DebtResponse]:
    debts = await use_case.execute(actor, on)
    return [DebtResponse.from_entity(d) for d in debts]


@router.get("/client/{client_id}", dependencies=[_view])
async def list_client_debts(
    client_id: int, actor: ActorDep, use_case: ListClientDebtsDep, on: date | None = None
) -> DebtsSummaryResponse:
    debts = await use_case.execute(actor, client_id, on)
    return DebtsSummaryResponse.from_debts(debts)


@router.get("/supplier/{supplier_id}", dependencies=[_view])
async def list_supplier_debts(
    supplier_id: int, actor: ActorDep, use_case: ListSupplierDebtsDep, on: date | None = None
) -> DebtsSummaryResponse:
    debts = await use_case.execute(actor, supplier_id, on)
    return DebtsSummaryResponse.from_debts(debts)


@router.get("/{debt_id}", dependencies=[_view])
async def get_debt(debt_id: int, actor: ActorDep, use_case: GetDebtDep) -> DebtResponse:
    return DebtResponse.from_entity(await use_case.execute(actor, debt_id))


@router.get("/{debt_id}/history", dependencies=[_view])
async def get_debt_history(
    debt_id: int, actor: ActorDep, use_case: GetDebtHistoryDep
) -> list[AuditEntryResponse]:
    entries = await use_case.execute(actor, debt_id)
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
