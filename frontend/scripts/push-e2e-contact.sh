#!/bin/sh
# Шаг бота за человека: принимает контакт по токену регистрации и печатает код.
# Кнопку «Поделиться номером» в Telegram скрипт нажать не может, поэтому зовём
# тот же use case, что и бот. Только локально (нужен контейнер backend).
#   push-e2e-contact.sh <token> <+7...>
exec docker exec -i waysklad-backend-1 python - "$1" "$2" <<'PY'
import asyncio, sys
from app.application.auth.telegram_signup import AcceptContactUseCase, ContactCommand
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.security import BcryptPasswordHasher

async def main() -> None:
    token, phone = sys.argv[1], sys.argv[2]
    telegram_id = "770000" + phone[-4:]
    result = await AcceptContactUseCase(
        SqlAlchemyUnitOfWork(None), BcryptPasswordHasher()
    ).execute(
        ContactCommand(
            token=token,
            contact_phone=phone.lstrip("+"),
            contact_user_id=telegram_id,
            sender_user_id=telegram_id,
            chat_id=telegram_id,
        )
    )
    print(result.code or result.check)

asyncio.run(main())
PY
