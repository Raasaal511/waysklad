from typing import Annotated

from fastapi import Depends

from app.application.analytics.dashboard import GetDashboardUseCase
from app.application.analytics.dead_stock import GetDeadStockUseCase, GetStockValueUseCase
from app.application.analytics.period_totals import GetPeriodTotalsUseCase
from app.application.analytics.restock_recommendations import (
    GetRestockRecommendationsUseCase,
)
from app.application.analytics.revenue_timeline import GetRevenueTimelineUseCase
from app.application.analytics.top_products import (
    GetCategoryProfitUseCase,
    GetTopProductsUseCase,
)
from app.application.auth.change_password import ChangePasswordUseCase
from app.application.auth.connect_telegram import ConnectTelegramUseCase
from app.application.auth.create_employee import CreateEmployeeUseCase
from app.application.auth.get_shop import GetShopUseCase
from app.application.auth.list_employees import ListEmployeesUseCase
from app.application.auth.login import LoginUseCase
from app.application.auth.logout_all import LogoutAllUseCase
from app.application.auth.register_shop import RegisterShopUseCase
from app.application.auth.update_employee import UpdateEmployeeUseCase
from app.application.auth.update_shop import UpdateShopUseCase
from app.application.counterparties.create_client import CreateClientUseCase
from app.application.counterparties.create_supplier import CreateSupplierUseCase
from app.application.counterparties.get_client_summary import GetClientSummaryUseCase
from app.application.counterparties.get_client_timeline import GetClientTimelineUseCase
from app.application.counterparties.list_suppliers import ListSuppliersUseCase
from app.application.counterparties.search_clients import SearchClientsUseCase
from app.application.counterparties.update_client import UpdateClientUseCase
from app.application.debts.create_installment import CreateInstallmentUseCase
from app.application.debts.extend_debt import ExtendDebtUseCase
from app.application.debts.get_debt import GetDebtUseCase
from app.application.debts.get_debt_history import GetDebtHistoryUseCase
from app.application.debts.get_debts_overview import GetDebtsOverviewUseCase
from app.application.debts.issue_debt import IssueDebtUseCase
from app.application.debts.issue_supplier_debt import IssueSupplierDebtUseCase
from app.application.debts.list_counterparty_debts import (
    ListClientDebtsUseCase,
    ListSupplierDebtsUseCase,
)
from app.application.debts.list_debts import ListDebtsUseCase
from app.application.debts.list_due_debts import ListDueDebtsUseCase
from app.application.debts.repay_debt import RepayDebtUseCase
from app.application.inventory.create_warehouse import CreateWarehouseUseCase
from app.application.inventory.receive_goods import ReceiveGoodsUseCase
from app.application.inventory.set_warehouse_assignments import (
    SetWarehouseAssignmentsUseCase,
)
from app.application.inventory.stocktake import StocktakeUseCase
from app.application.inventory.transfer import TransferUseCase
from app.application.inventory.update_warehouse_details import (
    UpdateWarehouseDetailsUseCase,
)
from app.application.inventory.write_off import WriteOffUseCase
from app.application.notifications.mark_read import (
    MarkAllNotificationsReadUseCase,
    MarkNotificationReadUseCase,
)
from app.application.orders.cancel_order import CancelOrderUseCase
from app.application.orders.change_status import ChangeOrderStatusUseCase
from app.application.orders.create_order import CreateOrderUseCase
from app.application.orders.get_order import GetOrderUseCase
from app.application.orders.get_order_history import GetOrderHistoryUseCase
from app.application.orders.issue_order import IssueOrderUseCase
from app.application.orders.list_orders import ListActiveOrdersUseCase, ListCompletedOrdersUseCase
from app.application.orders.update_order import UpdateOrderUseCase
from app.application.products.apply_import import ApplyProductImportUseCase
from app.application.products.create_category import CreateCategoryUseCase
from app.application.products.create_product import CreateProductUseCase
from app.application.products.create_unit import CreateUnitUseCase
from app.application.products.get_export_data import GetProductsExportDataUseCase
from app.application.products.get_product import GetProductUseCase
from app.application.products.get_product_by_barcode import GetProductByBarcodeUseCase
from app.application.products.get_product_history import GetProductHistoryUseCase
from app.application.products.import_excel import ImportProductsUseCase
from app.application.products.import_preview import PreviewProductsUseCase
from app.application.products.list_categories import ListCategoriesUseCase
from app.application.products.list_units import ListUnitsUseCase
from app.application.products.search_products import SearchProductsUseCase
from app.application.products.set_product_photo import SetProductPhotoUseCase
from app.application.products.update_product import UpdateProductUseCase
from app.application.sales.create_sale import CreateSaleUseCase
from app.application.sales.delete_sale import DeleteSaleUseCase
from app.application.sales.edit_sale import EditSaleUseCase
from app.application.sales.get_receipt_data import GetReceiptDataUseCase
from app.application.sales.get_sale import GetSaleUseCase
from app.application.sales.get_sale_history import GetSaleHistoryUseCase
from app.application.sales.get_sales_summary import GetSalesSummaryUseCase
from app.application.sales.list_sale_returns import ListSaleReturnsUseCase
from app.application.sales.list_sales import ListSalesUseCase
from app.application.sales.return_sale import ReturnSaleUseCase
from app.application.storefront.accept_request import AcceptStorefrontRequestUseCase
from app.application.storefront.create_request import CreateStorefrontRequestUseCase
from app.application.storefront.get_catalog import GetStorefrontCatalogUseCase
from app.application.storefront.get_product import GetStorefrontProductUseCase
from app.application.storefront.get_request_status import GetStorefrontRequestStatusUseCase
from app.application.storefront.list_messages import (
    ListStaffStorefrontMessagesUseCase,
    ListStorefrontMessagesUseCase,
)
from app.application.storefront.list_requests import ListStorefrontRequestsUseCase
from app.application.storefront.reject_request import RejectStorefrontRequestUseCase
from app.application.storefront.send_message import (
    SendStaffStorefrontMessageUseCase,
    SendStorefrontMessageUseCase,
)
from app.application.sync.apply_offline_ops import ApplyOfflineSalesUseCase
from app.application.tasks.change_status import ChangeTaskStatusUseCase
from app.application.tasks.update_task import UpdateTaskUseCase
from app.application.tasks.create_task import CreateTaskUseCase
from app.presentation.deps.notifier import NotifierDep
from app.presentation.deps.security import FileStorageDep, HasherDep
from app.presentation.deps.session import SessionFactoryDep
from app.presentation.deps.uow import PublicUowDep, UowDep


