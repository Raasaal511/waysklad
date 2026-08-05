from typing import Annotated

from fastapi import Depends

from app.application.auth.create_employee import CreateEmployeeUseCase
from app.application.auth.login import LoginUseCase
from app.application.auth.register_shop import RegisterShopUseCase
from app.application.counterparties.create_client import CreateClientUseCase
from app.application.counterparties.create_supplier import CreateSupplierUseCase
from app.application.debts.create_installment import CreateInstallmentUseCase
from app.application.debts.issue_debt import IssueDebtUseCase
from app.application.debts.repay_debt import RepayDebtUseCase
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
get_create_sale = _with_uow(CreateSaleUseCase)
get_issue_debt = _with_uow(IssueDebtUseCase)
get_repay_debt = _with_uow(RepayDebtUseCase)
get_create_installment = _with_uow(CreateInstallmentUseCase)
get_create_order = _with_uow(CreateOrderUseCase)
get_change_order_status = _with_uow(ChangeOrderStatusUseCase)
get_create_client = _with_uow(CreateClientUseCase)
get_create_supplier = _with_uow(CreateSupplierUseCase)

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
CreateSaleDep = Annotated[CreateSaleUseCase, Depends(get_create_sale)]
IssueDebtDep = Annotated[IssueDebtUseCase, Depends(get_issue_debt)]
RepayDebtDep = Annotated[RepayDebtUseCase, Depends(get_repay_debt)]
CreateInstallmentDep = Annotated[CreateInstallmentUseCase, Depends(get_create_installment)]
CreateOrderDep = Annotated[CreateOrderUseCase, Depends(get_create_order)]
ChangeOrderStatusDep = Annotated[ChangeOrderStatusUseCase, Depends(get_change_order_status)]
CreateClientDep = Annotated[CreateClientUseCase, Depends(get_create_client)]
CreateSupplierDep = Annotated[CreateSupplierUseCase, Depends(get_create_supplier)]
