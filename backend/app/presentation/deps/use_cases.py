from typing import Annotated

from fastapi import Depends

from app.application.analytics.dashboard import GetDashboardUseCase
from app.application.analytics.dead_stock import GetDeadStockUseCase, GetStockValueUseCase
from app.application.analytics.missed_sales import GetMissedSalesUseCase
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
from app.application.auth.delete_shop_logo import DeleteShopLogoUseCase
from app.application.auth.get_shop import GetShopUseCase
from app.application.auth.list_employees import ListEmployeesUseCase
from app.application.auth.login import LoginUseCase
from app.application.auth.logout_all import LogoutAllUseCase
from app.application.auth.register_shop import RegisterShopUseCase
from app.application.auth.set_shop_logo import SetShopLogoUseCase
from app.application.auth.update_employee import UpdateEmployeeUseCase
from app.application.auth.update_shop import UpdateShopUseCase
from app.application.counterparties.create_client import CreateClientUseCase
from app.application.counterparties.create_supplier import CreateSupplierUseCase
from app.application.counterparties.get_client_summary import GetClientSummaryUseCase
from app.application.counterparties.get_client_timeline import GetClientTimelineUseCase
from app.application.counterparties.list_suppliers import ListSuppliersUseCase
from app.application.counterparties.search_clients import SearchClientsUseCase
from app.application.counterparties.update_client import UpdateClientUseCase
from app.application.customers.get_login_status import GetCustomerLoginStatusUseCase
from app.application.customers.get_profile import GetCustomerProfileUseCase
from app.application.customers.list_my_requests import ListMyStorefrontRequestsUseCase
from app.application.customers.request_login_link import RequestCustomerLoginLinkUseCase
from app.application.customers.update_profile import UpdateCustomerProfileUseCase
from app.application.debts.create_installment import CreateInstallmentUseCase
from app.application.debts.extend_debt import ExtendDebtUseCase
from app.application.debts.get_debt import GetDebtUseCase
from app.application.debts.get_debt_history import GetDebtHistoryUseCase
from app.application.debts.get_debt_receipt_data import GetDebtReceiptDataUseCase
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
from app.application.inventory.get_document import GetDocumentUseCase
from app.application.inventory.get_document_export_data import GetDocumentExportDataUseCase
from app.application.inventory.list_documents import ListDocumentsUseCase
from app.application.inventory.list_stock import ListStockUseCase
from app.application.inventory.list_warehouses import ListWarehousesUseCase
from app.application.inventory.receive_goods import ReceiveGoodsUseCase
from app.application.inventory.set_warehouse_assignments import (
    SetWarehouseAssignmentsUseCase,
)
from app.application.inventory.set_warehouse_photo import SetWarehousePhotoUseCase
from app.application.inventory.stocktake import StocktakeUseCase
from app.application.inventory.transfer import TransferUseCase
from app.application.inventory.update_warehouse_details import (
    UpdateWarehouseDetailsUseCase,
)
from app.application.inventory.write_off import WriteOffUseCase
from app.application.marketplace.get_home import GetMarketplaceHomeUseCase
from app.application.marketplace.get_product import GetMarketplaceProductUseCase
from app.application.marketplace.list_cities import ListCitiesUseCase
from app.application.marketplace.list_platform_categories import ListPlatformCategoriesUseCase
from app.application.marketplace.list_products import ListMarketplaceProductsUseCase
from app.application.marketplace.list_shops import ListShopsUseCase
from app.application.marketplace.suggest import SuggestUseCase
from app.application.notifications.list_notifications import ListNotificationsUseCase
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
from app.application.products.add_storefront_photo import AddStorefrontPhotoUseCase
from app.application.products.apply_import import ApplyProductImportUseCase
from app.application.products.create_category import CreateCategoryUseCase
from app.application.products.update_category import UpdateCategoryUseCase
from app.application.products.create_product import CreateProductUseCase
from app.application.products.create_unit import CreateUnitUseCase
from app.application.products.delete_product import DeleteProductUseCase
from app.application.products.generate_barcode import GenerateBarcodeUseCase
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
from app.application.products.set_variant_photo import SetVariantPhotoUseCase
from app.application.products.set_storefront_photos import SetStorefrontPhotosUseCase
from app.application.products.update_product import UpdateProductUseCase
from app.application.sales.create_sale import CreateSaleUseCase
from app.application.sales.delete_sale import DeleteSaleUseCase
from app.application.sales.edit_sale import EditSaleUseCase
from app.application.reviews.check_review_eligibility import CheckReviewEligibilityUseCase
from app.application.reviews.create_review import CreateReviewUseCase
from app.application.reviews.list_all_reviews_for_owner import ListAllReviewsForOwnerUseCase
from app.application.reviews.list_product_reviews import ListProductReviewsUseCase
from app.application.reviews.list_reviews_for_owner import ListReviewsForOwnerUseCase
from app.application.reviews.set_review_hidden import SetReviewHiddenUseCase
from app.application.reviews.upload_review_photo import UploadReviewPhotoUseCase
from app.application.reviews.vote_review import VoteReviewUseCase
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
from app.application.storefront.get_profile import GetStorefrontProfileUseCase
from app.application.storefront.get_similar_products import GetSimilarProductsUseCase
from app.application.storefront.get_request import GetStorefrontRequestUseCase
from app.application.storefront.get_request_status import GetStorefrontRequestStatusUseCase
from app.application.storefront.list_messages import (
    ListStaffStorefrontMessagesUseCase,
    ListStorefrontMessagesUseCase,
)
from app.application.storefront.list_requests import ListStorefrontRequestsUseCase
from app.application.storefront.record_product_view import RecordProductViewUseCase
from app.application.storefront.reject_request import RejectStorefrontRequestUseCase
from app.application.storefront.send_message import (
    SendStaffStorefrontMessageUseCase,
    SendStorefrontMessageUseCase,
)
from app.application.sync.apply_offline_ops import ApplyOfflineSalesUseCase
from app.application.tasks.change_status import ChangeTaskStatusUseCase
from app.application.tasks.get_task import GetTaskUseCase
from app.application.tasks.get_task_history import GetTaskHistoryUseCase
from app.application.tasks.list_tasks import ListActiveTasksUseCase, ListCompletedTasksUseCase
from app.application.tasks.update_task import UpdateTaskUseCase
from app.application.tasks.create_task import CreateTaskUseCase
from app.presentation.deps.cache import CacheDep
from app.presentation.deps.notifier import NotifierDep
from app.presentation.deps.security import FileStorageDep, HasherDep
from app.presentation.deps.session import SessionFactoryDep
from app.presentation.deps.uow import PublicUowDep, UowDep


