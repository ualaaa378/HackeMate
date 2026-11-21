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

**Primera versión completa para probar (sáb 21/11).** La API (flujo A) tiene todos los endpoints del contrato y el guion de la demo funciona de punta a punta con el bot en local. Cómo probarla y qué revisar: [`docs/PRUEBAS_V1.md`](docs/PRUEBAS_V1.md).

👉 **Para hoy:** propuesta de cómo trabajamos, revisión conjunta de la v1 a las 10:00 y decisiones pendientes en [`docs/SINCRONIZACION_SABADO.md`](docs/SINCRONIZACION_SABADO.md). Para revisarla entre los tres.

## 🔗 Pendiente entre flujos

Revisado el 21/11/2026 a las 09:20. Todo esto ya lo usa la app web (flujo C) o el bot (flujo B), pero depende de otro flujo. Mientras no esté, **la web vuelve sola a los datos de prueba (mocks) y el bot guarda la petición en cola**, así que nada se rompe, pero la demo no usa datos reales. Al cerrar cada punto, se borra de esta lista.

> **Regla del equipo (ver `CLAUDE.md`):** cada flujo apunta aquí, bajo el flujo responsable, lo que necesita de los demás. Antes de empezar una tarea, revisa tu apartado.

### 📋 Reparto del sábado 21/11 (09:30) · prueba de la v1

Quién hace qué ahora. Cada uno marca su línea al terminar y apunta los fallos en el apartado del flujo que los tiene que arreglar (más abajo).

