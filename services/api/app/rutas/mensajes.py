"""Chat del evento (H3.4): leer (público), escribir (vecino con sesión o el bot en su nombre) y fijar/ocultar.

Permisos (diapositiva 17):
- Leer: cualquiera, si la ficha del evento es visible. Los mensajes ocultos solo los ven el organizador, los
  moderadores y el bot.
- Escribir: usuario con sesión, o el bot con X-Internal-Token y `usuario_id`. Un vecino solo escribe en eventos
  publicados; el organizador y los moderadores, en cualquiera visible.
- Plan terminado (`finalizado`, o publicado con la fecha ya pasada): cualquiera con sesión puede comentar, pero solo
  `tipo: comentario` (si no, 409 `evento_finalizado`).
- Fotos (`imagen_url`): solo en comentarios de planes terminados y solo de quien se inscribió (`confirmada`,
  `asistio` o `no_asistio`), del organizador o de un moderador; si no, 403 `sin_permiso`. Se admite una URL
  `http(s)://` (hasta 2048 caracteres) o una data URL `data:image/(png|jpeg|webp|gif);base64,…`; otra cosa da
  422 `imagen_invalida` y una data URL de más de 2 MB (de imagen ya decodificada) da 413 `imagen_demasiado_grande`.
- Anuncios (salen fijados): solo el organizador del evento o un moderador.
- PATCH: fijar/desfijar y ocultar/mostrar, organizador o moderador (o el bot). El autor solo puede ocultar el
  suyo (`oculto: true`); no puede volver a mostrar un mensaje ocultado por moderación.
- Silenciar (PATCH con `silenciar_autor`): organizador o moderador (o el bot). `true` impide al autor del mensaje
  volver a escribir en el chat de ese evento (403 `usuario_silenciado`); `false` se lo vuelve a permitir. No se
  puede silenciar al organizador ni a un moderador, ni a un mensaje sin autor (la IA): 409 `no_silenciable`.

Spam: se puntúa antes de guardar (`bot /ai/spam`, contexto «mensaje», con reglas de respaldo). Si llega al
umbral (MODERACION_UMBRAL_SPAM) se rechaza con 422 `mensaje_spam` y el motivo: así quien escribe sabe por qué
y no queda basura oculta en la base. Los teléfonos del texto se sustituyen por «[teléfono oculto]».
"""

from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Header
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.chat import (
    NOMBRE_ASISTENTE,
    autor_en_evento,
    avisar_pregunta_al_organizador,
    mensaje_a_dict,
    ocultar_telefonos,
    respuesta_automatica,
)
from app.config import get_settings
from app.db import get_db
from app.errores import ErrorApi
from app.imagenes import validar_imagen as _validar_imagen
from app.inscripciones import estuvo_inscrito, plan_terminado
from app.modelos import Evento, MensajeEvento, Silenciado, Usuario
from app.moderacion import clasificar_spam
from app.notificaciones import enviar_en_segundo_plano, notificar
from app.paginacion import Pagina, pagina, paginar
from app.rutas.eventos import VISIBLES_EN_FICHA
from app.rutas.publico import es_uuid
from app.seguridad import Quien, es_organizador, es_servicio_interno, puede_gestionar, quien_llama, usuario_actual
from app.serializar import inscritos_por_evento

router = APIRouter(prefix="/api/v1", tags=["chat"])


class MensajeCrear(BaseModel):
    """components/schemas/MensajeCrear de openapi.yaml."""

    model_config = ConfigDict(extra="forbid")

    texto: Annotated[str, Field(min_length=1, max_length=1000)]
    tipo: Literal["pregunta", "comentario", "anuncio"] = "comentario"
    en_respuesta_a: str | None = None
    imagen_url: str | None = None
    usuario_id: str | None = None


class MensajeEditar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fijado: bool | None = None
    oculto: bool | None = None
    silenciar_autor: bool | None = None


def _prohibido(mensaje: str) -> ErrorApi:
    return ErrorApi(403, "prohibido", mensaje)


MAX_BYTES_IMAGEN = 2 * 1024 * 1024


def validar_imagen(imagen_url: str) -> str:
    """URL http(s) o data URL de imagen en base64. 422 `imagen_invalida` o 413 `imagen_demasiado_grande` (2 MB)."""
    return _validar_imagen(imagen_url, MAX_BYTES_IMAGEN)


def _evento(db: Session, id: str, gestor_interno: bool = False) -> Evento:
    """Evento visible (o cualquiera para el bot). 404 si no existe o no se puede ver."""
    evento = db.get(Evento, id, options=[selectinload(Evento.publicador)]) if es_uuid(id) else None
    if evento is None or (evento.estado not in VISIBLES_EN_FICHA and not gestor_interno):
        raise ErrorApi(404, "evento_no_encontrado", "No existe ese evento")
    return evento


