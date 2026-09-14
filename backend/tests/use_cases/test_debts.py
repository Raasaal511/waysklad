from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest
from app.application.auth.create_employee import CreateEmployeeCommand, CreateEmployeeUseCase
from app.application.counterparties.create_client import (
    CreateClientCommand,
    CreateClientUseCase,
)
from app.application.counterparties.create_supplier import (
    CreateSupplierCommand,
    CreateSupplierUseCase,
)
from app.application.debts.create_installment import (
    CreateInstallmentCommand,
    CreateInstallmentUseCase,
    InstallmentInput,
)
from app.application.debts.issue_debt import IssueDebtCommand, IssueDebtUseCase
from app.application.debts.issue_supplier_debt import (
    IssueSupplierDebtCommand,
    IssueSupplierDebtUseCase,
)
from app.application.debts.extend_debt import ExtendDebtCommand, ExtendDebtUseCase
from app.application.debts.get_debt_receipt_data import GetDebtReceiptDataUseCase
from app.application.debts.repay_debt import RepayDebtCommand, RepayDebtUseCase
from app.domain.common.exceptions import (
    AccessDeniedError,
    ClientHasDebtError,
    DomainError,
    InsufficientStockError,
    NotFoundError,
)
from app.domain.common.money import Money
from app.domain.debts.entities import Debt, DebtStatus, total_balance
from app.domain.debts.receipt import render_debt_message
from app.domain.notifications.entities import NotificationKind
from app.domain.identity.entities import Role, Warehouse
from app.domain.identity.permissions import Actor


def test_debt_requires_exactly_one_counterparty():
    both = Debt(
        id=None, warehouse_id=1, amount=Money.of("100"), issued_at=date.today(),
        client_id=1, supplier_id=2,
    )
    with pytest.raises(DomainError):
        both.validate()

    neither = Debt(id=None, warehouse_id=1, amount=Money.of("100"), issued_at=date.today())
    with pytest.raises(DomainError):
        neither.validate()

    Debt(id=None, warehouse_id=1, amount=Money.of("100"), issued_at=date.today(), client_id=1).validate()
    Debt(id=None, warehouse_id=1, amount=Money.of("100"), issued_at=date.today(), supplier_id=1).validate()


def test_total_balance_sums_debts():
    debts = [
        Debt(id=1, warehouse_id=1, amount=Money.of("500"), issued_at=date.today(), client_id=1),
        Debt(id=2, warehouse_id=1, amount=Money.of("300"), issued_at=date.today(), client_id=1),
    ]
    assert total_balance(debts) == Money.of("800")
    assert total_balance([]) == Money.zero()


async def test_issue_supplier_debt_and_list_by_supplier(make_uow, registered_shop, warehouse_id):
    tenant_id, _, owner = registered_shop
    supplier = await CreateSupplierUseCase(make_uow(tenant_id)).execute(
        owner, CreateSupplierCommand(name="ООО СтройПоставка")
    )

    debt = await IssueSupplierDebtUseCase(make_uow(tenant_id)).execute(
        owner,
        IssueSupplierDebtCommand(
            supplier_id=supplier.id, warehouse_id=warehouse_id,
            amount=Decimal("50000"), note="партия цемента",
        ),
    )
    assert debt.supplier_id == supplier.id
    assert debt.client_id is None
    assert debt.balance == Money.of("50000")

    async with make_uow(tenant_id) as uow:
        debts = await uow.debts.list_by_supplier(supplier.id)
        assert len(debts) == 1
        assert total_balance(debts) == Money.of("50000")


async def test_storekeeper_cannot_issue_supplier_debt(
    make_uow, hasher, registered_shop, random_phone, warehouse_id
):
    tenant_id, _, owner = registered_shop
    supplier = await CreateSupplierUseCase(make_uow(tenant_id)).execute(
        owner, CreateSupplierCommand(name="Поставщик")
    )
    storekeeper = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner, CreateEmployeeCommand("Руслан", random_phone(), "secret123", Role.STOREKEEPER)
    )
    with pytest.raises(AccessDeniedError):
        await IssueSupplierDebtUseCase(make_uow(tenant_id)).execute(
            Actor(id=storekeeper.id, role=storekeeper.role),
            IssueSupplierDebtCommand(supplier_id=supplier.id, warehouse_id=warehouse_id, amount=Decimal("1000")),
        )


