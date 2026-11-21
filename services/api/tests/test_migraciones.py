"""La migración crea todas las tablas en una base vacía, coincide con los modelos y se puede deshacer."""

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app import modelos  # noqa: F401
from app.db import Base, crear_motor

API = Path(__file__).resolve().parents[1]

TABLAS = {
    "municipios", "lugares", "usuarios", "publicadores", "fuentes", "eventos",
    "inscripciones", "mensajes_evento", "notificaciones", "metricas_tokens", "codigos_verificacion", "silenciados",
}


def _config(url: str) -> Config:
    cfg = Config(str(API / "alembic.ini"))
    cfg.attributes["url"] = url
    cfg.attributes["configurar_logs"] = False
    return cfg


@pytest.fixture
def url(tmp_path):
    return f"sqlite:///{(tmp_path / 'vacia.db').as_posix()}"


def test_upgrade_crea_todas_las_tablas(url):
    command.upgrade(_config(url), "head")
    motor = crear_motor(url)
    assert TABLAS <= set(inspect(motor).get_table_names())
    motor.dispose()


def test_migracion_coincide_con_los_modelos(url):
    command.upgrade(_config(url), "head")
    motor = crear_motor(url)
    with motor.connect() as conexion:
        diferencias = compare_metadata(MigrationContext.configure(conexion), Base.metadata)
    motor.dispose()
    assert not diferencias, f"Los modelos han cambiado sin migración: {diferencias}"


