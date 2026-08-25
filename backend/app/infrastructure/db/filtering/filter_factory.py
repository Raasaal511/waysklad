from typing import ClassVar, Generic, TypeVar

from sqlalchemy import Select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.common.exceptions import InvalidFilterError
from app.domain.filtering.operators import Operator
from app.domain.filtering.spec import Criterion, CriteriaGroup, FilterSpec, LogicOp, Node
from app.infrastructure.db.filtering.field_spec import FieldSpec
from app.infrastructure.db.filtering.operator_registry import resolve

ModelT = TypeVar("ModelT")

_RESERVED_PARAMS = {"limit", "offset", "order_by"}


class BaseQueryFilterFactory(Generic[ModelT]):
    """Наследники объявляют только конфиг (model, fields, allowed_order_fields) —
    сам алгоритм разбора query-параметров и сборки WHERE/ORDER BY здесь один
    для всех сущностей и не переопределяется."""

    model: ClassVar[type]
    fields: ClassVar[dict[str, FieldSpec]] = {}
    allowed_order_fields: ClassVar[set[str]] = set()
    default_limit: ClassVar[int] = 50
    max_limit: ClassVar[int] = 200

    @classmethod
    async def fetch_list(
        cls,
        session: AsyncSession,
        raw_params: dict,
        base_stmt: Select,
        fields: dict[str, FieldSpec] | None = None,
    ) -> list:
        spec = cls._to_spec(raw_params)
        fields = fields if fields is not None else cls.fields
        stmt = cls._with_order(cls._with_where(base_stmt, spec, fields), spec.order_by, fields)
        stmt = stmt.limit(spec.limit).offset(spec.offset)
        return list((await session.execute(stmt)).scalars().all())

    @classmethod
    async def fetch_count(
        cls,
        session: AsyncSession,
        raw_params: dict,
        base_stmt: Select,
        fields: dict[str, FieldSpec] | None = None,
    ) -> int:
        spec = cls._to_spec(raw_params)
        fields = fields if fields is not None else cls.fields
        stmt = cls._with_where(base_stmt, spec, fields)
        return (await session.execute(stmt)).scalar_one()

    @classmethod
    def _to_spec(cls, raw_params: dict) -> FilterSpec:
        criteria: list[Criterion] = []
        for key, value in raw_params.items():
            if value is None or key in _RESERVED_PARAMS:
                continue
            field, _, op_suffix = key.partition("__")
            operator = Operator(op_suffix) if op_suffix else Operator.EQ
            criteria.append(Criterion(field, operator, value))
        limit = min(raw_params.get("limit") or cls.default_limit, cls.max_limit)
        return FilterSpec(
            root=CriteriaGroup(LogicOp.AND, criteria) if criteria else None,
            order_by=raw_params.get("order_by"),
            limit=limit,
            offset=raw_params.get("offset") or 0,
        )

    @classmethod
    def _with_where(cls, stmt: Select, spec: FilterSpec, fields: dict[str, FieldSpec]) -> Select:
        return stmt if spec.root is None else stmt.where(cls._build_node(spec.root, fields))

    @classmethod
    def _build_node(cls, node: Node, fields: dict[str, FieldSpec]):
        if isinstance(node, CriteriaGroup):
            parts = [cls._build_node(item, fields) for item in node.items]
            return {LogicOp.AND: and_, LogicOp.OR: or_}[node.op](*parts)
        field_spec = fields.get(node.field)
        if field_spec is None:
            raise InvalidFilterError(f"Неизвестное поле фильтра: «{node.field}»")
        if node.operator not in field_spec.allowed_ops:
            raise InvalidFilterError(
                f"Оператор «{node.operator}» недопустим для поля «{node.field}»"
            )
        return resolve(node.operator)(field_spec.column, node.value)

    @classmethod
    def _with_order(cls, stmt: Select, order_by: str | None, fields: dict[str, FieldSpec]) -> Select:
        if not order_by:
            return stmt
        field = order_by.removeprefix("-")
        if field not in cls.allowed_order_fields:
            raise InvalidFilterError(f"Сортировка по «{field}» недопустима")
        column = fields[field].column
        return stmt.order_by(column.desc() if order_by.startswith("-") else column.asc())
