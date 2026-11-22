import httpx
import pytest

from app.llm import proveedores
from app.llm.proveedores import ErrorProveedor, FreeLLM
from app.schemas import FichaLLM


def _falso_post(contenido: str, capturado: dict):
    def post(url, json, headers, timeout):
        capturado.update(url=url, cuerpo=json, headers=headers)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": contenido}}],
                  "usage": {"prompt_tokens": 50, "completion_tokens": 10}},
            headers={"X-Routed-Via": "groq/llama-3.3-70b"},
            request=httpx.Request("POST", url),
        )
    return post


@pytest.fixture
def freellm(monkeypatch):
    monkeypatch.setenv("FREELLM_API_KEY", "freellmapi-test")
    from app.config import get_settings
    get_settings.cache_clear()
    return FreeLLM()


def test_freellm_lee_json_aunque_venga_en_markdown(monkeypatch, freellm):
    capturado = {}
    contenido = '```json\n{"es_evento": true, "titulo": "Ruta", "municipio": "Senés"}\n```'
    monkeypatch.setattr(httpx, "post", _falso_post(contenido, capturado))
    obj, t_in, t_out = freellm.estructurado("sistema", "texto", FichaLLM)
    assert obj.titulo == "Ruta" and obj.municipio == "Senés"
    assert (t_in, t_out) == (50, 10)
    assert freellm.modelo == "groq/llama-3.3-70b"
    assert capturado["url"] == "http://freellm.test/v1/chat/completions"
    assert capturado["headers"]["Authorization"] == "Bearer freellmapi-test"
    assert capturado["cuerpo"]["response_format"] == {"type": "json_object"}


def test_freellm_json_invalido_es_error_de_proveedor(monkeypatch, freellm):
    monkeypatch.setattr(httpx, "post", _falso_post("no es json", {}))
    with pytest.raises(ErrorProveedor):
        freellm.estructurado("s", "t", FichaLLM)


def test_freellm_sin_clave_no_esta_disponible():
    assert not proveedores.construir("freellm").disponible()


def test_freellm_pasa_al_siguiente_modelo_si_uno_se_cuelga(monkeypatch, freellm):
    llamadas = []
    bueno = _falso_post('{"es_evento": false}', {})

    def post(url, json, headers, timeout):
        llamadas.append((json["model"], timeout))
        if len(llamadas) == 1:
            raise httpx.ReadTimeout("colgado")
        return bueno(url, json, headers, timeout)

    monkeypatch.setattr(httpx, "post", post)
    obj, _, _ = freellm.estructurado("s", "t", FichaLLM)
    assert obj.es_evento is False
    assert [m for m, _ in llamadas] == freellm.modelos[:2]
    assert llamadas[0][1] == freellm.timeout_intento


def test_freellm_todos_fallan_es_error_de_proveedor(monkeypatch, freellm):
    def post(url, json, headers, timeout):
        raise httpx.ReadTimeout("colgado")

    monkeypatch.setattr(httpx, "post", post)
    with pytest.raises(ErrorProveedor, match="ReadTimeout"):
        freellm.estructurado("s", "t", FichaLLM)


# ---------- NVIDIA NIM (B2) ----------

@pytest.fixture
def nim(monkeypatch):
    monkeypatch.setenv("NIM_API_KEY", "nvapi-test")
    from app.config import get_settings
    get_settings.cache_clear()
    return proveedores.Nim()


def test_nim_es_compatible_openai_sin_response_format(monkeypatch, nim):
    capturado = {}
    monkeypatch.setattr(httpx, "post", _falso_post('{"es_evento": true, "titulo": "Taller de esparto"}', capturado))
    obj, t_in, t_out = nim.estructurado("sistema", "texto", FichaLLM)
    assert obj.titulo == "Taller de esparto" and (t_in, t_out) == (50, 10)
    assert capturado["url"] == "http://nim.test/v1/chat/completions"
    assert capturado["headers"]["Authorization"] == "Bearer nvapi-test"
    assert capturado["cuerpo"]["model"] == "nvidia/nemotron-3.5-bolt-e4b"
    assert "response_format" not in capturado["cuerpo"]  # no todos los modelos de NIM lo aceptan


def test_nim_sin_clave_no_esta_disponible():
    assert proveedores.construir("nim").disponible() is False  # conftest: NIM_API_KEY vacía


def test_cadena_por_defecto_nim_antes_que_freellm(monkeypatch):
    monkeypatch.delenv("LLM_CADENA", raising=False)
    from app.config import Settings
    assert Settings(_env_file=None).proveedores == ["gemini", "nim", "freellm", "claude", "reglas"]


def test_si_nim_falla_pasa_a_freellm(monkeypatch):
    """Router: NIM caído → FreeLLM responde, y las métricas apuntan el fallo de NIM."""
    from app import metrics
    from app.config import get_settings
    from app.llm import router
    monkeypatch.setenv("NIM_API_KEY", "nvapi-test")
    monkeypatch.setenv("FREELLM_API_KEY", "freellmapi-test")
    monkeypatch.setenv("LLM_CADENA", "nim,freellm,reglas")
    get_settings.cache_clear()

    def post(url, json, headers, timeout):
        if "nim.test" in url:
            raise httpx.ConnectError("NIM caído")
        return _falso_post('{"es_evento": true, "titulo": "Desde FreeLLM"}', {})(url, json, headers, timeout)
    monkeypatch.setattr(httpx, "post", post)
    res = router.estructurado("t", "s", "x", FichaLLM, reglas=lambda t: FichaLLM(es_evento=False))
    assert res.proveedor.startswith("freellm") and res.salida.titulo == "Desde FreeLLM"
    assert any(u["proveedor"] == "nim" and not u["ok"] for u in metrics.resumen()["ultimas"])
