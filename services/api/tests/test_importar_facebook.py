"""scripts/importar_facebook.py (A2): lo que hace sin red, con las llamadas HTTP simuladas."""

import importlib.util
import json
from pathlib import Path

import pytest

RUTA = Path(__file__).resolve().parents[3] / "scripts" / "importar_facebook.py"
_spec = importlib.util.spec_from_file_location("importar_facebook", RUTA)
fb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fb)

PAGINA = {"url": "https://www.facebook.com/AytoUleila", "publicador_id": "pub-1", "publicador": "Ayto. Uleila"}
POST = {
    "url": "https://www.facebook.com/AytoUleila/posts/1",
    "pagina_url": PAGINA["url"],
    "pagina": "Ayuntamiento de Uleila del Campo",
    "publicador_id": "pub-1",
    "fecha": "2026-11-18T10:00:00.000Z",
    "texto": "Ruta de la tapa el sábado 28 de noviembre a las 13:00",
    "texto_fotos": ["RUTA DE LA TAPA"],
}
EXTRACCION = {"campos": {}, "faltan": [], "es_evento": True, "proveedor_ia": "reglas"}


def test_url_local_cambia_los_nombres_de_docker():
    assert fb.url_local("http://api:8000", "x") == "http://localhost:8000"
    assert fb.url_local("http://bot:8001/", "x") == "http://localhost:8001"
    assert fb.url_local("https://api.ejemplo.org", "x") == "https://api.ejemplo.org"
    assert fb.url_local(None, "http://localhost:8000") == "http://localhost:8000"