def _with_uow(use_case_cls):
    def provider(uow: UowDep):
        return use_case_cls(uow)

    return provider


def _with_uow_and_cache(use_case_cls):
    """Для use case, чьи мутации инвалидируют storefront-кеш (см. invalidate_shop_cache
    в app/infrastructure/cache_aside.py) — в отличие от _with_uow, пробрасывает CacheDep."""

    def provider(uow: UowDep, cache: CacheDep):
        return use_case_cls(uow, cache)

    return provider


def _with_uow_and_notifier(use_case_cls):
    """Для use case, отправляющих мгновенное уведомление (Telegram + in-app) —
    пробрасывает NotifierDep вторым позиционным аргументом."""

    def provider(uow: UowDep, notifier: NotifierDep):
        return use_case_cls(uow, notifier)

    return provider


def get_register_shop(uow: PublicUowDep, hasher: HasherDep) -> RegisterShopUseCase:
    return RegisterShopUseCase(uow, hasher)


def get_request_customer_login_link(uow: PublicUowDep) -> RequestCustomerLoginLinkUseCase:
    return RequestCustomerLoginLinkUseCase(uow)


def get_customer_login_status(uow: PublicUowDep) -> GetCustomerLoginStatusUseCase:
    return GetCustomerLoginStatusUseCase(uow)


