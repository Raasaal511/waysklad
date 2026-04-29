from pydantic_settings import BaseSettings

from dotenv import load_dotenv

load_dotenv()


class DBSettings(BaseSettings):
    database_url: str


db_settings = DBSettings()
db_url = db_settings.database_url
