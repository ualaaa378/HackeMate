"""Login y permisos (H2.6 + H3.1): JWT propio, roles, código por WhatsApp/Telegram, Google, modo demo y
/usuarios/me. Bot caído (BOT_URL vacío): los avisos quedan en cola y nada falla."""

import json
import time
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select

from app.config import get_settings
from app.modelos import CodigoVerificacion, Notificacion, Publicador, Usuario
from app.rutas import auth
from app.seed import sembrar
from app.seguridad import _b64, _b64_leer, emitir_jwt, exigir_rol, leer_jwt
from tests.test_importar import TOKEN, VIERNES, _error
from tests.test_moderacion_rutas import PENDIENTES, _validador, _valida

TOKEN_SCHEMA = _validador("urn:openapi#/components/schemas/Token")
USUARIO_SCHEMA = _validador("./schemas/usuario.json")

CARMEN = "5a5e0000-0000-4000-8000-000000000001"
LUCIA = "5a5e0000-0000-4000-8000-000000000002"
TEL_CARMEN = "+34600000201"
TEL_NUEVO = "+34600000888"
TEL_PUBLICADOR = "+34600000887"
CODIGO = "/api/v1/auth/whatsapp/codigo"
VERIFICAR = "/api/v1/auth/whatsapp/verificar"
GOOGLE = "/api/v1/auth/google"
DEMO = "/api/v1/auth/demo"
ME = "/api/v1/usuarios/me"
CLIENT_ID = "cliente-de-prueba.apps.googleusercontent.com"


def _ajustes(monkeypatch, **valores):
    for k, v in valores.items():
        monkeypatch.setenv(k, str(v))
    get_settings.cache_clear()


@pytest.fixture
def api(cliente, db, monkeypatch):
    _ajustes(monkeypatch, BOT_URL="", DEMO_MODE="false", GOOGLE_CLIENT_ID="")
    sembrar(db, ahora=VIERNES)
    db.commit()
    yield cliente
    get_settings.cache_clear()


def _bearer(usuario_id: str, rol: str = "vecino", **kw) -> dict:
    return {"Authorization": f"Bearer {emitir_jwt(usuario_id, rol, **kw)}"}


def _token_valido(datos: dict) -> dict:
    _valida(TOKEN_SCHEMA, datos)
    assert datos["token_type"] == "bearer"
    return leer_jwt(datos["access_token"])


# --- JWT ------------------------------------------------------------------------------------------


def test_jwt_ida_y_vuelta():
    claims = leer_jwt(emitir_jwt(CARMEN, "vecino"))
    assert claims["sub"] == CARMEN and claims["rol"] == "vecino"
    assert claims["exp"] - claims["iat"] == get_settings().jwt_expira_min * 60


def test_sin_token_401(api):
    _error(api.get(ME), 401, "no_autenticado")


def test_token_caducado_401(api):
    hace_rato = time.time() - 3600
    _error(api.get(ME, headers=_bearer(CARMEN, ahora=hace_rato, expira_min=5)), 401, "token_caducado")


def test_token_mal_firmado_o_manipulado_401(api, monkeypatch):
    bueno = emitir_jwt(CARMEN, "vecino")
    cabecera, carga, firma = bueno.split(".")
    # Carga cambiada (otro usuario y rol) con la firma original
    datos = json.loads(_b64_leer(carga)) | {"sub": LUCIA, "rol": "moderador"}
    manipulado = f"{cabecera}.{_b64(json.dumps(datos).encode())}.{firma}"
    _error(api.get(ME, headers={"Authorization": f"Bearer {manipulado}"}), 401, "token_invalido")
    # alg "none" sin firma
    sin_firma = _b64(json.dumps({"alg": "none", "typ": "JWT"}).encode()) + "." + carga + "."
    _error(api.get(ME, headers={"Authorization": f"Bearer {sin_firma}"}), 401, "token_invalido")
    # Basura y esquema que no es Bearer
    _error(api.get(ME, headers={"Authorization": "Bearer abc.def"}), 401, "token_invalido")
    _error(api.get(ME, headers={"Authorization": f"Basic {bueno}"}), 401, "token_invalido")
    # Firmado con otro secreto
    secreto = get_settings().jwt_secret
    _ajustes(monkeypatch, JWT_SECRET=secreto + "-otro")
    otro = emitir_jwt(CARMEN, "vecino")
    _ajustes(monkeypatch, JWT_SECRET=secreto)
    _error(api.get(ME, headers={"Authorization": f"Bearer {otro}"}), 401, "token_invalido")


