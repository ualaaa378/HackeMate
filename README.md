<div align="center">

#  HackeMate

### Equipo de la Hackathon UAL para el Desarrollo del Interior

*Reto 1 · Reactiva tu pueblo: comercio y turismo inteligente*

![Hackathon](https://img.shields.io/badge/Hackathon-UAL-0055A4?style=for-the-badge)
![Reto](https://img.shields.io/badge/Reto%201-Reactiva%20tu%20pueblo-2E7D32?style=for-the-badge)
![Estado](https://img.shields.io/badge/Estado-En%20desarrollo-F57C00?style=for-the-badge)

</div>

---

## 👥 Quiénes somos

<div align="center">

| 🧑‍💻 | 🧑‍💻 | 🧑‍💻 | 🧑‍💻 |
|:-:|:-:|:-:|:-:|
| **Adán Álvarez Amat** | **Francisco Sánchez López** | **Benas Sapogas** | **Juan Carlos Pascual Escañuela** |

</div>

## 🎯 El reto

Impulsar el **comercio y el turismo** de los pueblos del interior de Almería con tecnología, empezando por cuatro municipios:

<div align="center">

| 📍 Lucainena de las Torres | 📍 Senes | 📍 Velefique | 📍 Uleila del Campo |
|:-:|:-:|:-:|:-:|

</div>

## 💡 Nuestra idea

Una plataforma web que conecte a **negocios locales**, **ayuntamientos** y **visitantes**:

| | Qué queremos conseguir |
|:-:|:--|
| 🏪 **Negocios** | Publicar ofertas, promociones y eventos, con ayuda de IA para redactarlos. |
| 🏛️ **Ayuntamientos** | Moderar las publicaciones, con una IA que las preclasifica antes. |
| 🎒 **Visitantes** | Descubrir qué hacer según sus intereses, la fecha y la ubicación en un mapa. |
| 📅 **Calendario** | Reunir las actividades turísticas, culturales y deportivas. |
| 🤖 **Asistente** | Un chatbot que responda solo con la información de la plataforma. |

## 🛠️ Tecnologías previstas

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)
![OpenStreetMap](https://img.shields.io/badge/OpenStreetMap-7EBC6F?style=flat-square&logo=openstreetmap&logoColor=white)
![Claude](https://img.shields.io/badge/Claude-D97757?style=flat-square&logo=anthropic&logoColor=white)

## 🚧 Estado

El proyecto está **en sus primeras fases**. Iremos actualizando este README a medida que avancemos.

## 🔗 Pendiente entre flujos

Revisado el 21/11/2026 a las 01:55. Todo esto ya lo usa la app web (flujo C) o el bot (flujo B), pero depende de otro flujo. Mientras no esté, **la web vuelve sola a los datos de prueba (mocks) y el bot guarda la petición en cola**, así que nada se rompe, pero la demo no usa datos reales. Al cerrar cada punto, se borra de esta lista.

> **Regla del equipo (ver `CLAUDE.md`):** cada flujo apunta aquí, bajo el flujo responsable, lo que necesita de los demás. Antes de empezar una tarea, revisa tu apartado.

### Flujo A · API (Benas)

Rutas que ya están en `contracts/openapi.yaml` pero la API aún no tiene:

| Ruta | La usa | Para qué en la demo |
|---|---|---|
| `GET /moderacion/pendientes` · `POST /moderacion/{id}/decision` | web `/admin` (Bandeja) y bot | El moderador aprueba un plan y el antispam frena otro |
| `POST /publicadores/{id}/aprobar` · `POST /publicadores/{id}/pausar` | web `/admin` (Asociaciones) | Dar de alta o pausar a una asociación |
| `POST /eventos/{id}/confirmar` | bot | El publicador confirma la ficha por Telegram |
| `GET/POST /eventos/{id}/inscripciones` | web (Ficha) y bot | La vecina se apunta |
| `GET/POST /eventos/{id}/mensajes` | web (chat del evento) y bot | Pregunta en el chat del evento |
| `GET /recomendaciones` | bot | A la vecina le llega la recomendación |
| `POST /auth/whatsapp/codigo` · `POST /auth/whatsapp/verificar` | web (crear cuenta) | Alta con nombre + móvil + código |
| `GET/PATCH /usuarios/me` | web (Perfil) | Sesión del vecino y sus gustos |
| `GET /estadisticas` | web `/admin` (Panel) | Panel de estadísticas para el jurado |

Otros puntos de la API:
- **Moderación automática al confirmar:** `POST /eventos/{id}/confirmar` tiene que llamar a `bot POST /ai/spam` y aplicar los niveles de confianza y `MODERACION_UMBRAL_SPAM` (antispam del paso 3 de la demo).
- **Aviso de cambio de hora:** cuando `PATCH /eventos/{id}` cambia la hora, la API llama a `bot POST /notify` para cada inscrito, con `formato: "audio"` si el usuario lo pidió (pasos 6 y 7 de la demo).
- **`POST /metrics/tokens`:** el bot ya manda el coste de cada llamada a la IA y hoy recibe 404. Sin esto, `GET /estadisticas` no puede mostrar los tokens.
- **Panel de robustez (lo pide la web, pasando por la API):** que la API exponga el interruptor `bot POST /admin/simular-caida` y las cifras de `bot GET /metrics`, para no poner el `INTERNAL_TOKEN` en el navegador.
- **Permisos de `POST /eventos` y `PATCH /eventos/{id}`:** hoy solo aceptan `X-Internal-Token`. La web (Proponer y `/admin`) llama con el JWT del usuario, así que tienen que aceptar `Authorization: Bearer` con rol de vecino, publicador o moderador.
- **Imagen del plan (`imagen_url`):** la web manda la foto opcional como *data URL* WebP comprimida dentro de `imagen_url`. La API tiene que aceptarla (puede ocupar cientos de KB) o, mejor, ofrecer una ruta de subida de archivos que devuelva la URL. Si se añade esa ruta, primero va al contrato.
- **Planes terminados para «Recuerdos»:** la pestaña pide `GET /eventos?hasta=<ahora>`, pero el seed omite los eventos ya terminados, así que con la API real sale vacía. Hace falta sembrar algunos planes pasados (estado `finalizado`) o que el seed no los borre.
- **Datos para el ayuntamiento al proponer un plan** (responsable, teléfono, público, necesidades, seguro): la web los tiene en `DatosAyuntamiento` (`apps/web/src/api/types.ts`), pero no están en el contrato. Hay que añadirlos como objeto opcional y privado (PR con etiqueta `contract-change`).

- **Revisión a mano o automática de las asociaciones (lo pide la web `/admin` → Asociaciones):** solo hay dos modos. Toda asociación empieza **a mano** (`nivel_confianza` 0 o 1) y pasa a **automática** (`nivel_confianza` 2) cuando el moderador lo decide y cumple las reglas de `apps/web/src/admin/confianza.ts`: responsable identificado (DNI y residencia comprobados), al menos 3 planes aprobados en 60 días, ningún rechazo en 60 días y algún plan en los últimos 90 días. Hace falta en la API:
  - Objeto opcional y privado `responsable` en el publicador (`nombre`, `dni`, `residencia`, `identidad_verificada`), que solo vea el moderador (PR `contract-change`). Hoy está en `DatosResponsable` de `apps/web/src/api/types.ts`. Es un dato personal: guardar lo mínimo y no devolverlo nunca en las rutas públicas.
  - Una ruta para que el moderador marque la identidad como comprobada (por ejemplo `POST /publicadores/{id}/verificar-identidad`), primero en el contrato. Sin ella, el botón solo funciona en modo demo.
  - Actividad reciente en el publicador (`planes_60_dias`, `rechazados_60_dias`, `ultimo_plan`), calculada por la API. Hoy la web la tiene en `ActividadPublicador` con mocks.
  - Que `POST /publicadores/{id}/aprobar` acepte cambiar `nivel_confianza` en un publicador ya aprobado (la web lo usa para pasar a automática o volver a mano), y que la API rechace el nivel 2 si no se cumplen las reglas.

- **Frase de portada del plan (lo pide la web, Inicio → «Próximos planes»):** quien publica puede escribir una frase corta (máx. 90 letras) que sale bajo la foto del carrusel. Hace falta el campo opcional `frase_portada` en `evento` y `EventoCrear` (PR con etiqueta `contract-change`). Hoy la web la guarda en `DatosAyuntamiento` y la lee de `evento.frase_portada` si llega (`apps/web/src/eventos/frases.ts`). Si viene vacía, la API pide la frase al bot (ver flujo B) y la guarda.

### Flujos A y B · a acordar (Benas + Francisco)

- **`PATCH /usuarios/{id}`:** el bot lo usa para guardar los gustos de la vecina (`services/bot/app/api_cliente.py`, `guardar_preferencias`), pero no está en el contrato, que solo tiene `PATCH /usuarios/me`. O se añade al contrato con `X-Internal-Token`, o el bot pasa a usar otra ruta.
- **Código de acceso por mensajería (Telegram y WhatsApp):** `POST /auth/whatsapp/codigo` tiene que pedir al bot (`POST /notify`) que mande el código. El nombre de la ruta no se cambia (el contrato no renombra), pero vale para los dos canales. Con Telegram, el bot no puede escribir a un móvil que nunca le ha hablado. Hace falta acordar el paso previo: por ejemplo, que la web enseñe el enlace `t.me/HackeMate_bot?start=alta` y el vecino comparta su número con «Compartir mi número» (`POST /usuarios/vincular`) antes de pedir el código. Si hace falta un campo `canal` en la petición, se añade como opcional con `contract-change`.

### Todos · Telegram ahora, WhatsApp más adelante

Regla en `CLAUDE.md` § «Canales de mensajería». Cómo se elige el canal hoy, sin tocar código:
- **Bot (B):** Telegram se activa con `TELEGRAM_TOKEN`, y los contactos `tg:<chat_id>` salen por ahí. WhatsApp sale por `CANAL` (`meta`, `twilio` o `console`). Los dos pueden funcionar a la vez.
- **API (A):** guarda los dos contactos (`telefono` E.164 y `telegram_id`) y los distingue en `services/api/app/canales.py`. Nada de la API puede dar por hecho un canal concreto.
- **Web (C):** `VITE_CANAL=telegram|whatsapp` (en `.env.example`, el compose y el `Dockerfile`) elige qué canal nombra la web en el alta y en los avisos (`apps/web/src/canal.ts`).

Pendiente: Benas y Francisco, que el aviso al vecino use el contacto que tenga (`telegram_id` si existe, si no `telefono`) en vez de suponer WhatsApp.

### Flujo C · web (Adán), lo que pide el bot

- Botón «Simular caída de la IA» y coste en tokens en `/admin/panel`, en cuanto la API los exponga (ver arriba).
- Opcional, como plan C de la demo: un chat simulado en la web que llame a `bot POST /dev/mensaje`.

### Flujo B · bot (Francisco), alta de asociaciones

- **Datos del responsable al dar de alta una asociación:** cuando alguien pide publicar por Telegram (y por WhatsApp cuando Meta lo permita, con el mismo flujo de conversación), el bot tiene que pedir el nombre, el DNI y el pueblo donde vive el responsable, y mandarlos a la API en el alta (cuando el campo `responsable` esté en el contrato, ver flujo A). Sin esos datos la asociación nunca podrá publicar sin revisión.

### Flujo B · bot (Francisco), frase de portada con IA

- **`POST /ai/frase`** (o el nombre que se acuerde, primero en el contrato): a partir del título, la categoría y el pueblo, devolver una frase breve, espontánea y alegre (máx. 90 letras, sin inventar datos del plan) para la portada del carrusel. La llama la API cuando el publicador no escribe la suya. Mientras no exista, la web elige una frase fija por tipo de plan y la marca como «✨ Frase automática».

### Flujo B · bot (Francisco), opcional en el compose

- Volumen `bot_data` con `COLA_PATH` para que la cola sobreviva si se recrea el contenedor, y `PUBLIC_URL` en el `.env` si el túnel tiene URL fija (ver `services/bot/PARA_FLUJO_A.md` §4).

Detalle del flujo B, con los cuerpos exactos de cada llamada: [`services/bot/PARA_FLUJO_A.md`](services/bot/PARA_FLUJO_A.md) y [`docs/PLAN_FLUJO_B.md`](docs/PLAN_FLUJO_B.md) §5.

### Ya resuelto

- Docker compose arranca el bot real de `services/bot` (PR #23, probado en Docker).

---

## ⚙️ Backend (flujo A)

API FastAPI + SQLAlchemy + Alembic en `services/api/`, con PostgreSQL (pgvector) en Docker o SQLite en local. Contratos en `contracts/` (`openapi.yaml`, schemas y fixtures): ningún endpoint ni campo existe sin estar antes ahí.

### Arranque con Docker (3 comandos)

```bash
cp .env.example .env                                   # y rellenar las claves (llegan por mensaje privado)
docker compose -f infra/docker-compose.yml up --build  # db, api, bot, web y tunnel
scripts/smoke_test.sh                                   # debe acabar en «SMOKE TEST EN VERDE»
```

El contenedor `api` crea las tablas y siembra la demo al arrancar. API en `http://localhost:8000` (docs en `/docs`), bot en `:8001`, web en `:8080`. La URL pública del túnel sale en `docker compose -f infra/docker-compose.yml logs tunnel`.

### Arranque en Windows sin Docker

```powershell
cd services\api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
# Solo si sale «DLL load failed while importing _util_cy» (Control de aplicaciones de Windows): SQLAlchemy en Python puro
$env:DISABLE_SQLALCHEMY_CEXT='1'; python -m pip install --force-reinstall --no-deps --no-binary sqlalchemy sqlalchemy==2.1.9
copy ..\..\.env.example ..\..\.env       # opcional; sin .env se usa SQLite en services\api\hackemate.db
python ..\..\scripts\seed.py             # tablas + datos de la demo (repetible)
uvicorn app.main:app --reload --port 8000
```

Python 3.15: `uvicorn` va sin el extra `[standard]` y para YAML se usa `ruamel.yaml` (no hay wheel de PyYAML).

### Arquitectura

```
WhatsApp/Telegram ──> tunnel (HTTPS) ──> bot :8001 ──HTTP + X-Internal-Token──> api :8000 ──> db :5432
                                          ^   │                                   ^
          Twilio/Meta/Telegram, IA  <─────┘   └─<── POST /notify, /ai/* ──────────┘
                                                        web :8080 ──HTTP + Bearer JWT──> api
```

- **Solo `api` toca la base de datos** y decide los estados. `bot` y `web` hablan con ella por HTTP.
- **Solo `bot` habla con Twilio/Meta/Telegram y con la IA.** Si la `api` necesita IA, llama a `bot` en `POST /ai/...`; los avisos los pide con `POST /notify` y, si el bot está caído, quedan en cola y se reintentan.
- Entre servicios: cabecera `X-Internal-Token: ${INTERNAL_TOKEN}`. Usuarios (app y panel): `Authorization: Bearer <jwt>` (login con Google, código por WhatsApp o `/auth/demo` en modo demo).
- Cada servicio arranca aunque los demás estén caídos y expone `GET /health` → `{"status":"ok","version":"x.y.z"}`.

### Variables de entorno del backend

La lista completa y comentada está en `.env.example` (manda sobre esta tabla).

| Variable | Ejemplo | Para qué |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./hackemate.db` | Base de datos. En Docker el compose la fija a PostgreSQL (`db`). |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` / `DB_PORT` | `hackemate` / … / `5432` | Contenedor `db`. |
| `INTERNAL_TOKEN` | `cambia-esto` | Cabecera `X-Internal-Token` entre api y bot. Cambiarlo en la demo. |
| `JWT_SECRET` / `JWT_EXPIRA_MIN` | `cambia-esto-tambien` / `1440` | Firma y duración de las sesiones. Con el valor de ejemplo y `DEMO_MODE=false`, la api arranca igual pero escribe un `WARNING` en el log: pon un secreto aleatorio. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_TOKENINFO_URL` / `GOOGLE_TIMEOUT_S` | vacío / URL de Google / `5` | Login con Google (vacío → `/auth/google` responde 503). |
| `DEMO_MODE` | `false` | `true` habilita `POST /api/v1/auth/demo`. Solo en la presentación. |
| `BOT_URL` | `http://bot:8001` | Dónde están `/notify` y `/ai/*`. |
| `API_URL` | `http://api:8000` | La usa el bot para llamar a la api. |
| `APP_VERSION` | vacío | Versión de `/health` (vacío = la del código). |
| `ZONA_HORARIA` | `Europe/Madrid` | Zona de las fechas y del `.ics`. |
| `MODERACION_APROBACIONES_SUBIR_NIVEL` / `MODERACION_UMBRAL_SPAM` | `3` / `0.7` | Confianza del publicador y umbral del antispam. |
| `NOTIFICACIONES_TIMEOUT_S` / `NOTIFICACIONES_MAX_INTENTOS` | `3` / `5` | Cola de avisos hacia el bot: espera máxima a `/notify` e intentos antes de darlo por fallido. |
| `NOTIFICACIONES_REINTENTO_S` | `60` | Cada cuántos segundos la api reintenta en segundo plano los avisos pendientes (`0` = desactivado). |
| `PRECIOS_TOKENS_EUR_MTOK` | JSON por proveedor | Coste de la IA en `/estadisticas` (euros por millón de tokens; lo que no aparece cuenta como gratuito). |
| `CORS_ORIGENES` | `http://localhost:8080,…` | Orígenes permitidos. |
| `FIXTURES_DIR` | vacío | Carpeta de los fixtures del seed (vacío = `contracts/fixtures`). |

### Endpoints por hito (implementados)

Todos bajo `/api/v1/` salvo `/health`. Detalle, errores y ejemplos en `contracts/openapi.yaml`.

| Hito | Endpoints |
|---|---|
| H0 · Arranque | `GET /health` |
| H1 · Datos y CRUD | `GET /municipios` · `GET /lugares`, `GET /lugares/{id}` · `GET/POST /eventos` · `GET/PATCH /eventos/{id}` · `GET/POST /publicadores` · `GET /publicadores/{id}` · `POST /usuarios` · `GET /usuarios/by-phone/{e164}`, `/usuarios/by-contacto/{contacto}` · `POST /usuarios/vincular` |
| H2 · Ingesta y moderación | `POST /eventos/importar` · `POST /eventos/{id}/confirmar` · `GET /moderacion/pendientes` · `POST /moderacion/{id}/decision` · `POST /publicadores/{id}/aprobar`, `/pausar`, `/fuentes` · `POST /auth/whatsapp/codigo`, `/auth/whatsapp/verificar` |
| H3 · La vecina | `POST /auth/google` · `POST /auth/demo` · `GET/PATCH /usuarios/me` · `GET/POST /eventos/{id}/inscripciones` · `DELETE/PATCH /eventos/{id}/inscripciones/{insc_id}` · `GET/POST /eventos/{id}/mensajes` · `PATCH /eventos/{id}/mensajes/{msg_id}` (fijar, ocultar y silenciar al autor en ese chat con `silenciar_autor`) · `GET /eventos/{id}/ics` · `GET /usuarios/me/ics` · `GET /recomendaciones` |
| H4 · Jurado | `GET /estadisticas` (panel: actividades, inscripciones vs asistencia, ocupación, solapamientos y coste de la IA) · `POST /metrics/tokens` (el bot registra los tokens por proveedor) |

### Sembrar y reiniciar la demo

- `python scripts/seed.py`: crea/actualiza tablas y carga los fixtures. Repetible; omite los eventos que ya han terminado y solo toca los datos de `contracts/fixtures`.
- **Reinicio completo** (borra todo lo creado en el ensayo y vuelve al estado inicial; ~1–2 s, no hace falta reiniciar la api):
  - Docker: `scripts/demo_reset.sh`
  - Sin Docker (Linux/Git Bash): `scripts/demo_reset.sh --local`
  - Windows: `.\scripts\demo_reset.ps1`

### Tests y smoke test

```bash
cd services/api && python -m pytest -q        # tests unitarios y de contratos (sin Docker)
scripts/smoke_test.sh                         # o .\scripts\smoke_test.ps1 en Windows
```

El smoke test solo usa HTTP. Lee `API_URL` (por defecto `http://localhost:8000`), `INTERNAL_TOKEN` (del entorno o del `.env`) y, si se define, `BOT_URL`. Comprueba `/health`, la agenda, la ficha de la Ruta Solidaria, los municipios, la bandeja de moderación, que la Ruta Solidaria sale primera para Carmen y el `.ics`. Sale con código ≠ 0 si algo falla.

### Modo demo

Con `DEMO_MODE=true`, `POST /api/v1/auth/demo` con `{"rol": "moderador"}` o `{"usuario_id": "<uuid>"}` devuelve un JWT sin login (Carmen, la vecina de la demo, es `5a5e0000-0000-4000-8000-000000000001`). Con `false` responde 404. No dejarlo activo fuera de la presentación.

### Guion de la demo y qué lo sostiene en la api

| Paso | Endpoint de la api |
|---|---|
| 1. Post o audio → ficha | El bot extrae (`/ai/extraer`) y llama a `POST /eventos/importar` (queda `pendiente_confirmacion`) |
| 2. El publicador confirma por WhatsApp | `POST /eventos/{id}/confirmar` → pasa a moderación |
| 3. El moderador aprueba uno; el antispam para otro | `GET /moderacion/pendientes` · `POST /moderacion/{id}/decision` (antispam con `MODERACION_UMBRAL_SPAM`) |
| 4. A una vecina le llega la recomendación y se apunta | `GET /recomendaciones?usuario_id=…` · `POST /eventos/{id}/inscripciones` |
| 5. Pregunta en el chat del evento | `POST /eventos/{id}/mensajes` (la api pide la respuesta a `bot /ai/responder-ficha`) |
| 6. Cambio de hora → aviso a los inscritos | `PATCH /eventos/{id}` → `bot /notify` a cada inscrito + anuncio fijado en el chat |
| 7. Una persona mayor solo con audios | El bot transcribe y usa los mismos endpoints (pasos 1, 2 y 4) |

## 🤖 Bot (flujo B)

*Pendiente: sección a cargo del flujo B (`services/bot/`).*

## 📱 App web y Android (flujo C)

*Pendiente: sección a cargo del flujo C (`apps/web/`).*

---

<div align="center">

Hecho en la **Universidad de Almería**

</div>
