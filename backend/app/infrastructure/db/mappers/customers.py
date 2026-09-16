from app.domain.common.phone import Phone
from app.domain.customers.entities import Customer, CustomerLoginLink
from app.infrastructure.db.models.customers import CustomerLoginLinkModel, CustomerModel


class CustomerMapper:
    @staticmethod
    def to_orm(customer: Customer) -> CustomerModel:
        return CustomerModel(
            phone=str(customer.phone),
            name=customer.name,
            telegram_chat_id=customer.telegram_chat_id,
            token_version=customer.token_version,
        )

    @staticmethod
    def to_entity(model: CustomerModel) -> Customer:
        return Customer(
            id=model.id,
            phone=Phone(model.phone),
            name=model.name,
            telegram_chat_id=model.telegram_chat_id,
            token_version=model.token_version,
        )


class CustomerLoginLinkMapper:
    @staticmethod
    def to_orm(link: CustomerLoginLink) -> CustomerLoginLinkModel:
        return CustomerLoginLinkModel(
            token=link.token,
            phone=str(link.phone),
            created_at=link.created_at,
            customer_id=link.customer_id,
            confirmed_at=link.confirmed_at,
        )

    @staticmethod
    def to_entity(model: CustomerLoginLinkModel) -> CustomerLoginLink:
        return CustomerLoginLink(
            token=model.token,
            phone=Phone(model.phone),
            created_at=model.created_at,
            customer_id=model.customer_id,
            confirmed_at=model.confirmed_at,
        )