**Adán (flujo C) · Docker y web**
- [ ] `git pull` de `develop` (ya lleva la API de la #35), `docker compose -f infra/docker-compose.yml down -v` (borra la base vieja para probar la migración 0007 en PostgreSQL), `cp .env.example .env` con las claves y `up --build`.
- [ ] `scripts/smoke_test.sh` hasta «SMOKE TEST EN VERDE». Si falla, `docker compose -f infra/docker-compose.yml logs api` y el error a Benas.
- [ ] Guion sin móvil con `scripts/simular_chat.py` y, después, los siete pasos con Telegram y la web en `http://localhost:8080` (`DEMO_MODE=true`). Ver [`docs/PRUEBAS_V1.md`](docs/PRUEBAS_V1.md) §0 y §3.
- [ ] Tests de la web (`cd apps/web && npm ci && npm run test:unit`, y `npm run test:e2e`), que Benas no puede pasar sin Node.
- [ ] Conectar en `/admin/panel` el botón «Simular caída de la IA» y el coste en tokens con `GET /admin/bot/metricas` y `POST /admin/bot/simular-caida` (ya en la API).
- [ ] Entre ensayos, `scripts/demo_reset.sh`.

**Benas (flujo A) · API**
- [x] PR `Flujo-A` → `develop` fusionada (#35, 09:21). Adán ya puede empezar la prueba con Docker.
- [ ] Arreglar lo que salga de la prueba con Docker (apartado «Flujo A» de abajo).
- [ ] Con Francisco: avisos a quien solo usa Telegram y código de acceso por Telegram («Flujos A y B · a acordar»).

**Francisco (flujo B) · bot**
- [ ] Hallazgos de la prueba de la v1: título sin IA, pregunta por chat privado y post de spam sin fecha (apartado «hallazgos» de abajo).
- [ ] Pedir nombre, DNI y residencia del responsable en el alta de asociaciones (la API ya lo acepta).
- [ ] `POST /ai/frase` para la frase de portada (primero en el contrato).
- [ ] Con Benas: avisos a quien solo usa Telegram y código de acceso por Telegram.

### Flujo A · API (Benas)

Todas las rutas de `contracts/openapi.yaml` que usan la web y el bot ya existen en la API (ninguna queda con `x-implementado: false`).

- **Frase de portada automática:** `frase_portada` ya se guarda y se devuelve (`POST`/`PATCH /eventos`, confirmar). Si llega vacía, la API se la pedirá al bot cuando exista `POST /ai/frase` (ver flujo B); mientras, la web pone una frase fija por tipo de plan.
- **Una propuesta de un vecino sin asociación:** entra en revisión y el moderador ve sus `datos_ayuntamiento`, pero el vecino solo los ve en la respuesta del alta (la API no guarda quién propuso el plan si no es un publicador).

### Flujos A y B · a acordar (Benas + Francisco)

- **Avisos a quien solo usa Telegram (paso 6 de la demo):** el bot ya lee `contacto` en `POST /notify`, pero el contrato (`schemas/notificacion.json`) y el modelo del bot siguen exigiendo `telefono`. Un vecino que entró por Telegram sin «Compartir mi número» no tiene teléfono y la API deja su aviso como `fallida` («sin telefono»). Quitar el `required` no es un cambio aditivo: hay que decidirlo juntos. Mientras tanto, en la demo, todos los inscritos tienen que haber compartido su número.

- **Código de acceso por mensajería (Telegram y WhatsApp):** `POST /auth/whatsapp/codigo` tiene que pedir al bot (`POST /notify`) que mande el código. El nombre de la ruta no se cambia (el contrato no renombra), pero vale para los dos canales. Con Telegram, el bot no puede escribir a un móvil que nunca le ha hablado. Hace falta acordar el paso previo: por ejemplo, que la web enseñe el enlace `t.me/HackeMate_bot?start=alta` y el vecino comparta su número con «Compartir mi número» (`POST /usuarios/vincular`) antes de pedir el código. Si hace falta un campo `canal` en la petición, se añade como opcional con `contract-change`.

### Todos · Telegram ahora, WhatsApp más adelante

Regla en `CLAUDE.md` § «Canales de mensajería». Cómo se elige el canal hoy, sin tocar código:
- **Bot (B):** Telegram se activa con `TELEGRAM_TOKEN`, y los contactos `tg:<chat_id>` salen por ahí. WhatsApp sale por `CANAL` (`meta`, `twilio` o `console`). Los dos pueden funcionar a la vez.
- **API (A):** guarda los dos contactos (`telefono` E.164 y `telegram_id`) y los distingue en `services/api/app/canales.py`. Nada de la API puede dar por hecho un canal concreto.
- **Web (C):** `VITE_CANAL=telegram|whatsapp` (en `.env.example`, el compose y el `Dockerfile`) elige qué canal nombra la web en el alta y en los avisos (`apps/web/src/canal.ts`).

### Flujo C · web (Adán), lo que pide el bot

- Botón «Simular caída de la IA» y coste en tokens en `/admin/panel`: la API ya los expone en `GET /admin/bot/metricas` y `POST /admin/bot/simular-caida` (con la sesión del moderador; el `INTERNAL_TOKEN` no va al navegador).
- Opcional, como plan C de la demo: un chat simulado en la web que llame a `bot POST /dev/mensaje`.

### Flujo B · bot (Francisco), alta de asociaciones

- **Datos del responsable al dar de alta una asociación:** cuando alguien pide publicar por Telegram (y por WhatsApp cuando Meta lo permita, con el mismo flujo de conversación), el bot tiene que pedir el nombre, el DNI y el pueblo donde vive el responsable, y mandarlos a la API en el alta (`POST /publicadores` con `responsable` {`nombre`, `dni`, `residencia`}; la API ya lo acepta y responde 422 `dni_invalido` si la letra del DNI/NIE no cuadra). Sin esos datos la asociación nunca podrá publicar sin revisión.

### Flujo B · bot (Francisco), frase de portada con IA

- **`POST /ai/frase`** (o el nombre que se acuerde, primero en el contrato): a partir del título, la categoría y el pueblo, devolver una frase breve, espontánea y alegre (máx. 90 letras, sin inventar datos del plan) para la portada del carrusel. La llama la API cuando el publicador no escribe la suya. Mientras no exista, la web elige una frase fija por tipo de plan y la marca como «✨ Frase automática».

### Flujo B · bot (Francisco), hallazgos de la prueba de la v1 (sin claves de IA)

Probado con `scripts/simular_chat.py` (bot con `CANAL=console`, sin Gemini ni FreeLLM: solo reglas). Detalle en [`docs/PRUEBAS_V1.md`](docs/PRUEBAS_V1.md) §4.
- **Título por reglas:** sin IA, el título de la ficha es el post entero recortado («Taller de esparto en Senés el sábado 28 de noviembre a las 11:00 en la plaza. Gr»). Conviene cortar en la primera frase o antes de « en <pueblo>»/« el <día>».
- **Pregunta sobre un plan por chat privado** («¿Hay que llevar agua a la ruta solidaria?»): el bot la trata como una búsqueda y enseña la ficha, sin responder. En el chat del evento sí se responde (la API llama a `/ai/responder-ficha`).
- **Post de apuestas por el bot:** sin fecha, el bot se queda pidiendo «¿Qué día y a qué hora empieza?» y no llega a la API, así que el antispam no lo ve. Para el paso 3, el post de spam tiene que llevar fecha (el del seed ya está en la bandeja con `score_spam` 0,95).

### Flujo B · bot (Francisco), opcional en el compose

- Volumen `bot_data` con `COLA_PATH` para que la cola sobreviva si se recrea el contenedor, y `PUBLIC_URL` en el `.env` si el túnel tiene URL fija (ver `services/bot/PARA_FLUJO_A.md` §4).

Detalle del flujo B, con los cuerpos exactos de cada llamada: [`services/bot/PARA_FLUJO_A.md`](services/bot/PARA_FLUJO_A.md) y [`docs/PLAN_FLUJO_B.md`](docs/PLAN_FLUJO_B.md) §5.

### Ya resuelto

- Docker compose arranca el bot real de `services/bot` (PR #23, probado en Docker).
- El aviso al vecino usa el contacto que tenga: la API manda `contacto` en `POST /notify` (`tg:<telegram_id>` si existe, si no `telefono`) en vez de suponer WhatsApp.
- `POST /eventos` y `PATCH /eventos/{id}` con sesión (JWT): la web «Proponer» y el organizador o el moderador editan sin token interno.
- `PATCH /usuarios/{id}` (preferencias que guarda el bot).
- Panel del bot por la API: `GET /admin/bot/metricas` y `POST /admin/bot/simular-caida` con la sesión del moderador.
- `POST /publicadores/{id}/verificar-identidad` (DNI/NIE y residencia del responsable comprobados).
- Filtro por estado en `GET /eventos`: `publicado` y `finalizado` («Recuerdos») para todos; los demás estados, el moderador (todos) y el publicador (solo los suyos), con sesión.

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

**Con el bot también en local (sin Docker):** el valor por defecto `BOT_URL=http://bot:8001` es el nombre del contenedor y fuera de Docker no existe; los avisos se quedan en cola (`pendiente`, `getaddrinfo failed`). Pon `BOT_URL=http://localhost:8001` en el `.env` (y en el del bot `API_URL=http://localhost:8000`). Guía completa de pruebas: [`docs/PRUEBAS_V1.md`](docs/PRUEBAS_V1.md).

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
| H4 · Jurado | `GET /estadisticas` (panel: actividades, inscripciones vs asistencia, ocupación, solapamientos y coste de la IA) · `POST /metrics/tokens` (el bot registra los tokens por proveedor) · `GET /admin/bot/metricas`, `POST /admin/bot/simular-caida` (panel de robustez: la API reenvía al bot con su `INTERNAL_TOKEN`; 503 `bot_no_disponible` si no responde en 3 s, 502 si responde con error) |
| Asociaciones (revisión a mano o automática) | `POST /publicadores/{id}/verificar-identidad` · `POST /publicadores/{id}/aprobar` sobre un publicador ya aprobado cambia `nivel_confianza` (el 2 exige las reglas de `apps/web/src/admin/confianza.ts`; si no, 409 `reglas_confianza_no_cumplidas` con `details.faltan`) · `responsable` y `actividad` solo con sesión de moderador · alta con `responsable` (422 `dni_invalido` si el DNI/NIE no es válido) |

Niveles de confianza: la subida automática por aprobaciones (`MODERACION_APROBACIONES_SUBIR_NIVEL`) llega como mucho al nivel 1; el nivel 2 (revisión automática) solo lo da un moderador y solo si se cumplen las reglas. La `actividad` se cuenta por la fecha en que se propuso cada plan (`creado_en`); «aprobados» son los `publicado` y `finalizado`.

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
