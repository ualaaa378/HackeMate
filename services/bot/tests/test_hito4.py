"""Hito 4: respuestas en audio, otros idiomas y caída simulada de la IA para la demo."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app import canales, conversacion, telegram, vecino
from app.agentes import idiomas, medios, preferencias, voz
from app.llm import router
from app.main import app
from app.schemas import FichaLLM, MensajeEntrante

cliente = TestClient(app)
CAB = {"X-Internal-Token": "test"}


def _msg(texto="", de="+34600000201", **kw):
    return MensajeEntrante(canal=kw.pop("canal", "whatsapp"), de=de, texto=texto, **kw)


def _voces():
    return [m for m in canales.bandeja_consola if m.get("voz")]


# ---------- Voz ----------

def test_texto_para_voz_quita_lo_que_no_se_lee():
    t = voz.texto_para_voz(["📌 *Ruta por la sierra*\n📅 28/11 a las 10:00\n💶 5 €\n\n🔗 http://x.es/evento/1",
                            "✅ ¡Apuntado!"])
    assert "http" not in t and "*" not in t and "📌" not in t
    assert "28 del 11 a las 10:00" in t and "5  euros" not in t and "5 euros" in t
    assert t.endswith("¡Apuntado!")


def test_sintetizar_convierte_el_wav_a_ogg(monkeypatch):
    monkeypatch.setenv("FREELLM_API_KEY", "k")
    from app.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setattr(httpx, "post", lambda url, **kw: httpx.Response(
        200, content=b"RIFF....WAVE", request=httpx.Request("POST", url)))
    monkeypatch.setattr(voz, "_a_ogg", lambda wav: b"OggS-convertido")
    assert voz.sintetizar("hola") == b"OggS-convertido"


def test_sin_clave_o_con_caida_no_hay_voz(monkeypatch):
    assert voz.sintetizar("hola") is None  # sin FREELLM_API_KEY
    monkeypatch.setenv("FREELLM_API_KEY", "k")
    from app.config import get_settings
    get_settings.cache_clear()
    router.forzar_caida(True)
    assert voz.sintetizar("hola") is None


def test_quien_escribe_con_audio_recibe_audio(api, monkeypatch):
    monkeypatch.setattr(telegram, "descargar_archivo", lambda fid: b"OGG")
    monkeypatch.setattr(medios, "transcribir", lambda d, m: "hola")
    monkeypatch.setattr(voz, "sintetizar", lambda texto: b"OggS" if texto else None)
    conversacion.procesar(_msg(media_id="V", media_tipo="audio/ogg"))
    assert len(_voces()) == 1


def test_texto_normal_no_lleva_audio_salvo_que_lo_pida(api, monkeypatch):
    monkeypatch.setattr(voz, "sintetizar", lambda texto: b"OggS")
    conversacion.procesar(_msg("hola"))
    assert _voces() == []
    vecino.preferencias_locales["+34600000201"] = preferencias.Preferencias(formato_aviso="audio")
    conversacion.procesar(_msg("hola"))
    assert len(_voces()) == 1


def test_simulador_nunca_manda_audio(monkeypatch):
    monkeypatch.setattr(voz, "sintetizar", lambda texto: pytest.fail("el simulador no genera audio"))
    vecino.preferencias_locales["+34600000000"] = preferencias.Preferencias(formato_aviso="audio")
    assert cliente.post("/dev/mensaje", json={"texto": "hola"}).status_code == 200


def test_notify_en_audio(monkeypatch):
    monkeypatch.setattr(voz, "sintetizar", lambda texto: b"OggS")
    cliente.post("/notify", headers=CAB, json={"telefono": "+34600000201", "tipo": "cambio_evento",
                                               "texto": "La ruta pasa a las 11:00", "formato": "audio"})
    assert canales.bandeja_consola[-2]["texto"] == "La ruta pasa a las 11:00" and len(_voces()) == 1


def test_telegram_envia_nota_de_voz(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "123:abc")
    from app.config import get_settings
    get_settings.cache_clear()
    enviados = []

    def post(url, data=None, files=None, timeout=None, **kw):
        enviados.append((url.rsplit("/", 1)[1], data, files["voice"][2]))
        return httpx.Response(200, json={"ok": True}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    assert canales.enviar_voz("tg:5", b"OggS") is True
    assert enviados == [("sendVoice", {"chat_id": "5"}, "audio/ogg")]


# ---------- Idiomas ----------

@pytest.mark.parametrize("texto,idioma", [
    ("What events are there this weekend near me?", "en"),
    ("Bonjour, qu'est-ce qu'il y a ce week-end?", "fr"),
    ("¿Qué hay este finde en Senés?", "es"),
    ("hola", None),
])
def test_detectar_idioma(texto, idioma):
    assert idiomas.detectar(texto) == idioma


def test_visitante_en_ingles(api, monkeypatch):
    llamadas = []

    def traducir(textos, idioma, origen="es"):
        llamadas.append((list(textos), idioma))
        if idioma == "es":
            return ["¿qué hay este mes?"]
        return [f"[EN] {t}" for t in textos]

    monkeypatch.setattr(idiomas, "traducir", traducir)
    api.caida = False
    api.agenda = []
    r = conversacion.procesar(_msg("What events are there this month?", de="tg:44", canal="telegram"))
    assert llamadas[0] == (["What events are there this month?"], "es")
    assert all(x.startswith("[EN]") for x in r)
    # Sigue en inglés aunque el siguiente mensaje sea un botón
    conversacion.procesar(_msg("", de="tg:44", canal="telegram", boton_id="info:x"))
    assert llamadas[-1][1] == "en"


def test_traducir_sin_ia_devuelve_el_original():
    assert idiomas.traducir(["Hola"], "en") == ["Hola"]


# ---------- Caída simulada ----------

def test_interruptor_de_caida(monkeypatch):
    assert cliente.post("/admin/simular-caida", json={"activa": True}).status_code == 401
    assert cliente.post("/admin/simular-caida", json={"activa": True}, headers=CAB).json() == {"activa": True}
    assert cliente.get("/metrics").json()["caida_simulada"] is True

    class _IA:
        nombre, modelo = "freellm", "x"

        def disponible(self):
            return True

        def estructurado(self, *a):
            pytest.fail("con la caída activa no se llama a la IA")

    monkeypatch.setattr(router, "construir", lambda n: _IA())
    res = router.estructurado("t", "s", "x", FichaLLM, reglas=lambda t: FichaLLM(es_evento=False))
    assert res.proveedor == "reglas" and any("caída simulada" in i for i in res.intentos)

    assert cliente.post("/admin/simular-caida", json={"activa": False}, headers=CAB).json() == {"activa": False}


def test_traducir_al_espanol_si_llama_a_la_ia(monkeypatch):
    llamado = []
    monkeypatch.setattr(router, "estructurado",
                        lambda **kw: llamado.append(kw["texto"]) or router.Resultado(
                            salida=idiomas._Traduccion(textos=["¿Qué hay?"]), proveedor="freellm:x"))
    assert idiomas.traducir(["What's on?"], "es", origen="en") == ["¿Qué hay?"]
    assert "español" in llamado[0]