def test_token_de_usuario_inexistente_401(api):
    _error(api.get(ME, headers=_bearer("00000000-0000-4000-8000-000000000000")), 401, "token_invalido")


def test_exigir_rol_rechaza_roles_desconocidos():
    with pytest.raises(ValueError):
        exigir_rol("administrador")


# --- Roles: moderador con Bearer --------------------------------------------------------------------


def test_moderador_con_bearer_entra_en_la_bandeja(api):
    r = api.get(PENDIENTES, headers=_bearer(LUCIA, "moderador"))
    assert r.status_code == 200, r.text


def test_vecino_con_bearer_recibe_403(api):
    _error(api.get(PENDIENTES, headers=_bearer(CARMEN)), 403, "rol_insuficiente")


def test_rol_lo_decide_la_base_no_el_token(api):
    # Un token que dice «moderador» para Carmen (vecina) no le da permisos de moderadora.
    _error(api.get(PENDIENTES, headers=_bearer(CARMEN, "moderador")), 403, "rol_insuficiente")


def test_moderacion_sin_credenciales_401(api):
    _error(api.get(PENDIENTES), 401, "no_autenticado")


def test_moderador_con_bearer_decide_y_firma_con_su_nombre(api, db):
    from tests.test_moderacion_rutas import _decidir, _evento_confirmado, _publicador

    _publicador(db, "+34600000781", nivel=0)
    evento = _evento_confirmado(api, "+34600000781")
    assert evento["estado"] == "en_revision"
    r = _decidir(api, evento["id"], "aprobar", headers=_bearer(LUCIA, "moderador"))
    assert r.status_code == 200, r.text
    assert r.json()["moderacion"]["revisado_por"] == "Lucía (moderadora)"


# --- Código por WhatsApp / Telegram ---------------------------------------------------------------


@pytest.fixture
def codigo_fijo(monkeypatch):
    monkeypatch.setattr(auth, "generar_codigo", lambda: "123456")
    return "123456"


def test_pedir_codigo_guarda_el_aviso_y_solo_el_hash(api, db, codigo_fijo):
    r = api.post(CODIGO, json={"telefono": TEL_CARMEN})
    assert r.status_code == 200, r.text
    assert r.json()["enviado"] is True  # en camino: con el bot caído queda en la cola
    assert r.json()["expira_en"].endswith("+01:00")
    db.expire_all()
    aviso = db.scalar(select(Notificacion).where(Notificacion.telefono == TEL_CARMEN, Notificacion.tipo == "confirmacion"))
    assert aviso.tipo == "confirmacion" and "123456" in aviso.texto and aviso.usuario_id == CARMEN
    assert aviso.estado_envio == "pendiente" and aviso.intentos == 1  # se intentó tras responder
    registro = db.scalar(select(CodigoVerificacion).where(CodigoVerificacion.telefono == TEL_CARMEN))
    assert registro.codigo_hash != "123456" and len(registro.codigo_hash) == 64


def test_codigo_va_por_telegram_si_el_usuario_lo_tiene(api, db, codigo_fijo):
    db.get(Usuario, CARMEN).telegram_id = "555"
    db.commit()
    api.post(CODIGO, json={"telefono": TEL_CARMEN})
    db.expire_all()
    aviso = db.scalar(select(Notificacion).where(Notificacion.telefono == TEL_CARMEN, Notificacion.tipo == "confirmacion"))
    assert aviso.contacto == "tg:555"


