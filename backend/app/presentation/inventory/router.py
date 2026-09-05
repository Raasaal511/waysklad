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
    GetDocumentDep,
    GetDocumentExportDataDep,
    GetRestockRecommendationsDep,
    ListDocumentsDep,
    ListStockDep,
    ListWarehousesDep,
    ReceiveGoodsDep,
    SetWarehouseAssignmentsDep,
    StocktakeDep,
    TransferDep,
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
async def list_warehouses(actor: ActorDep, use_case: ListWarehousesDep) -> list[WarehouseResponse]:
    warehouses = await use_case.execute(actor)
    return [WarehouseResponse.from_entity(w) for w in warehouses]


@router.get("/restock-recommendations")
async def get_restock_recommendations(
    actor: ActorDep, use_case: GetRestockRecommendationsDep, warehouse_id: int | None = None,
) -> list[RestockRecommendationResponse]:
    result = await use_case.execute(actor, RestockRecommendationsQuery(warehouse_id=warehouse_id))
    return [RestockRecommendationResponse.from_entity(item) for item in result]


@router.get("/stock")
async def list_stock(actor: ActorDep, use_case: ListStockDep) -> list[StockItemResponse]:
    items = await use_case.execute(actor)
    return [StockItemResponse.from_entity(item) for item in items]


@router.get("/documents")
async def list_documents(actor: ActorDep, use_case: ListDocumentsDep) -> list[DocumentHistoryResponse]:
    documents = await use_case.execute(actor)
    return [DocumentHistoryResponse.from_entity(d) for d in documents]


@router.get("/documents/export.xlsx")
async def export_documents_xlsx(actor: ActorDep, use_case: GetDocumentExportDataDep) -> Response:
    data = await use_case.execute(actor)
    content = render_documents_xlsx(
        data.documents, data.warehouse_names, data.product_names, data.product_fractional, data.user_names
    )
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="ostatki.xlsx"'},
    )


@router.get("/documents/export.csv")
async def export_documents_csv(actor: ActorDep, use_case: GetDocumentExportDataDep) -> Response:
    data = await use_case.execute(actor)
    content = render_documents_csv(
        data.documents, data.warehouse_names, data.product_names, data.product_fractional, data.user_names
    )
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ostatki.csv"'},
    )


@router.get("/documents/export.pdf")
async def export_documents_pdf(actor: ActorDep, use_case: GetDocumentExportDataDep) -> Response:
    data = await use_case.execute(actor)
    content = render_documents_pdf(
        data.shop_name,
        data.documents,
        data.warehouse_names,
        data.product_names,
        data.product_fractional,
        data.user_names,
    )
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="ostatki.pdf"'},
    )


@router.get("/documents/{document_id}")
async def get_document(
    document_id: int, actor: ActorDep, use_case: GetDocumentDep
) -> DocumentHistoryResponse:
    return DocumentHistoryResponse.from_entity(await use_case.execute(actor, document_id))


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
