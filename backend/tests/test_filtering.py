import pytest

from app.domain.common.exceptions import InvalidFilterError
from app.domain.filtering.operators import Operator
from app.domain.filtering.spec import Criterion, CriteriaGroup, LogicOp
from app.infrastructure.db.filtering.field_spec import BOOL_OPS, FieldSpec, NUMERIC_OPS, TEXT_OPS
from app.infrastructure.db.filtering.filter_factory import BaseQueryFilterFactory
from app.infrastructure.db.filtering.operator_registry import resolve
from app.infrastructure.db.models.debts import DebtModel


class _DebtFilter(BaseQueryFilterFactory[DebtModel]):
    model = DebtModel
    fields = {
        "client_id": FieldSpec(DebtModel.client_id, NUMERIC_OPS),
        "note": FieldSpec(DebtModel.note, TEXT_OPS),
        "issued_at": FieldSpec(DebtModel.issued_at, NUMERIC_OPS),
        "due_date": FieldSpec(DebtModel.due_date, NUMERIC_OPS),
    }
    allowed_order_fields = {"issued_at", "due_date"}


class TestToSpec:
    def test_parses_implicit_eq(self):
        spec = _DebtFilter._to_spec({"client_id": 5})
        assert spec.root == CriteriaGroup(LogicOp.AND, [Criterion("client_id", Operator.EQ, 5)])

    def test_parses_operator_suffix(self):
        spec = _DebtFilter._to_spec({"note__ilike": "долг"})
        assert spec.root == CriteriaGroup(LogicOp.AND, [Criterion("note", Operator.ILIKE, "долг")])

    def test_skips_none_values(self):
        spec = _DebtFilter._to_spec({"client_id": None, "note": "x"})
        assert spec.root == CriteriaGroup(LogicOp.AND, [Criterion("note", Operator.EQ, "x")])

    def test_skips_reserved_params(self):
        spec = _DebtFilter._to_spec({"limit": 10, "offset": 5, "order_by": "-due_date"})
        assert spec.root is None
        assert spec.limit == 10
        assert spec.offset == 5
        assert spec.order_by == "-due_date"

    def test_empty_params_gives_no_root(self):
        spec = _DebtFilter._to_spec({})
        assert spec.root is None

    def test_default_and_max_limit(self):
        spec = _DebtFilter._to_spec({})
        assert spec.limit == _DebtFilter.default_limit
        spec_over = _DebtFilter._to_spec({"limit": 10_000})
        assert spec_over.limit == _DebtFilter.max_limit


class TestBuildNode:
    def test_simple_criterion_builds_sql_condition(self):
        node = Criterion("client_id", Operator.EQ, 5)
        cond = _DebtFilter._build_node(node, _DebtFilter.fields)
        assert "client_id" in str(cond)

    def test_group_and(self):
        node = CriteriaGroup(
            LogicOp.AND,
            [Criterion("client_id", Operator.EQ, 5), Criterion("note", Operator.ILIKE, "x")],
        )
        cond = _DebtFilter._build_node(node, _DebtFilter.fields)
        sql = str(cond)
        assert "AND" in sql

    def test_group_or(self):
        node = CriteriaGroup(
            LogicOp.OR,
            [Criterion("client_id", Operator.EQ, 5), Criterion("client_id", Operator.EQ, 6)],
        )
        cond = _DebtFilter._build_node(node, _DebtFilter.fields)
        assert "OR" in str(cond)

    def test_unknown_field_raises(self):
        node = Criterion("bogus_field", Operator.EQ, 1)
        with pytest.raises(InvalidFilterError, match="Неизвестное поле"):
            _DebtFilter._build_node(node, _DebtFilter.fields)

    def test_disallowed_operator_raises(self):
        node = Criterion("client_id", Operator.ILIKE, "5")
        with pytest.raises(InvalidFilterError, match="недопустим"):
            _DebtFilter._build_node(node, _DebtFilter.fields)


class TestWithOrder:
    def test_allowed_field_ascending(self):
        from sqlalchemy import select

        stmt = _DebtFilter._with_order(select(DebtModel), "issued_at", _DebtFilter.fields)
        assert "ORDER BY debts.issued_at ASC" in str(stmt)

    def test_allowed_field_descending(self):
        from sqlalchemy import select

        stmt = _DebtFilter._with_order(select(DebtModel), "-issued_at", _DebtFilter.fields)
        assert "ORDER BY debts.issued_at DESC" in str(stmt)

    def test_no_order_by_is_noop(self):
        from sqlalchemy import select

        base = select(DebtModel)
        stmt = _DebtFilter._with_order(base, None, _DebtFilter.fields)
        assert stmt is base

    def test_disallowed_field_raises(self):
        from sqlalchemy import select

        with pytest.raises(InvalidFilterError, match="Сортировка"):
            _DebtFilter._with_order(select(DebtModel), "note", _DebtFilter.fields)


class TestOperatorRegistry:
    @pytest.mark.parametrize(
        "op",
        [
            Operator.EQ, Operator.NE, Operator.GT, Operator.GTE, Operator.LT, Operator.LTE,
            Operator.IN, Operator.NOT_IN, Operator.ILIKE, Operator.IS_NULL, Operator.BETWEEN,
        ],
    )
    def test_all_operators_resolve(self, op):
        fn = resolve(op)
        assert callable(fn)

    def test_between_applies_both_bounds(self):
        fn = resolve(Operator.BETWEEN)
        cond = fn(DebtModel.amount, (1, 10))
        sql = str(cond)
        assert "BETWEEN" in sql

    def test_is_null_true_vs_false(self):
        fn = resolve(Operator.IS_NULL)
        assert "IS NULL" in str(fn(DebtModel.due_date, True))
        assert "IS NOT NULL" in str(fn(DebtModel.due_date, False))


def test_field_spec_op_sets_are_disjoint_from_bool_and_numeric_where_expected():
    # BOOL_OPS не должен разрешать числовые сравнения — контроль от случайного расширения
    assert Operator.GT not in BOOL_OPS
    assert Operator.ILIKE not in NUMERIC_OPS