def _mensaje(db: Session, evento: Evento, msg_id: str) -> MensajeEvento:
    mensaje = db.get(MensajeEvento, msg_id) if es_uuid(msg_id) else None
    if mensaje is None or mensaje.evento_id != evento.id:
        raise ErrorApi(404, "mensaje_no_encontrado", "No existe ese mensaje en este evento")
    return mensaje


@router.get("/eventos/{id}/mensajes")
def listar_mensajes(
    id: str,
    p: Pagina = Depends(pagina),
    x_internal_token: str | None = Header(None),
    usuario: Usuario | None = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    interno = es_servicio_interno(x_internal_token)
    evento = _evento(db, id, interno)
    consulta = (
        select(MensajeEvento)
        .where(MensajeEvento.evento_id == evento.id)
        .order_by(MensajeEvento.fijado.desc(), MensajeEvento.creado_en, MensajeEvento.id)
    )
    if not puede_gestionar(Quien(interno, usuario), evento):
        consulta = consulta.where(MensajeEvento.oculto.is_(False))
    return paginar(db, consulta, p, mensaje_a_dict)


@router.post("/eventos/{id}/mensajes", status_code=201)
def publicar_mensaje(
    id: str,
    datos: MensajeCrear,
    background_tasks: BackgroundTasks,
    quien: Quien = Depends(quien_llama),
    db: Session = Depends(get_db),
):
    if quien.usuario is not None and not quien.interno:
        usuario = quien.usuario
        if datos.usuario_id is not None and datos.usuario_id != usuario.id:
            raise _prohibido("Solo puedes escribir en tu nombre")
    else:
        if datos.usuario_id is None:
            raise ErrorApi(422, "falta_usuario_id", "Con X-Internal-Token hay que indicar usuario_id",
                           {"campo": "usuario_id"})
        usuario = db.get(Usuario, datos.usuario_id) if es_uuid(datos.usuario_id) else None
        if usuario is None:
            raise ErrorApi(404, "usuario_no_encontrado", "No existe ese usuario")

    evento = _evento(db, id)
    organizador = es_organizador(usuario, evento)
    gestor = organizador or usuario.rol == "moderador"
    terminado = plan_terminado(evento)
    if terminado:
        if datos.tipo != "comentario":
            raise ErrorApi(409, "evento_finalizado", "Este plan ya ha terminado: solo se admiten comentarios",
                           {"estado": evento.estado, "tipo": datos.tipo})
    elif evento.estado != "publicado" and not gestor:
        raise ErrorApi(409, "chat_cerrado", f"El evento está {evento.estado}: el chat ya no admite mensajes",
                       {"estado": evento.estado})
    if not gestor and db.get(Silenciado, (evento.id, usuario.id)) is not None:
        raise ErrorApi(403, "usuario_silenciado", "El organizador o un moderador te ha silenciado en este chat")
    if datos.tipo == "anuncio" and not gestor:
        raise _prohibido("Solo el organizador del evento o un moderador pueden publicar anuncios")
    imagen_url = (datos.imagen_url or "").strip() or None
    if imagen_url is not None:
        if not terminado:
            raise ErrorApi(403, "sin_permiso", "Las fotos solo se pueden subir cuando el plan ya ha pasado")
        if not gestor and not estuvo_inscrito(db, evento, usuario):
            raise ErrorApi(403, "sin_permiso", "Solo quien se apuntó al plan o la organización pueden subir fotos")
        validar_imagen(imagen_url)
    if datos.en_respuesta_a is not None:
        original = db.get(MensajeEvento, datos.en_respuesta_a) if es_uuid(datos.en_respuesta_a) else None
        if original is None or original.evento_id != evento.id:
            raise ErrorApi(422, "mensaje_no_encontrado", "en_respuesta_a no es un mensaje de este evento",
                           {"campo": "en_respuesta_a"})
    else:
        original = None

    # El spam se mira sobre el texto original: un teléfono con reclamo de venta es una de las señales.
    score, motivo = clasificar_spam(datos.texto, contexto="mensaje")
    if score >= get_settings().moderacion_umbral_spam:
        raise ErrorApi(422, "mensaje_spam", "El mensaje parece spam y no se ha publicado",
                       {"score_spam": score, "motivo": motivo})
    texto = ocultar_telefonos(datos.texto.strip())[:1000]
    if not texto:
        raise ErrorApi(422, "validacion", "El mensaje está vacío", {"campo": "texto"})

    # La respuesta del asistente (bot /ai/responder-ficha) se pide antes de escribir nada en la sesión: así no se
    # retiene el bloqueo de escritura de SQLite mientras se espera al bot.
    texto_ia = None
    if datos.tipo == "pregunta" and not gestor:
        inscritos = inscritos_por_evento(db, [evento.id]).get(evento.id, 0)
        texto_ia = respuesta_automatica(evento, texto, inscritos)

    nombre, rol = autor_en_evento(usuario, evento, organizador)
    mensaje = MensajeEvento(
        evento_id=evento.id, autor_id=usuario.id, autor_nombre=nombre, autor_rol=rol, tipo=datos.tipo,
        texto=texto, en_respuesta_a=datos.en_respuesta_a, imagen_url=imagen_url, fijado=datos.tipo == "anuncio", oculto=False,
        respondido_por_ia=False, score_spam=score,
    )
    db.add(mensaje)
    db.flush()

    avisos, respuesta_ia = [], None
    if datos.tipo == "pregunta" and not gestor:
        if texto_ia:
            respuesta_ia = MensajeEvento(
                evento_id=evento.id, autor_id=None, autor_nombre=NOMBRE_ASISTENTE, autor_rol="ia",
                tipo="respuesta", texto=texto_ia, en_respuesta_a=mensaje.id, fijado=False, oculto=False,
                respondido_por_ia=True, score_spam=None,
            )
            db.add(respuesta_ia)
            db.flush()
        else:
            avisos += avisar_pregunta_al_organizador(db, evento, texto)
    elif original is not None and gestor and original.autor_id and original.autor_id != usuario.id:
        # El organizador contesta a una pregunta: se avisa a quien la hizo.
        autor_original = db.get(Usuario, original.autor_id)
        if autor_original is not None and original.tipo == "pregunta":
            avisos.append(notificar(
                db, tipo="respuesta", texto=f"{nombre} ha contestado tu pregunta en «{evento.titulo}»: {texto}",
                usuario=autor_original, evento_id=evento.id, enviar=False,
            ))

    db.commit()
    enviar_en_segundo_plano(background_tasks, db, avisos)
    return {
        "mensaje": mensaje_a_dict(mensaje),
        "respuesta_ia": mensaje_a_dict(respuesta_ia) if respuesta_ia is not None else None,
    }


@router.patch("/eventos/{id}/mensajes/{msg_id}")
def editar_mensaje(
    id: str,
    msg_id: str,
    datos: MensajeEditar,
    quien: Quien = Depends(quien_llama),
    db: Session = Depends(get_db),
):
    evento = _evento(db, id, quien.interno)
    mensaje = _mensaje(db, evento, msg_id)
    cambios = datos.model_dump(exclude_none=True)
    silenciar = cambios.pop("silenciar_autor", None)
    if not puede_gestionar(quien, evento):
        # El autor solo puede ocultar el suyo: ni fijar, ni silenciar, ni volver a mostrar uno ocultado por moderación.
        es_autor = quien.usuario is not None and mensaje.autor_id == quien.usuario.id
        if not es_autor or cambios != {"oculto": True} or silenciar is not None:
            raise _prohibido("Solo el organizador del evento o un moderador pueden fijar, mostrar u ocultar "
                             "mensajes ajenos o silenciar; el autor solo puede ocultar el suyo")
    if silenciar is not None:
        _silenciar(db, evento, mensaje, silenciar, quien)
    for campo, valor in cambios.items():
        setattr(mensaje, campo, valor)
    db.commit()
    return mensaje_a_dict(mensaje)


def _silenciar(db: Session, evento: Evento, mensaje: MensajeEvento, silenciar: bool, quien: Quien) -> None:
    """Silencia (o vuelve a dejar escribir) al autor de `mensaje` en el chat de `evento`. No hace commit."""
    autor = db.get(Usuario, mensaje.autor_id) if mensaje.autor_id else None
    if autor is None:
        raise ErrorApi(409, "no_silenciable", "Este mensaje no tiene un autor al que silenciar",
                       {"mensaje_id": mensaje.id})
    actual = db.get(Silenciado, (evento.id, autor.id))
    if not silenciar:
        if actual is not None:
            db.delete(actual)
        return
    if autor.rol == "moderador" or es_organizador(autor, evento):
        raise ErrorApi(409, "no_silenciable", "No se puede silenciar al organizador del evento ni a un moderador",
                       {"usuario_id": autor.id})
    if actual is None:
        por = quien.usuario.id if quien.usuario is not None else "bot"
        db.add(Silenciado(evento_id=evento.id, usuario_id=autor.id, por=por))
