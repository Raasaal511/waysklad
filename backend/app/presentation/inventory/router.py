from fastapi import APIRouter

from app.presentation.deps import (
    ActorDep,
    ReceiveGoodsDep,
    StocktakeDep,
    TransferDep,
    WriteOffDep,
)
from app.presentation.inventory.schemas import (
    DocumentResponse,
    ReceiveRequest,
    StocktakeRequest,
    StocktakeResponse,
    TransferRequest,
    WriteOffRequest,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.post("/receive", status_code=201)
async def receive_goods(
    body: ReceiveRequest, actor: ActorDep, use_case: ReceiveGoodsDep
) -> DocumentResponse:
    return DocumentResponse.from_entity(await use_case.execute(actor, body.to_command()))


@router.post("/write-off", status_code=201)
async def write_off(
    body: WriteOffRequest, actor: ActorDep, use_case: WriteOffDep
) -> DocumentResponse:
    return DocumentResponse.from_entity(await use_case.execute(actor, body.to_command()))


@router.post("/transfer", status_code=201)
async def transfer(
    body: TransferRequest, actor: ActorDep, use_case: TransferDep
) -> DocumentResponse:
    return DocumentResponse.from_entity(await use_case.execute(actor, body.to_command()))


@router.post("/stocktake", status_code=201)
async def stocktake(
    body: StocktakeRequest, actor: ActorDep, use_case: StocktakeDep
) -> StocktakeResponse:
    return StocktakeResponse.from_result(await use_case.execute(actor, body.to_command()))
