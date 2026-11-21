import logging
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# El .env vive en la raíz del monorepo y uvicorn se lanza desde services/api.
# En Docker no hay raíz del monorepo (la ruta es más corta) y las variables llegan por env_file del compose.
_rutas = Path(__file__).resolve().parents
_ENV_FILES = ((_rutas[3] / ".env",) if len(_rutas) > 3 else ()) + (".env",)

# Valor de ejemplo de JWT_SECRET (.env.example). Con él cualquiera puede firmar sesiones válidas.
JWT_SECRET_POR_DEFECTO = "cambia-esto-tambien"

log = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILES, extra="ignore")

    # Sin .env: SQLite en services/api/hackemate.db. Docker fija la de PostgreSQL en el compose.
    database_url: str = "sqlite:///./hackemate.db"
    internal_token: str = "cambia-esto"
    # Login (app/seguridad.py y app/rutas/auth.py)
    jwt_secret: str = JWT_SECRET_POR_DEFECTO
    jwt_expira_min: int = 1440
    google_client_id: str = ""
    google_tokeninfo_url: str = "https://oauth2.googleapis.com/tokeninfo"
    google_timeout_s: float = 5.0
    # Solo para la demo: POST /auth/demo da sesión como cualquier usuario sin contraseña. Nunca en producción.
    demo_mode: bool = False
    bot_url: str = "http://bot:8001"
    zona_horaria: str = "Europe/Madrid"
    app_version: str | None = None
    cors_origenes: str = "http://localhost:8080,http://localhost:5173,http://localhost:8100"
    # Vacío = contracts/fixtures del monorepo. En Docker se monta en /srv/contracts/fixtures.
    fixtures_dir: str = ""
    # Moderación (app/moderacion.py)
    moderacion_aprobaciones_subir_nivel: int = 3  # sin uso desde la 0008 (solo dos modos): se conserva por compatibilidad
    moderacion_umbral_spam: float = 0.7
    # Cola de avisos (app/notificaciones.py)
    notificaciones_timeout_s: float = 3.0
    notificaciones_max_intentos: int = 5
    # Tarea de fondo que reintenta los avisos pendientes (app/main.py). 0 = desactivada.
    notificaciones_reintento_s: float = 60.0
    # Coste de la IA (app/estadisticas.py): euros por millón de tokens. Clave «proveedor:modelo» o «proveedor»;
    # lo que no aparece cuenta como gratuito (0 €). JSON en la variable PRECIOS_TOKENS_EUR_MTOK.
    precios_tokens_eur_mtok: dict[str, dict[str, float]] = {
        "gemini": {"entrada": 0.0, "salida": 0.0},
        "freellm": {"entrada": 0.0, "salida": 0.0},
        "reglas": {"entrada": 0.0, "salida": 0.0},
        "claude": {"entrada": 5.0, "salida": 25.0},
    }

    @property
    def lista_cors(self) -> list[str]:
        return [o.strip() for o in self.cors_origenes.split(",") if o.strip()]


def avisar_configuracion_insegura(ajustes: Settings | None = None) -> list[str]:
    """Registra un WARNING por cada ajuste peligroso fuera del modo demo. No bloquea el arranque (la demo y el
    compose dependen de que la API arranque). Devuelve los avisos."""
    ajustes = ajustes or get_settings()
    avisos = []
    if not ajustes.demo_mode and ajustes.jwt_secret in (JWT_SECRET_POR_DEFECTO, ""):
        avisos.append(
            "JWT_SECRET tiene el valor de ejemplo: cualquiera podría firmar sesiones válidas. "
            "Pon un secreto aleatorio en .env (p. ej. python -c \"import secrets; print(secrets.token_urlsafe(32))\")."
        )
    for aviso in avisos:
        log.warning(aviso)
    return avisos


@lru_cache
def get_settings() -> Settings:
    return Settings()
