from datetime import date
from zoneinfo import ZoneInfo

from app.agentes import extractor
from app.llm import router
from app.schemas import FichaLLM

TZ = ZoneInfo("Europe/Madrid")
HOY = date(2026, 11, 20)

POST = """II Ruta Solidaria Sierra de Velefique
El domingo 30 de noviembre a las 9:00 salimos desde la plaza.
12 km de senderismo. Inscripción 5 euros, 40 plazas."""


def test_reglas_extraen_ficha_de_un_post():
    f = extractor.extraer_con_reglas(POST, HOY, TZ)
    assert f.es_evento
    assert f.titulo == "II Ruta Solidaria Sierra de Velefique"
    assert f.municipio == "Velefique"
    assert f.categoria == "deportiva"
    assert f.fecha_inicio == "2026-11-30T09:00:00+01:00"
    assert f.precio_eur == 5.0 and f.es_gratuito is False
    assert f.plazas_totales == 40


def test_reglas_fecha_sin_ano_pasada_va_al_ano_siguiente():
    f = extractor.extraer_con_reglas("Fiesta el 6 de enero a las 8 de la tarde", HOY, TZ)
    assert f.fecha_inicio == "2027-01-06T20:00:00+01:00"
    assert f.categoria == "fiestas"


def test_reglas_no_es_evento():
    assert not extractor.extraer_con_reglas("hola buenas", HOY, TZ).es_evento


def test_extraer_sin_claves_usa_reglas_y_marca_lo_que_falta():
    ex = extractor.extraer("Migas gratis en la plaza de Senés el 13 de diciembre", hoy=HOY)
    assert ex.proveedor_ia == "reglas"
    assert ex.campos["municipio"].valor == "Senés"
    assert ex.campos["categoria"].confianza == "media"  # deducida, no explícita
    assert ex.campos["es_gratuito"].valor is True
    assert "precio_eur" not in ex.faltan
    assert "lugar" in ex.faltan


class _Falla:
    nombre, modelo = "claude", "falso"

    def disponible(self):
        return True

    def estructurado(self, *a):
        from app.llm.proveedores import ErrorProveedor
        raise ErrorProveedor("claude: timeout")


class _Funciona:
    nombre, modelo = "gemini", "falso"

    def disponible(self):
        return True

    def estructurado(self, system, texto, salida):
        return salida(es_evento=True, titulo="Desde Gemini"), 100, 20


def test_router_pasa_al_siguiente_proveedor(monkeypatch):
    monkeypatch.setenv("LLM_CADENA", "claude,gemini,reglas")
    monkeypatch.setattr(router, "construir", lambda n: {"claude": _Falla(), "gemini": _Funciona()}.get(n))
    res = router.estructurado("t", "s", "x", FichaLLM, reglas=lambda t: FichaLLM(es_evento=False))
    assert res.proveedor == "gemini:falso"
    assert res.salida.titulo == "Desde Gemini"
    assert res.tokens_entrada == 100
    assert res.intentos == ["claude: timeout"]


def test_router_caida_simulada_acaba_en_reglas(monkeypatch):
    monkeypatch.setenv("LLM_SIMULAR_CAIDA", "true")
    monkeypatch.setenv("LLM_CADENA", "claude,gemini,reglas")
    monkeypatch.setattr(router, "construir", lambda n: {"claude": _Funciona(), "gemini": _Funciona()}.get(n))
    res = router.estructurado("t", "s", "x", FichaLLM, reglas=lambda t: FichaLLM(es_evento=False, titulo="reglas"))
    assert res.proveedor == "reglas"
    assert len(res.intentos) == 2


def test_reglas_hora_con_h_y_polideportivo_no_es_deporte():
    f = extractor.extraer_con_reglas(
        "Mañana sábado a partir de las 13h migas en el polideportivo de Senés, gratis", HOY, TZ)
    assert f.fecha_inicio == "2026-11-21T13:00:00+01:00"
    assert f.categoria == "gastronomia"


def test_ficha_tolera_salidas_algo_raras_de_modelos_gratuitos():
    f = FichaLLM.model_validate_json(
        '{"es_evento": true, "categoria": "Gastronomía", "precio_eur": "9€", '
        '"plazas_totales": "40 plazas", "campos_dudosos": null}')
    assert f.categoria == "gastronomia" and f.precio_eur == 9.0 and f.plazas_totales == 40
    assert f.campos_dudosos == []
    assert FichaLLM.model_validate_json('{"es_evento": true, "categoria": "otra"}').categoria is None
