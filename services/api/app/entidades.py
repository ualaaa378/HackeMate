"""Solo ayuntamientos como entidades publicadoras (decisión de Adán, 22/11 01:33).

Con `SOLO_AYUNTAMIENTOS=true` (por defecto):
- `POST /publicadores` solo admite `tipo: ayuntamiento` (422 `solo_ayuntamientos`). El contrato no cambia: el enum
  conserva los otros tipos (contract-first: nunca se borra), pero la API no los acepta.
- El seed no carga las entidades de los fixtures que no son ayuntamientos y pasa lo suyo (planes, usuario, Telegram y
  fuentes de Facebook) al ayuntamiento de su pueblo. Si le pasa una persona que publicaba, el ayuntamiento se queda
  con el modo más prudente de los dos: Antonio (Amigos de Velefique, a mano) publica ahora como Ayto. de Velefique
  y sus planes siguen pasando por la bandeja, como pide el guion de la demo.
- `depurar` borra de la base las que ya estaban (de seeds anteriores o dadas de alta por usuarios), pasando antes lo
  suyo al ayuntamiento del pueblo. No se convierten: se borran, como pidió Adán.

Los tests corren con `SOLO_AYUNTAMIENTOS=false` (tests/conftest.py) porque prueban la confianza, la moderación y la
ingesta con asociaciones y bares de los fixtures; tests/test_entidades.py prueba este modo.
"""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modelos import Evento, Fuente, Publicador, Usuario

TIPO = "ayuntamiento"
# 22/11 09:35 (Adán): los ayuntamientos ya vienen dados de alta con su perfil; el alta de la web y del bot es para
# asociaciones. Bares, comercios y demás siguen fuera.
TIPOS_ALTA = ("ayuntamiento", "asociacion")


def id_perfil(ayto_id: str) -> str:
    """Usuario predeterminado de cada ayuntamiento: 5a5e…01NN, con NN los dos últimos dígitos del ayuntamiento."""
    return f"5a5e0000-0000-4000-8000-0000000001{ayto_id[-2:]}"


def remapeo_fixtures(publicadores: list[dict]) -> tuple[list[dict], dict[str, str | None]]:
    """(ayuntamientos a cargar, {id de la entidad quitada: id del ayuntamiento de su pueblo o None}).
    El usuario, el Telegram y las fuentes de la entidad quitada pasan al ayuntamiento si este no tiene."""
    aytos = {p["municipio"]: dict(p, fuentes=list(p.get("fuentes", []))) for p in publicadores if p["tipo"] == TIPO}
    remapeo: dict[str, str | None] = {}
    for p in publicadores:
        if p["tipo"] == TIPO:
            continue
        ayto = aytos.get(p["municipio"])
        remapeo[p["id"]] = ayto["id"] if ayto else None
        if ayto is None:
            continue
        for campo in ("usuario_id", "telegram_id"):
            if p.get(campo) and not ayto.get(campo):
                ayto[campo] = p[campo]
        if p.get("usuario_id"):  # quien publicaba se queda con el modo más prudente (a mano antes que automática)
            ayto["nivel_confianza"] = min(ayto.get("nivel_confianza", 0), p.get("nivel_confianza", 0))
        ayto["fuentes"] += p.get("fuentes", [])
    return list(aytos.values()), remapeo


def ayuntamiento_de(db: Session, municipio: str) -> Publicador | None:
    return db.scalar(select(Publicador).where(Publicador.tipo == TIPO, Publicador.municipio == municipio)
                     .order_by(Publicador.creado_en))


def depurar(db: Session, ids: list[str] | None = None) -> int:
    """Borra las entidades que no son ayuntamientos (con `ids`, solo esas: las de los fixtures, para no borrar las
    asociaciones que se dan de alta). Antes pasa sus planes, fuentes, usuario y Telegram al ayuntamiento de su pueblo
    (si no hay, los planes se quedan sin entidad y el usuario, como vecino). No hace commit. Devuelve cuántas ha
    borrado."""
    consulta = select(Publicador).where(Publicador.tipo != TIPO)
    if ids is not None:
        consulta = consulta.where(Publicador.id.in_(ids))
    otras = db.scalars(consulta).all()
    for p in otras:
        ayto = ayuntamiento_de(db, p.municipio)
        destino = ayto.id if ayto else None
        db.execute(update(Evento).where(Evento.publicador_id == p.id).values(publicador_id=destino)
                   .execution_options(synchronize_session=False))
        db.execute(update(Usuario).where(Usuario.publicador_id == p.id).values(publicador_id=destino)
                   .execution_options(synchronize_session=False))
        if ayto is not None:
            db.execute(update(Fuente).where(Fuente.publicador_id == p.id).values(publicador_id=ayto.id)
                       .execution_options(synchronize_session=False))
            usuario_id, telegram_id = p.usuario_id, p.telegram_id
            p.usuario_id, p.telegram_id = None, None
            db.flush()  # libera los únicos antes de pasarlos
            if usuario_id and not ayto.usuario_id:
                ayto.usuario_id = usuario_id
            if usuario_id:
                ayto.nivel_confianza = min(ayto.nivel_confianza, p.nivel_confianza)
            if telegram_id and not ayto.telegram_id:
                ayto.telegram_id = telegram_id
        db.flush()
        db.expire_all()
        db.delete(db.get(Publicador, p.id))
    db.flush()
    return len(otras)


def perfiles_ayuntamientos(db: Session) -> int:
    """Cada ayuntamiento sin usuario recibe uno predeterminado (rol publicador, con el teléfono del ayuntamiento), para
    que pueda entrar en su zona sin darse de alta. No hace commit. Devuelve cuántos ha creado."""
    creados = 0
    for ayto in db.scalars(select(Publicador).where(Publicador.tipo == TIPO, Publicador.usuario_id.is_(None))).all():
        usuario = db.get(Usuario, id_perfil(ayto.id))
        if usuario is None:
            ocupado = ayto.telefono and db.scalar(select(Usuario).where(Usuario.telefono == ayto.telefono))
            usuario = Usuario(id=id_perfil(ayto.id), nombre=ayto.nombre, rol="publicador", municipio=ayto.municipio,
                              telefono=None if ocupado else ayto.telefono)
            db.add(usuario)
            creados += 1
        db.flush()
        if usuario.publicador_id is None:
            usuario.publicador_id = ayto.id
        ayto.usuario_id = usuario.id
    db.flush()
    return creados
