"""Respuestas en audio (texto → nota de voz) para quien escribe con audios o pidió avisos por voz.
TTS gratis vía FreeLLMAPI (/audio/speech, devuelve WAV) y conversión a OGG/Opus con el ffmpeg
que trae imageio-ffmpeg (Telegram solo acepta notas de voz en OGG/Opus, MP3 o M4A)."""

import logging
import re
import subprocess
import time

import httpx

from app import metrics
from app.config import get_settings
from app.llm import router

log = logging.getLogger(__name__)

MAX_CARACTERES = 700
_EMOJIS = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍⭐⬆↔-⇿]")


def texto_para_voz(textos: list[str]) -> str:
    """Quita lo que no se puede leer en voz alta: enlaces, emojis, asteriscos, comillas raras."""
    partes = []
    for t in textos:
        t = re.sub(r"https?://\S+", "", t)
        t = "\n".join(l for l in t.splitlines() if not l.strip().startswith("🔗"))
        t = _EMOJIS.sub("", t).replace("*", "").replace("«", "").replace("»", "")
        t = t.replace("€", " euros")
        t = re.sub(r"\b(\d{1,2})/(\d{1,2})\b", r"\1 del \2", t)  # 28/11 → «28 del 11»
        t = re.sub(r"[ \t]+", " ", t)
        t = re.sub(r"\s*\n\s*", ". ", t.strip())
        t = re.sub(r"\.\s*\.", ".", t)
        if t:
            partes.append(t)
    texto = " ".join(partes).strip()
    if len(texto) > MAX_CARACTERES:
        texto = texto[:MAX_CARACTERES].rsplit(".", 1)[0] + "."
    return texto


def _a_ogg(wav: bytes) -> bytes | None:
    try:
        import imageio_ffmpeg

        p = subprocess.run(
            [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
             "-ac", "1", "-c:a", "libopus", "-b:a", "24k", "-f", "ogg", "pipe:1"],
            input=wav, capture_output=True, timeout=30)
    except (ImportError, OSError, subprocess.SubprocessError) as e:
        log.warning("No se pudo convertir el audio a OGG: %s", e)
        return None
    return p.stdout if p.returncode == 0 and p.stdout else None


def sintetizar(texto: str) -> bytes | None:
    """Nota de voz OGG/Opus, o None si no hay forma de generarla (entonces solo va el texto)."""
    s = get_settings()
    if not texto or not s.freellm_api_key or router.caida_simulada():
        return None
    inicio = time.monotonic()
    try:
        r = httpx.post(f"{s.freellm_url.rstrip('/')}/audio/speech",
                       headers={"Authorization": f"Bearer {s.freellm_api_key}"}, timeout=s.medios_timeout_s,
                       json={"model": s.freellm_modelo_voz, "voice": s.freellm_voz, "input": texto})
        r.raise_for_status()
    except httpx.HTTPError as e:
        log.warning("Síntesis de voz falló: %s", e)
        metrics.registrar("freellm", s.freellm_modelo_voz, "sintetizar_voz", 0, 0, _ms(inicio), ok=False)
        return None
    audio = r.content
    ogg = audio if audio[:4] == b"OggS" else _a_ogg(audio)
    metrics.registrar("freellm", s.freellm_modelo_voz, "sintetizar_voz", 0, 0, _ms(inicio), ok=bool(ogg))
    return ogg


def _ms(inicio: float) -> int:
    return int((time.monotonic() - inicio) * 1000)
