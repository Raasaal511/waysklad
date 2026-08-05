from typing import Annotated

from fastapi import Depends

from app.infrastructure.files import LocalFileStorage
from app.infrastructure.security import BcryptPasswordHasher


def get_password_hasher() -> BcryptPasswordHasher:
    return BcryptPasswordHasher()


def get_file_storage() -> LocalFileStorage:
    return LocalFileStorage()


HasherDep = Annotated[BcryptPasswordHasher, Depends(get_password_hasher)]
FileStorageDep = Annotated[LocalFileStorage, Depends(get_file_storage)]