def _with_uow(use_case_cls):
    def provider(uow: UowDep):
        return use_case_cls(uow)

    return provider


def get_register_shop(uow: PublicUowDep, hasher: HasherDep) -> RegisterShopUseCase:
    return RegisterShopUseCase(uow, hasher)


def get_login(uow: PublicUowDep, hasher: HasherDep) -> LoginUseCase:
    return LoginUseCase(uow, hasher)


def get_create_employee(uow: UowDep, hasher: HasherDep) -> CreateEmployeeUseCase:
    return CreateEmployeeUseCase(uow, hasher)


get_update_employee = _with_uow(UpdateEmployeeUseCase)
get_list_employees = _with_uow(ListEmployeesUseCase)
get_shop = _with_uow(GetShopUseCase)


def get_change_password(uow: UowDep, hasher: HasherDep) -> ChangePasswordUseCase:
    return ChangePasswordUseCase(uow, hasher)


get_logout_all = _with_uow(LogoutAllUseCase)


def get_set_product_photo(uow: UowDep, storage: FileStorageDep) -> SetProductPhotoUseCase:
    return SetProductPhotoUseCase(uow, storage)


get_create_product = _with_uow(CreateProductUseCase)
get_update_product = _with_uow(UpdateProductUseCase)
get_create_unit = _with_uow(CreateUnitUseCase)
get_create_category = _with_uow(CreateCategoryUseCase)
get_import_products = _with_uow(ImportProductsUseCase)
get_preview_import_products = _with_uow(PreviewProductsUseCase)
get_apply_import_products = _with_uow(ApplyProductImportUseCase)
get_list_units = _with_uow(ListUnitsUseCase)
get_list_categories = _with_uow(ListCategoriesUseCase)
get_search_products = _with_uow(SearchProductsUseCase)
get_product_by_barcode = _with_uow(GetProductByBarcodeUseCase)
get_product = _with_uow(GetProductUseCase)
get_product_history = _with_uow(GetProductHistoryUseCase)
get_products_export_data = _with_uow(GetProductsExportDataUseCase)
get_receive_goods = _with_uow(ReceiveGoodsUseCase)
get_write_off = _with_uow(WriteOffUseCase)
get_transfer = _with_uow(TransferUseCase)
get_stocktake = _with_uow(StocktakeUseCase)
get_create_warehouse = _with_uow(CreateWarehouseUseCase)
get_set_warehouse_assignments = _with_uow(SetWarehouseAssignmentsUseCase)
get_update_warehouse_details = _with_uow(UpdateWarehouseDetailsUseCase)
get_create_sale = _with_uow(CreateSaleUseCase)
get_return_sale = _with_uow(ReturnSaleUseCase)
get_edit_sale = _with_uow(EditSaleUseCase)
get_delete_sale = _with_uow(DeleteSaleUseCase)
get_list_sales = _with_uow(ListSalesUseCase)
get_sales_summary = _with_uow(GetSalesSummaryUseCase)
get_sale = _with_uow(GetSaleUseCase)
get_sale_history = _with_uow(GetSaleHistoryUseCase)
get_sale_returns = _with_uow(ListSaleReturnsUseCase)
get_receipt_data = _with_uow(GetReceiptDataUseCase)
get_issue_debt = _with_uow(IssueDebtUseCase)
get_issue_supplier_debt = _with_uow(IssueSupplierDebtUseCase)
get_repay_debt = _with_uow(RepayDebtUseCase)
get_create_installment = _with_uow(CreateInstallmentUseCase)
get_extend_debt = _with_uow(ExtendDebtUseCase)
get_list_debts = _with_uow(ListDebtsUseCase)
get_debts_overview = _with_uow(GetDebtsOverviewUseCase)
get_list_due_debts = _with_uow(ListDueDebtsUseCase)
get_list_client_debts = _with_uow(ListClientDebtsUseCase)
get_list_supplier_debts = _with_uow(ListSupplierDebtsUseCase)
get_debt = _with_uow(GetDebtUseCase)
get_debt_history = _with_uow(GetDebtHistoryUseCase)
get_create_order = _with_uow(CreateOrderUseCase)
get_update_order = _with_uow(UpdateOrderUseCase)
get_change_order_status = _with_uow(ChangeOrderStatusUseCase)
get_cancel_order = _with_uow(CancelOrderUseCase)
get_issue_order = _with_uow(IssueOrderUseCase)
get_list_active_orders = _with_uow(ListActiveOrdersUseCase)
get_list_completed_orders = _with_uow(ListCompletedOrdersUseCase)
get_order = _with_uow(GetOrderUseCase)
get_order_history = _with_uow(GetOrderHistoryUseCase)
get_create_client = _with_uow(CreateClientUseCase)
get_update_client = _with_uow(UpdateClientUseCase)
get_client_timeline = _with_uow(GetClientTimelineUseCase)
get_client_summary = _with_uow(GetClientSummaryUseCase)
get_create_supplier = _with_uow(CreateSupplierUseCase)
get_search_clients = _with_uow(SearchClientsUseCase)
get_list_suppliers = _with_uow(ListSuppliersUseCase)
get_dashboard = _with_uow(GetDashboardUseCase)
get_period_totals = _with_uow(GetPeriodTotalsUseCase)
get_revenue_timeline = _with_uow(GetRevenueTimelineUseCase)
get_top_products = _with_uow(GetTopProductsUseCase)
get_category_profit = _with_uow(GetCategoryProfitUseCase)
get_dead_stock = _with_uow(GetDeadStockUseCase)
get_stock_value = _with_uow(GetStockValueUseCase)
get_restock_recommendations = _with_uow(GetRestockRecommendationsUseCase)
get_apply_offline_sales = _with_uow(ApplyOfflineSalesUseCase)
get_connect_telegram = _with_uow(ConnectTelegramUseCase)
get_update_shop = _with_uow(UpdateShopUseCase)
get_mark_notification_read = _with_uow(MarkNotificationReadUseCase)
get_mark_all_notifications_read = _with_uow(MarkAllNotificationsReadUseCase)


