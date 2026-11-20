"""Cola de avisos salientes (H4.5). La API nunca habla con WhatsApp ni Telegram: pide al bot `POST {BOT_URL}/notify`.

- Cada aviso se guarda en la tabla `notificaciones` antes de enviarlo. Si el bot está caído o tarda más de
  NOTIFICACIONES_TIMEOUT_S, queda `pendiente` y `reintentar_pendientes` lo vuelve a intentar; tras
  NOTIFICACIONES_MAX_INTENTOS fallos pasa a `fallida`.
- Ninguna función de este módulo lanza excepciones: un aviso que no sale nunca hace fallar la ruta que lo pide.
- Hacen `db.flush()`, pero el commit es de quien llama (así el aviso entra en la misma transacción que el cambio
  que lo provoca).
- Las rutas usan `enviar=False`: dentro de la transacción solo se crea la fila `pendiente` (sin HTTP) y, tras el
  `db.commit()`, `enviar_en_segundo_plano(background_tasks, db, avisos)` la manda al bot cuando ya se ha
  respondido. Así el bot nunca recibe un aviso de un cambio que luego se deshace, y un bot caído no hace esperar
  a quien llama. Con `enviar=True` (por defecto) se intenta en el acto, antes del commit.

Destino (contracts/schemas/notificacion.json): `telefono` E.164 es obligatorio y `contacto` (`tg:<chat_id>`) va
aparte; si viene, el bot envía ahí. Un usuario solo de Telegram (sin telefono) no se puede avisar con el contrato
actual: su aviso se guarda como `fallida` con `ultimo_error = "sin telefono"`.
"""

import logging
from collections.abc import Iterable

import httpx
from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

from app.canales import contacto_de, reconocer_contacto
from app.config import get_settings
from app.modelos import FORMATOS_AVISO, TIPOS_NOTIFICACION, Notificacion, Publicador, Usuario, ahora
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
    enviar: bool = True,
) -> Notificacion:
    """Guarda el aviso y, con `enviar=True`, lo intenta enviar ya; con `enviar=False` queda `pendiente` para
    `enviar_en_segundo_plano`. `telefono`/`contacto` explícitos mandan sobre los del usuario.
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
        if enviar:
            _intentar(n)
            db.flush()
        elif not n.telefono:
            n.estado_envio, n.ultimo_error = "fallida", SIN_TELEFONO
            db.flush()
    except Exception:  # noqa: BLE001 — el aviso nunca tumba la ruta que lo pide
        log.exception("no se pudo guardar el aviso %s", n.id)
    return n


def notificar_moderadores(db: Session, tipo: str, texto: str, evento_id: str | None = None, **extra) -> list[Notificacion]:
    """Un aviso a cada usuario con rol `moderador`. `extra` se pasa a `notificar` (botones, plantilla…)."""
    moderadores = db.scalars(select(Usuario).where(Usuario.rol == "moderador").order_by(Usuario.creado_en)).all()
    return [notificar(db, tipo=tipo, texto=texto, usuario=m, evento_id=evento_id, **extra) for m in moderadores]


def notificar_publicador(
    db: Session, publicador: Publicador, tipo: str, texto: str, evento_id: str | None = None, **extra
) -> Notificacion:
    """Aviso al responsable del publicador: su usuario (por `usuario_id` o, si no, por el teléfono) y, si no
    es usuario, el teléfono / Telegram del propio publicador. Mismas garantías que `notificar`."""
    usuario = None
    try:
        if publicador.usuario_id:
            usuario = db.get(Usuario, publicador.usuario_id)
        if usuario is None and publicador.telefono:
            usuario = db.scalar(select(Usuario).where(Usuario.telefono == publicador.telefono))
    except Exception:  # noqa: BLE001
        log.exception("no se pudo buscar el usuario del publicador %s", publicador.id)
    if usuario is not None:
        return notificar(db, tipo=tipo, texto=texto, usuario=usuario, evento_id=evento_id, **extra)
    contacto = contacto_de("telegram", publicador.telegram_id) if publicador.telegram_id else None
    return notificar(
        db, tipo=tipo, texto=texto, telefono=publicador.telefono, contacto=contacto, evento_id=evento_id, **extra
    )


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
        enviadas = _enviar_lote(db, pendientes)
    except Exception:  # noqa: BLE001
        log.exception("fallo al reintentar los avisos pendientes")
    return enviadas


def _enviar_lote(db: Session, avisos: Iterable[Notificacion]) -> int:
    """Intenta los avisos `pendiente` en orden; para en cuanto el bot no responde (caído, timeout o 5xx): los
    demás fallarían igual y cada uno esperaría el timeout. Devuelve cuántos han salido. No hace commit."""
    enviadas = 0
    for n in avisos:
        if n.estado_envio != "pendiente":
            continue
        enviada, bot_caido = _intentar(n)
        enviadas += enviada
        if bot_caido:
            break
    db.flush()
    return enviadas


def enviar_avisos(bind: Engine | Connection, ids: list[str]) -> int:
    """Envía los avisos `ids` (en ese orden) con una sesión propia y guarda el resultado. Pensada para
    BackgroundTasks: se ejecuta después de responder, cuando la sesión de la petición ya está cerrada.
    No lanza. Devuelve cuántos han salido."""
    if not ids:
        return 0
    try:
        with Session(bind=bind, expire_on_commit=False) as db:
            por_id = {n.id: n for n in db.scalars(select(Notificacion).where(Notificacion.id.in_(ids))).all()}
            enviadas = _enviar_lote(db, [por_id[i] for i in ids if i in por_id])
            db.commit()
            return enviadas
    except Exception:  # noqa: BLE001 — quedan pendientes; reintentar_pendientes los recogerá
        log.exception("fallo al enviar los avisos %s", ids)
        return 0


def enviar_en_segundo_plano(
    background_tasks: BackgroundTasks, db: Session, avisos: Iterable[Notificacion | None]
) -> list[str]:
    """Programa el envío de `avisos` (creados con `enviar=False`) para después de la respuesta. Llamar tras el
    `db.commit()` que los guarda. Devuelve los ids programados."""
    ids = [n.id for n in avisos if n is not None and n.id and n.estado_envio == "pendiente"]
    if ids:
        background_tasks.add_task(enviar_avisos, db.get_bind(), ids)
    return ids


def ciclo_reintentos(fabrica: sessionmaker[Session] | None = None, limite: int = 50) -> int:
    """Una vuelta de la tarea de fondo (app/main.py): sesión propia, `reintentar_pendientes` y commit.
    No lanza nunca (ni con la base o el bot caídos). Devuelve cuántos avisos han salido."""
    try:
        if fabrica is None:
            from app.db import _fabrica_sesiones

            fabrica = _fabrica_sesiones()
        with fabrica() as db:
            enviadas = reintentar_pendientes(db, limite)
            db.commit()
            return enviadas
    except Exception:  # noqa: BLE001 — la tarea de fondo nunca tumba la API
        log.exception("fallo en el ciclo de reintento de avisos")
        return 0