async def test_issue_debt_respects_debt_limit_without_sale(make_uow, registered_shop, warehouse_id):
    tenant_id, _, owner = registered_shop
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Ибрагим", debt_limit=Decimal("2000"))
    )

    debt = await IssueDebtUseCase(make_uow(tenant_id)).execute(
        owner,
        IssueDebtCommand(
            client_id=client.id, warehouse_id=warehouse_id,
            amount=Decimal("1500"), note="стройматериалы в долг",
        ),
    )
    assert debt.balance == Money.of("1500")

    with pytest.raises(DomainError):
        await IssueDebtUseCase(make_uow(tenant_id)).execute(
            owner, IssueDebtCommand(client_id=client.id, warehouse_id=warehouse_id, amount=Decimal("1000"))
        )


async def test_issue_debt_sends_instant_notification_to_owner(make_uow, registered_shop, warehouse_id):
    tenant_id, _, owner = registered_shop
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Ибрагим")
    )

    debt = await IssueDebtUseCase(make_uow(tenant_id)).execute(
        owner, IssueDebtCommand(client_id=client.id, warehouse_id=warehouse_id, amount=Decimal("1500"))
    )

    async with make_uow(tenant_id) as uow:
        notifications = await uow.notifications.list_for_user(owner.id)
        assert any(
            n.kind is NotificationKind.DEBT_ISSUED and n.entity_id == debt.id for n in notifications
        )


async def test_debt_receipt_message_for_installment(make_uow, registered_shop, warehouse_id, random_phone):
    tenant_id, _, owner = registered_shop
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Юсупов Расул", whatsapp=random_phone())
    )
    debt = await IssueDebtUseCase(make_uow(tenant_id)).execute(
        owner,
        IssueDebtCommand(
            client_id=client.id, warehouse_id=warehouse_id,
            amount=Decimal("84700"), note="17 AIR 256, Б/У, 3 ЦИКЛА",
        ),
    )
    await CreateInstallmentUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateInstallmentCommand(
            debt_id=debt.id,
            schedule=[
                InstallmentInput(due_date=date(2026, 10, 10), amount=Decimal("11200")),
                InstallmentInput(due_date=date(2026, 11, 10), amount=Decimal("11200")),
                InstallmentInput(due_date=date(2026, 12, 10), amount=Decimal("62300")),
            ],
        ),
    )

    data = await GetDebtReceiptDataUseCase(make_uow(tenant_id)).execute(debt.id)
    assert data.client.id == client.id
    text = render_debt_message(data.tenant.name, data.debt, data.client.name)
    assert "Юсупов Расул" in text
    assert "84700" in text
    assert "Ежемесячный платёж: 11200" in text
    assert "10-е число" in text
    assert "Остаток: 84700" in text


async def test_create_installment_schedule_must_match_balance(make_uow, registered_shop, warehouse_id):
    tenant_id, _, owner = registered_shop
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Заур")
    )
    debt = await IssueDebtUseCase(make_uow(tenant_id)).execute(
        owner, IssueDebtCommand(client_id=client.id, warehouse_id=warehouse_id, amount=Decimal("3000"))
    )

    with pytest.raises(DomainError):
        await CreateInstallmentUseCase(make_uow(tenant_id)).execute(
            owner,
            CreateInstallmentCommand(
                debt_id=debt.id,
                schedule=[
                    InstallmentInput(due_date=date.today() + timedelta(days=7), amount=Decimal("1000"))
                ],
            ),
        )

    updated = await CreateInstallmentUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateInstallmentCommand(
            debt_id=debt.id,
            schedule=[
                InstallmentInput(due_date=date.today() + timedelta(days=7), amount=Decimal("1500")),
                InstallmentInput(due_date=date.today() + timedelta(days=14), amount=Decimal("1500")),
            ],
        ),
    )
    assert len(updated.schedule) == 2


