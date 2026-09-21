from datetime import datetime

from sqlalchemy import delete, func, select

from app.domain.common.exceptions import NotFoundError
from app.domain.customers.entities import Customer, CustomerLoginLink
from app.domain.customers.repository import ICustomerLoginLinkRepository, ICustomerRepository
from app.infrastructure.db.mappers.customers import CustomerLoginLinkMapper, CustomerMapper
from app.infrastructure.db.models.customers import CustomerLoginLinkModel, CustomerModel
from app.infrastructure.db.repositories.base import SqlAlchemyRepository


class SqlAlchemyCustomerRepository(SqlAlchemyRepository, ICustomerRepository):
    async def add(self, customer: Customer) -> Customer:
        model = CustomerMapper.to_orm(customer)
        self._session.add(model)
        await self._session.flush()
        customer.id = model.id
        return customer

    async def get(self, customer_id: int) -> Customer:
        model = (
            await self._session.execute(
                select(CustomerModel).where(CustomerModel.id == customer_id)
            )
        ).scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"Покупатель {customer_id} не найден")
        return CustomerMapper.to_entity(model)

    async def get_by_phone(self, phone: str) -> Customer | None:
        model = (
            await self._session.execute(
                select(CustomerModel).where(CustomerModel.phone == phone)
            )
        ).scalar_one_or_none()
        return CustomerMapper.to_entity(model) if model else None

    async def get_by_username(self, username: str) -> Customer | None:
        model = (
            await self._session.execute(
                select(CustomerModel).where(
                    func.lower(CustomerModel.username) == username.strip().lower(),
                    CustomerModel.username != "",
                )
            )
        ).scalar_one_or_none()
        return CustomerMapper.to_entity(model) if model else None

    async def get_token_version(self, customer_id: int) -> int | None:
        return (
            await self._session.execute(
                select(CustomerModel.token_version).where(CustomerModel.id == customer_id)
            )
        ).scalar_one_or_none()

    async def save(self, customer: Customer) -> Customer:
        model = (
            await self._session.execute(
                select(CustomerModel).where(CustomerModel.id == customer.id)
            )
        ).scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"Покупатель {customer.id} не найден")
        model.phone = str(customer.phone)
        model.name = customer.name
        model.telegram_chat_id = customer.telegram_chat_id
        model.username = customer.username
        model.password_hash = customer.password_hash
        model.token_version = customer.token_version
        await self._session.flush()
        return customer


class SqlAlchemyCustomerLoginLinkRepository(SqlAlchemyRepository, ICustomerLoginLinkRepository):
    async def add(self, link: CustomerLoginLink) -> CustomerLoginLink:
        model = CustomerLoginLinkMapper.to_orm(link)
        self._session.add(model)
        await self._session.flush()
        return link

    async def get_by_token(self, token: str) -> CustomerLoginLink | None:
        model = (
            await self._session.execute(
                select(CustomerLoginLinkModel).where(CustomerLoginLinkModel.token == token)
            )
        ).scalar_one_or_none()
        return CustomerLoginLinkMapper.to_entity(model) if model else None

    async def save(self, link: CustomerLoginLink) -> CustomerLoginLink:
        model = (
            await self._session.execute(
                select(CustomerLoginLinkModel).where(CustomerLoginLinkModel.token == link.token)
            )
        ).scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"Ссылка входа {link.token} не найдена")
        model.customer_id = link.customer_id
        model.confirmed_at = link.confirmed_at
        await self._session.flush()
        return link

    async def delete_created_before(self, cutoff: datetime) -> int:
        result = await self._session.execute(
            delete(CustomerLoginLinkModel).where(CustomerLoginLinkModel.created_at < cutoff)
        )
        return result.rowcount or 0
