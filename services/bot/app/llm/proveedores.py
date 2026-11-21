"""Un proveedor recibe (system, texto, modelo Pydantic) y devuelve una instancia
validada de ese modelo más los tokens gastados. Si falla, lanza ErrorProveedor."""

from functools import lru_cache
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import get_settings

T = TypeVar("T", bound=BaseModel)


class ErrorProveedor(Exception):
    pass


class Proveedor(Protocol):
    nombre: str
    modelo: str

    def disponible(self) -> bool: ...

    def estructurado(self, system: str, texto: str, salida: type[T]) -> tuple[T, int, int]: ...


class Claude:
    nombre = "claude"

    def __init__(self):
        s = get_settings()
        self.modelo = s.claude_model
        self.effort = s.claude_effort
        self.api_key = s.anthropic_api_key
        self.timeout = s.llm_timeout_s

    def disponible(self) -> bool:
        return bool(self.api_key)

    @lru_cache
    def _cliente(self):
        import anthropic

        # Sin reintentos del SDK: si Claude va lento, preferimos pasar al siguiente proveedor
        return anthropic.Anthropic(api_key=self.api_key, timeout=self.timeout, max_retries=0)

    def estructurado(self, system, texto, salida):
        import anthropic

        try:
            resp = self._cliente().beta.messages.parse(
                model=self.modelo,
                max_tokens=4000,
                system=system,
                messages=[{"role": "user", "content": texto}],
                output_format=salida,
                output_config={"effort": self.effort},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.APIError as e:
            raise ErrorProveedor(f"claude: {e}") from e
        if resp.stop_reason != "end_turn":
            raise ErrorProveedor(f"claude: stop_reason={resp.stop_reason}")
        if resp.parsed_output is None:
            raise ErrorProveedor("claude: respuesta sin JSON válido")
        return resp.parsed_output, resp.usage.input_tokens, resp.usage.output_tokens


class Gemini:
    nombre = "gemini"

    def __init__(self):
        s = get_settings()
        self.modelo = s.gemini_model
        self.api_key = s.gemini_api_key
        self.timeout_ms = int(s.llm_timeout_s * 1000)

    def disponible(self) -> bool:
        return bool(self.api_key)

    @lru_cache
    def _cliente(self):
        from google import genai

        return genai.Client(api_key=self.api_key, http_options={"timeout": self.timeout_ms})

    def estructurado(self, system, texto, salida):
        try:
            resp = self._cliente().models.generate_content(
                model=self.modelo,
                contents=texto,
                config={
                    "system_instruction": system,
                    "response_mime_type": "application/json",
                    "response_schema": salida,
                },
            )
            obj = salida.model_validate_json(resp.text)
        except ValidationError as e:
            raise ErrorProveedor(f"gemini: JSON no válido: {e}") from e
        except Exception as e:  # el SDK de Google lanza varias jerarquías de error
            raise ErrorProveedor(f"gemini: {e}") from e
        uso = resp.usage_metadata
        entrada = (uso.prompt_token_count or 0) if uso else 0
        salida_tokens = (uso.candidates_token_count or 0) if uso else 0
        return obj, entrada, salida_tokens


class CompatibleOpenAI:
    """Cualquier endpoint compatible con OpenAI (/v1/chat/completions): FreeLLMAPI o NVIDIA NIM.

    Los planes gratuitos son muy irregulares (el mismo modelo tarda 0,5 s o 12 s, o
    devuelve 429), así que probamos varios modelos con un timeout corto cada uno."""

    nombre = ""
    modo_json = True  # pedir response_format json_object (no todos los endpoints lo aceptan)

    def __init__(self, url: str, api_key: str, modelos: str, timeout_intento: float):
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.modelos = [m.strip() for m in modelos.split(",") if m.strip()]
        self.modelo = ",".join(self.modelos)
        self.timeout_intento = timeout_intento
        self.timeout = get_settings().llm_timeout_s

    def disponible(self) -> bool:
        return bool(self.api_key and self.url and self.modelos)

    def estructurado(self, system, texto, salida):
        import json
        import time

        import httpx

        # Los modelos gratuitos no siempre respetan un JSON Schema: se lo damos en el
        # prompt, pedimos JSON y lo validamos con Pydantic igualmente
        esquema = json.dumps(salida.model_json_schema(), ensure_ascii=False)
        mensajes = [
            {"role": "system", "content": f"{system}\n\nResponde SOLO con un objeto JSON que cumpla este esquema:\n{esquema}"},
            {"role": "user", "content": texto},
        ]
        limite = time.monotonic() + self.timeout
        errores = []
        for modelo in self.modelos:
            restante = limite - time.monotonic()
            if restante < 1:
                break
            cuerpo = {"model": modelo, "messages": mensajes, "temperature": 0}
            if self.modo_json:
                cuerpo["response_format"] = {"type": "json_object"}
            try:
                r = httpx.post(f"{self.url}/chat/completions", json=cuerpo,
                               headers={"Authorization": f"Bearer {self.api_key}"},
                               timeout=min(self.timeout_intento, restante))
                r.raise_for_status()
                datos = r.json()
                contenido = datos["choices"][0]["message"]["content"] or ""
                obj = salida.model_validate_json(_quitar_markdown(contenido))
            except httpx.HTTPError as e:
                errores.append(f"{modelo}: {type(e).__name__}")
                continue
            except (KeyError, IndexError, ValueError) as e:  # ValidationError hereda de ValueError
                errores.append(f"{modelo}: respuesta no válida ({type(e).__name__})")
                continue
            # Qué proveedor gratuito respondió de verdad, para las métricas
            self.modelo = r.headers.get("X-Routed-Via", modelo)
            uso = datos.get("usage") or {}
            return obj, uso.get("prompt_tokens", 0), uso.get("completion_tokens", 0)
        raise ErrorProveedor(f"{self.nombre}: " + "; ".join(errores or ["sin tiempo"]))


class FreeLLM(CompatibleOpenAI):
    """FreeLLMAPI: proxy local que reparte entre los planes gratuitos de varios proveedores."""

    nombre = "freellm"

    def __init__(self):
        s = get_settings()
        super().__init__(s.freellm_url, s.freellm_api_key, s.freellm_modelos, s.freellm_timeout_intento_s)


class Nim(CompatibleOpenAI):
    """NVIDIA NIM (build.nvidia.com), plan gratuito con clave propia. Directo, sin pasar por FreeLLMAPI:
    si el proxy o el portátil donde corre fallan, la IA sigue (tarea B2; la usa la ingesta de Facebook)."""

    nombre = "nim"
    modo_json = False  # no todos los modelos de NIM aceptan response_format: el JSON se pide en el prompt

    def __init__(self):
        s = get_settings()
        super().__init__(s.nim_url, s.nim_api_key, s.nim_modelos, s.nim_timeout_intento_s)


def _quitar_markdown(texto: str) -> str:
    """Algunos modelos envuelven el JSON en ```json … ```."""
    t = texto.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        t = t.rsplit("```", 1)[0]
    return t.strip()


def construir(nombre: str) -> Proveedor | None:
    return {"claude": Claude, "gemini": Gemini, "nim": Nim, "freellm": FreeLLM}.get(nombre, lambda: None)()