async def test_extend_debt_records_history_and_changes_due_date(make_uow, registered_shop, warehouse_id):
    tenant_id, _, owner = registered_shop
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Тимур")
    )
    original_due = date.today() + timedelta(days=3)
    debt = await IssueDebtUseCase(make_uow(tenant_id)).execute(
        owner,
        IssueDebtCommand(client_id=client.id, warehouse_id=warehouse_id, amount=Decimal("1000"), due_date=original_due),
    )

    new_due = date.today() + timedelta(days=10)
    updated = await ExtendDebtUseCase(make_uow(tenant_id)).execute(
        owner, ExtendDebtCommand(debt_id=debt.id, new_due_date=new_due, reason="попросил ещё неделю"),
    )
    assert updated.due_date == new_due
    assert len(updated.extensions) == 1
    assert updated.extensions[0].old_due_date == original_due
    assert updated.extensions[0].new_due_date == new_due
    assert updated.extensions[0].reason == "попросил ещё неделю"
    assert updated.extensions[0].author_id == owner.id


async def test_extend_debt_fails_when_already_closed(make_uow, registered_shop, warehouse_id):
    tenant_id, _, owner = registered_shop
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Рустам")
    )
    debt = await IssueDebtUseCase(make_uow(tenant_id)).execute(
        owner, IssueDebtCommand(client_id=client.id, warehouse_id=warehouse_id, amount=Decimal("500")),
    )
    await RepayDebtUseCase(make_uow(tenant_id)).execute(
        owner, RepayDebtCommand(debt_id=debt.id, amount=Decimal("500")),
    )

    with pytest.raises(DomainError):
        await ExtendDebtUseCase(make_uow(tenant_id)).execute(
            owner,
            ExtendDebtCommand(debt_id=debt.id, new_due_date=date.today() + timedelta(days=5)),
        )


async def test_repay_debt_records_note_and_author(make_uow, registered_shop, warehouse_id):
    tenant_id, _, owner = registered_shop
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Иса")
    )
    debt = await IssueDebtUseCase(make_uow(tenant_id)).execute(
        owner, IssueDebtCommand(client_id=client.id, warehouse_id=warehouse_id, amount=Decimal("800")),
    )

    updated = await RepayDebtUseCase(make_uow(tenant_id)).execute(
        owner,
        RepayDebtCommand(debt_id=debt.id, amount=Decimal("300"), note="занёс наличкой"),
    )
    assert updated.repayments[-1].note == "занёс наличкой"
    assert updated.repayments[-1].author_id == owner.id
    assert updated.balance == Money.of("500")


async def test_debt_status_transitions(make_uow, registered_shop, warehouse_id):
    tenant_id, _, owner = registered_shop
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Магомед")
    )

    active = await IssueDebtUseCase(make_uow(tenant_id)).execute(
        owner,
        IssueDebtCommand(
            client_id=client.id, warehouse_id=warehouse_id,
            amount=Decimal("100"), due_date=date.today() + timedelta(days=30),
        ),
    )
    assert active.status() == DebtStatus.ACTIVE

    due_soon = await IssueDebtUseCase(make_uow(tenant_id)).execute(
        owner,
        IssueDebtCommand(
            client_id=client.id, warehouse_id=warehouse_id,
            amount=Decimal("100"), due_date=date.today() + timedelta(days=2),
        ),
    )
    assert due_soon.status() == DebtStatus.DUE_SOON

    overdue = await IssueDebtUseCase(make_uow(tenant_id)).execute(
        owner,
        IssueDebtCommand(
            client_id=client.id, warehouse_id=warehouse_id,
            amount=Decimal("100"), due_date=date.today() - timedelta(days=1),
        ),
    )
    assert overdue.status() == DebtStatus.OVERDUE

    partially_paid = await IssueDebtUseCase(make_uow(tenant_id)).execute(
        owner,
        IssueDebtCommand(
            client_id=client.id, warehouse_id=warehouse_id,
            amount=Decimal("100"), due_date=date.today() + timedelta(days=30),
        ),
    )
    partially_paid = await RepayDebtUseCase(make_uow(tenant_id)).execute(
        owner, RepayDebtCommand(debt_id=partially_paid.id, amount=Decimal("40")),
    )
    assert partially_paid.status() == DebtStatus.PARTIALLY_PAID

    closed = await IssueDebtUseCase(make_uow(tenant_id)).execute(
        owner, IssueDebtCommand(client_id=client.id, warehouse_id=warehouse_id, amount=Decimal("100")),
    )
    closed = await RepayDebtUseCase(make_uow(tenant_id)).execute(
        owner, RepayDebtCommand(debt_id=closed.id, amount=Decimal("100")),
    )
    assert closed.status() == DebtStatus.CLOSED
