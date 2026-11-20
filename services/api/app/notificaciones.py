"""Cola de avisos salientes (H4.5). La API nunca habla con WhatsApp ni Telegram: pide al bot `POST {BOT_URL}/notify`.

- Cada aviso se guarda en la tabla `notificaciones` antes de enviarlo. Si el bot está caído o tarda más de
  NOTIFICACIONES_TIMEOUT_S, queda `pendiente` y `reintentar_pendientes` lo vuelve a intentar; tras
  NOTIFICACIONES_MAX_INTENTOS fallos pasa a `fallida`.
- Ninguna función de este módulo lanza excepciones: un aviso que no sale nunca hace fallar la ruta que lo pide.
- Hacen `db.flush()`, pero el commit es de quien llama (así el aviso entra en la misma transacción que el cambio
  que lo provoca). Ojo: el bot recibe el aviso antes del commit, así que conviene llamar a `notificar` cuando el
  cambio ya está decidido y validado.

Destino (contracts/schemas/notificacion.json): `telefono` E.164 es obligatorio y `contacto` (`tg:<chat_id>`) va
aparte; si viene, el bot envía ahí. Un usuario solo de Telegram (sin telefono) no se puede avisar con el contrato
actual: su aviso se guarda como `fallida` con `ultimo_error = "sin telefono"`.
"""

import logging

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.canales import contacto_de, reconocer_contacto
from app.config import get_settings
from app.modelos import FORMATOS_AVISO, TIPOS_NOTIFICACION, Notificacion, Usuario, ahora
from app.telefonos import normalizar_telefono

log = logging.getLogger(__name__)

MAX_BOTONES = 3  # contracts/schemas/notificacion.json
SIN_TELEFONO = "sin telefono"

# Transporte de httpx. None = red real; los tests ponen un httpx.MockTransport.
_transporte: httpx.BaseTransport | None = None


def destino_de(usuario: Usuario) -> tuple[str | None, str | None]:
    """(telefono, contacto) del usuario. Si tiene Telegram, contacto = `tg:<chat_id>` y el bot le avisa por ahí
    (Telegram es el canal activo en la demo); si no, contacto = None y el aviso va al telefono por WhatsApp."""
    telefono = usuario.telefono or None
    contacto = contacto_de("telegram", usuario.telegram_id) if usuario.telegram_id else None
    return telefono, contacto


def _cuerpo(n: Notificacion) -> dict:
    """Cuerpo de POST /notify según contracts/schemas/notificacion.json."""
    cuerpo = {
        "id": n.id,
        "telefono": n.telefono,
        "tipo": n.tipo,
        "texto": n.texto,
        "formato": n.formato,
        "usuario_id": n.usuario_id,
        "evento_id": n.evento_id,
        "botones": list(n.botones or []),
    }
    if n.contacto:
        cuerpo["contacto"] = n.contacto
    if n.plantilla:
        cuerpo["plantilla"] = n.plantilla
        cuerpo["parametros"] = list(n.parametros or [])
    return cuerpo


def _post_notify(n: Notificacion) -> tuple[str | None, bool]:
    """Llama al bot. Devuelve (motivo del fallo o None si lo ha aceptado, si el bot no responde)."""
    ajustes = get_settings()
    if not ajustes.bot_url:
        return "BOT_URL sin configurar", True
    try:
        with httpx.Client(transport=_transporte, timeout=ajustes.notificaciones_timeout_s) as cliente:
            r = cliente.post(
                ajustes.bot_url.rstrip("/") + "/notify",
                json=_cuerpo(n),
                headers={"X-Internal-Token": ajustes.internal_token},
            )
    except Exception as e:  # noqa: BLE001 — bot caído, lento o URL rara: el aviso queda en cola
        return f"{type(e).__name__}: {e}"[:500], True
    if not 200 <= r.status_code < 300:
        return f"HTTP {r.status_code}: {r.text[:200]}", r.status_code >= 500
    try:
        datos = r.json()
    except ValueError:
        datos = None
    if isinstance(datos, dict) and datos.get("enviado") is False:
        return "el bot respondio enviado=false", False
    return None, False


