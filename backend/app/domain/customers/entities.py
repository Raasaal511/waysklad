import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.domain.common.exceptions import DomainError
from app.domain.common.phone import Phone

LOGIN_LINK_TTL = timedelta(minutes=10)

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 32
# латиница/цифры/._- : имя показывается продавцу в заявке, кириллица и пробелы
# слишком легко дают визуально неотличимые логины
_USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def validate_username(username: str) -> str:
    """Проверяет и возвращает нормализованный (обрезанный) username.
    Общая точка для регистрации и для Customer.set_username."""
    username = username.strip()
    if len(username) < USERNAME_MIN_LENGTH:
        raise DomainError(f"Имя пользователя короче {USERNAME_MIN_LENGTH} символов")
    if len(username) > USERNAME_MAX_LENGTH:
        raise DomainError(f"Имя пользователя длиннее {USERNAME_MAX_LENGTH} символов")
    if not _USERNAME_RE.match(username):
        raise DomainError("Имя пользователя: латиница, цифры, точка, дефис и подчёркивание")
    return username


@dataclass
class Customer:
    """Аккаунт покупателя витрины — общий на всю платформу (не привязан к
    одному tenant), в отличие от User (сотрудник конкретного магазина).

    Входит по телефону — паролем (password_hash) или подтверждением через
    Telegram-бота (CustomerLoginLink). Аккаунт, заведённый только входом через
    Telegram, остаётся без username и пароля — это обычное состояние, а не ошибка.

    Телефон в обоих случаях подтверждён ботом: регистрация с паролем тоже
    завершается в Telegram, иначе можно зарегистрировать чужой номер."""

    id: int | None
    phone: Phone
    # необязательное — заполняется покупателем один раз в профиле, подставляется
    # автоматически в новые заявки вместо ручного ввода имени каждый раз
    name: str = ""
    telegram_chat_id: str = ""
    # "" — имя пользователя не задано (аккаунт из входа через Telegram)
    username: str = ""
    # "" — пароль не задан (вход только через Telegram), см. set_password
    password_hash: str = ""
    # инкрементируется при отзыве всех токенов (logout-all) — тот же паттерн,
    # что и у User.token_version
    token_version: int = 0

    @property
    def has_password(self) -> bool:
        return bool(self.password_hash)

    def set_password(self, password_hash: str) -> None:
        """Хеш считается снаружи (infrastructure.security.hash_password) —
        домен не знает про bcrypt, как и в остальном коде проекта."""
        if not password_hash:
            raise DomainError("Пустой хеш пароля")
        self.password_hash = password_hash

    def set_username(self, username: str) -> None:
        """Хранится как ввёл покупатель, сравнивается без учёта регистра
        (нормализацию для поиска делает репозиторий)."""
        self.username = validate_username(username)

    def update_name(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise DomainError("Укажите имя")
        self.name = name


@dataclass
class CustomerLoginLink:
    """Одноразовая ссылка входа: покупатель вводит телефон на витрине, получает
    deep-link на Telegram-бота — бот подтверждает владение номером, когда
    покупатель сам открывает диалог и присылает свой chat_id боту.

    Та же ссылка завершает регистрацию по паролю: username и хеш пароля ждут
    здесь, пока бот не подтвердит номер (create_for_registration). Без этого
    можно было бы зарегистрировать аккаунт на чужой телефон."""

    token: str
    phone: Phone
    created_at: datetime
    customer_id: int | None = None  # заполняется при подтверждении ботом
    confirmed_at: datetime | None = None
    # заполнены только у ссылок регистрации — у обычного входа пустые
    username: str = ""
    password_hash: str = ""

    @classmethod
    def create(cls, phone: Phone) -> "CustomerLoginLink":
        return cls(
            token=secrets.token_urlsafe(24),
            phone=phone,
            created_at=datetime.now(timezone.utc),
        )

    @classmethod
    def create_for_registration(
        cls, phone: Phone, username: str, password_hash: str
    ) -> "CustomerLoginLink":
        return cls(
            token=secrets.token_urlsafe(24),
            phone=phone,
            created_at=datetime.now(timezone.utc),
            username=username,
            password_hash=password_hash,
        )

    @property
    def is_registration(self) -> bool:
        return bool(self.password_hash)

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.created_at + LOGIN_LINK_TTL

    @property
    def is_confirmed(self) -> bool:
        return self.confirmed_at is not None

    def confirm(self, customer_id: int) -> None:
        self.customer_id = customer_id
        self.confirmed_at = datetime.now(timezone.utc)
