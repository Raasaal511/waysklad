from app.domain.catalog.barcode import Barcode
from app.domain.catalog.entities import Category, Product, ProductVariant, ServiceDetails
from app.domain.common.money import Money
from app.domain.common.quantity import Unit
from app.infrastructure.db.models.catalog import (
    CategoryModel,
    ProductModel,
    ProductVariantModel,
    ServiceModel,
    UnitModel,
)


class CategoryMapper:
    @staticmethod
    def to_orm(category: Category, tenant_id: int) -> CategoryModel:
        return CategoryModel(
            tenant_id=tenant_id,
            name=category.name,
            parent_id=category.parent_id,
            platform_category_id=category.platform_category_id,
        )

    @staticmethod
    def to_entity(model: CategoryModel) -> Category:
        return Category(
            id=model.id,
            name=model.name,
            parent_id=model.parent_id,
            platform_category_id=model.platform_category_id,
        )


class UnitMapper:
    @staticmethod
    def to_orm(unit: Unit, tenant_id: int) -> UnitModel:
        return UnitModel(
            tenant_id=tenant_id, code=unit.code, name=unit.name, fractional=unit.fractional
        )

    @staticmethod
    def to_entity(model: UnitModel) -> Unit:
        return Unit(code=model.code, name=model.name, fractional=model.fractional)


class ProductVariantMapper:
    @staticmethod
    def to_orm(variant: ProductVariant, tenant_id: int) -> ProductVariantModel:
        return ProductVariantModel(
            tenant_id=tenant_id,
            size=variant.size,
            color=variant.color,
            barcode=variant.barcode.value if variant.barcode else None,
            photo=variant.photo,
            price=variant.price.amount if variant.price else None,
            name=variant.name,
            addon=variant.addon,
        )

    @staticmethod
    def to_entity(model: ProductVariantModel) -> ProductVariant:
        return ProductVariant(
            id=model.id,
            size=model.size,
            color=model.color,
            barcode=Barcode(model.barcode) if model.barcode else None,
            photo=model.photo,
            price=Money(model.price) if model.price is not None else None,
            name=model.name,
            addon=model.addon,
        )


class ProductMapper:
    @staticmethod
    def to_orm(product: Product, tenant_id: int) -> ProductModel:
        return ProductModel(
            tenant_id=tenant_id,
            name=product.name,
            sku=product.sku or None,
            barcode=product.barcode.value if product.barcode else None,
            category_id=product.category_id,
            unit_code=product.unit.code,
            purchase_price=product.purchase_price.amount,
            retail_price=product.retail_price.amount,
            compare_at_price=product.compare_at_price.amount
            if product.compare_at_price is not None
            else None,
            min_stock=product.min_stock,
            photo=product.photo,
            description=product.description,
            warranty_text=product.warranty_text,
            storefront_photos=list(product.storefront_photos),
            show_on_storefront=product.show_on_storefront,
            storefront_min_qty=product.storefront_min_qty,
            storefront_step_qty=product.storefront_step_qty,
            kind=product.kind,
            variants=[ProductVariantMapper.to_orm(v, tenant_id) for v in product.variants],
            service=ServiceMapper.to_orm(product.service, tenant_id)
            if product.service is not None
            else None,
        )

    @staticmethod
    def to_entity(model: ProductModel, units: dict[str, Unit]) -> Product:
        fallback = Unit(model.unit_code, model.unit_code, fractional=True)
        return Product(
            id=model.id,
            name=model.name,
            unit=units.get(model.unit_code, fallback),
            purchase_price=Money(model.purchase_price),
            retail_price=Money(model.retail_price),
            compare_at_price=Money(model.compare_at_price)
            if model.compare_at_price is not None
            else None,
            sku=model.sku or "",
            barcode=Barcode(model.barcode) if model.barcode else None,
            category_id=model.category_id,
            photo=model.photo,
            description=model.description,
            warranty_text=model.warranty_text,
            storefront_photos=list(model.storefront_photos or []),
            min_stock=model.min_stock,
            show_on_storefront=model.show_on_storefront,
            storefront_min_qty=model.storefront_min_qty,
            storefront_step_qty=model.storefront_step_qty,
            kind=model.kind,
            variants=[ProductVariantMapper.to_entity(v) for v in model.variants],
            service=ServiceMapper.to_entity(model.service) if model.service is not None else None,
        )


class ServiceMapper:
    @staticmethod
    def to_orm(service: ServiceDetails, tenant_id: int) -> ServiceModel:
        return ServiceModel(
            tenant_id=tenant_id,
            duration_minutes=service.duration_minutes,
            performer_id=service.performer_id,
        )

    @staticmethod
    def to_entity(model: ServiceModel) -> ServiceDetails:
        return ServiceDetails(
            duration_minutes=model.duration_minutes,
            performer_id=model.performer_id,
        )
