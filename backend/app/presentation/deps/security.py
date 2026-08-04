from typing import Annotated

from fastapi import Depends

from app.infrastructure.security import BcryptPasswordHasher


def get_password_hasher() -> BcryptPasswordHasher:
    return BcryptPasswordHasher()


HasherDep = Annotated[BcryptPasswordHasher, Depends(get_password_hasher)]
