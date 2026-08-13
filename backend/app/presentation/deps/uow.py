from typing import Annotated

from fastapi import Depends

from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.presentation.deps.auth import CurrentUserDep
from app.presentation.deps.session import (  # noqa: F401  (реэкспорт для обратной совместимости)
    SessionFactoryDep,
    get_session_factory,
)


def get_public_uow(factory: SessionFactoryDep) -> SqlAlchemyUnitOfWork:
    # без tenant — только для регистрации и логина
    return SqlAlchemyUnitOfWork(None, session_factory=factory)


def get_uow(user: CurrentUserDep, factory: SessionFactoryDep) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(user.tenant_id, session_factory=factory)


PublicUowDep = Annotated[SqlAlchemyUnitOfWork, Depends(get_public_uow)]
UowDep = Annotated[SqlAlchemyUnitOfWork, Depends(get_uow)]