def get_customer_profile(factory: SessionFactoryDep) -> GetCustomerProfileUseCase:
    return GetCustomerProfileUseCase(factory)


def get_update_customer_profile(factory: SessionFactoryDep) -> UpdateCustomerProfileUseCase:
    return UpdateCustomerProfileUseCase(factory)


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


def get_set_product_photo(
    uow: UowDep, storage: FileStorageDep, cache: CacheDep
) -> SetProductPhotoUseCase:
    return SetProductPhotoUseCase(uow, storage, cache)


def get_set_variant_photo(
    uow: UowDep, storage: FileStorageDep, cache: CacheDep
) -> SetVariantPhotoUseCase:
    return SetVariantPhotoUseCase(uow, storage, cache)


def get_add_storefront_photo(
    uow: UowDep, storage: FileStorageDep, cache: CacheDep
) -> AddStorefrontPhotoUseCase:
    return AddStorefrontPhotoUseCase(uow, storage, cache)


def get_set_storefront_photos(
    uow: UowDep, storage: FileStorageDep, cache: CacheDep
) -> SetStorefrontPhotosUseCase:
    return SetStorefrontPhotosUseCase(uow, storage, cache)


get_create_product = _with_uow_and_cache(CreateProductUseCase)
get_update_product = _with_uow_and_cache(UpdateProductUseCase)
get_delete_product = _with_uow_and_cache(DeleteProductUseCase)
get_create_unit = _with_uow(CreateUnitUseCase)
get_create_category = _with_uow_and_cache(CreateCategoryUseCase)
get_update_category = _with_uow_and_cache(UpdateCategoryUseCase)
get_import_products = _with_uow_and_cache(ImportProductsUseCase)
get_preview_import_products = _with_uow(PreviewProductsUseCase)


get_generate_barcode = _with_uow(GenerateBarcodeUseCase)

get_apply_import_products = _with_uow_and_cache(ApplyProductImportUseCase)
get_list_units = _with_uow(ListUnitsUseCase)
get_list_categories = _with_uow(ListCategoriesUseCase)
get_search_products = _with_uow(SearchProductsUseCase)
get_product_by_barcode = _with_uow(GetProductByBarcodeUseCase)
get_product = _with_uow(GetProductUseCase)
get_product_history = _with_uow(GetProductHistoryUseCase)
get_products_export_data = _with_uow(GetProductsExportDataUseCase)
get_receive_goods = _with_uow_and_cache(ReceiveGoodsUseCase)
get_write_off = _with_uow_and_cache(WriteOffUseCase)
get_transfer = _with_uow_and_cache(TransferUseCase)
get_stocktake = _with_uow_and_cache(StocktakeUseCase)
get_create_warehouse = _with_uow_and_cache(CreateWarehouseUseCase)
get_set_warehouse_assignments = _with_uow(SetWarehouseAssignmentsUseCase)
get_update_warehouse_details = _with_uow_and_cache(UpdateWarehouseDetailsUseCase)


def get_set_warehouse_photo(uow: UowDep, storage: FileStorageDep) -> SetWarehousePhotoUseCase:
    return SetWarehousePhotoUseCase(uow, storage)

get_list_warehouses = _with_uow(ListWarehousesUseCase)
get_list_stock = _with_uow(ListStockUseCase)
get_list_documents = _with_uow(ListDocumentsUseCase)
get_document = _with_uow(GetDocumentUseCase)
get_document_export_data = _with_uow(GetDocumentExportDataUseCase)
def get_create_sale(uow: UowDep, cache: CacheDep, notifier: NotifierDep) -> CreateSaleUseCase:
    return CreateSaleUseCase(uow, cache, notifier)