def get_storefront_catalog(factory: SessionFactoryDep) -> GetStorefrontCatalogUseCase:
    return GetStorefrontCatalogUseCase(factory)


def get_storefront_product(factory: SessionFactoryDep) -> GetStorefrontProductUseCase:
    return GetStorefrontProductUseCase(factory)


def get_storefront_request_status(factory: SessionFactoryDep) -> GetStorefrontRequestStatusUseCase:
    return GetStorefrontRequestStatusUseCase(factory)


def get_create_storefront_request(factory: SessionFactoryDep) -> CreateStorefrontRequestUseCase:
    return CreateStorefrontRequestUseCase(factory)


get_list_storefront_requests = _with_uow(ListStorefrontRequestsUseCase)
get_accept_storefront_request = _with_uow(AcceptStorefrontRequestUseCase)
get_reject_storefront_request = _with_uow(RejectStorefrontRequestUseCase)
get_list_staff_storefront_messages = _with_uow(ListStaffStorefrontMessagesUseCase)
get_send_staff_storefront_message = _with_uow(SendStaffStorefrontMessageUseCase)


def get_list_storefront_messages(factory: SessionFactoryDep) -> ListStorefrontMessagesUseCase:
    return ListStorefrontMessagesUseCase(factory)


def get_send_storefront_message(
    factory: SessionFactoryDep, notifier: NotifierDep
) -> SendStorefrontMessageUseCase:
    return SendStorefrontMessageUseCase(factory, notifier)


