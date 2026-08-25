from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Union

from app.domain.filtering.operators import Operator


class LogicOp(StrEnum):
    AND = "and"
    OR = "or"


@dataclass(frozen=True)
class Criterion:
    field: str
    operator: Operator
    value: Any = None


@dataclass(frozen=True)
class CriteriaGroup:
    op: LogicOp
    items: list["Node"] = field(default_factory=list)


Node = Union[Criterion, CriteriaGroup]


@dataclass(frozen=True)
class FilterSpec:
    root: Node | None = None
    order_by: str | None = None
    limit: int = 50
    offset: int = 0
