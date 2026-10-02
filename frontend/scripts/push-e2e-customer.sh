#!/bin/sh
# Печатает JWT нового покупателя витрины — для scripts/push-e2e.mjs
# (PUSH_E2E_CUSTOMER_TOKEN_CMD=scripts/push-e2e-customer.sh). Только локально.
exec docker exec waysklad-backend-1 python -c "
import asyncio, random
from app.domain.common.phone import Phone
from app.domain.customers.entities import Customer
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.security import create_customer_access_token

async def main():
    async with SqlAlchemyUnitOfWork(None) as uow:
        customer = await uow.customers.add(Customer(id=None, phone=Phone('+7928' + str(random.randint(1000000, 9999999)))))
        await uow.commit()
    print(create_customer_access_token(customer.id))

asyncio.run(main())
"
