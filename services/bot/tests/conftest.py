import os

import pytest

# Sin claves ni red: los tests usan el plan C (reglas) salvo que simulen un proveedor
os.environ.update({
    "ANTHROPIC_API_KEY": "",
    "GEMINI_API_KEY": "",
    "FREELLM_API_KEY": "",
    "FREELLM_URL": "http://freellm.test/v1",
    "CANAL": "console",
    "META_TOKEN": "",
    "META_PHONE_NUMBER_ID": "",
    "META_APP_SECRET": "",
    "META_VERIFY_TOKEN": "",
    "API_URL": "http://127.0.0.1:9",
    "INTERNAL_TOKEN": "test",
    "LLM_SIMULAR_CAIDA": "false",
})


@pytest.fixture(autouse=True)
def limpiar_estado():
    from app import api_cliente, canales, conversacion
    from app.config import get_settings

    get_settings.cache_clear()
    conversacion.estados.clear()
    canales.bandeja_consola.clear()
    api_cliente.pendientes.clear()
    yield
    get_settings.cache_clear()
