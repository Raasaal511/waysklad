from app.domain.common.money import format_rub
from app.domain.common.phone import Phone
from app.domain.counterparties.entities import Client
from app.domain.debts.entities import Debt
from app.domain.sales.receipt import build_whatsapp_link


def render_debt_reminder_text(debt: Debt) -> str:
    """Текст напоминания о просроченном долге для отправки клиенту в WhatsApp."""
    due = debt.due_date.strftime("%d.%m.%Y") if debt.due_date else debt.issued_at.strftime("%d.%m.%Y")
    return (
        f"Здравствуйте! Напоминаем о задолженности {format_rub(debt.balance)} "
        f"по заказу от {due}. Будем благодарны за оплату."
    )


def build_debt_reminder_link(debt: Debt, client: Client | None) -> str | None:
    """Готовая wa.me-ссылка с текстом напоминания — только для клиентских долгов
    с телефоном; долги поставщику и клиенты без телефона — None."""
    if client is None:
        return None
    phone: Phone | None = client.phone or client.whatsapp
    if phone is None:
        return None
    return build_whatsapp_link(phone, render_debt_reminder_text(debt))
