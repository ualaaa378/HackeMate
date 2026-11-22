"""Datos de la demo: carga contracts/fixtures en la base de datos.

- Crea o actualiza las tablas (alembic upgrade head) antes de cargar.
- Se puede ejecutar las veces que haga falta: actualiza por id, no duplica.
- Los eventos con fechas reales que ya han terminado no se cargan, y si ya estaban en la base
  (de un seed anterior) se borran, junto con sus inscripciones y mensajes. Así la agenda solo
  enseña lo que aún va a pasar y, llegado el día, cada evento desaparece solo al volver a sembrar.
- Excepción: el histórico para el panel de estadísticas (H4.3). `eventos_pasados.json` trae actividades ya
  celebradas (estado `finalizado`, con aforo) e `inscripciones_pasadas.json` su asistencia (`asistio`/`no_asistio`).
  Se cargan siempre: no salen en la agenda ni en las recomendaciones (solo muestran `publicado`), pero así las
  gráficas no están vacías. Incluyen el solapamiento de demo «Cine de verano en Uleila» con la verbena de Senés.
- Solo toca los datos de los fixtures; lo que creen los usuarios no se borra (salvo con --reset).
- `--solo-nuevos` (el que usa el contenedor `api` al arrancar): añade lo que falte y NO sobrescribe lo que ya
  existe. Sin él, cada reinicio devolvería los datos de la demo a los fixtures y desharía lo que hayan hecho las
  personas (cambios de hora, decisiones del moderador, plazas libres tras inscribirse, gustos guardados…).

Uso:  python scripts/seed.py [--reset | --solo-nuevos]   (desde la raíz del repo)
      python -m app.seed [--reset | --solo-nuevos]       (desde services/api o dentro del contenedor api)
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import delete, inspect, select
from sqlalchemy.orm import Session

from app import entidades
from app.config import get_settings
from app.db import API_DIR, crear_motor
from app.inscripciones import recalcular_plazas
from app.modelos import (
    Base,
    Evento,
    Fuente,
    Inscripcion,
    Lugar,
    MensajeEvento,
    Municipio,
    Notificacion,
    Publicador,
    Usuario,
)

FICHEROS_EVENTOS = ("eventos.json", "eventos_demo.json")
FICHERO_HISTORICO = "eventos_pasados.json"
FICHERO_INSCRIPCIONES_HISTORICO = "inscripciones_pasadas.json"


def directorio_fixtures() -> Path:
    configurado = get_settings().fixtures_dir
    if configurado:
        return Path(configurado)
    # Monorepo: services/api/app/seed.py -> raiz/contracts/fixtures
    return Path(__file__).resolve().parents[3] / "contracts" / "fixtures"


def _leer(nombre: str, directorio: Path) -> list[dict]:
    with open(directorio / nombre, encoding="utf-8") as f:
        return json.load(f)


def _fecha(valor: str | None) -> datetime | None:
    return datetime.fromisoformat(valor.replace("Z", "+00:00")) if valor else None


def _columnas(modelo, datos: dict, fechas: tuple[str, ...] = ()) -> dict:
    """Quita los campos que no son columnas (p. ej. inscritos, publicador_nombre, usuario_nombre)."""
    cols = {c.key for c in modelo.__table__.columns}
    fila = {k: v for k, v in datos.items() if k in cols}
    for f in fechas:
        if f in fila:
            fila[f] = _fecha(fila[f])
    return fila


def ha_terminado(evento: dict, ahora: datetime) -> bool:
    fin = _fecha(evento.get("fecha_fin")) or _fecha(evento["fecha_inicio"])
    return fin < ahora


def _fila_evento(e: dict) -> dict:
    fila = _columnas(Evento, e, ("fecha_inicio", "fecha_fin", "creado_en", "actualizado_en"))
    origen = e.get("origen") or {}
    moderacion = e.get("moderacion") or {}
    fila |= {
        "origen_canal": origen.get("canal", "manual"),
        "origen_url": origen.get("url"),
        "importado_auto": origen.get("importado_auto", False),
        "motivo_moderacion": moderacion.get("motivo"),
        "score_spam": moderacion.get("score_spam"),
        "revisado_por": moderacion.get("revisado_por"),
    }
    return fila


def _fila_publicador(p: dict) -> dict:
    """`responsable.identidad_verificada` del fixture va en su propia columna; `responsable` guarda el resto."""
    fila = _columnas(Publicador, p, ("creado_en",))
    responsable = dict(p.get("responsable") or {})
    fila["identidad_verificada"] = bool(responsable.pop("identidad_verificada", False))
    fila["responsable"] = responsable or None
    return fila


def migrar(url: str | None = None) -> None:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.attributes["configurar_logs"] = False
    if url:
        cfg.attributes["url"] = url
    command.upgrade(cfg, "head")


def vaciar(db: Session) -> None:
    """--reset: deja la base vacía (en orden inverso a las dependencias)."""
    db.execute(Usuario.__table__.update().values(publicador_id=None))
    for tabla in reversed(Base.metadata.sorted_tables):
        if tabla.name != "alembic_version":
            db.execute(delete(tabla))


def _guardar(db: Session, fila, sobrescribir: bool) -> bool:
    """`merge` (actualiza por id) o, con sobrescribir=False, solo inserta si no existe. True si la escribe."""
    if sobrescribir:
        db.merge(fila)
        return True
    clave = inspect(fila).mapper.primary_key_from_instance(fila)
    if db.get(type(fila), clave[0] if len(clave) == 1 else tuple(clave)) is not None:
        return False
    db.add(fila)
    return True


def sembrar(db: Session, directorio: Path | None = None, ahora: datetime | None = None,
            sobrescribir: bool = True) -> dict:
    """Carga los fixtures y devuelve un resumen. No hace commit: lo hace quien llama.
    Con sobrescribir=False (`--solo-nuevos`) no toca las filas que ya existen: solo añade las que faltan."""
    directorio = directorio or directorio_fixtures()
    ahora = ahora or datetime.now(timezone.utc)
    resumen: dict[str, int] = {}

    for m in _leer("municipios.json", directorio):
        _guardar(db, Municipio(**m), sobrescribir)
    resumen["municipios"] = len(_leer("municipios.json", directorio))

    lugares = _leer("lugares.json", directorio)
    for lugar in lugares:
        _guardar(db, Lugar(**_columnas(Lugar, lugar)), sobrescribir)
    resumen["lugares"] = len(lugares)

    # usuarios <-> publicadores se apuntan entre sí: primero sin el enlace, luego se completa.
    usuarios = _leer("usuarios.json", directorio)
    nuevos_usuarios = set()
    for u in usuarios:
        if _guardar(db, Usuario(**(_columnas(Usuario, u, ("creado_en",)) | {"publicador_id": None})), sobrescribir):
            nuevos_usuarios.add(u["id"])
    db.flush()

    publicadores = _leer("publicadores.json", directorio)
    remapeo: dict[str, str | None] = {}
    if get_settings().solo_ayuntamientos:
        publicadores, remapeo = entidades.remapeo_fixtures(publicadores)

    def _remapear(fila: dict) -> dict:
        if fila.get("publicador_id") in remapeo:
            return dict(fila, publicador_id=remapeo[fila["publicador_id"]])
        return fila

    usuarios = [_remapear(u) for u in usuarios]
    fuentes = 0
    for p in publicadores:
        _guardar(db, Publicador(**_fila_publicador(p)), sobrescribir)
        db.flush()
        for f in p.get("fuentes", []):
            _guardar(db, Fuente(**_columnas(Fuente, f), publicador_id=p["id"]), sobrescribir)
            fuentes += 1
    db.flush()
    for u in usuarios:
        if u.get("publicador_id") and u["id"] in nuevos_usuarios:
            db.get(Usuario, u["id"]).publicador_id = u["publicador_id"]
    resumen |= {"usuarios": len(usuarios), "publicadores": len(publicadores), "fuentes": fuentes}

    cargados, terminados = set(), set()
    for nombre in FICHEROS_EVENTOS:
        for e in map(_remapear, _leer(nombre, directorio)):
            if ha_terminado(e, ahora):
                terminados.add(e["id"])
            else:
                _guardar(db, Evento(**_fila_evento(e)), sobrescribir)
                cargados.add(e["id"])
    db.flush()
    borrados = 0
    for id_evento in terminados:
        evento = db.get(Evento, id_evento)
        if evento is not None:
            db.delete(evento)  # la base borra en cascada sus inscripciones y mensajes
            borrados += 1
    db.flush()
    resumen |= {"eventos": len(cargados), "eventos_terminados_omitidos": len(terminados), "eventos_terminados_borrados": borrados}

    historico = set()
    for e in map(_remapear, _leer(FICHERO_HISTORICO, directorio)):
        _guardar(db, Evento(**_fila_evento(e)), sobrescribir)
        historico.add(e["id"])
    db.flush()
    n = 0
    for fila in _leer(FICHERO_INSCRIPCIONES_HISTORICO, directorio):
        if fila["evento_id"] in historico:
            _guardar(db, Inscripcion(**_columnas(Inscripcion, fila, ("creado_en", "actualizado_en"))), sobrescribir)
            n += 1
    db.flush()
    resumen |= {"eventos_historico": len(historico), "inscripciones_historico": n}

    # Lo que cuelga de un evento solo se carga si el evento sigue en la agenda.
    for clave, modelo, fichero, fechas in (
        ("inscripciones", Inscripcion, "inscripciones.json", ("creado_en", "actualizado_en")),
        ("mensajes", MensajeEvento, "mensajes_evento.json", ("creado_en",)),
        ("notificaciones", Notificacion, "notificaciones.json", ("creado_en", "enviada_en")),
    ):
        n = 0
        for fila in _leer(fichero, directorio):
            if fila.get("evento_id") and fila["evento_id"] not in cargados:
                continue
            _guardar(db, modelo(**_columnas(modelo, fila, fechas)), sobrescribir)
            db.flush()  # respuestas que apuntan a mensajes anteriores del mismo fichero
            n += 1
        resumen[clave] = n

    if get_settings().solo_ayuntamientos:
        db.flush()
        resumen["entidades_no_ayuntamiento_borradas"] = entidades.depurar(db)

    # N6: plazas libres a partir de las inscripciones de la base, no de los números de los fixtures
    db.flush()
    resumen["plazas_recalculadas"] = recalcular_plazas(db)
    return resumen


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Carga los datos de la demo en la base de datos")
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument("--reset", action="store_true", help="vacía todas las tablas antes de cargar")
    modo.add_argument("--solo-nuevos", action="store_true",
                      help="solo añade lo que falte; no sobrescribe lo que ya existe (arranque del contenedor)")
    args = parser.parse_args(argv)

    migrar()
    motor = crear_motor()
    with Session(motor) as db, db.begin():
        if args.reset:
            vaciar(db)
        resumen = sembrar(db, sobrescribir=not args.solo_nuevos)
    motor.dispose()

    destino = motor.url.database if motor.url.get_backend_name() == "sqlite" else motor.url.render_as_string(True)
    print(f"Base de datos: {destino}")
    for clave, valor in resumen.items():
        print(f"  {clave:28} {valor}")


if __name__ == "__main__":
    main()
