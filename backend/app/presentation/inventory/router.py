from fastapi import APIRouter

from app.presentation.deps import (
    ActorDep,
    CreateWarehouseDep,
    ReceiveGoodsDep,
    StocktakeDep,
    TransferDep,
    UowDep,
    WriteOffDep,
)
from app.presentation.inventory.schemas import (
    DocumentResponse,
    ReceiveRequest,
    StockItemResponse,
    StocktakeRequest,
    StocktakeResponse,
    TransferRequest,
    WarehouseCreateRequest,
    WarehouseResponse,
    WriteOffRequest,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.post("/warehouses", status_code=201)
async def create_warehouse(
    body: WarehouseCreateRequest, actor: ActorDep, use_case: CreateWarehouseDep
) -> WarehouseResponse:
    return WarehouseResponse.from_entity(await use_case.execute(actor, body.to_command()))


@router.get("/warehouses")
async def list_warehouses(uow: UowDep) -> list[WarehouseResponse]:
    async with uow:
        return [WarehouseResponse.from_entity(w) for w in await uow.warehouses.list()]


@router.get("/stock")
async def list_stock(uow: UowDep) -> list[StockItemResponse]:
    async with uow:
        return [StockItemResponse.from_entity(item) for item in await uow.stock.list_all()]


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