def test_downgrade_deja_la_base_vacia(url):
    cfg = _config(url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    motor = crear_motor(url)
    assert not TABLAS & set(inspect(motor).get_table_names())
    motor.dispose()


def test_la_base_rechaza_datos_fuera_del_contrato(url):
    command.upgrade(_config(url), "head")
    motor = crear_motor(url)
    with motor.begin() as c:
        c.execute(text("INSERT INTO municipios (nombre, lat, lon) VALUES ('Senés', 37.1983, -2.3447)"))
    insertar = (
        "INSERT INTO publicadores (id, nombre, tipo, municipio, estado, nivel_confianza, aprobaciones, "
        "automatizaciones_pausadas, categorias_habituales, creado_en) "
        "VALUES (:id, 'Prueba', 'otro', :municipio, 'aprobado', :nivel, 0, 0, '[]', '2026-11-20 10:00:00')"
    )
    # Nivel de confianza fuera de 0/1/2
    with pytest.raises(IntegrityError), motor.begin() as c:
        c.execute(text(insertar), {"id": "a", "municipio": "Senés", "nivel": 3})
    # Pueblo que no existe (clave foránea)
    with pytest.raises(IntegrityError), motor.begin() as c:
        c.execute(text(insertar), {"id": "b", "municipio": "Almería", "nivel": 0})
    motor.dispose()


def test_canal_telegram_se_puede_deshacer_y_rehacer(url):
    """0002: `telegram` en el CHECK del enum canal y columna telegram_id; downgrade a 0001 y upgrade head."""
    cfg = _config(url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0001")
    motor = crear_motor(url)
    assert "telegram_id" not in {c["name"] for c in inspect(motor).get_columns("usuarios")}
    motor.dispose()
    command.upgrade(cfg, "head")
    motor = crear_motor(url)
    for tabla in ("usuarios", "publicadores"):
        assert "telegram_id" in {c["name"] for c in inspect(motor).get_columns(tabla)}
    insertar = (
        "INSERT INTO eventos (id, titulo, categoria, etiquetas, municipio, lat, lon, fecha_inicio, es_gratuito, "
        "estado, origen_canal, importado_auto, faltan, creado_en, actualizado_en) VALUES (:id, 'Prueba', "
        "'cultural', '[]', 'Senés', 0, 0, '2026-11-20 10:00:00', 0, 'borrador', :canal, 0, '[]', "
        "'2026-11-20 10:00:00', '2026-11-20 10:00:00')"
    )
    with motor.begin() as c:
        c.execute(text("INSERT INTO municipios (nombre, lat, lon) VALUES ('Senés', 37.1983, -2.3447)"))
        c.execute(text(insertar), {"id": "a", "canal": "telegram"})
    with pytest.raises(IntegrityError), motor.begin() as c:
        c.execute(text(insertar), {"id": "b", "canal": "sms"})
    motor.dispose()
    # Al deshacer, lo que entró por Telegram pasa a `manual` y el CHECK vuelve a rechazar `telegram`.
    command.downgrade(cfg, "0001")
    motor = crear_motor(url)
    with motor.connect() as c:
        assert c.execute(text("SELECT origen_canal FROM eventos WHERE id = 'a'")).scalar() == "manual"
    with pytest.raises(IntegrityError), motor.begin() as c:
        c.execute(text(insertar), {"id": "c", "canal": "telegram"})
    motor.dispose()


def test_notificaciones_contacto_se_puede_deshacer_y_rehacer(url):
    """0003: contacto, plantilla y parametros en notificaciones y telefono opcional. Al deshacer se borran los
    avisos sin telefono (no caben en la tabla antigua)."""
    cfg = _config(url)
    command.upgrade(cfg, "head")
    motor = crear_motor(url)
    insertar = (
        "INSERT INTO notificaciones (id, telefono, contacto, tipo, texto, formato, botones, estado_envio, intentos, "
        "creado_en) VALUES (:id, :telefono, :contacto, 'anuncio', 'Hola', 'texto', '[]', 'pendiente', 0, "
        "'2026-11-20 10:00:00')"
    )
    with motor.begin() as c:
        c.execute(text(insertar), {"id": "a", "telefono": "+34600000201", "contacto": "tg:1"})
        c.execute(text(insertar), {"id": "b", "telefono": None, "contacto": "tg:2"})
    motor.dispose()
    command.downgrade(cfg, "0002")
    motor = crear_motor(url)
    assert "contacto" not in {c["name"] for c in inspect(motor).get_columns("notificaciones")}
    with motor.connect() as c:
        assert [f[0] for f in c.execute(text("SELECT id FROM notificaciones"))] == ["a"]
    motor.dispose()
    command.upgrade(cfg, "head")
    motor = crear_motor(url)
    columnas = {c["name"]: c for c in inspect(motor).get_columns("notificaciones")}
    assert {"contacto", "plantilla", "parametros"} <= set(columnas) and columnas["telefono"]["nullable"]
    motor.dispose()


def test_imagen_de_mensajes_se_puede_deshacer_y_rehacer(url):
    """0006: columna opcional imagen_url (Text) en mensajes_evento."""
    cfg = _config(url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0005")
    motor = crear_motor(url)
    assert "imagen_url" not in {c["name"] for c in inspect(motor).get_columns("mensajes_evento")}
    motor.dispose()
    command.upgrade(cfg, "head")
    motor = crear_motor(url)
    columnas = {c["name"]: c for c in inspect(motor).get_columns("mensajes_evento")}
    assert "imagen_url" in columnas and columnas["imagen_url"]["nullable"]
    motor.dispose()


def test_portada_ayuntamiento_y_responsable_se_pueden_deshacer_y_rehacer(url):
    """0007: frase_portada y datos_ayuntamiento en eventos; responsable e identidad_verificada (false por defecto,
    también en filas que ya existían) en publicadores. Con datos y tablas hijas (claves foráneas activas): la
    migración no puede recrear `eventos` ni `publicadores`."""
    cfg = _config(url)
    command.upgrade(cfg, "0006")
    motor = crear_motor(url)
    with motor.begin() as c:
        c.execute(text("INSERT INTO municipios (nombre, lat, lon) VALUES ('Senés', 37.1983, -2.3447)"))
        c.execute(text(
            "INSERT INTO publicadores (id, nombre, tipo, municipio, estado, nivel_confianza, aprobaciones, "
            "automatizaciones_pausadas, categorias_habituales, creado_en) VALUES ('p', 'Prueba', 'otro', 'Senés', "
            "'aprobado', 0, 0, 0, '[]', '2026-11-20 10:00:00')"
        ))
        c.execute(text(
            "INSERT INTO eventos (id, titulo, categoria, etiquetas, municipio, lat, lon, fecha_inicio, es_gratuito, "
            "estado, origen_canal, importado_auto, faltan, creado_en, actualizado_en, publicador_id) VALUES ('e', "
            "'Prueba', 'cultural', '[]', 'Senés', 0, 0, '2026-11-20 10:00:00', 0, 'borrador', 'manual', 0, '[]', "
            "'2026-11-20 10:00:00', '2026-11-20 10:00:00', 'p')"
        ))
        c.execute(text(
            "INSERT INTO notificaciones (id, telefono, tipo, texto, formato, botones, estado_envio, intentos, "
            "creado_en, evento_id) VALUES ('n', '+34600000201', 'anuncio', 'Hola', 'texto', '[]', 'pendiente', 0, "
            "'2026-11-20 10:00:00', 'e')"
        ))
    motor.dispose()

    command.upgrade(cfg, "head")
    motor = crear_motor(url)
    assert {"frase_portada", "datos_ayuntamiento"} <= {c["name"] for c in inspect(motor).get_columns("eventos")}
    assert {"responsable", "identidad_verificada"} <= {c["name"] for c in inspect(motor).get_columns("publicadores")}
    imagen = "data:image/png;base64," + "A" * 2000
    with motor.begin() as c:
        assert c.execute(text("SELECT identidad_verificada FROM publicadores WHERE id = 'p'")).scalar() in (0, False)
        # En SQLite la columna sigue siendo VARCHAR(500), que no limita la longitud.
        c.execute(text("UPDATE eventos SET imagen_url = :imagen WHERE id = 'e'"), {"imagen": imagen})
        assert c.execute(text("SELECT imagen_url FROM eventos WHERE id = 'e'")).scalar() == imagen
    motor.dispose()

    command.downgrade(cfg, "0006")
    motor = crear_motor(url)
    assert "frase_portada" not in {c["name"] for c in inspect(motor).get_columns("eventos")}
    assert "responsable" not in {c["name"] for c in inspect(motor).get_columns("publicadores")}
    with motor.connect() as c:
        assert c.execute(text("SELECT count(*) FROM notificaciones WHERE evento_id = 'e'")).scalar() == 1
    motor.dispose()
    command.upgrade(cfg, "head")


def test_0008_pasa_el_nivel_1_obsoleto_a_mano(url):
    """0008: solo dos modos de publicación. Los publicadores con nivel 1 pasan a 0; el 0 y el 2 no cambian."""
    cfg = _config(url)
    command.upgrade(cfg, "0007")
    motor = crear_motor(url)
    with motor.begin() as c:
        c.execute(text("INSERT INTO municipios (nombre, lat, lon) VALUES ('Senés', 37.1983, -2.3447)"))
        for id, nivel in (("p0", 0), ("p1", 1), ("p2", 2)):
            c.execute(text(
                "INSERT INTO publicadores (id, nombre, tipo, municipio, estado, nivel_confianza, aprobaciones, "
                "automatizaciones_pausadas, categorias_habituales, identidad_verificada, creado_en) VALUES (:id, "
                ":id, 'otro', 'Senés', 'aprobado', :nivel, 0, 0, '[]', 0, '2026-11-20 10:00:00')"
            ), {"id": id, "nivel": nivel})
    motor.dispose()

    command.upgrade(cfg, "head")
    motor = crear_motor(url)
    with motor.connect() as c:
        niveles = dict(c.execute(text("SELECT id, nivel_confianza FROM publicadores")).all())
    motor.dispose()
    assert niveles == {"p0": 0, "p1": 0, "p2": 2}


def test_0009_plazas_libres_salen_de_las_inscripciones(url):
    """0009 (N6): plazas_libres = plazas_totales − inscritos confirmados. Los finalizados y los sin aforo no cambian."""
    from datetime import datetime, timezone

    from sqlalchemy import insert
    from sqlalchemy.orm import Session

    from app.modelos import Evento, Inscripcion, Municipio, Usuario

    cfg = _config(url)
    command.upgrade(cfg, "0008")
    motor = crear_motor(url)
    fecha = datetime(2026, 12, 1, 10, 0, tzinfo=timezone.utc)
    with Session(motor) as db:
        db.add(Municipio(nombre="Senés", lat=37.1983, lon=-2.3447))
        db.flush()

        def evento(id_, estado, total, libres):
            # INSERT solo con estas columnas: la base está en 0008 y el modelo ya tiene columnas posteriores.
            db.execute(insert(Evento), [dict(id=id_, titulo=id_, categoria="cultural", municipio="Senés", lat=0,
                                             lon=0, fecha_inicio=fecha, estado=estado, plazas_totales=total,
                                             plazas_libres=libres)])

        evento("abierto", "publicado", 10, 2)  # 8 inscritos inventados en el fixture
        evento("pasado", "finalizado", 10, 1)
        evento("sin_aforo", "publicado", None, None)
        evento("lleno", "publicado", 1, 1)
        db.flush()
        for i, (ev, estado, plazas) in enumerate((("abierto", "confirmada", 2), ("abierto", "confirmada", 1),
                                                   ("abierto", "lista_espera", 1), ("abierto", "cancelada", 1),
                                                   ("lleno", "confirmada", 1), ("pasado", "asistio", 1))):
            u = Usuario(nombre=f"u{i}")
            db.add(u)
            db.flush()
            db.add(Inscripcion(evento_id=ev, usuario_id=u.id, estado=estado, plazas=plazas, canal="web"))
        db.commit()
    motor.dispose()

    command.upgrade(cfg, "head")
    motor = crear_motor(url)
    with motor.connect() as c:
        libres = dict(c.execute(text("SELECT id, plazas_libres FROM eventos")).all())
    motor.dispose()
    assert libres == {"abierto": 7, "pasado": 1, "sin_aforo": None, "lleno": 0}
