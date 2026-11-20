from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://hackemate:hackemate@db:5432/hackemate"
    internal_token: str = "cambia-esto"
    jwt_secret: str = "cambia-esto-tambien"
    google_client_id: str = ""
    bot_url: str = "http://bot:8001"
    zona_horaria: str = "Europe/Madrid"
    app_version: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
