import logging
import sys

_CONFIGURED = False


def configure_logging() -> None:
    """stdout-логи в формате, читаемом через `docker compose logs backend`.
    Вызывается один раз при старте приложения (app/main.py)."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