get_return_sale = _with_uow_and_cache(ReturnSaleUseCase)
get_edit_sale = _with_uow(EditSaleUseCase)
get_delete_sale = _with_uow_and_cache(DeleteSaleUseCase)
get_list_sales = _with_uow(ListSalesUseCase)
get_sales_summary = _with_uow(GetSalesSummaryUseCase)
get_sale = _with_uow(GetSaleUseCase)
get_sale_history = _with_uow(GetSaleHistoryUseCase)
get_sale_returns = _with_uow(ListSaleReturnsUseCase)
get_receipt_data = _with_uow(GetReceiptDataUseCase)
get_issue_debt = _with_uow_and_notifier(IssueDebtUseCase)
get_issue_supplier_debt = _with_uow_and_notifier(IssueSupplierDebtUseCase)
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
get_debt_receipt_data = _with_uow(GetDebtReceiptDataUseCase)
get_create_order = _with_uow(CreateOrderUseCase)
get_update_order = _with_uow(UpdateOrderUseCase)
get_change_order_status = _with_uow(ChangeOrderStatusUseCase)
get_cancel_order = _with_uow(CancelOrderUseCase)
get_issue_order = _with_uow_and_cache(IssueOrderUseCase)
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
get_missed_sales = _with_uow(GetMissedSalesUseCase)
get_apply_offline_sales = _with_uow_and_cache(ApplyOfflineSalesUseCase)
get_connect_telegram = _with_uow(ConnectTelegramUseCase)
get_update_shop = _with_uow_and_cache(UpdateShopUseCase)


def get_set_shop_logo(
    uow: UowDep, storage: FileStorageDep, cache: CacheDep
) -> SetShopLogoUseCase:
    return SetShopLogoUseCase(uow, storage, cache)


def get_delete_shop_logo(
    uow: UowDep, storage: FileStorageDep, cache: CacheDep
) -> DeleteShopLogoUseCase:
    return DeleteShopLogoUseCase(uow, storage, cache)
get_mark_notification_read = _with_uow(MarkNotificationReadUseCase)
get_mark_all_notifications_read = _with_uow(MarkAllNotificationsReadUseCase)
get_list_notifications = _with_uow(ListNotificationsUseCase)


def get_storefront_catalog(
    factory: SessionFactoryDep, cache: CacheDep
) -> GetStorefrontCatalogUseCase:
    return GetStorefrontCatalogUseCase(factory, cache)


def get_list_marketplace_products(
    factory: SessionFactoryDep, cache: CacheDep
) -> ListMarketplaceProductsUseCase:
    return ListMarketplaceProductsUseCase(factory, cache)


def get_marketplace_product(
    factory: SessionFactoryDep, cache: CacheDep
) -> GetMarketplaceProductUseCase:
    return GetMarketplaceProductUseCase(factory, cache)


def get_list_platform_categories(
    factory: SessionFactoryDep, cache: CacheDep
) -> ListPlatformCategoriesUseCase:
    return ListPlatformCategoriesUseCase(factory, cache)


def get_list_cities(factory: SessionFactoryDep, cache: CacheDep) -> ListCitiesUseCase:
    return ListCitiesUseCase(factory, cache)


def get_marketplace_home(factory: SessionFactoryDep, cache: CacheDep) -> GetMarketplaceHomeUseCase:
    return GetMarketplaceHomeUseCase(factory, cache)


def get_list_shops(factory: SessionFactoryDep, cache: CacheDep) -> ListShopsUseCase:
    return ListShopsUseCase(factory, cache)


def get_suggest(factory: SessionFactoryDep, cache: CacheDep) -> SuggestUseCase:
    return SuggestUseCase(factory, cache)


def get_storefront_product(
    factory: SessionFactoryDep, cache: CacheDep
) -> GetStorefrontProductUseCase:
    return GetStorefrontProductUseCase(factory, cache)


def get_storefront_profile(
    factory: SessionFactoryDep, cache: CacheDep
) -> GetStorefrontProfileUseCase:
    return GetStorefrontProfileUseCase(factory, cache)


def get_similar_products(
    factory: SessionFactoryDep, cache: CacheDep
) -> GetSimilarProductsUseCase:
    return GetSimilarProductsUseCase(factory, cache)


