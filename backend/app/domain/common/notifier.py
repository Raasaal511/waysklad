from typing import Protocol


class INotifier(Protocol):
    """Отправка уведомлений владельцу (реализация — infrastructure/telegram.py)."""

    def send(self, chat_id: str, text: str) -> None: ...
