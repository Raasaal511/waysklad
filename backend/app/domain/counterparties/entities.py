from dataclasses import dataclass

from app.domain.common.money import Money
from app.domain.common.phone import Phone


@dataclass
class Client:
    id: int | None
    name: str
    phone: Phone | None = None
    whatsapp: Phone | None = None
    city: str = ""
    debt_limit: Money | None = None  # лимит долга, None — без лимита
    is_active: bool = True


@dataclass
class Supplier:
    id: int | None
    name: str
    contact: str = ""
    note: str = ""
