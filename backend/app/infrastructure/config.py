from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://waysklad:change-me@localhost:5432/waysklad"
    secret_key: str = "dev-secret-change-me"
    access_token_expire_minutes: int = 60 * 24 * 30
    debug: bool = False
    telegram_bot_token: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
