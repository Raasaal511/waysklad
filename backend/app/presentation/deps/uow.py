from typing import Annotated

from fastapi import Depends

from app.infrastructure.db.session import SessionLocal
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.presentation.deps.auth import CurrentUserDep


def get_session_factory():
    # единая точка подмены БД в тестах через dependency_overrides
    return SessionLocal


SessionFactoryDep = Annotated[object, Depends(get_session_factory)]


def get_public_uow(factory: SessionFactoryDep) -> SqlAlchemyUnitOfWork:
    # без tenant — только для регистрации и логина
    return SqlAlchemyUnitOfWork(None, session_factory=factory)


def get_uow(user: CurrentUserDep, factory: SessionFactoryDep) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(user.tenant_id, session_factory=factory)


PublicUowDep = Annotated[SqlAlchemyUnitOfWork, Depends(get_public_uow)]
UowDep = Annotated[SqlAlchemyUnitOfWork, Depends(get_uow)]
