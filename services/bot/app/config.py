from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Comunicación con el servicio api (Flujo A)
    api_url: str = "http://api:8000"
    internal_token: str = "cambia-esto"

    # Canal de WhatsApp: "meta" (WhatsApp Cloud API, el de producción), "twilio"
    # (alternativa) o "console" (solo imprime, para desarrollar y tests)
    canal: str = "console"

    # Telegram: activo en cuanto hay token. Los destinos «tg:…» siempre van por aquí,
    # así Telegram y WhatsApp pueden funcionar a la vez
    telegram_token: str = ""
    telegram_secret: str = ""  # cabecera X-Telegram-Bot-Api-Secret-Token del webhook

    # WhatsApp Cloud API (Meta)
    meta_token: str = ""  # token permanente de un usuario del sistema
    meta_phone_number_id: str = ""
    meta_app_secret: str = ""  # para comprobar la firma X-Hub-Signature-256
    meta_verify_token: str = ""  # lo inventamos nosotros y se pega en la config del webhook
    meta_graph_version: str = "v26.0"
    meta_idioma_plantillas: str = "es"

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = "whatsapp:+14155238886"  # número del sandbox
    twilio_validar_firma: bool = False

    # Proveedores de IA, en el orden en que se prueban. Primero los gratuitos;
    # Claude (de pago) solo se usa si hay clave y fallan los demás.
    llm_cadena: str = "gemini,freellm,claude,reglas"
    llm_timeout_s: float = 25.0
    llm_simular_caida: bool = False  # para la demo de robustez
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    freellm_url: str = "http://127.0.0.1:31415/v1"
    freellm_api_key: str = ""
    # Se prueban en orden; "auto" deja elegir al proxy. Ver GET /v1/models del proxy
    freellm_modelos: str = "qwen3.8-27b,gemini-flash-lite,auto"
    freellm_timeout_intento_s: float = 8.0
    # Carteles (visión) y notas de voz (transcripción, endpoint /audio/transcriptions del proxy)
    freellm_modelos_vision: str = "gemini-flash-lite,auto"
    freellm_modelo_audio: str = "whisper-large-v3"
    medios_timeout_s: float = 30.0
    # Respuestas en audio (TTS del proxy; «auto» elige proveedor gratuito)
    freellm_modelo_voz: str = "auto"
    freellm_voz: str = "alloy"
    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-5-5"
    claude_effort: str = "low"

    zona_horaria: str = "Europe/Madrid"
    # Enlaces a la ficha en la web/PWA (Flujo C): {web_url}/evento/{id}
    web_url: str = "http://localhost:8080"

    # Cola de peticiones a la api cuando está caída: se guarda en disco y se reintenta sola
    cola_path: str = "data/cola_pendiente.json"  # vacío = solo en memoria
    cola_reintento_s: float = 30.0

    # URL pública (túnel) del bot. Si está, al arrancar registra el webhook de Telegram él solo
    public_url: str = ""

    @property
    def proveedores(self) -> list[str]:
        return [p.strip() for p in self.llm_cadena.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
