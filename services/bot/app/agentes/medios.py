"""Notas de voz y carteles → texto. Después el texto pasa por el extractor de siempre, que
ya tiene su cadena de IAs y las reglas sin IA. Aquí no hay plan «reglas»: si ninguna IA
puede leer el archivo, se devuelve None y el bot pide que se lo escriban."""

import base64
import logging
import time

import httpx

from app import metrics
from app.config import get_settings

log = logging.getLogger(__name__)

PROMPT_CARTEL = (
    "Transcribe todo el texto de este cartel o imagen tal cual, línea a línea. "
    "Si no hay texto, describe en una frase qué anuncia. No añadas nada más."
)


def _cabeceras() -> dict:
    return {"Authorization": f"Bearer {get_settings().freellm_api_key}"}


# ---------- Audio ----------

def transcribir(audio: bytes, mime: str = "audio/ogg") -> str | None:
    s = get_settings()
    extension = {"audio/ogg": "ogg", "audio/mpeg": "mp3", "audio/mp4": "m4a", "audio/wav": "wav",
                 "audio/x-wav": "wav", "audio/webm": "webm", "audio/amr": "amr"}.get(mime.split(";")[0], "ogg")
    if s.freellm_api_key and not s.llm_simular_caida:
        inicio = time.monotonic()
        try:
            r = httpx.post(f"{s.freellm_url.rstrip('/')}/audio/transcriptions", headers=_cabeceras(),
                           files={"file": (f"nota.{extension}", audio, mime)},
                           data={"model": s.freellm_modelo_audio, "language": "es"}, timeout=s.medios_timeout_s)
            r.raise_for_status()
            texto = (r.json().get("text") or "").strip()
            metrics.registrar("freellm", s.freellm_modelo_audio, "transcribir", 0, 0, _ms(inicio), ok=bool(texto))
            if texto:
                return texto
        except (httpx.HTTPError, ValueError) as e:
            log.warning("Transcripción con FreeLLMAPI falló: %s", e)
            metrics.registrar("freellm", s.freellm_modelo_audio, "transcribir", 0, 0, _ms(inicio), ok=False)
    return _gemini(audio, mime, "Transcribe literalmente este audio en español. Solo el texto.", "transcribir")


# ---------- Imagen ----------

def leer_imagen(imagen: bytes, mime: str = "image/jpeg") -> str | None:
    s = get_settings()
    if s.freellm_api_key and not s.llm_simular_caida:
        url = f"data:{mime};base64,{base64.b64encode(imagen).decode()}"
        for modelo in [m.strip() for m in s.freellm_modelos_vision.split(",") if m.strip()]:
            inicio = time.monotonic()
            try:
                r = httpx.post(f"{s.freellm_url.rstrip('/')}/chat/completions", headers=_cabeceras(),
                               timeout=s.medios_timeout_s, json={
                                   "model": modelo, "temperature": 0,
                                   "messages": [{"role": "user", "content": [
                                       {"type": "text", "text": PROMPT_CARTEL},
                                       {"type": "image_url", "image_url": {"url": url}}]}]})
                r.raise_for_status()
                datos = r.json()
                texto = (datos["choices"][0]["message"]["content"] or "").strip()
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
                log.warning("Visión con %s falló: %s", modelo, e)
                metrics.registrar("freellm", modelo, "leer_cartel", 0, 0, _ms(inicio), ok=False)
                continue
            uso = datos.get("usage") or {}
            metrics.registrar("freellm", r.headers.get("X-Routed-Via", modelo), "leer_cartel",
                              uso.get("prompt_tokens", 0), uso.get("completion_tokens", 0), _ms(inicio), ok=bool(texto))
            if texto:
                return texto
    return _gemini(imagen, mime, PROMPT_CARTEL, "leer_cartel")


# ---------- Gemini directo (si hay clave) ----------

def _gemini(datos: bytes, mime: str, prompt: str, tarea: str) -> str | None:
    s = get_settings()
    if not s.gemini_api_key or s.llm_simular_caida:
        return None
    inicio = time.monotonic()
    try:
        from google import genai
        from google.genai import types

        cliente = genai.Client(api_key=s.gemini_api_key, http_options={"timeout": int(s.medios_timeout_s * 1000)})
        resp = cliente.models.generate_content(
            model=s.gemini_model, contents=[types.Part.from_bytes(data=datos, mime_type=mime), prompt])
        texto = (resp.text or "").strip()
    except Exception as e:  # el SDK de Google lanza varias jerarquías de error
        log.warning("Gemini (%s) falló: %s", tarea, e)
        metrics.registrar("gemini", s.gemini_model, tarea, 0, 0, _ms(inicio), ok=False)
        return None
    uso = resp.usage_metadata
    metrics.registrar("gemini", s.gemini_model, tarea, (uso.prompt_token_count or 0) if uso else 0,
                      (uso.candidates_token_count or 0) if uso else 0, _ms(inicio), ok=bool(texto))
    return texto or None


def _ms(inicio: float) -> int:
    return int((time.monotonic() - inicio) * 1000)
