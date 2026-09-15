from app.domain.debts.entities import Debt


def render_debt_message(shop_name: str, debt: Debt, client_name: str) -> str:
    """Текст для отправки клиенту в WhatsApp при выдаче долга/рассрочки —
    аналог товарной квитанции продажи (app.domain.sales.receipt)."""
    lines = [shop_name, f"Оформлен долг №{debt.id}", f"Клиент: {client_name}"]
    if debt.note:
        lines.append(f"Товар: {debt.note}")
    lines.append(f"Сумма: {debt.amount} ₽")

    next_installment = next(
        (p for p in debt.schedule if p.due_date == debt.next_installment_due_date), None
    )
    if next_installment is not None:
        lines.append(f"Ежемесячный платёж: {next_installment.amount} ₽")
        lines.append(f"Дата платежа: {next_installment.due_date.day}-е число каждого месяца")
    elif debt.due_date is not None:
        lines.append(f"Срок: {debt.due_date.strftime('%d.%m.%Y')}")

    lines.append(f"Остаток: {debt.balance} ₽")
    return "\n".join(lines)