def get_record_product_view(
    factory: SessionFactoryDep, cache: CacheDep
) -> RecordProductViewUseCase:
    return RecordProductViewUseCase(factory, cache)


def get_storefront_request_status(factory: SessionFactoryDep) -> GetStorefrontRequestStatusUseCase:
    return GetStorefrontRequestStatusUseCase(factory)


def get_list_my_storefront_requests(
    factory: SessionFactoryDep,
) -> ListMyStorefrontRequestsUseCase:
    return ListMyStorefrontRequestsUseCase(factory)


def get_create_storefront_request(
    factory: SessionFactoryDep, notifier: NotifierDep
) -> CreateStorefrontRequestUseCase:
    return CreateStorefrontRequestUseCase(factory, notifier)


get_list_storefront_requests = _with_uow(ListStorefrontRequestsUseCase)
get_storefront_request = _with_uow(GetStorefrontRequestUseCase)
get_accept_storefront_request = _with_uow_and_cache(AcceptStorefrontRequestUseCase)
get_reject_storefront_request = _with_uow(RejectStorefrontRequestUseCase)
get_list_staff_storefront_messages = _with_uow(ListStaffStorefrontMessagesUseCase)
get_send_staff_storefront_message = _with_uow(SendStaffStorefrontMessageUseCase)


def get_list_storefront_messages(factory: SessionFactoryDep) -> ListStorefrontMessagesUseCase:
    return ListStorefrontMessagesUseCase(factory)


def get_send_storefront_message(
    factory: SessionFactoryDep, notifier: NotifierDep
) -> SendStorefrontMessageUseCase:
    return SendStorefrontMessageUseCase(factory, notifier)


def get_create_review(factory: SessionFactoryDep, cache: CacheDep) -> CreateReviewUseCase:
    return CreateReviewUseCase(factory, cache)


def get_list_product_reviews(factory: SessionFactoryDep) -> ListProductReviewsUseCase:
    return ListProductReviewsUseCase(factory)


def get_upload_review_photo(
    factory: SessionFactoryDep, storage: FileStorageDep
) -> UploadReviewPhotoUseCase:
    return UploadReviewPhotoUseCase(factory, storage)


def get_vote_review(factory: SessionFactoryDep) -> VoteReviewUseCase:
    return VoteReviewUseCase(factory)


def get_check_review_eligibility(factory: SessionFactoryDep) -> CheckReviewEligibilityUseCase:
    return CheckReviewEligibilityUseCase(factory)


get_list_reviews_for_owner = _with_uow(ListReviewsForOwnerUseCase)
get_list_all_reviews_for_owner = _with_uow(ListAllReviewsForOwnerUseCase)
get_set_review_hidden = _with_uow_and_cache(SetReviewHiddenUseCase)


def get_create_task(uow: UowDep, notifier: NotifierDep) -> CreateTaskUseCase:
    return CreateTaskUseCase(uow, notifier)


def get_change_task_status(uow: UowDep, notifier: NotifierDep) -> ChangeTaskStatusUseCase:
    return ChangeTaskStatusUseCase(uow, notifier)


def get_update_task(uow: UowDep, notifier: NotifierDep) -> UpdateTaskUseCase:
    return UpdateTaskUseCase(uow, notifier)


get_list_active_tasks = _with_uow(ListActiveTasksUseCase)
get_list_completed_tasks = _with_uow(ListCompletedTasksUseCase)
get_task = _with_uow(GetTaskUseCase)
get_task_history = _with_uow(GetTaskHistoryUseCase)

