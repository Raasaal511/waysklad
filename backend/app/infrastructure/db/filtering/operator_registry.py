from typing import Any, Callable

from sqlalchemy import ColumnElement

from app.domain.common.exceptions import InvalidFilterError
from app.domain.filtering.operators import Operator

OperatorFn = Callable[[ColumnElement, Any], ColumnElement]

_OPERATORS: dict[Operator, OperatorFn] = {
    Operator.EQ: lambda col, v: col == v,
    Operator.NE: lambda col, v: col != v,
    Operator.GT: lambda col, v: col > v,
    Operator.GTE: lambda col, v: col >= v,
    Operator.LT: lambda col, v: col < v,
    Operator.LTE: lambda col, v: col <= v,
    Operator.IN: lambda col, v: col.in_(v),
    Operator.NOT_IN: lambda col, v: col.notin_(v),
    Operator.ILIKE: lambda col, v: col.ilike(f"%{v}%"),
    Operator.IS_NULL: lambda col, v: col.is_(None) if v else col.is_not(None),
    Operator.BETWEEN: lambda col, v: col.between(v[0], v[1]),
}


def resolve(op: Operator) -> OperatorFn:
    try:
        return _OPERATORS[op]
    except KeyError:
        raise InvalidFilterError(f"Оператор «{op}» не зарегистрирован") from None
