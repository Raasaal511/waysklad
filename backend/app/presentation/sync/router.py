from fastapi import APIRouter

from app.presentation.deps import ActorDep, ApplyOfflineSalesDep
from app.presentation.sync.schemas import SyncSalesRequest, SyncSalesResponse

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/sales")
async def sync_sales(
    body: SyncSalesRequest, actor: ActorDep, use_case: ApplyOfflineSalesDep
) -> SyncSalesResponse:
    return SyncSalesResponse.from_result(await use_case.execute(actor, body.to_command()))