def get_create_task(uow: UowDep, notifier: NotifierDep) -> CreateTaskUseCase:
    return CreateTaskUseCase(uow, notifier)


def get_change_task_status(uow: UowDep, notifier: NotifierDep) -> ChangeTaskStatusUseCase:
    return ChangeTaskStatusUseCase(uow, notifier)


def get_update_task(uow: UowDep, notifier: NotifierDep) -> UpdateTaskUseCase:
    return UpdateTaskUseCase(uow, notifier)

# готовые зависимости для сигнатур роутов
RegisterShopDep = Annotated[RegisterShopUseCase, Depends(get_register_shop)]
LoginDep = Annotated[LoginUseCase, Depends(get_login)]
CreateEmployeeDep = Annotated[CreateEmployeeUseCase, Depends(get_create_employee)]
UpdateEmployeeDep = Annotated[UpdateEmployeeUseCase, Depends(get_update_employee)]
ListEmployeesDep = Annotated[ListEmployeesUseCase, Depends(get_list_employees)]
GetShopDep = Annotated[GetShopUseCase, Depends(get_shop)]
CreateProductDep = Annotated[CreateProductUseCase, Depends(get_create_product)]
UpdateProductDep = Annotated[UpdateProductUseCase, Depends(get_update_product)]
CreateUnitDep = Annotated[CreateUnitUseCase, Depends(get_create_unit)]
CreateCategoryDep = Annotated[CreateCategoryUseCase, Depends(get_create_category)]
ImportProductsDep = Annotated[ImportProductsUseCase, Depends(get_import_products)]
PreviewImportProductsDep = Annotated[PreviewProductsUseCase, Depends(get_preview_import_products)]
ApplyImportProductsDep = Annotated[ApplyProductImportUseCase, Depends(get_apply_import_products)]
ListUnitsDep = Annotated[ListUnitsUseCase, Depends(get_list_units)]
ListCategoriesDep = Annotated[ListCategoriesUseCase, Depends(get_list_categories)]
SearchProductsDep = Annotated[SearchProductsUseCase, Depends(get_search_products)]
GetProductByBarcodeDep = Annotated[GetProductByBarcodeUseCase, Depends(get_product_by_barcode)]
GetProductDep = Annotated[GetProductUseCase, Depends(get_product)]
GetProductHistoryDep = Annotated[GetProductHistoryUseCase, Depends(get_product_history)]
GetProductsExportDataDep = Annotated[
    GetProductsExportDataUseCase, Depends(get_products_export_data)
]
SetProductPhotoDep = Annotated[SetProductPhotoUseCase, Depends(get_set_product_photo)]
ReceiveGoodsDep = Annotated[ReceiveGoodsUseCase, Depends(get_receive_goods)]
WriteOffDep = Annotated[WriteOffUseCase, Depends(get_write_off)]
TransferDep = Annotated[TransferUseCase, Depends(get_transfer)]
StocktakeDep = Annotated[StocktakeUseCase, Depends(get_stocktake)]
CreateWarehouseDep = Annotated[CreateWarehouseUseCase, Depends(get_create_warehouse)]
SetWarehouseAssignmentsDep = Annotated[
    SetWarehouseAssignmentsUseCase, Depends(get_set_warehouse_assignments)
]
UpdateWarehouseDetailsDep = Annotated[
    UpdateWarehouseDetailsUseCase, Depends(get_update_warehouse_details)
]
CreateSaleDep = Annotated[CreateSaleUseCase, Depends(get_create_sale)]
ReturnSaleDep = Annotated[ReturnSaleUseCase, Depends(get_return_sale)]
EditSaleDep = Annotated[EditSaleUseCase, Depends(get_edit_sale)]
DeleteSaleDep = Annotated[DeleteSaleUseCase, Depends(get_delete_sale)]
ListSalesDep = Annotated[ListSalesUseCase, Depends(get_list_sales)]
GetSalesSummaryDep = Annotated[GetSalesSummaryUseCase, Depends(get_sales_summary)]
GetSaleDep = Annotated[GetSaleUseCase, Depends(get_sale)]
GetSaleHistoryDep = Annotated[GetSaleHistoryUseCase, Depends(get_sale_history)]
ListSaleReturnsDep = Annotated[ListSaleReturnsUseCase, Depends(get_sale_returns)]
GetReceiptDataDep = Annotated[GetReceiptDataUseCase, Depends(get_receipt_data)]
IssueDebtDep = Annotated[IssueDebtUseCase, Depends(get_issue_debt)]
IssueSupplierDebtDep = Annotated[
    IssueSupplierDebtUseCase, Depends(get_issue_supplier_debt)
]
RepayDebtDep = Annotated[RepayDebtUseCase, Depends(get_repay_debt)]
CreateInstallmentDep = Annotated[CreateInstallmentUseCase, Depends(get_create_installment)]
ExtendDebtDep = Annotated[ExtendDebtUseCase, Depends(get_extend_debt)]
ListDebtsDep = Annotated[ListDebtsUseCase, Depends(get_list_debts)]
GetDebtsOverviewDep = Annotated[GetDebtsOverviewUseCase, Depends(get_debts_overview)]
ListDueDebtsDep = Annotated[ListDueDebtsUseCase, Depends(get_list_due_debts)]
ListClientDebtsDep = Annotated[ListClientDebtsUseCase, Depends(get_list_client_debts)]
ListSupplierDebtsDep = Annotated[ListSupplierDebtsUseCase, Depends(get_list_supplier_debts)]
GetDebtDep = Annotated[GetDebtUseCase, Depends(get_debt)]
GetDebtHistoryDep = Annotated[GetDebtHistoryUseCase, Depends(get_debt_history)]
CreateOrderDep = Annotated[CreateOrderUseCase, Depends(get_create_order)]
UpdateOrderDep = Annotated[UpdateOrderUseCase, Depends(get_update_order)]
ChangeOrderStatusDep = Annotated[ChangeOrderStatusUseCase, Depends(get_change_order_status)]
CancelOrderDep = Annotated[CancelOrderUseCase, Depends(get_cancel_order)]
IssueOrderDep = Annotated[IssueOrderUseCase, Depends(get_issue_order)]
ListActiveOrdersDep = Annotated[ListActiveOrdersUseCase, Depends(get_list_active_orders)]
ListCompletedOrdersDep = Annotated[ListCompletedOrdersUseCase, Depends(get_list_completed_orders)]
GetOrderDep = Annotated[GetOrderUseCase, Depends(get_order)]
GetOrderHistoryDep = Annotated[GetOrderHistoryUseCase, Depends(get_order_history)]
CreateClientDep = Annotated[CreateClientUseCase, Depends(get_create_client)]
UpdateClientDep = Annotated[UpdateClientUseCase, Depends(get_update_client)]
GetClientTimelineDep = Annotated[GetClientTimelineUseCase, Depends(get_client_timeline)]
GetClientSummaryDep = Annotated[GetClientSummaryUseCase, Depends(get_client_summary)]
CreateSupplierDep = Annotated[CreateSupplierUseCase, Depends(get_create_supplier)]
SearchClientsDep = Annotated[SearchClientsUseCase, Depends(get_search_clients)]
ListSuppliersDep = Annotated[ListSuppliersUseCase, Depends(get_list_suppliers)]
GetDashboardDep = Annotated[GetDashboardUseCase, Depends(get_dashboard)]
GetPeriodTotalsDep = Annotated[GetPeriodTotalsUseCase, Depends(get_period_totals)]
GetRevenueTimelineDep = Annotated[GetRevenueTimelineUseCase, Depends(get_revenue_timeline)]
GetTopProductsDep = Annotated[GetTopProductsUseCase, Depends(get_top_products)]
GetCategoryProfitDep = Annotated[GetCategoryProfitUseCase, Depends(get_category_profit)]
GetDeadStockDep = Annotated[GetDeadStockUseCase, Depends(get_dead_stock)]
GetStockValueDep = Annotated[GetStockValueUseCase, Depends(get_stock_value)]
GetRestockRecommendationsDep = Annotated[
    GetRestockRecommendationsUseCase, Depends(get_restock_recommendations)
]
ApplyOfflineSalesDep = Annotated[
    ApplyOfflineSalesUseCase, Depends(get_apply_offline_sales)
]
ConnectTelegramDep = Annotated[ConnectTelegramUseCase, Depends(get_connect_telegram)]
UpdateShopDep = Annotated[UpdateShopUseCase, Depends(get_update_shop)]
ChangePasswordDep = Annotated[ChangePasswordUseCase, Depends(get_change_password)]
LogoutAllDep = Annotated[LogoutAllUseCase, Depends(get_logout_all)]
CreateTaskDep = Annotated[CreateTaskUseCase, Depends(get_create_task)]
ChangeTaskStatusDep = Annotated[ChangeTaskStatusUseCase, Depends(get_change_task_status)]
UpdateTaskDep = Annotated[UpdateTaskUseCase, Depends(get_update_task)]
MarkNotificationReadDep = Annotated[
    MarkNotificationReadUseCase, Depends(get_mark_notification_read)
]
MarkAllNotificationsReadDep = Annotated[
    MarkAllNotificationsReadUseCase, Depends(get_mark_all_notifications_read)
]
GetStorefrontCatalogDep = Annotated[
    GetStorefrontCatalogUseCase, Depends(get_storefront_catalog)
]
GetStorefrontProductDep = Annotated[
    GetStorefrontProductUseCase, Depends(get_storefront_product)
]
GetStorefrontRequestStatusDep = Annotated[
    GetStorefrontRequestStatusUseCase, Depends(get_storefront_request_status)
]
CreateStorefrontRequestDep = Annotated[
    CreateStorefrontRequestUseCase, Depends(get_create_storefront_request)
]
ListStorefrontRequestsDep = Annotated[
    ListStorefrontRequestsUseCase, Depends(get_list_storefront_requests)
]
AcceptStorefrontRequestDep = Annotated[
    AcceptStorefrontRequestUseCase, Depends(get_accept_storefront_request)
]
RejectStorefrontRequestDep = Annotated[
    RejectStorefrontRequestUseCase, Depends(get_reject_storefront_request)
]
ListStorefrontMessagesDep = Annotated[
    ListStorefrontMessagesUseCase, Depends(get_list_storefront_messages)
]
SendStorefrontMessageDep = Annotated[
    SendStorefrontMessageUseCase, Depends(get_send_storefront_message)
]
ListStaffStorefrontMessagesDep = Annotated[
    ListStaffStorefrontMessagesUseCase, Depends(get_list_staff_storefront_messages)
]
SendStaffStorefrontMessageDep = Annotated[
    SendStaffStorefrontMessageUseCase, Depends(get_send_staff_storefront_message)
]
 