"""Núcleo de moderación (H2.4): antispam, niveles de confianza y decisión de estado."""

import json
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from app import moderacion
from app.config import get_settings
from app.modelos import Evento, Municipio, Publicador

TEXTO_APUESTAS = "¡¡GANA DINERO con nuestras APUESTAS deportivas!! Entra en bit.ly/xxx"
TEXTO_NORMAL = "Ruta solidaria por la Sierra de los Filabres, salida a las 9 desde la plaza"


FIXTURES = Path(__file__).resolve().parents[3] / "contracts" / "fixtures"


@pytest.fixture(autouse=True)
def _circuito_limpio():
    moderacion.reiniciar_circuito_spam()
    yield
    moderacion.reiniciar_circuito_spam()


@pytest.fixture
def ajustes(monkeypatch):
    """Permite fijar variables de entorno y deja la configuración limpia al acabar."""

    def fijar(**variables):
        for k, v in variables.items():
            monkeypatch.setenv(k, str(v))
        get_settings.cache_clear()

    get_settings.cache_clear()
    yield fijar
    get_settings.cache_clear()


@pytest.fixture
def base(db):
    db.add(Municipio(nombre="Senés", lat=37.19, lon=-2.35))
    db.commit()
    return db


def _publicador(db, nivel=0, **extra) -> Publicador:
    p = Publicador(nombre="Bar La Plaza", tipo="bar_restaurante", municipio="Senés",
                   estado="aprobado", nivel_confianza=nivel, **extra)
    db.add(p)
    db.commit()
    return p


def _evento(db, publicador=None, categoria="gastronomia", estado="pendiente_confirmacion", **extra) -> Evento:
    e = Evento(titulo="Menú del domingo", categoria=categoria, municipio="Senés", lat=37.19, lon=-2.35,
               fecha_inicio=datetime.now(timezone.utc) + timedelta(days=3), estado=estado,
               publicador_id=publicador.id if publicador else None, **extra)
    db.add(e)
    db.commit()
    return e


def _puerto_cerrado() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# --- reglas locales ---------------------------------------------------------

def test_reglas_apuestas_es_spam():
    score, razones = moderacion.puntuar_spam_reglas(TEXTO_APUESTAS)
    assert score >= 0.7
    texto = " ".join(razones)
    assert "apuesta" in texto and "bit.ly" in texto and "MAYÚSCULAS" in texto


def test_reglas_evento_normal_no_es_spam():
    score, razones = moderacion.puntuar_spam_reglas(TEXTO_NORMAL)
    assert score < 0.3 and razones == []


def _texto(evento: dict) -> str:
    # Igual que confirmar_evento: título y descripción.
    return "\n".join(t for t in (evento["titulo"], evento.get("descripcion")) if t)


def _eventos_fixture() -> list[dict]:
    return [e for f in ("eventos.json", "eventos_demo.json")
            for e in json.loads((FIXTURES / f).read_text(encoding="utf-8"))]


def test_reglas_apuestas_de_la_demo_es_spam():
    spam = next(e for e in _eventos_fixture() if e["id"] == "1e5d0000-0000-4000-8000-000000000010")
    score, razones = moderacion.puntuar_spam_reglas(_texto(spam))
    assert score >= 0.7, razones
    assert "apuesta" in " ".join(razones)


def test_reglas_publicados_de_los_fixtures_no_son_spam():
    publicados = [e for e in _eventos_fixture() if e["estado"] == "publicado"]
    assert any(e["titulo"] == "II Ruta Solidaria Sierra de Velefique" for e in publicados)
    altos = {e["titulo"]: moderacion.puntuar_spam_reglas(_texto(e)) for e in publicados}
    altos = {t: r for t, r in altos.items() if r[0] >= 0.3}
    assert not altos


@pytest.mark.parametrize("texto, minimo", [
    ("Apuestas del partido en el bar", 0.5),
    ("Gana 500 € esta noche", 0.4),
    ("Te damos 100 euros garantizados", 0.7),
    ("Cuotas altísimas y código promocional", 0.7),
    ("Duplica tu dinero con nuestras ganancias", 0.7),
])
def test_reglas_reforzadas(texto, minimo):
    assert moderacion.puntuar_spam_reglas(texto)[0] >= minimo


