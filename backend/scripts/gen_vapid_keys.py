"""Сгенерировать ключ VAPID для Web Push и напечатать строку для .env.

    docker compose exec backend python scripts/gen_vapid_keys.py

Ключ генерируется один раз на сервис. Сменить его = все браузеры, уже
подписанные на уведомления, молча перестанут их получать, пока сотрудник
не включит уведомления в профиле заново.
"""

import base64

from cryptography.hazmat.primitives.asymmetric import ec


def main() -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    raw = key.private_numbers().private_value.to_bytes(32, "big")
    print("VAPID_PRIVATE_KEY=" + base64.urlsafe_b64encode(raw).rstrip(b"=").decode())


if __name__ == "__main__":
    main()