def test_verificar_bien_da_token_y_crea_vecino_verificado(api, db, codigo_fijo):
    api.post(CODIGO, json={"telefono": TEL_NUEVO})
    r = api.post(VERIFICAR, json={"telefono": TEL_NUEVO, "codigo": "123456"})
    assert r.status_code == 200, r.text
    claims = _token_valido(r.json())
    usuario = r.json()["usuario"]
    assert usuario["telefono"] == TEL_NUEVO and usuario["rol"] == "vecino" and usuario["whatsapp_verificado"]
    assert claims["sub"] == usuario["id"] and claims["rol"] == "vecino"
    # El token sirve para /usuarios/me
    assert api.get(ME, headers={"Authorization": f"Bearer {r.json()['access_token']}"}).json()["id"] == usuario["id"]
    # Un código solo vale una vez
    _error(api.post(VERIFICAR, json={"telefono": TEL_NUEVO, "codigo": "123456"}), 401, "codigo_invalido")


def test_verificar_mal_o_sin_pedir_401(api, codigo_fijo):
    _error(api.post(VERIFICAR, json={"telefono": TEL_CARMEN, "codigo": "123456"}), 401, "codigo_invalido")
    api.post(CODIGO, json={"telefono": TEL_CARMEN})
    _error(api.post(VERIFICAR, json={"telefono": TEL_CARMEN, "codigo": "000000"}), 401, "codigo_invalido")
    # Sigue valiendo tras un fallo
    assert api.post(VERIFICAR, json={"telefono": TEL_CARMEN, "codigo": "123456"}).status_code == 200


def test_codigo_caducado_401(api, db, codigo_fijo):
    api.post(CODIGO, json={"telefono": TEL_CARMEN})
    registro = db.scalar(select(CodigoVerificacion).where(CodigoVerificacion.telefono == TEL_CARMEN))
    registro.expira_en = registro.expira_en - timedelta(minutes=11)
    db.commit()
    _error(api.post(VERIFICAR, json={"telefono": TEL_CARMEN, "codigo": "123456"}), 401, "codigo_invalido")


def test_cinco_fallos_anulan_el_codigo(api, codigo_fijo):
    api.post(CODIGO, json={"telefono": TEL_CARMEN})
    for _ in range(auth.CODIGO_MAX_INTENTOS):
        _error(api.post(VERIFICAR, json={"telefono": TEL_CARMEN, "codigo": "999999"}), 401, "codigo_invalido")
    _error(api.post(VERIFICAR, json={"telefono": TEL_CARMEN, "codigo": "123456"}), 401, "codigo_invalido")


def test_solo_vale_el_ultimo_codigo(api, monkeypatch):
    codigos = iter(["111111", "222222"])
    monkeypatch.setattr(auth, "generar_codigo", lambda: next(codigos))
    api.post(CODIGO, json={"telefono": TEL_CARMEN})
    api.post(CODIGO, json={"telefono": TEL_CARMEN})
    _error(api.post(VERIFICAR, json={"telefono": TEL_CARMEN, "codigo": "111111"}), 401, "codigo_invalido")
    assert api.post(VERIFICAR, json={"telefono": TEL_CARMEN, "codigo": "222222"}).status_code == 200


def test_cuarto_codigo_en_una_hora_429(api, codigo_fijo):
    for _ in range(auth.CODIGOS_POR_HORA):
        assert api.post(CODIGO, json={"telefono": TEL_CARMEN}).status_code == 200
    _error(api.post(CODIGO, json={"telefono": TEL_CARMEN}), 429, "demasiados_codigos")
    # Otro teléfono no se ve afectado
    assert api.post(CODIGO, json={"telefono": TEL_NUEVO}).status_code == 200


def test_telefono_no_e164_422(api):
    _error(api.post(CODIGO, json={"telefono": "tg:123"}), 422, "validacion")
    _error(api.post(VERIFICAR, json={"telefono": TEL_CARMEN, "codigo": "12ab56"}), 422, "validacion")


