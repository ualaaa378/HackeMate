from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# El .env vive en la raíz del monorepo y uvicorn se lanza desde services/api.
# En Docker no hay raíz del monorepo (la ruta es más corta) y las variables llegan por env_file del compose.
_rutas = Path(__file__).resolve().parents
_ENV_FILES = ((_rutas[3] / ".env",) if len(_rutas) > 3 else ()) + (".env",)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILES, extra="ignore")

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