def test_reglas_texto_vacio():
    assert moderacion.puntuar_spam_reglas("") == (0.0, [])
    assert moderacion.puntuar_spam_reglas(None) == (0.0, [])


# --- clasificar_spam ---------------------------------------------------------

def test_clasificar_con_bot_caido_usa_reglas(ajustes):
    ajustes(BOT_URL=f"http://127.0.0.1:{_puerto_cerrado()}")
    score, motivo = moderacion.clasificar_spam(TEXTO_APUESTAS)
    assert score >= 0.7 and motivo.startswith("reglas")
    score, motivo = moderacion.clasificar_spam(TEXTO_NORMAL)
    assert score < 0.3 and motivo == "reglas: sin indicios"


def test_circuito_tras_un_fallo_no_vuelve_a_llamar(ajustes, monkeypatch):
    ajustes(BOT_URL="http://bot-falso:8001")
    llamadas = []

    def caido(*a, **k):
        llamadas.append(1)
        raise httpx.ConnectError("conexion rechazada")

    monkeypatch.setattr(moderacion.httpx, "post", caido)
    assert moderacion.clasificar_spam(TEXTO_NORMAL)[1].startswith("reglas")
    assert moderacion.clasificar_spam(TEXTO_APUESTAS)[1].startswith("reglas")
    assert len(llamadas) == 1  # el segundo ni lo intenta
    moderacion.reiniciar_circuito_spam()
    moderacion.clasificar_spam(TEXTO_NORMAL)
    assert len(llamadas) == 2


def test_clasificar_sin_bot_url_usa_reglas(ajustes):
    ajustes(BOT_URL="")
    _, motivo = moderacion.clasificar_spam(TEXTO_NORMAL)
    assert motivo.startswith("reglas")


def test_clasificar_con_bot_simulado_usa_ia(ajustes, monkeypatch):
    ajustes(BOT_URL="http://bot-falso:8001", INTERNAL_TOKEN="secreto")
    llamadas = []

    def post_falso(url, json=None, headers=None, timeout=None):
        llamadas.append((url, json, headers, timeout))
        return httpx.Response(200, json={"score_spam": 0.91, "es_spam": True,
                                         "motivo": "promociona apuestas", "proveedor_ia": "gemini"})

    monkeypatch.setattr(moderacion.httpx, "post", post_falso)
    score, motivo = moderacion.clasificar_spam(TEXTO_NORMAL)
    assert score == 0.91
    assert motivo == "IA (gemini): promociona apuestas"
    url, cuerpo, cabeceras, timeout = llamadas[0]
    assert url == "http://bot-falso:8001/ai/spam"
    assert cuerpo["texto"] == TEXTO_NORMAL and cuerpo["contexto"] == "evento"
    assert cabeceras["X-Internal-Token"] == "secreto"
    assert timeout <= 1.5


@pytest.mark.parametrize("respuesta", [
    httpx.Response(404, json={"detail": "Not Found"}),
    httpx.Response(200, json={"score": 0.5}),
    httpx.Response(200, json={"score_spam": 7, "es_spam": True}),
    httpx.Response(200, text="no es json"),
])
def test_clasificar_respuesta_rara_usa_reglas(ajustes, monkeypatch, respuesta):
    ajustes(BOT_URL="http://bot-falso:8001")
    monkeypatch.setattr(moderacion.httpx, "post", lambda *a, **k: respuesta)
    score, motivo = moderacion.clasificar_spam(TEXTO_APUESTAS)
    assert motivo.startswith("reglas") and score >= 0.7


# --- decidir_estado -----------------------------------------------------------

def test_sin_publicador_a_revision(base):
    e = _evento(base)
    assert moderacion.decidir_estado(base, e, None, 0.0) == ("en_revision", "Sin publicador identificado")


