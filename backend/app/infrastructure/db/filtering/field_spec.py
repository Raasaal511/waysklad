from dataclasses import dataclass

from sqlalchemy import ColumnElement

from app.domain.filtering.operators import Operator


@dataclass(frozen=True)
class FieldSpec:
    column: ColumnElement
    allowed_ops: frozenset[Operator]


NUMERIC_OPS = frozenset({
    Operator.EQ, Operator.NE, Operator.GT, Operator.GTE, Operator.LT, Operator.LTE,
    Operator.BETWEEN, Operator.IN, Operator.IS_NULL,
})
TEXT_OPS = frozenset({Operator.EQ, Operator.ILIKE, Operator.IN, Operator.IS_NULL})
BOOL_OPS = frozenset({Operator.EQ, Operator.IS_NULL})
DATE_OPS = frozenset({Operator.EQ, Operator.GTE, Operator.LTE, Operator.BETWEEN})
