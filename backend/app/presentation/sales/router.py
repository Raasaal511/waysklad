from fastapi import APIRouter

from app.presentation.deps import ActorDep, CreateSaleDep
from app.presentation.sales.schemas import SaleCreateRequest, SaleResponse

router = APIRouter(prefix="/sales", tags=["sales"])


@router.post("", status_code=201)
async def create_sale(
    body: SaleCreateRequest, actor: ActorDep, use_case: CreateSaleDep
) -> SaleResponse:
    return SaleResponse.from_result(await use_case.execute(actor, body.to_command()))