def test_automatizaciones_pausadas_e_importado_auto(base):
    p = _publicador(base, nivel=2, automatizaciones_pausadas=True)
    auto = _evento(base, p, importado_auto=True)
    estado, motivo = moderacion.decidir_estado(base, auto, p, 0.0)
    assert estado == "en_revision" and "pausadas" in motivo
    # Publicado a mano por el propio publicador: las automatizaciones pausadas no le afectan
    manual = _evento(base, p, importado_auto=False)
    assert moderacion.decidir_estado(base, manual, p, 0.0)[0] == "publicado"


def test_publicador_pausado_a_revision(base):
    p = _publicador(base, nivel=2)
    p.estado = "pausado"
    assert moderacion.decidir_estado(base, _evento(base, p), p, 0.0) == ("en_revision", "Publicador pausado")


def test_spam_alto_a_revision_aunque_sea_nivel_2(base, ajustes):
    ajustes(BOT_URL="")
    p = _publicador(base, nivel=2)
    e = _evento(base, p)
    score, motivo_spam = moderacion.clasificar_spam(TEXTO_APUESTAS, p)
    estado, motivo = moderacion.decidir_estado(base, e, p, score, motivo_spam)
    assert estado == "en_revision"
    assert motivo.startswith("Posible spam") and "bit.ly" in motivo


def test_nivel_0_a_revision(base):
    p = _publicador(base, nivel=0)
    assert moderacion.decidir_estado(base, _evento(base, p), p, 0.1) == ("en_revision", "Publicador nuevo (nivel 0)")


def test_nivel_1_categoria_habitual_publica(base):
    p = _publicador(base, nivel=1, categorias_habituales=["gastronomia"])
    assert moderacion.decidir_estado(base, _evento(base, p), p, 0.1)[0] == "publicado"


def test_nivel_1_categoria_ya_publicada_publica(base):
    p = _publicador(base, nivel=1)
    _evento(base, p, categoria="deportiva", estado="publicado")
    nuevo = _evento(base, p, categoria="deportiva")
    assert moderacion.decidir_estado(base, nuevo, p, 0.1)[0] == "publicado"


def test_nivel_1_categoria_nueva_a_revision(base):
    p = _publicador(base, nivel=1, categorias_habituales=["gastronomia"])
    _evento(base, p, categoria="cultural", estado="rechazado")  # rechazado no cuenta como habitual
    e = _evento(base, p, categoria="cultural")
    estado, motivo = moderacion.decidir_estado(base, e, p, 0.1)
    assert estado == "en_revision" and motivo.startswith("Categoría fuera de lo habitual")


def test_nivel_2_publica(base):
    p = _publicador(base, nivel=2)
    assert moderacion.decidir_estado(base, _evento(base, p, categoria="ludica"), p, 0.3)[0] == "publicado"
    assert moderacion.decidir_estado(base, _evento(base, p), p, None)[0] == "publicado"


def test_umbral_configurable(base, ajustes):
    ajustes(MODERACION_UMBRAL_SPAM=0.2)
    p = _publicador(base, nivel=2)
    assert moderacion.decidir_estado(base, _evento(base, p), p, 0.3)[0] == "en_revision"


# --- registrar_aprobacion -------------------------------------------------------

def test_tres_aprobaciones_suben_de_0_a_1_y_luego_a_2(base, ajustes):
    ajustes(MODERACION_APROBACIONES_SUBIR_NIVEL=3)
    p = _publicador(base, nivel=0)
    assert [moderacion.registrar_aprobacion(p) for _ in range(3)] == [False, False, True]
    assert p.nivel_confianza == 1 and p.aprobaciones == 3
    assert [moderacion.registrar_aprobacion(p) for _ in range(3)] == [False, False, True]
    assert p.nivel_confianza == 2 and p.aprobaciones == 6
    base.commit()


def test_nivel_2_no_sube_mas(base, ajustes):
    ajustes(MODERACION_APROBACIONES_SUBIR_NIVEL=3)
    p = _publicador(base, nivel=2)
    assert not any(moderacion.registrar_aprobacion(p) for _ in range(6))
    assert p.nivel_confianza == 2 and p.aprobaciones == 6
    base.commit()  # el CHECK de nivel_confianza (0..2) sigue cumpliéndose
