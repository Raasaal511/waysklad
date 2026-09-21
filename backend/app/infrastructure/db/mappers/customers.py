from app.domain.common.phone import Phone
from app.domain.customers.entities import Customer, CustomerLoginLink, PhoneVerificationCode
from app.infrastructure.db.models.customers import (
    CustomerLoginLinkModel,
    CustomerModel,
    CustomerPhoneCodeModel,
)


class CustomerMapper:
    @staticmethod
    def to_orm(customer: Customer) -> CustomerModel:
        return CustomerModel(
            phone=str(customer.phone),
            name=customer.name,
            telegram_chat_id=customer.telegram_chat_id,
            username=customer.username,
            password_hash=customer.password_hash,
            phone_verified=customer.phone_verified,
            phone_verified_at=customer.phone_verified_at,
            token_version=customer.token_version,
        )

    @staticmethod
    def to_entity(model: CustomerModel) -> Customer:
        return Customer(
            id=model.id,
            phone=Phone(model.phone),
            name=model.name,
            telegram_chat_id=model.telegram_chat_id,
            username=model.username,
            password_hash=model.password_hash,
            phone_verified=model.phone_verified,
            phone_verified_at=model.phone_verified_at,
            created_at=model.created_at,
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
            username=link.username,
            password_hash=link.password_hash,
        )

    @staticmethod
    def to_entity(model: CustomerLoginLinkModel) -> CustomerLoginLink:
        return CustomerLoginLink(
            token=model.token,
            phone=Phone(model.phone),
            created_at=model.created_at,
            customer_id=model.customer_id,
            confirmed_at=model.confirmed_at,
            username=model.username,
            password_hash=model.password_hash,
        )


class PhoneVerificationCodeMapper:
    @staticmethod
    def to_orm(code: PhoneVerificationCode) -> CustomerPhoneCodeModel:
        return CustomerPhoneCodeModel(
            customer_id=code.customer_id,
            phone=str(code.phone),
            code_hash=code.code_hash,
            attempts=code.attempts,
            expires_at=code.expires_at,
            created_at=code.created_at,
            sent_via=code.sent_via,
        )

    @staticmethod
    def to_entity(model: CustomerPhoneCodeModel) -> PhoneVerificationCode:
        return PhoneVerificationCode(
            id=model.id,
            customer_id=model.customer_id,
            phone=Phone(model.phone),
            code_hash=model.code_hash,
            attempts=model.attempts,
            expires_at=model.expires_at,
            created_at=model.created_at,
            sent_via=model.sent_via,
        )
