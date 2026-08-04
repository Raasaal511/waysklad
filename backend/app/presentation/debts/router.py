from fastapi import APIRouter

from app.presentation.debts.schemas import (
    CreateInstallmentRequest,
    DebtResponse,
    IssueDebtRequest,
    RepayDebtRequest,
)
from app.presentation.deps import (
    ActorDep,
    CreateInstallmentDep,
    IssueDebtDep,
    RepayDebtDep,
    UowDep,
)

router = APIRouter(prefix="/debts", tags=["debts"])


@router.post("", status_code=201)
async def issue_debt(
    body: IssueDebtRequest, actor: ActorDep, use_case: IssueDebtDep
) -> DebtResponse:
    return DebtResponse.from_entity(await use_case.execute(actor, body.to_command()))


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


@router.get("/client/{client_id}")
async def list_client_debts(client_id: int, uow: UowDep) -> list[DebtResponse]:
    async with uow:
        return [DebtResponse.from_entity(d) for d in await uow.debts.list_by_client(client_id)]
