import os
import uuid

import pytest

# Sin claves ni red: los tests usan el plan C (reglas) salvo que simulen un proveedor
os.environ.update({
    "ANTHROPIC_API_KEY": "",
    "GEMINI_API_KEY": "",
    "FREELLM_API_KEY": "",
    "FREELLM_URL": "http://freellm.test/v1",
    "NIM_API_KEY": "",
    "NIM_URL": "http://nim.test/v1",
    "CANAL": "console",
    "META_TOKEN": "",
    "TELEGRAM_TOKEN": "",
    "TELEGRAM_SECRET": "",
    "META_PHONE_NUMBER_ID": "",
    "META_APP_SECRET": "",
    "META_VERIFY_TOKEN": "",
    "API_URL": "http://api.test",
    "INTERNAL_TOKEN": "test",
    "LLM_SIMULAR_CAIDA": "false",
    "COLA_PATH": "",
    "PUBLIC_URL": "",
})


class ApiFalsa:
    """Imita las rutas de la api que usa el bot. Por defecto está caída (como en producción sin api)."""

    def __init__(self):
        self.caida = True
        self.llamadas: list[tuple[str, str, dict | None]] = []
        self.usuarios: dict[str, dict] = {}  # contacto -> usuario
        self.eventos: dict[str, dict] = {}
        self.confirmar_implementado = True
        self.estado_tras_confirmar = "en_revision"
        self.pendientes: list[dict] | None = None  # None = ruta sin implementar (404)
        self.agenda: list[dict] = []  # eventos publicados que devuelve GET /eventos
        self.inscripciones_implementadas = True
        self.lleno = False
        self.recomendaciones: list[dict] | None = None
        self.chat_implementado = False
        self.finalizados: set[str] = set()  # eventos que la api da por terminados (409)

    def __call__(self, metodo, ruta, json=None):
        from app.api_cliente import ApiNoDisponible, ErrorApi

        self.llamadas.append((metodo, ruta, json))
        if self.caida:
            raise ApiNoDisponible("api caída en los tests")
        if metodo == "POST" and ruta == "/api/v1/eventos/importar":
            faltan = [c for c, v in json["extraccion"]["campos"].items()
                      if c in ("titulo", "categoria", "municipio", "fecha_inicio") and v["confianza"] == "falta"]
            ev = {"id": str(uuid.uuid4()), "titulo": "x", "estado": "pendiente_confirmacion"}
            self.eventos[ev["id"]] = ev
            return {"evento": ev, "faltan": faltan, "duplicado": False}
        if ruta.endswith("/confirmar"):
            if not self.confirmar_implementado:
                raise ErrorApi(404, "no_encontrado", "Not Found")
            ev = self.eventos[ruta.split("/")[4]]
            ev["estado"] = self.estado_tras_confirmar
            return {"evento": ev, "faltan": [], "duplicado": False}
        if metodo == "PATCH" and ruta.startswith("/api/v1/eventos/"):
            return self.eventos[ruta.split("/")[4]]
        if ruta.startswith("/api/v1/usuarios/by-contacto/"):
            contacto = ruta.rsplit("/", 1)[1].replace("%2B", "+")
            if contacto in self.usuarios:
                return self.usuarios[contacto]
            raise ErrorApi(404, "usuario_no_encontrado", "No hay ningún usuario con ese contacto")
        if ruta == "/api/v1/usuarios/vincular":
            usuario = {"id": str(uuid.uuid4()), "nombre": json.get("nombre") or "Vecino", "rol": "vecino",
                       "telefono": json["telefono"]}
            self.usuarios[json["contacto"]] = usuario
            return usuario
        if ruta.startswith("/api/v1/moderacion/pendientes"):
            if self.pendientes is None:
                raise ErrorApi(404, "no_encontrado", "Not Found")
            return {"items": self.pendientes, "total": len(self.pendientes), "page": 1, "size": 5}
        if ruta.startswith("/api/v1/moderacion/") and ruta.endswith("/decision"):
            return {"id": ruta.split("/")[4], "titulo": "Fiesta", "estado": "publicado"}
        if metodo == "GET" and ruta.startswith("/api/v1/eventos?"):
            from urllib.parse import parse_qs, urlparse
            q = {k: v[0] for k, v in parse_qs(urlparse(ruta).query).items()}
            items = [e for e in self.agenda
                     if (not q.get("municipio") or e["municipio"] == q["municipio"])
                     and (not q.get("categoria") or e["categoria"] == q["categoria"])
                     and (not q.get("desde") or e["fecha_inicio"] >= q["desde"])
                     and (not q.get("hasta") or e["fecha_inicio"] <= q["hasta"])]
            return {"items": items, "total": len(items), "page": 1, "size": 10}
        if metodo == "GET" and ruta.startswith("/api/v1/eventos/"):
            ev = next((e for e in self.agenda if e["id"] == ruta.split("/")[4]), None)
            if ev is None:
                raise ErrorApi(404, "evento_no_encontrado", "No existe")
            return ev
        if ruta.startswith("/api/v1/recomendaciones"):
            if self.recomendaciones is None:
                raise ErrorApi(404, "no_encontrado", "Not Found")
            return {"items": self.recomendaciones}
        if ruta.endswith("/inscripciones") or ruta.endswith("/mensajes"):
            if ruta.split("/")[4] in self.finalizados:
                raise ErrorApi(409, "evento_finalizado", "El plan ya ha terminado")
        if ruta.endswith("/inscripciones"):
            if not self.inscripciones_implementadas:
                raise ErrorApi(404, "no_encontrado", "Not Found")
            estado = "lista_espera" if self.lleno else "confirmada"
            return {"id": "i1", "evento_id": ruta.split("/")[4], "usuario_id": json["usuario_id"], "estado": estado,
                    "posicion_espera": 2 if self.lleno else None}
        if ruta.endswith("/mensajes"):
            if not self.chat_implementado:
                raise ErrorApi(404, "no_encontrado", "Not Found")
            return {"mensaje": {"id": "m1"}, "respuesta_ia": None}
        raise ErrorApi(404, "no_encontrado", "Not Found")


@pytest.fixture(autouse=True)
def api(monkeypatch):
    from app import api_cliente, metrics

    falsa = ApiFalsa()
    monkeypatch.setattr(api_cliente, "_peticion", falsa)
    # El envío de métricas va en un hilo aparte: en los tests no sale a la red
    monkeypatch.setattr(metrics, "_enviar_a_api", lambda registro: None)
    return falsa


@pytest.fixture(autouse=True)
def limpiar_estado():
    from app import api_cliente, canales, conversacion, vecino
    from app.config import get_settings

    get_settings.cache_clear()
    conversacion.estados.clear()
    vecino.vecinos.clear()
    vecino.preferencias_locales.clear()
    vecino.ubicaciones.clear()
    conversacion.idiomas_por_contacto.clear()
    from app import alta
    alta.altas.clear()
    from app.llm import router
    router.forzar_caida(None)
    conversacion._usuarios.clear()
    canales.bandeja_consola.clear()
    api_cliente.pendientes.clear()
    yield
    get_settings.cache_clear()
