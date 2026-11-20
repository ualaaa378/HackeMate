"""Exportación .ics (H3.3): GET /eventos/{id}/ics y GET /usuarios/me/ics."""

from datetime import datetime, timedelta, timezone

import pytest

from app.ics import calendario, escapar, nombre_fichero, plegar
from app.modelos import Evento, Inscripcion
from app.seed import sembrar
from app.seguridad import emitir_jwt
from tests.test_importar import TOKEN, VIERNES, _error

RUTA = "1e5d0000-0000-4000-8000-000000000001"
GRAFITI_EN_REVISION = "1e5d0000-0000-4000-8000-000000000009"
CARMEN = "5a5e0000-0000-4000-8000-000000000001"
JOSE = "5a5e0000-0000-4000-8000-000000000005"


def _bearer(usuario_id: str, rol: str = "vecino") -> dict:
    return {"Authorization": f"Bearer {emitir_jwt(usuario_id, rol)}"}


def desplegar(texto: str) -> list[str]:
    """Parser mínimo de RFC 5545: comprueba CRLF y longitud, y deshace el plegado."""
    assert texto.endswith("\r\n")
    fisicas = texto[:-2].split("\r\n")
    for linea in fisicas:
        assert "\n" not in linea and "\r" not in linea
        assert len(linea.encode("utf-8")) <= 75, linea
    logicas: list[str] = []
    for linea in fisicas:
        if linea.startswith(" "):
            logicas[-1] += linea[1:]
        else:
            logicas.append(linea)
    return logicas


def componentes(lineas: list[str]) -> list[dict[str, str]]:
    """Propiedades de cada VEVENT (nombre con parámetros -> valor), comprobando el anidamiento."""
    assert lineas[0] == "BEGIN:VCALENDAR" and lineas[-1] == "END:VCALENDAR"
    eventos, actual = [], None
    for linea in lineas[1:-1]:
        nombre, _, valor = linea.partition(":")
        assert nombre and _ == ":", linea
        if linea == "BEGIN:VEVENT":
            assert actual is None
            actual = {}
        elif linea == "END:VEVENT":
            eventos.append(actual)
            actual = None
        elif actual is not None:
            actual[nombre] = valor
    assert actual is None
    return eventos


def desescapar(valor: str) -> str:
    salida, i = [], 0
    while i < len(valor):
        if valor[i] == "\\":
            siguiente = valor[i + 1]
            salida.append("\n" if siguiente in "nN" else siguiente)
            i += 2
        else:
            salida.append(valor[i])
            i += 1
    return "".join(salida)


@pytest.fixture
def api(cliente, db):
    sembrar(db, ahora=VIERNES)
    db.commit()
    return cliente


# --- generación ----------------------------------------------------------------------------------


def test_escapar_texto():
    assert escapar("a\\b;c,d\ne\r\nf") == "a\\\\b\\;c\\,d\\ne\\nf"


def test_plegar_a_75_octetos_sin_romper_utf8():
    linea = "DESCRIPTION:" + "Senderismo por la sierra de Velefique, ñandú y café " * 6
    plegada = plegar(linea)
    trozos = plegada.split("\r\n")
    assert len(trozos) > 1
    assert all(len(t.encode("utf-8")) <= 75 for t in trozos)
    assert all(t.startswith(" ") for t in trozos[1:])
    assert trozos[0] + "".join(t[1:] for t in trozos[1:]) == linea
    assert plegar("SUMMARY:corto") == "SUMMARY:corto"


def test_nombre_fichero_ascii():
    assert nombre_fichero("II Ruta Solidaria Sierra de Velefique") == "ii-ruta-solidaria-sierra-de-velefique.ics"
    assert nombre_fichero("¡¡¿?!!") == "evento.ics"


def test_calendario_vacio_es_valido():
    lineas = desplegar(calendario([], dtstamp=VIERNES))
    assert {"VERSION:2.0", "CALSCALE:GREGORIAN"} <= set(lineas)
    assert any(l.startswith("PRODID:") for l in lineas)
    assert componentes(lineas) == []


def test_evento_sin_fin_dura_dos_horas_y_titulo_escapado():
    inicio = datetime(2026, 12, 1, 18, 0, tzinfo=timezone.utc)
    evento = Evento(
        id="00000000-0000-4000-8000-000000000123", titulo="Teatro; humor, y más\\", categoria="cultural",
        etiquetas=[], municipio="Senés", lugar="Plaza", lat=37.1, lon=-2.3, fecha_inicio=inicio,
        estado="publicado", es_gratuito=True, descripcion="Línea 1\nLínea 2",
    )
    (vevent,) = componentes(desplegar(calendario([evento], dtstamp=VIERNES)))
    assert vevent["DTSTART"] == "20261201T180000Z"
    assert vevent["DTEND"] == "20261201T200000Z"
    assert vevent["DTSTAMP"] == "20261120T180000Z"
    assert vevent["SUMMARY"] == "Teatro\\; humor\\, y más\\\\"
    assert desescapar(vevent["SUMMARY"]) == "Teatro; humor, y más\\"
    assert desescapar(vevent["DESCRIPTION"]) == "Línea 1\nLínea 2\n\nGratuito"
    assert desescapar(vevent["LOCATION"]) == "Plaza, Senés"