def test_publicador_solicitado_pasa_a_whatsapp_verificado(api, db, codigo_fijo):
    r = api.post(
        "/api/v1/publicadores",
        json={"nombre": "Peña de prueba", "tipo": "asociacion", "municipio": "Tahal", "telefono": TEL_PUBLICADOR},
        headers=TOKEN,
    )
    assert r.status_code == 201, r.text
    publicador_id = r.json()["id"]
    assert r.json()["estado"] == "solicitado"
    api.post(CODIGO, json={"telefono": TEL_PUBLICADOR})
    r = api.post(VERIFICAR, json={"telefono": TEL_PUBLICADOR, "codigo": "123456"})
    assert r.status_code == 200, r.text
    db.expire_all()
    publicador = db.get(Publicador, publicador_id)
    assert publicador.estado == "whatsapp_verificado"
    assert publicador.usuario_id == r.json()["usuario"]["id"]
    # Y el moderador puede aprobarlo con su sesión
    r = api.post(f"/api/v1/publicadores/{publicador_id}/aprobar", json={}, headers=_bearer(LUCIA, "moderador"))
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "aprobado"


# --- Google ---------------------------------------------------------------------------------------


@pytest.fixture
def google(monkeypatch):
    """Simula tokeninfo de Google: devuelve lo que haya en `respuesta` (o el status que se fije)."""
    estado = {"status": 200, "respuesta": {}, "peticiones": []}

    def _manejar(peticion: httpx.Request) -> httpx.Response:
        estado["peticiones"].append(peticion)
        return httpx.Response(estado["status"], json=estado["respuesta"])

    monkeypatch.setattr(auth, "_transporte", httpx.MockTransport(_manejar))
    _ajustes(monkeypatch, GOOGLE_CLIENT_ID=CLIENT_ID)
    return estado


def _info_google(**cambios) -> dict:
    return {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "1098765432101234567",
        "email": "Vecina.Nueva@example.org",
        "email_verified": "true",
        "name": "Vecina Nueva",
        "exp": str(int(time.time()) + 600),
    } | cambios


def test_google_crea_vecino_y_da_token(api, google):
    google["respuesta"] = _info_google()
    r = api.post(GOOGLE, json={"id_token": "token-de-google"})
    assert r.status_code == 200, r.text
    _token_valido(r.json())
    usuario = r.json()["usuario"]
    assert usuario["email"] == "vecina.nueva@example.org" and usuario["rol"] == "vecino"
    assert usuario["nombre"] == "Vecina Nueva"
    assert google["peticiones"][0].url.params["id_token"] == "token-de-google"
    # Segundo login: el mismo usuario
    assert api.post(GOOGLE, json={"id_token": "otro"}).json()["usuario"]["id"] == usuario["id"]


def test_google_encuentra_usuario_existente_por_email(api, google):
    google["respuesta"] = _info_google(email="moderacion@example.org", sub="42")
    r = api.post(GOOGLE, json={"id_token": "x"})
    assert r.status_code == 200, r.text
    assert r.json()["usuario"]["id"] == LUCIA and leer_jwt(r.json()["access_token"])["rol"] == "moderador"


def test_google_aud_incorrecto_401(api, google):
    google["respuesta"] = _info_google(aud="otra-app.apps.googleusercontent.com")
    _error(api.post(GOOGLE, json={"id_token": "x"}), 401, "token_google_invalido")


def test_google_email_sin_verificar_401(api, google):
    google["respuesta"] = _info_google(email_verified="false")
    _error(api.post(GOOGLE, json={"id_token": "x"}), 401, "email_no_verificado")


def test_google_rechaza_el_token_401(api, google):
    google["status"], google["respuesta"] = 400, {"error": "invalid_token"}
    _error(api.post(GOOGLE, json={"id_token": "x"}), 401, "token_google_invalido")


def test_google_caido_503(api, google, monkeypatch):
    def _caido(_):
        raise httpx.ConnectError("sin red")

    monkeypatch.setattr(auth, "_transporte", httpx.MockTransport(_caido))
    _error(api.post(GOOGLE, json={"id_token": "x"}), 503, "google_no_disponible")


def test_google_sin_client_id_503(api):
    _error(api.post(GOOGLE, json={"id_token": "x"}), 503, "google_no_configurado")


# --- Modo demo ------------------------------------------------------------------------------------


