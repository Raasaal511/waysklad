from aiogram.fsm.storage.base import StorageKey

from app.infrastructure.telegram_bot.storage import PostgresStorage


async def test_postgres_storage_state_and_data_roundtrip(db_session_factory):
    storage = PostgresStorage(db_session_factory)
    key = StorageKey(bot_id=1, chat_id=100, user_id=100)

    assert await storage.get_state(key) is None
    assert await storage.get_data(key) == {}

    await storage.set_state(key, "browsing_catalog")
    assert await storage.get_state(key) == "browsing_catalog"

    await storage.set_data(key, {"slug": "aina", "offset": 0})
    assert await storage.get_data(key) == {"slug": "aina", "offset": 0}

    # смена state не должна затирать уже сохранённые data (и наоборот)
    await storage.set_state(key, "viewing_product")
    assert await storage.get_state(key) == "viewing_product"
    assert await storage.get_data(key) == {"slug": "aina", "offset": 0}

    await storage.set_data(key, {"product_id": 42})
    assert await storage.get_data(key) == {"product_id": 42}
    assert await storage.get_state(key) == "viewing_product"


async def test_postgres_storage_isolates_different_keys(db_session_factory):
    storage = PostgresStorage(db_session_factory)
    key_a = StorageKey(bot_id=1, chat_id=100, user_id=100)
    key_b = StorageKey(bot_id=1, chat_id=200, user_id=200)

    await storage.set_state(key_a, "browsing_catalog")
    await storage.set_data(key_a, {"slug": "aina"})

    assert await storage.get_state(key_b) is None
    assert await storage.get_data(key_b) == {}
