from typing import Annotated

from fastapi import Depends

from app.infrastructure.db.session import SessionLocal


def get_session_factory():
    # единая точка подмены БД в тестах через dependency_overrides
    return SessionLocal


SessionFactoryDep = Annotated[object, Depends(get_session_factory)]
