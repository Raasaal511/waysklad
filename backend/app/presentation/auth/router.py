import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile

from app.application.auth.telegram_signup import code_message
from app.domain.common.notifier import INotifier
from app.domain.identity.telegram_verification import TelegramVerification
from app.infrastructure.config import settings

from app.application.auth.set_shop_logo import SetShopLogoCommand
from app.domain.identity.entities import User
from app.domain.identity.permissions import Permission
from app.infrastructure.rate_limit import limiter
from app.infrastructure.security import create_access_token
from app.presentation.auth.schemas import (
    ChangePasswordRequest,
    CreateEmployeeRequest,
    LoginRequest,
    RegisterRequest,
    TelegramCodeRequest,
    TelegramTokenRequest,
    TelegramVerificationStartResponse,
    TelegramVerificationStatusResponse,
    TenantResponse,
    TokenResponse,
    UpdateEmployeeRequest,
    UpdateShopRequest,
    UserResponse,
)
from app.presentation.deps import (
    ActorDep,
    ChangePasswordDep,
    CompleteLinkDep,
    CompleteSignupDep,
    CreateEmployeeDep,
    DeleteShopLogoDep,
    GetShopDep,
    ListEmployeesDep,
    LoginDep,
    LogoutAllDep,
    NotifierDep,
    ResendCodeDep,
    StartLinkDep,
    StartSignupDep,
    SetShopLogoDep,
    UpdateEmployeeDep,
    UpdateShopDep,
    VerificationStatusDep,
)
from app.presentation.deps.auth import require_permission

router = APIRouter(prefix="/auth", tags=["auth"])
_logger = logging.getLogger(__name__)


def _token_response(user: User, shop_slug: str | None = None) -> TokenResponse:
    token = create_access_token(user.id, user.tenant_id, user.role.value, user.token_version)
    return TokenResponse(
        access_token=token, user=UserResponse.from_entity(user), shop_slug=shop_slug
    )


def _bot_link(verification: TelegramVerification, prefix: str) -> TelegramVerificationStartResponse:
    bot = settings.telegram_bot_username_clean
    return TelegramVerificationStartResponse(
        token=verification.token,
        telegram_link=f"https://t.me/{bot}?start={prefix}_{verification.token}",
        expires_at=verification.expires_at,
    )


def _require_bot() -> None:
    # без бота регистрация невозможна по решению владельца продукта — честный
    # 503 вместо формы, которая ведёт в никуда
    if not settings.telegram_bot_username_clean:
        raise HTTPException(status_code=503, detail="Регистрация временно недоступна: не настроен Telegram-бот")


async def _tell(notifier: INotifier | None, chat_id: str, text: str) -> None:
    """Сообщение в чат владельца. Telegram недоступен — операция всё равно
    состоялась (магазин создан), поэтому ошибку только пишем в лог."""
    if notifier is None or not chat_id:
        return
    try:
        await asyncio.to_thread(notifier.send, chat_id, text)
    except Exception:
        _logger.warning("Telegram send failed chat_id=%s", chat_id, exc_info=True)


@router.post("/register", status_code=201)
@limiter.limit("10/hour")
async def register_shop(
    request: Request, body: RegisterRequest, use_case: StartSignupDep
) -> TelegramVerificationStartResponse:
    """Шаг 1: форма проверена, магазин создастся после подтверждения в Telegram."""
    _require_bot()
    return _bot_link(await use_case.execute(body.to_command()), "reg")


@router.post("/register/confirm", status_code=201)
@limiter.limit("30/hour")
async def confirm_register(
    request: Request, body: TelegramCodeRequest, use_case: CompleteSignupDep, notifier: NotifierDep
) -> TokenResponse:
    """Шаг 2: код из бота — создаём магазин и сразу входим."""
    done = await use_case.execute(body.token, body.code)
    site = settings.public_base_url.rstrip("/")
    await _tell(
        notifier,
        done.chat_id,
        f"Готово! Магазин «{done.shop_name}» создан.\n\n"
        "Сюда будут приходить новые заявки с витрины, напоминания о долгах и вечерняя сводка."
        + (f"\n\nКабинет: {site}" if site else ""),
    )
    return _token_response(done.result.owner, done.result.shop_slug)


