from typing import Protocol


class INotifier(Protocol):
    """Отправка уведомлений владельцу (реализация — infrastructure/telegram.py)."""

    def send(self, chat_id: str, text: str) -> None: ...

    def send_with_buttons(
        self, chat_id: str, text: str, buttons: list[tuple[str, str]]
    ) -> None:
        """Как send(), но с inline-кнопками под сообщением — список
        (текст кнопки, callback_data). Нажатие обрабатывает
        infrastructure/telegram_bot (тот же бот, что обслуживает покупателей
        витрины) — не влияет на обычный флоу через панель управления, это
        просто более быстрый путь для того, кто подключил Telegram."""
        ...