def test_leer_env_el_entorno_manda(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# comentario\nFB_MAX_POSTS=5\nFB_DESDE='7 days'\nINTERNAL_TOKEN=del-fichero\n", encoding="utf-8")
    monkeypatch.setenv("INTERNAL_TOKEN", "del-entorno")
    valores = fb.leer_env(env)
    assert valores["FB_MAX_POSTS"] == "5" and valores["FB_DESDE"] == "7 days"
    assert valores["INTERNAL_TOKEN"] == "del-entorno"


def test_unir_paginas_sin_repetir():
    unidas = fb.unir_paginas([PAGINA], [PAGINA["url"] + "/", " https://www.facebook.com/Senes ", ""])
    assert [p["url"] for p in unidas] == [PAGINA["url"], "https://www.facebook.com/Senes"]
    assert unidas[0]["publicador_id"] == "pub-1" and unidas[1]["publicador_id"] is None


def test_resumir_post_guarda_solo_lo_necesario():
    item = {
        "url": POST["url"], "inputUrl": PAGINA["url"] + "/", "pageName": "Ayuntamiento de Uleila del Campo",
        "time": POST["fecha"], "text": POST["texto"], "likes": 30,
        "user": {"id": "1", "name": "Ayuntamiento de Uleila del Campo", "profilePic": "https://…"},
        "media": [{"ocrText": "RUTA DE LA TAPA", "url": "https://…"}, {"url": "sin texto"}],
    }
    assert fb.resumir_post(item, [PAGINA]) == POST
    # Sin URL, o sin texto ni cartel: no sirve.
    assert fb.resumir_post({"text": "hola"}, [PAGINA]) is None
    assert fb.resumir_post({"url": POST["url"], "text": "  "}, [PAGINA]) is None
    # Solo cartel y página sin alta: se guarda sin asociación.
    solo_foto = fb.resumir_post({"url": "https://www.facebook.com/otra/posts/2", "media": [{"ocrText": "FIESTA"}]}, [PAGINA])
    assert solo_foto["texto_fotos"] == ["FIESTA"] and solo_foto["publicador_id"] is None


def test_nombre_de_pagina_legible():
    assert fb.nombre_pagina("Ayuntamiento-de-Sen%C3%A9s") == "Ayuntamiento de Senés"
    assert fb.nombre_pagina("Ayuntamiento de Uleila del Campo") == "Ayuntamiento de Uleila del Campo"
    assert fb.nombre_pagina(None) is None


def test_texto_para_ia_deja_la_fecha_de_publicacion_al_final():
    texto = fb.texto_para_ia(POST)
    assert texto.startswith(POST["texto"])
    assert "Texto del cartel: RUTA DE LA TAPA" in texto
    assert texto.endswith("(Publicado en Facebook por Ayuntamiento de Uleila del Campo el 2026-11-18)")


def test_guardar_y_cargar_junta_por_url(tmp_path):
    ruta = tmp_path / "posts.json"
    fb.guardar_posts([POST], [PAGINA], ruta)
    otro = {**POST, "url": POST["url"].replace("/1", "/2"), "fecha": "2026-11-19T10:00:00.000Z"}
    fb.guardar_posts([otro, {**POST, "texto": "editado"}], [PAGINA], ruta)
    posts = fb.cargar_posts(ruta)
    assert [p["url"] for p in posts] == [otro["url"], POST["url"]]  # el más reciente primero
    assert posts[1]["texto"] == "editado"
    assert json.loads(ruta.read_text(encoding="utf-8"))["paginas"] == [PAGINA["url"]]


class _Http:
    """Sustituye a `peticion`: responde según la URL y guarda lo que se envió."""

    def __init__(self, respuestas):
        self.respuestas = respuestas
        self.llamadas = []

    def __call__(self, metodo, url, cuerpo=None, cabeceras=None, timeout=None):
        self.llamadas.append((metodo, url, cuerpo, cabeceras))
        for trozo, respuesta in self.respuestas.items():
            if trozo in url:
                if isinstance(respuesta, Exception):
                    raise respuesta
                return respuesta
        raise AssertionError(f"URL inesperada {url}")


def _evento(estado="pendiente_confirmacion", motivo=None):
    return {"id": "ev-1", "titulo": "Ruta de la tapa", "estado": estado, "moderacion": {"motivo": motivo}}


def _procesar(monkeypatch, respuestas, confirmar=True):
    http = _Http(respuestas)
    monkeypatch.setattr(fb, "peticion", http)
    return fb.procesar_post(POST, "http://api", "http://bot", "tok", confirmar), http


def test_post_que_no_es_evento_no_llega_a_la_api(monkeypatch):
    r, http = _procesar(monkeypatch, {"/ai/extraer": (200, {**EXTRACCION, "es_evento": False})})
    assert r["resultado"] == "no_es_evento"
    assert len(http.llamadas) == 1


def test_bot_caido_no_inventa_nada(monkeypatch):
    r, http = _procesar(monkeypatch, {"/ai/extraer": fb.ErrorHttp(None, None, "sin respuesta")})
    assert r["resultado"] == "error" and r["paso"] == "bot /ai/extraer"
    assert len(http.llamadas) == 1


def test_importa_con_origen_facebook_y_confirma(monkeypatch):
    r, http = _procesar(monkeypatch, {
        "/ai/extraer": (200, EXTRACCION),
        "/eventos/importar": (201, {"evento": _evento(), "faltan": [], "duplicado": False}),
        "/confirmar": (200, {"evento": _evento("en_revision", "Publicación a mano: la revisa el moderador")}),
    })
    assert r == {"resultado": "en_revision", "estado": "en_revision", "evento_id": "ev-1", "titulo": "Ruta de la tapa",
                 "motivo": "Publicación a mano: la revisa el moderador", "proveedor_ia": "reglas"}
    _, url, cuerpo, cabeceras = http.llamadas[1]
    assert url == "http://api/api/v1/eventos/importar" and cabeceras == {"X-Internal-Token": "tok"}
    assert cuerpo["origen"] == {"canal": "facebook", "url": POST["url"], "importado_auto": True}
    assert cuerpo["publicador_id"] == "pub-1"
    assert http.llamadas[2][1] == "http://api/api/v1/eventos/ev-1/confirmar"


def test_duplicado_no_se_vuelve_a_confirmar(monkeypatch):
    r, http = _procesar(monkeypatch, {
        "/ai/extraer": (200, EXTRACCION),
        "/eventos/importar": (200, {"evento": _evento("publicado"), "faltan": [], "duplicado": True}),
    })
    assert r["resultado"] == "duplicado" and len(http.llamadas) == 2


def test_sin_fecha_se_queda_pendiente(monkeypatch):
    error = fb.ErrorHttp(422, {"error": {"code": "faltan_campos", "message": "…", "details": {"faltan": ["fecha_inicio"]}}})
    r, _ = _procesar(monkeypatch, {
        "/ai/extraer": (200, EXTRACCION),
        "/eventos/importar": (201, {"evento": _evento(), "faltan": ["fecha_inicio"], "duplicado": False}),
        "/confirmar": error,
    })
    assert r["resultado"] == "pendiente" and r["faltan"] == ["fecha_inicio"]


def test_sin_confirmar_solo_importa(monkeypatch):
    r, http = _procesar(monkeypatch, {
        "/ai/extraer": (200, EXTRACCION),
        "/eventos/importar": (201, {"evento": _evento(), "faltan": [], "duplicado": False}),
    }, confirmar=False)
    assert r["resultado"] == "creado" and len(http.llamadas) == 2


def test_sin_token_y_sin_json_avisa(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(fb, "leer_env", lambda: {})
    assert fb.main([]) == 2
    assert fb.main(["--desde-json", "--json", str(tmp_path / "no-existe.json")]) == 2
    assert "FB_SCRAPER_TOKEN" in capsys.readouterr().err


@pytest.mark.parametrize("args", [["--desde-json"]])
def test_desde_json_procesa_los_guardados(monkeypatch, tmp_path, args, capsys):
    ruta = tmp_path / "posts.json"
    fb.guardar_posts([POST], [PAGINA], ruta)
    monkeypatch.setattr(fb, "leer_env", lambda: {"INTERNAL_TOKEN": "tok"})
    monkeypatch.setattr(fb, "procesar_post", lambda post, *a, **k: {"resultado": "en_revision", "titulo": post["url"]})
    assert fb.main(args + ["--json", str(ruta)]) == 0
    assert "en_revision 1" in capsys.readouterr().out
