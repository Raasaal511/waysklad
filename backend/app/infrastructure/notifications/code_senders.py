"""Реализации доставки кода подтверждения телефона.

Выбор — через settings.verification_sender (telegram | console). SMS-провайдера
пока нет: SmsCodeSender появится здесь же, когда будет договор с провайдером,
и на use-case'ы это не повлияет (см. IVerificationCodeSender).
"""

import asyncio

from app.infrastructure.notifications.telegram import TelegramNotifier
from app.infrastructure.observability.logging import get_logger

_logger = get_logger("app.customers.code")


class TelegramCodeSender:
    """Код приходит в диалог с ботом витрины — тем же, через который покупатель
    входит по ссылке. Работает только если у покупателя уже есть chat_id, то
    есть он хоть раз нажимал «Старт»."""

    def __init__(self, notifier: TelegramNotifier | None = None):
        self._notifier = notifier or TelegramNotifier()

    @property
    def name(self) -> str:
        return "telegram"

    async def send(self, chat_id: str, phone: str, code: str) -> None:
        text = (
            f"Код подтверждения номера {phone}: <b>{code}</b>\n\n"
            "Можно ввести код на сайте или отправить боту:\n"
            f"<code>/confirm {code}</code>\n\n"
            "Код действует 5 минут. Если вы его не запрашивали — просто "
            "проигнорируйте сообщение."
        )
        # TelegramNotifier синхронный (requests) — уводим в поток, чтобы не
        # блокировать событийный цикл на время HTTP-запроса к Telegram
        await asyncio.to_thread(self._notifier.send, chat_id, text)


class ConsoleCodeSender:
    """Для локальной разработки и тестов: код уходит в лог, никуда не шлётся.
    В проде включать нельзя — код виден каждому, кто читает логи."""

    @property
    def name(self) -> str:
        return "console"

    async def send(self, chat_id: str, phone: str, code: str) -> None:
        _logger.warning("Код подтверждения для %s: %s (ConsoleCodeSender)", phone, code)


def build_code_sender(kind: str):
    if kind == "console":
        return ConsoleCodeSender()
    return TelegramCodeSender()