@router.get("/telegram/verification")
@limiter.limit("120/minute")
async def telegram_verification_status(
    request: Request, token: str, use_case: VerificationStatusDep
) -> TelegramVerificationStatusResponse:
    """Сайт опрашивает, пока человек в Telegram делится номером."""
    status = await use_case.execute(token)
    return TelegramVerificationStatusResponse(
        contact_confirmed=status.contact_confirmed,
        completed=status.completed,
        expired=status.expired,
        expires_at=status.expires_at,
        code_sent_at=status.code_sent_at,
    )


@router.post("/telegram/verification/resend", status_code=204)
@limiter.limit("10/hour")
async def resend_telegram_code(
    request: Request, body: TelegramTokenRequest, use_case: ResendCodeDep, notifier: NotifierDep
) -> Response:
    sent = await use_case.execute(body.token)
    await _tell(notifier, sent.chat_id, code_message(sent.code))
    return Response(status_code=204)


@router.post("/login")
@limiter.limit("20/minute")
async def login(request: Request, body: LoginRequest, use_case: LoginDep) -> TokenResponse:
    return _token_response(await use_case.execute(body.to_command()))


@router.post("/employees", status_code=201)
async def create_employee(
    body: CreateEmployeeRequest, actor: ActorDep, use_case: CreateEmployeeDep
) -> UserResponse:
    return UserResponse.from_entity(await use_case.execute(actor, body.to_command()))


@router.get("/employees", dependencies=[require_permission(Permission.USERS_MANAGE)])
async def list_employees(use_case: ListEmployeesDep) -> list[UserResponse]:
    items = await use_case.execute()
    return [UserResponse.from_entity(item.user, warehouse_ids=item.warehouse_ids) for item in items]


@router.patch("/employees/{employee_id}", dependencies=[require_permission(Permission.USERS_MANAGE)])
async def update_employee(
    employee_id: int, body: UpdateEmployeeRequest, actor: ActorDep, use_case: UpdateEmployeeDep
) -> UserResponse:
    employee = await use_case.execute(actor, body.to_command(employee_id))
    return UserResponse.from_entity(employee)


@router.post("/telegram/link", status_code=201)
@limiter.limit("20/hour")
async def start_telegram_link(
    request: Request, actor: ActorDep, use_case: StartLinkDep
) -> TelegramVerificationStartResponse:
    """Владелец, зарегистрированный до бота, привязывает Telegram из кабинета."""
    _require_bot()
    return _bot_link(await use_case.execute(actor), "link")


@router.post("/telegram/link/confirm")
@limiter.limit("30/hour")
async def confirm_telegram_link(
    request: Request, body: TelegramCodeRequest, actor: ActorDep, use_case: CompleteLinkDep,
    notifier: NotifierDep, shop: GetShopDep,
) -> TenantResponse:
    done = await use_case.execute(actor, body.token, body.code)
    await _tell(
        notifier,
        done.chat_id,
        f"Telegram подключён к магазину «{done.shop_name}». Сюда будут приходить новые заявки, "
        "напоминания о долгах и вечерняя сводка.",
    )
    return TenantResponse.from_entity(await shop.execute())


@router.get("/shop")
async def get_shop(use_case: GetShopDep) -> TenantResponse:
    return TenantResponse.from_entity(await use_case.execute())


@router.patch("/shop")
async def update_shop(
    body: UpdateShopRequest, actor: ActorDep, use_case: UpdateShopDep
) -> TenantResponse:
    return TenantResponse.from_entity(await use_case.execute(actor, body.to_command()))


@router.post("/shop/logo", status_code=201)
async def set_shop_logo(
    actor: ActorDep, file: UploadFile, use_case: SetShopLogoDep
) -> TenantResponse:
    command = SetShopLogoCommand(file.filename or "logo.jpg", await file.read())
    return TenantResponse.from_entity(await use_case.execute(actor, command))


@router.delete("/shop/logo")
async def delete_shop_logo(actor: ActorDep, use_case: DeleteShopLogoDep) -> TenantResponse:
    return TenantResponse.from_entity(await use_case.execute(actor))


@router.patch("/me/password")
async def change_password(
    body: ChangePasswordRequest, actor: ActorDep, use_case: ChangePasswordDep
) -> TokenResponse:
    # смена пароля инкрементирует token_version — без выдачи свежего токена
    # пользователь сам разлогинил бы себя же текущим запросом
    return _token_response(await use_case.execute(actor, body.to_command()))


@router.post("/me/logout-all", status_code=204)
async def logout_all(actor: ActorDep, use_case: LogoutAllDep) -> None:
    """Разлогинить себя на всех устройствах — включая то, с которого вызван запрос."""
    await use_case.execute(actor)