def test_demo_desactivado_404(api):
    _error(api.post(DEMO, json={"rol": "moderador"}), 404, "no_encontrado")


def test_demo_activado_nunca_da_sesion_de_moderador(api, monkeypatch):
    # La demo va por una URL pública: la moderación entra solo con usuario y contraseña (POST /auth/admin).
    _ajustes(monkeypatch, DEMO_MODE="true")
    _error(api.post(DEMO, json={"rol": "moderador"}), 403, "demo_sin_moderador")
    _error(api.post(DEMO, json={"usuario_id": LUCIA}), 403, "demo_sin_moderador")


def test_demo_activado_da_token_de_otros_roles(api, monkeypatch):
    _ajustes(monkeypatch, DEMO_MODE="true")
    r = api.post(DEMO, json={"rol": "publicador"})
    assert r.status_code == 200, r.text
    assert _token_valido(r.json())["rol"] == "publicador"

    r = api.post(DEMO, json={"usuario_id": CARMEN})
    assert r.status_code == 200 and r.json()["usuario"]["nombre"] == "Carmen"
    _error(api.post(DEMO, json={"usuario_id": "00000000-0000-4000-8000-000000000000"}), 404, "usuario_no_encontrado")
    _error(api.post(DEMO, json={}), 422, "validacion")
    _error(api.post(DEMO, json={"rol": "administrador"}), 422, "validacion")


# --- /usuarios/me ---------------------------------------------------------------------------------


def test_me_devuelve_el_perfil(api):
    r = api.get(ME, headers=_bearer(CARMEN))
    assert r.status_code == 200, r.text
    _valida(USUARIO_SCHEMA, r.json())
    assert r.json()["nombre"] == "Carmen" and r.json()["telefono"] == TEL_CARMEN


def test_me_patch_actualiza_preferencias(api):
    cambios = {
        "nombre": "  Carmen López ",
        "municipio": "Tahal",
        "gustos": ["gastronomia", "fiestas", "fiestas"],
        "etiquetas_interes": ["Senderismo", "migas"],
        "formato_aviso": "texto",
        "acepta_avisos": False,
        "radio_km": 25,
    }
    r = api.patch(ME, json=cambios, headers=_bearer(CARMEN))
    assert r.status_code == 200, r.text
    _valida(USUARIO_SCHEMA, r.json())
    u = r.json()
    assert u["nombre"] == "Carmen López" and u["municipio"] == "Tahal"
    assert u["gustos"] == ["gastronomia", "fiestas"] and u["etiquetas_interes"] == ["senderismo", "migas"]
    assert u["formato_aviso"] == "texto" and u["acepta_avisos"] is False and u["radio_km"] == 25
    assert u["lat"] is not None and u["lat"] != 37.1983  # ubicación de Tahal
    # Persistido
    assert api.get(ME, headers=_bearer(CARMEN)).json() == u


def test_me_patch_cambiar_telefono_quita_la_verificacion(api):
    r = api.patch(ME, json={"telefono": "+34 600 000 299"}, headers=_bearer(CARMEN))
    assert r.status_code == 200, r.text
    assert r.json()["telefono"] == "+34600000299" and r.json()["whatsapp_verificado"] is False
    _error(api.patch(ME, json={"telefono": "+34600000202"}, headers=_bearer(CARMEN)), 409, "telefono_en_uso")


def test_me_patch_rechaza_lo_que_no_se_puede_editar(api):
    _error(api.patch(ME, json={"rol": "moderador"}, headers=_bearer(CARMEN)), 422, "validacion")
    _error(api.patch(ME, json={"nombre": None}, headers=_bearer(CARMEN)), 422, "validacion")
    _error(api.patch(ME, json={"gustos": ["apuestas"]}, headers=_bearer(CARMEN)), 422, "validacion")
    _error(api.patch(ME, json={"municipio": "Almería"}, headers=_bearer(CARMEN)), 422, "municipio_no_encontrado")


def test_me_sin_token_401(api):
    _error(api.get(ME), 401, "no_autenticado")
    _error(api.patch(ME, json={"nombre": "X"}), 401, "no_autenticado")
