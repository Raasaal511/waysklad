from enum import StrEnum


class Operator(StrEnum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    ILIKE = "ilike"
    IS_NULL = "is_null"
    BETWEEN = "between"
