from app.domain.catalog.barcode import Barcode
from app.domain.catalog.entities import Product, ProductVariant
from app.domain.common.money import Money
from app.domain.common.quantity import Unit
from app.infrastructure.db.models.catalog import ProductModel, ProductVariantModel


class ProductVariantMapper:
    @staticmethod
    def to_orm(variant: ProductVariant, tenant_id: int) -> ProductVariantModel:
        return ProductVariantModel(
            tenant_id=tenant_id,
            size=variant.size,
            color=variant.color,
            barcode=variant.barcode.value if variant.barcode else None,
        )

    @staticmethod
    def to_entity(model: ProductVariantModel) -> ProductVariant:
        return ProductVariant(
            id=model.id,
            size=model.size,
            color=model.color,
            barcode=Barcode(model.barcode) if model.barcode else None,
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
            min_stock=product.min_stock,
            photo=product.photo,
            variants=[ProductVariantMapper.to_orm(v, tenant_id) for v in product.variants],
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
            sku=model.sku or "",
            barcode=Barcode(model.barcode) if model.barcode else None,
            category_id=model.category_id,
            photo=model.photo,
            min_stock=model.min_stock,
            variants=[ProductVariantMapper.to_entity(v) for v in model.variants],
        )
