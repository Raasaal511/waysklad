from datetime import date

from fastapi import APIRouter

from app.domain.identity.permissions import Permission
from app.presentation.audit.schemas import AuditEntryResponse
from app.presentation.debts.schemas import (
    CreateInstallmentRequest,
    DebtResponse,
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
async def list_active_debts(uow: UowDep) -> list[DebtResponse]:
    async with uow:
        return [DebtResponse.from_entity(d) for d in await uow.debts.list_active()]


@router.get("/due", dependencies=[_view])
async def list_due_debts(uow: UowDep, on: date | None = None) -> list[DebtResponse]:
    async with uow:
        return [DebtResponse.from_entity(d) for d in await uow.debts.list_due(on or date.today())]


@router.get("/client/{client_id}", dependencies=[_view])
async def list_client_debts(client_id: int, uow: UowDep) -> DebtsSummaryResponse:
    async with uow:
        return DebtsSummaryResponse.from_debts(await uow.debts.list_by_client(client_id))


@router.get("/supplier/{supplier_id}", dependencies=[_view])
async def list_supplier_debts(supplier_id: int, uow: UowDep) -> DebtsSummaryResponse:
    async with uow:
        return DebtsSummaryResponse.from_debts(await uow.debts.list_by_supplier(supplier_id))


@router.get("/{debt_id}", dependencies=[_view])
async def get_debt(debt_id: int, uow: UowDep) -> DebtResponse:
    async with uow:
        return DebtResponse.from_entity(await uow.debts.get(debt_id))


@router.get("/{debt_id}/history", dependencies=[_view])
async def get_debt_history(debt_id: int, uow: UowDep) -> list[AuditEntryResponse]:
    async with uow:
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
