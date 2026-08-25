from app.domain.common.money import Money
from app.domain.common.phone import Phone
from app.domain.counterparties.entities import Client, Supplier
from app.infrastructure.db.models.counterparties import ClientModel, SupplierModel


class ClientMapper:
    @staticmethod
    def to_orm(client: Client, tenant_id: int) -> ClientModel:
        return ClientModel(
            tenant_id=tenant_id,
            name=client.name,
            phone=str(client.phone) if client.phone else "",
            whatsapp=str(client.whatsapp) if client.whatsapp else "",
            city=client.city,
            debt_limit=client.debt_limit.amount if client.debt_limit else None,
        )

    @staticmethod
    def to_entity(model: ClientModel) -> Client:
        return Client(
            id=model.id,
            name=model.name,
            phone=Phone(model.phone) if model.phone else None,
            whatsapp=Phone(model.whatsapp) if model.whatsapp else None,
            city=model.city,
            debt_limit=Money(model.debt_limit) if model.debt_limit is not None else None,
            is_active=model.is_active,
        )


class SupplierMapper:
    @staticmethod
    def to_orm(supplier: Supplier, tenant_id: int) -> SupplierModel:
        return SupplierModel(
            tenant_id=tenant_id,
            name=supplier.name,
            contact=supplier.contact,
            note=supplier.note,
        )

    @staticmethod
    def to_entity(model: SupplierModel) -> Supplier:
        return Supplier(id=model.id, name=model.name, contact=model.contact, note=model.note)