def test_evento_sin_hora_es_de_dia_completo_en_fecha_de_madrid():
    # 00:00 en Madrid = 23:00 UTC del día anterior: el día que vale es el de Madrid.
    inicio = datetime(2027, 1, 4, 23, 0, tzinfo=timezone.utc)
    evento = Evento(
        id="00000000-0000-4000-8000-000000000124", titulo="Cabalgata", categoria="fiestas",
        etiquetas=["navidad", "sin_hora"], municipio="Tahal", lat=37.2, lon=-2.2, fecha_inicio=inicio,
        fecha_fin=inicio + timedelta(days=1, hours=23), estado="cancelado",
    )
    (vevent,) = componentes(desplegar(calendario([evento], dtstamp=VIERNES)))
    assert vevent["DTSTART;VALUE=DATE"] == "20270105"
    assert vevent["DTEND;VALUE=DATE"] == "20270107"
    assert vevent["STATUS"] == "CANCELLED"
    assert "DTSTART" not in vevent


# --- GET /eventos/{id}/ics -----------------------------------------------------------------------


def test_ics_de_la_ruta_solidaria(api):
    r = api.get(f"/api/v1/eventos/{RUTA}/ics")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "text/calendar; charset=utf-8"
    disposicion = r.headers["content-disposition"]
    assert disposicion.startswith("attachment;") and ".ics" in disposicion
    assert "ii-ruta-solidaria" in disposicion

    (vevent,) = componentes(desplegar(r.content.decode("utf-8")))
    assert vevent["UID"] == f"{RUTA}@hackemate"
    # 29 nov 09:00-14:00 en Madrid (+01:00) = 08:00-13:00 UTC
    assert vevent["DTSTART"] == "20261129T080000Z"
    assert vevent["DTEND"] == "20261129T130000Z"
    assert desescapar(vevent["SUMMARY"]) == "II Ruta Solidaria Sierra de Velefique"
    assert desescapar(vevent["LOCATION"]).endswith(", Velefique")
    assert vevent["DTSTAMP"].endswith("Z")
    assert "DESCRIPTION" in vevent


def test_ics_uid_estable(api):
    a = api.get(f"/api/v1/eventos/{RUTA}/ics").content.decode()
    b = api.get(f"/api/v1/eventos/{RUTA}/ics").content.decode()
    assert componentes(desplegar(a))[0]["UID"] == componentes(desplegar(b))[0]["UID"]


@pytest.mark.parametrize("id_", ["no-es-uuid", "00000000-0000-4000-8000-000000000000", GRAFITI_EN_REVISION])
def test_ics_evento_no_visible_404(api, id_):
    _error(api.get(f"/api/v1/eventos/{id_}/ics"), 404, "evento_no_encontrado")


def test_ics_en_revision_visible_para_el_bot(api):
    assert api.get(f"/api/v1/eventos/{GRAFITI_EN_REVISION}/ics", headers=TOKEN).status_code == 200


# --- GET /usuarios/me/ics ------------------------------------------------------------------------


def test_mis_eventos_sin_sesion_401(api):
    _error(api.get("/api/v1/usuarios/me/ics"), 401, "no_autenticado")
    _error(api.get("/api/v1/usuarios/me/ics", headers=TOKEN), 401, "no_autenticado")


def test_mis_eventos_solo_confirmados(api, db):
    # Seed: José confirmado en la Ruta, en lista de espera en el taller y cancelado en el torneo;
    # Carmen sin inscripciones (se apunta en el paso 4 del guion).
    r = api.get("/api/v1/usuarios/me/ics", headers=_bearer(JOSE))
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "text/calendar; charset=utf-8"
    assert "mis-eventos.ics" in r.headers["content-disposition"]
    assert [v["UID"] for v in componentes(desplegar(r.text))] == [f"{RUTA}@hackemate"]

    r = api.get("/api/v1/usuarios/me/ics", headers=_bearer(CARMEN))
    assert r.status_code == 200
    assert componentes(desplegar(r.text)) == []


def test_mis_eventos_excluye_eventos_no_visibles(api, db):
    db.add(Inscripcion(evento_id=GRAFITI_EN_REVISION, usuario_id=JOSE, estado="confirmada"))
    db.commit()
    r = api.get("/api/v1/usuarios/me/ics", headers=_bearer(JOSE))
    assert [v["UID"] for v in componentes(desplegar(r.text))] == [f"{RUTA}@hackemate"]
