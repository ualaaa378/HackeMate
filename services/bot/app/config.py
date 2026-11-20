from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Comunicación con el servicio api (Flujo A)
    api_url: str = "http://api:8000"
    internal_token: str = "cambia-esto"

    # Canal de salida: "twilio" envía WhatsApp de verdad; "console" solo imprime
    canal: str = "console"
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
    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-5-5"
    claude_effort: str = "low"

    zona_horaria: str = "Europe/Madrid"

    @property
    def proveedores(self) -> list[str]:
        return [p.strip() for p in self.llm_cadena.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