def _intentar(n: Notificacion) -> tuple[bool, bool]:
    """Un intento de envío; actualiza estado_envio, intentos y ultimo_error. (ha salido, el bot no responde)."""
    if not n.telefono:
        n.estado_envio, n.ultimo_error = "fallida", SIN_TELEFONO
        return False, False
    n.intentos = (n.intentos or 0) + 1
    error, bot_caido = _post_notify(n)
    if error is None:
        n.estado_envio, n.ultimo_error, n.enviada_en = "enviada", None, ahora()
        return True, False
    n.ultimo_error = error
    n.estado_envio = "fallida" if n.intentos >= get_settings().notificaciones_max_intentos else "pendiente"
    log.info("aviso %s no enviado (intento %s): %s", n.id, n.intentos, error)
    return False, bot_caido


def notificar(
    db: Session,
    *,
    tipo: str,
    texto: str,
    usuario: Usuario | None = None,
    telefono: str | None = None,
    contacto: str | None = None,
    evento_id: str | None = None,
    botones: list[str] | None = None,
    plantilla: str | None = None,
    parametros: list[str] | None = None,
    formato: str | None = None,
) -> Notificacion:
    """Guarda el aviso y lo intenta enviar ya. `telefono`/`contacto` explícitos mandan sobre los del usuario.
    `formato` por defecto: el `formato_aviso` del usuario (texto/audio). No lanza; no hace commit."""
    tel_usuario, contacto_usuario = destino_de(usuario) if usuario is not None else (None, None)
    telefono = normalizar_telefono(telefono) if telefono else tel_usuario
    if contacto:
        reconocido = reconocer_contacto(contacto)
        contacto = contacto_de(*reconocido) if reconocido else None
    contacto = contacto or contacto_usuario
    if not telefono and contacto and contacto.startswith("+"):
        telefono = contacto
    if tipo not in TIPOS_NOTIFICACION:
        log.warning("tipo de aviso desconocido %r; se envía como 'anuncio'", tipo)
        tipo = "anuncio"
    formato = formato or (usuario.formato_aviso if usuario is not None else None)
    if formato not in FORMATOS_AVISO:
        formato = "texto"

    n = Notificacion(
        telefono=telefono,
        contacto=contacto,
        tipo=tipo,
        texto=texto or "",
        formato=formato,
        usuario_id=usuario.id if usuario is not None else None,
        evento_id=evento_id,
        botones=list(botones or [])[:MAX_BOTONES],
        plantilla=plantilla,
        parametros=list(parametros) if parametros else None,
        estado_envio="pendiente",
        intentos=0,
    )
    try:
        db.add(n)
        db.flush()
        _intentar(n)
        db.flush()
    except Exception:  # noqa: BLE001 — el aviso nunca tumba la ruta que lo pide
        log.exception("no se pudo guardar el aviso %s", n.id)
    return n


def notificar_moderadores(db: Session, tipo: str, texto: str, evento_id: str | None = None, **extra) -> list[Notificacion]:
    """Un aviso a cada usuario con rol `moderador`. `extra` se pasa a `notificar` (botones, plantilla…)."""
    moderadores = db.scalars(select(Usuario).where(Usuario.rol == "moderador").order_by(Usuario.creado_en)).all()
    return [notificar(db, tipo=tipo, texto=texto, usuario=m, evento_id=evento_id, **extra) for m in moderadores]


def reintentar_pendientes(db: Session, limite: int = 50) -> int:
    """Reenvía hasta `limite` avisos pendientes (los más antiguos primero). Devuelve cuántos han salido.
    Si el bot no responde (caído, timeout o 5xx), para ahí: los demás fallarían igual y cada uno esperaría el
    timeout. Un aviso que el bot rechaza (4xx) no frena la cola.
    No lanza; no hace commit."""
    enviadas = 0
    try:
        pendientes = db.scalars(
            select(Notificacion)
            .where(Notificacion.estado_envio == "pendiente")
            .order_by(Notificacion.creado_en)
            .limit(limite)
        ).all()
        for n in pendientes:
            enviada, bot_caido = _intentar(n)
            enviadas += enviada
            if bot_caido:
                break
        db.flush()
    except Exception:  # noqa: BLE001
        log.exception("fallo al reintentar los avisos pendientes")
    return enviadas
