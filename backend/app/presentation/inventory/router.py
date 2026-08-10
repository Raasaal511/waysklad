from fastapi import APIRouter

from app.domain.identity.entities import Role
from app.presentation.deps import (
    ActorDep,
    CreateWarehouseDep,
    ReceiveGoodsDep,
    SetWarehouseAssignmentsDep,
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
    WarehouseAssignmentsRequest,
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


@router.put("/warehouses/{warehouse_id}/assignments")
async def set_warehouse_assignments(
    warehouse_id: int,
    body: WarehouseAssignmentsRequest,
    actor: ActorDep,
    use_case: SetWarehouseAssignmentsDep,
) -> WarehouseResponse:
    return WarehouseResponse.from_entity(
        await use_case.execute(actor, body.to_command(warehouse_id))
    )


@router.get("/warehouses")
async def list_warehouses(actor: ActorDep, uow: UowDep) -> list[WarehouseResponse]:
    async with uow:
        if actor.role is Role.STOREKEEPER:
            warehouses = await uow.warehouses.list_for_user(actor.id)
        else:
            warehouses = await uow.warehouses.list()
        return [WarehouseResponse.from_entity(w) for w in warehouses]


@router.get("/stock")
async def list_stock(actor: ActorDep, uow: UowDep) -> list[StockItemResponse]:
    async with uow:
        items = await uow.stock.list_all()
        if actor.role is not Role.STOREKEEPER:
            return [StockItemResponse.from_entity(item) for item in items]
        allowed_ids = {w.id for w in await uow.warehouses.list_for_user(actor.id)}
        return [
            StockItemResponse.from_entity(item)
            for item in items
            if item.warehouse_id in allowed_ids
        ]


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
