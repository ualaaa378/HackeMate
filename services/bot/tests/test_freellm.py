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
