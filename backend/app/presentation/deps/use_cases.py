from typing import Annotated

from fastapi import Depends

from app.application.analytics.dashboard import GetDashboardUseCase
from app.application.analytics.dead_stock import GetDeadStockUseCase, GetStockValueUseCase
from app.application.analytics.top_products import (
    GetCategoryProfitUseCase,
    GetTopProductsUseCase,
)
from app.application.auth.connect_telegram import ConnectTelegramUseCase
from app.application.auth.create_employee import CreateEmployeeUseCase
from app.application.auth.login import LoginUseCase
from app.application.auth.register_shop import RegisterShopUseCase
from app.application.counterparties.create_client import CreateClientUseCase
from app.application.counterparties.create_supplier import CreateSupplierUseCase
from app.application.debts.create_installment import CreateInstallmentUseCase
from app.application.debts.issue_debt import IssueDebtUseCase
from app.application.debts.issue_supplier_debt import IssueSupplierDebtUseCase
from app.application.debts.repay_debt import RepayDebtUseCase
from app.application.inventory.create_warehouse import CreateWarehouseUseCase
from app.application.inventory.receive_goods import ReceiveGoodsUseCase
from app.application.inventory.stocktake import StocktakeUseCase
from app.application.inventory.transfer import TransferUseCase
from app.application.inventory.write_off import WriteOffUseCase
from app.application.orders.change_status import ChangeOrderStatusUseCase
from app.application.orders.create_order import CreateOrderUseCase
from app.application.products.create_product import CreateProductUseCase
from app.application.products.create_unit import CreateUnitUseCase
from app.application.products.import_excel import ImportProductsUseCase
from app.application.products.set_product_photo import SetProductPhotoUseCase
from app.application.products.update_product import UpdateProductUseCase
from app.application.sales.create_sale import CreateSaleUseCase
from app.application.sales.return_sale import ReturnSaleUseCase
from app.application.sync.apply_offline_ops import ApplyOfflineSalesUseCase
from app.presentation.deps.security import FileStorageDep, HasherDep
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


def get_set_product_photo(uow: UowDep, storage: FileStorageDep) -> SetProductPhotoUseCase:
    return SetProductPhotoUseCase(uow, storage)


get_create_product = _with_uow(CreateProductUseCase)
get_update_product = _with_uow(UpdateProductUseCase)
get_create_unit = _with_uow(CreateUnitUseCase)
get_import_products = _with_uow(ImportProductsUseCase)
get_receive_goods = _with_uow(ReceiveGoodsUseCase)
get_write_off = _with_uow(WriteOffUseCase)
get_transfer = _with_uow(TransferUseCase)
get_stocktake = _with_uow(StocktakeUseCase)
get_create_warehouse = _with_uow(CreateWarehouseUseCase)
get_create_sale = _with_uow(CreateSaleUseCase)
get_return_sale = _with_uow(ReturnSaleUseCase)
get_issue_debt = _with_uow(IssueDebtUseCase)
get_issue_supplier_debt = _with_uow(IssueSupplierDebtUseCase)
get_repay_debt = _with_uow(RepayDebtUseCase)
get_create_installment = _with_uow(CreateInstallmentUseCase)
get_create_order = _with_uow(CreateOrderUseCase)
get_change_order_status = _with_uow(ChangeOrderStatusUseCase)
get_create_client = _with_uow(CreateClientUseCase)
get_create_supplier = _with_uow(CreateSupplierUseCase)
get_dashboard = _with_uow(GetDashboardUseCase)
get_top_products = _with_uow(GetTopProductsUseCase)
get_category_profit = _with_uow(GetCategoryProfitUseCase)
get_dead_stock = _with_uow(GetDeadStockUseCase)
get_stock_value = _with_uow(GetStockValueUseCase)
get_apply_offline_sales = _with_uow(ApplyOfflineSalesUseCase)
get_connect_telegram = _with_uow(ConnectTelegramUseCase)

# готовые зависимости для сигнатур роутов
RegisterShopDep = Annotated[RegisterShopUseCase, Depends(get_register_shop)]
LoginDep = Annotated[LoginUseCase, Depends(get_login)]
CreateEmployeeDep = Annotated[CreateEmployeeUseCase, Depends(get_create_employee)]
CreateProductDep = Annotated[CreateProductUseCase, Depends(get_create_product)]
UpdateProductDep = Annotated[UpdateProductUseCase, Depends(get_update_product)]
CreateUnitDep = Annotated[CreateUnitUseCase, Depends(get_create_unit)]
ImportProductsDep = Annotated[ImportProductsUseCase, Depends(get_import_products)]
SetProductPhotoDep = Annotated[SetProductPhotoUseCase, Depends(get_set_product_photo)]
ReceiveGoodsDep = Annotated[ReceiveGoodsUseCase, Depends(get_receive_goods)]
WriteOffDep = Annotated[WriteOffUseCase, Depends(get_write_off)]
TransferDep = Annotated[TransferUseCase, Depends(get_transfer)]
StocktakeDep = Annotated[StocktakeUseCase, Depends(get_stocktake)]
CreateWarehouseDep = Annotated[CreateWarehouseUseCase, Depends(get_create_warehouse)]
CreateSaleDep = Annotated[CreateSaleUseCase, Depends(get_create_sale)]
ReturnSaleDep = Annotated[ReturnSaleUseCase, Depends(get_return_sale)]
IssueDebtDep = Annotated[IssueDebtUseCase, Depends(get_issue_debt)]
IssueSupplierDebtDep = Annotated[
    IssueSupplierDebtUseCase, Depends(get_issue_supplier_debt)
]
RepayDebtDep = Annotated[RepayDebtUseCase, Depends(get_repay_debt)]
CreateInstallmentDep = Annotated[CreateInstallmentUseCase, Depends(get_create_installment)]
CreateOrderDep = Annotated[CreateOrderUseCase, Depends(get_create_order)]
ChangeOrderStatusDep = Annotated[ChangeOrderStatusUseCase, Depends(get_change_order_status)]
CreateClientDep = Annotated[CreateClientUseCase, Depends(get_create_client)]
CreateSupplierDep = Annotated[CreateSupplierUseCase, Depends(get_create_supplier)]
GetDashboardDep = Annotated[GetDashboardUseCase, Depends(get_dashboard)]
GetTopProductsDep = Annotated[GetTopProductsUseCase, Depends(get_top_products)]
GetCategoryProfitDep = Annotated[GetCategoryProfitUseCase, Depends(get_category_profit)]
GetDeadStockDep = Annotated[GetDeadStockUseCase, Depends(get_dead_stock)]
GetStockValueDep = Annotated[GetStockValueUseCase, Depends(get_stock_value)]
ApplyOfflineSalesDep = Annotated[
    ApplyOfflineSalesUseCase, Depends(get_apply_offline_sales)
]
ConnectTelegramDep = Annotated[ConnectTelegramUseCase, Depends(get_connect_telegram)]
 