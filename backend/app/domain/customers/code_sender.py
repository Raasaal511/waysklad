from typing import Protocol


class IVerificationCodeSender(Protocol):
    """Доставка кода подтверждения телефона.

    Отдельный интерфейс, потому что канал доставки временный: сейчас код шлёт
    Telegram-бот (он уже работает и бесплатен), позже появится SMS-провайдер —
    подключение должно свестись к новой реализации и переменной в .env, без
    правок use-case'ов.
    """

    @property
    def name(self) -> str:
        """Чем отправлено — пишется в PhoneVerificationCode.sent_via и
        возвращается фронту, чтобы показать «код отправлен в Telegram»."""
        ...

    async def send(self, chat_id: str, phone: str, code: str) -> None:
        """chat_id пуст — у покупателя нет привязанного Telegram; вызывающий
        должен это проверить заранее и показать ссылку на бота."""
        ...
