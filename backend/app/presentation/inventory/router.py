from fastapi import APIRouter, Response

from app.infrastructure.inventory_export import (
    render_documents_csv,
    render_documents_pdf,
    render_documents_xlsx,
)
from app.application.analytics.restock_recommendations import (
    RestockRecommendationsQuery,
)
from app.presentation.deps import (
    ActorDep,
    CreateWarehouseDep,
    GetRestockRecommendationsDep,
    ReceiveGoodsDep,
    SetWarehouseAssignmentsDep,
    StocktakeDep,
    TransferDep,
    UowDep,
    UpdateWarehouseDetailsDep,
    WriteOffDep,
)
from app.presentation.inventory.schemas import (
    DocumentHistoryResponse,
    DocumentResponse,
    ReceiveRequest,
    RestockRecommendationResponse,
    StockItemResponse,
    StocktakeRequest,
    StocktakeResponse,
    TransferRequest,
    WarehouseAssignmentsRequest,
    WarehouseCreateRequest,
    WarehouseDetailsRequest,
    WarehouseResponse,
    WriteOffRequest,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])


async def _load_document_export_data(actor: ActorDep, uow: UowDep):
    async with uow:
        warehouse_ids = actor.warehouse_ids if actor.is_warehouse_scoped else None
        documents = await uow.stock_documents.list_all(warehouse_ids)
        warehouses = await uow.warehouses.list()
        products = await uow.products.search_all()
        users = await uow.users.list_by_tenant()
        tenant = await uow.tenants.get(uow.tenant_id)
        return (
            documents,
            {w.id: w.name for w in warehouses},
            {p.id: p.name for p in products},
            {p.id: p.unit.fractional for p in products},
            {u.id: u.name for u in users},
            tenant.name,
        )


@router.post("/warehouses", status_code=201)
async def create_warehouse(
    body: WarehouseCreateRequest, actor: ActorDep, use_case: CreateWarehouseDep
) -> WarehouseResponse:
    return WarehouseResponse.from_entity(await use_case.execute(actor, body.to_command()))


@router.put("/warehouses/{warehouse_id}")
async def update_warehouse_details(
    warehouse_id: int,
    body: WarehouseDetailsRequest,
    actor: ActorDep,
    use_case: UpdateWarehouseDetailsDep,
) -> WarehouseResponse:
    return WarehouseResponse.from_entity(
        await use_case.execute(actor, body.to_command(warehouse_id))
    )


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
        if actor.is_warehouse_scoped:
            warehouses = await uow.warehouses.list_for_user(actor.id)
        else:
            warehouses = await uow.warehouses.list()
        return [WarehouseResponse.from_entity(w) for w in warehouses]


@router.get("/restock-recommendations")
async def get_restock_recommendations(
    actor: ActorDep, use_case: GetRestockRecommendationsDep, warehouse_id: int | None = None,
) -> list[RestockRecommendationResponse]:
    result = await use_case.execute(actor, RestockRecommendationsQuery(warehouse_id=warehouse_id))
    return [RestockRecommendationResponse.from_entity(item) for item in result]


@router.get("/stock")
async def list_stock(actor: ActorDep, uow: UowDep) -> list[StockItemResponse]:
    async with uow:
        items = await uow.stock.list_all()
        if not actor.is_warehouse_scoped:
            return [StockItemResponse.from_entity(item) for item in items]
        allowed_ids = set(actor.warehouse_ids)
        return [
            StockItemResponse.from_entity(item)
            for item in items
            if item.warehouse_id in allowed_ids
        ]


@router.get("/documents")
async def list_documents(actor: ActorDep, uow: UowDep) -> list[DocumentHistoryResponse]:
    async with uow:
        warehouse_ids = actor.warehouse_ids if actor.is_warehouse_scoped else None
        documents = await uow.stock_documents.list_all(warehouse_ids)
        return [DocumentHistoryResponse.from_entity(d) for d in documents]


@router.get("/documents/export.xlsx")
async def export_documents_xlsx(actor: ActorDep, uow: UowDep) -> Response:
    documents, warehouses, products, fractional, users, _ = await _load_document_export_data(actor, uow)
    content = render_documents_xlsx(documents, warehouses, products, fractional, users)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="ostatki.xlsx"'},
    )


@router.get("/documents/export.csv")
async def export_documents_csv(actor: ActorDep, uow: UowDep) -> Response:
    documents, warehouses, products, fractional, users, _ = await _load_document_export_data(actor, uow)
    content = render_documents_csv(documents, warehouses, products, fractional, users)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ostatki.csv"'},
    )


@router.get("/documents/export.pdf")
async def export_documents_pdf(actor: ActorDep, uow: UowDep) -> Response:
    documents, warehouses, products, fractional, users, shop_name = await _load_document_export_data(actor, uow)
    content = render_documents_pdf(shop_name, documents, warehouses, products, fractional, users)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="ostatki.pdf"'},
    )


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