# готовые зависимости для сигнатур роутов
RegisterShopDep = Annotated[RegisterShopUseCase, Depends(get_register_shop)]
RequestCustomerLoginLinkDep = Annotated[
    RequestCustomerLoginLinkUseCase, Depends(get_request_customer_login_link)
]
GetCustomerLoginStatusDep = Annotated[
    GetCustomerLoginStatusUseCase, Depends(get_customer_login_status)
]
GetCustomerProfileDep = Annotated[GetCustomerProfileUseCase, Depends(get_customer_profile)]
UpdateCustomerProfileDep = Annotated[
    UpdateCustomerProfileUseCase, Depends(get_update_customer_profile)
]
LoginDep = Annotated[LoginUseCase, Depends(get_login)]
CreateEmployeeDep = Annotated[CreateEmployeeUseCase, Depends(get_create_employee)]
UpdateEmployeeDep = Annotated[UpdateEmployeeUseCase, Depends(get_update_employee)]
ListEmployeesDep = Annotated[ListEmployeesUseCase, Depends(get_list_employees)]
GetShopDep = Annotated[GetShopUseCase, Depends(get_shop)]
CreateProductDep = Annotated[CreateProductUseCase, Depends(get_create_product)]
UpdateProductDep = Annotated[UpdateProductUseCase, Depends(get_update_product)]
DeleteProductDep = Annotated[DeleteProductUseCase, Depends(get_delete_product)]
CreateUnitDep = Annotated[CreateUnitUseCase, Depends(get_create_unit)]
CreateCategoryDep = Annotated[CreateCategoryUseCase, Depends(get_create_category)]
UpdateCategoryDep = Annotated[UpdateCategoryUseCase, Depends(get_update_category)]
ImportProductsDep = Annotated[ImportProductsUseCase, Depends(get_import_products)]
PreviewImportProductsDep = Annotated[PreviewProductsUseCase, Depends(get_preview_import_products)]
GenerateBarcodeDep = Annotated[GenerateBarcodeUseCase, Depends(get_generate_barcode)]
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
SetVariantPhotoDep = Annotated[SetVariantPhotoUseCase, Depends(get_set_variant_photo)]
AddStorefrontPhotoDep = Annotated[
    AddStorefrontPhotoUseCase, Depends(get_add_storefront_photo)
]
SetStorefrontPhotosDep = Annotated[
    SetStorefrontPhotosUseCase, Depends(get_set_storefront_photos)
]
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
SetWarehousePhotoDep = Annotated[SetWarehousePhotoUseCase, Depends(get_set_warehouse_photo)]
ListWarehousesDep = Annotated[ListWarehousesUseCase, Depends(get_list_warehouses)]
ListStockDep = Annotated[ListStockUseCase, Depends(get_list_stock)]
ListDocumentsDep = Annotated[ListDocumentsUseCase, Depends(get_list_documents)]
GetDocumentDep = Annotated[GetDocumentUseCase, Depends(get_document)]
GetDocumentExportDataDep = Annotated[
    GetDocumentExportDataUseCase, Depends(get_document_export_data)
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
GetDebtReceiptDataDep = Annotated[GetDebtReceiptDataUseCase, Depends(get_debt_receipt_data)]
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
GetMissedSalesDep = Annotated[GetMissedSalesUseCase, Depends(get_missed_sales)]
ApplyOfflineSalesDep = Annotated[
    ApplyOfflineSalesUseCase, Depends(get_apply_offline_sales)
]
ConnectTelegramDep = Annotated[ConnectTelegramUseCase, Depends(get_connect_telegram)]
UpdateShopDep = Annotated[UpdateShopUseCase, Depends(get_update_shop)]
SetShopLogoDep = Annotated[SetShopLogoUseCase, Depends(get_set_shop_logo)]
DeleteShopLogoDep = Annotated[DeleteShopLogoUseCase, Depends(get_delete_shop_logo)]
ChangePasswordDep = Annotated[ChangePasswordUseCase, Depends(get_change_password)]
LogoutAllDep = Annotated[LogoutAllUseCase, Depends(get_logout_all)]
CreateTaskDep = Annotated[CreateTaskUseCase, Depends(get_create_task)]
ChangeTaskStatusDep = Annotated[ChangeTaskStatusUseCase, Depends(get_change_task_status)]
UpdateTaskDep = Annotated[UpdateTaskUseCase, Depends(get_update_task)]
ListActiveTasksDep = Annotated[ListActiveTasksUseCase, Depends(get_list_active_tasks)]
ListCompletedTasksDep = Annotated[ListCompletedTasksUseCase, Depends(get_list_completed_tasks)]
GetTaskDep = Annotated[GetTaskUseCase, Depends(get_task)]
GetTaskHistoryDep = Annotated[GetTaskHistoryUseCase, Depends(get_task_history)]
MarkNotificationReadDep = Annotated[
    MarkNotificationReadUseCase, Depends(get_mark_notification_read)
]
MarkAllNotificationsReadDep = Annotated[
    MarkAllNotificationsReadUseCase, Depends(get_mark_all_notifications_read)
]
ListNotificationsDep = Annotated[ListNotificationsUseCase, Depends(get_list_notifications)]
GetStorefrontCatalogDep = Annotated[
    GetStorefrontCatalogUseCase, Depends(get_storefront_catalog)
]
ListMarketplaceProductsDep = Annotated[
    ListMarketplaceProductsUseCase, Depends(get_list_marketplace_products)
]
GetMarketplaceProductDep = Annotated[
    GetMarketplaceProductUseCase, Depends(get_marketplace_product)
]
ListPlatformCategoriesDep = Annotated[
    ListPlatformCategoriesUseCase, Depends(get_list_platform_categories)
]
ListCitiesDep = Annotated[ListCitiesUseCase, Depends(get_list_cities)]
GetMarketplaceHomeDep = Annotated[GetMarketplaceHomeUseCase, Depends(get_marketplace_home)]
ListShopsDep = Annotated[ListShopsUseCase, Depends(get_list_shops)]
SuggestDep = Annotated[SuggestUseCase, Depends(get_suggest)]
GetStorefrontProductDep = Annotated[
    GetStorefrontProductUseCase, Depends(get_storefront_product)
]
GetStorefrontProfileDep = Annotated[
    GetStorefrontProfileUseCase, Depends(get_storefront_profile)
]
GetSimilarProductsDep = Annotated[
    GetSimilarProductsUseCase, Depends(get_similar_products)
]
RecordProductViewDep = Annotated[
    RecordProductViewUseCase, Depends(get_record_product_view)
]
GetStorefrontRequestStatusDep = Annotated[
    GetStorefrontRequestStatusUseCase, Depends(get_storefront_request_status)
]
ListMyStorefrontRequestsDep = Annotated[
    ListMyStorefrontRequestsUseCase, Depends(get_list_my_storefront_requests)
]
CreateStorefrontRequestDep = Annotated[
    CreateStorefrontRequestUseCase, Depends(get_create_storefront_request)
]
ListStorefrontRequestsDep = Annotated[
    ListStorefrontRequestsUseCase, Depends(get_list_storefront_requests)
]
GetStorefrontRequestDep = Annotated[
    GetStorefrontRequestUseCase, Depends(get_storefront_request)
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
CreateReviewDep = Annotated[CreateReviewUseCase, Depends(get_create_review)]
ListProductReviewsDep = Annotated[ListProductReviewsUseCase, Depends(get_list_product_reviews)]
UploadReviewPhotoDep = Annotated[UploadReviewPhotoUseCase, Depends(get_upload_review_photo)]
VoteReviewDep = Annotated[VoteReviewUseCase, Depends(get_vote_review)]
CheckReviewEligibilityDep = Annotated[
    CheckReviewEligibilityUseCase, Depends(get_check_review_eligibility)
]
ListReviewsForOwnerDep = Annotated[
    ListReviewsForOwnerUseCase, Depends(get_list_reviews_for_owner)
]
ListAllReviewsForOwnerDep = Annotated[
    ListAllReviewsForOwnerUseCase, Depends(get_list_all_reviews_for_owner)
]
SetReviewHiddenDep = Annotated[SetReviewHiddenUseCase, Depends(get_set_review_hidden)]
 