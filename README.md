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

Revisado el 21/11/2026 a las 11:00. Todo esto ya lo usa la app web (flujo C) o el bot (flujo B), pero depende de otro flujo. Mientras no esté, **la web vuelve sola a los datos de prueba (mocks) y el bot guarda la petición en cola**, así que nada se rompe, pero la demo no usa datos reales. Al cerrar cada punto, se borra de esta lista.

> **Regla del equipo (ver `CLAUDE.md`):** cada flujo apunta aquí, bajo el flujo responsable, lo que necesita de los demás. Antes de empezar una tarea, revisa tu apartado.

### 📋 Reparto del sábado 21/11 (11:00) · hasta la entrega

Acordado por Adán el sábado a las 11:00, después de revisar todo `develop` (tras las PR #41, #43 y #44). **Para los tres y para vuestros Claudes:** antes de empezar, leed este apartado entero y vuestra parte. Cada uno marca `[x]` en el mismo commit en que termina la tarea y apunta los fallos que encuentre en el apartado del flujo que los tiene que arreglar (más abajo), con el formato de `docs/SINCRONIZACION_SABADO.md` §3.

#### Dónde estamos (sáb 11:00)

- **El código va por delante del plan.** La API tiene todas las rutas del contrato (568 tests), el bot funciona con Telegram (108 tests) y la web tiene H0, H1 y H2 contra la API real.
- **Falta probarlo todo junto.** Todavía no se ha hecho ningún `up --build` con Telegram, la tabla del §5 de `SINCRONIZACION_SABADO.md` está en blanco y no hay ninguna etiqueta (`v0.1`, `v0.2`).
- **Web, H3 a medias:** ya están la inscripción, el `.ics` y el chat. Faltan «Para ti» (recomendaciones), el login y el service worker de la PWA. H4: el panel, el coste y la letra grande van a medias, y falta el APK.

#### Riesgos que ordenan el reparto (de más a menos grave)

1. **El jurado no puede usar la web desde fuera.** El túnel (`infra/docker-compose.yml`, servicio `tunnel`) solo expone `bot:8001`, y la web lleva `VITE_API_URL=http://localhost:8000` incrustado en el build. Desde el móvil del jurado o desde el APK, `localhost` no es nuestra API y la web cae a los mocks. → Tarea C3.
2. **El paso 7 (audios) depende del portátil de Fran.** La transcripción solo va por FreeLLM (`services/bot/app/agentes/medios.py`). Si su portátil o su red fallan, no hay plan B. → Tarea B3.
3. **Sin IA, la demo se ve floja** (títulos largos, el spam sin fecha no llega al antispam). → Tareas B1 y B2.
4. **Ningún checkpoint cerrado.** → Tarea C1 y la puesta en común de las 13:00.

#### Decisión nueva: eventos de Facebook con «Facebook Posts Scraper» y NVIDIA NIM

Para el paso 1 de la demo («post → ficha») y para llenar la agenda con datos reales. **No hace falta cambiar el contrato:** `POST /eventos/importar` ya acepta `origen.canal="facebook"`, `origen.url` y `origen.importado_auto`.

```
Facebook Posts Scraper ──> scripts/importar_facebook.py ──> bot POST /ai/extraer (NVIDIA NIM) ──> api POST /eventos/importar ──> bandeja del moderador ──> agenda web
     (páginas de los Aytos)        (A, Benas)                    (B, Francisco)                         (ya existe)
```

- **Páginas con Facebook activo:** Ayuntamientos de Uleila del Campo, Lucainena de las Torres y Senés, y Monte-Sión (ver `contracts/fixtures/FUENTES.md`).
- **Reglas que se mantienen:** solo el bot habla con la IA (NIM va en el `llm_router` del bot, nunca en el script ni en la API). Solo la API decide estados: lo importado de una asociación «a mano» pasa por la bandeja. Coste 0: plan gratuito del scraper y de NIM, claves solo en `.env` (nunca en `*.example`), y **cada ejecución guarda los posts en un JSON** para poder repetir la importación sin red ni créditos.
- Las descargas (APK, vídeos, exportaciones del scraper) van a `C:\Users\aalva\Desktop\Hackaton`.

#### Hitos y tareas por persona

**Adán (flujo C) · máquina de la demo, web y entrega**

| Hito | Hasta | Tarea |
|---|---|---|
| H2 · CP2 | sáb 13:00 | - [ ] **C1.** `docker compose -f infra/docker-compose.yml down -v`, `up --build`, `scripts/smoke_test.sh` en verde y pasos 1–3 con Telegram (`DEMO_MODE=true`). Rellenar la columna «Docker + Telegram» de `SINCRONIZACION_SABADO.md` §5. Si sale bien, etiqueta `v0.2`. |
| H3 · CP3 | sáb 19:00 | - [ ] **C2.** «Para ti» en la agenda con `GET /recomendaciones` y el motivo legible (Carmen ve la II Ruta Solidaria la primera). |
| H3 · CP3 | sáb 19:00 | - [ ] **C3.** **URL pública de la web:** que el `nginx.conf` de la web pase `/api/` a `api:8000`, que la web use una URL relativa (`VITE_API_URL` vacío) y un segundo túnel a `web:8080`. Es infra de A: lo hace Adán porque Benas no puede ejecutar Docker, en una PR que mira Benas. |
| H3 · CP3 | sáb 19:00 | - [ ] **C4.** PWA instalable: service worker e icono (el `manifest.json` ya existe). |
| H3 | — | - [-] **Login con Google: recortado.** En la demo se entra con el modo demo (`/auth/demo`). El código por Telegram, solo si sobra tiempo (D2). |
| H4 · CP4 | dom 00:00 | - [ ] **C5.** APK de debug con Capacitor que apunta a la URL de C3. Si en 30 min no sale, la demo va con la PWA instalada. |
| H4 · CP4 | dom 00:00 | - [ ] **C6.** Panel: % de eventos importados de Facebook y coste en tokens con NIM incluido (cuando A2 y B2 estén). Accesibilidad: teclado y letra grande en agenda y ficha. |
| H5 | dom 07:00 | - [ ] **C7.** Vídeo de respaldo, sección de la web en el README con capturas, dos ensayos seguidos del guion y `v1.0` en `main`. |

**Benas (flujo A) · API e ingesta de Facebook, en remoto y sin Docker**

| Hito | Hasta | Tarea |
|---|---|---|
| H2 · CP2 | sáb 13:00 | - [ ] **A1.** Arreglar lo que salga de la prueba con Docker de Adán (apartado «Flujo A» de abajo). |
| H3 · CP3 | sáb 19:00 | - [~] **A2.** *(script hecho y probado con API y bot locales desde JSON; falta la primera descarga real: token de Apify y URL de las páginas)* **`scripts/importar_facebook.py`** (solo Python, sin Docker): 1) lanza «Facebook Posts Scraper» sobre las páginas de `FUENTES.md` (token en `.env`, por ejemplo `FB_SCRAPER_TOKEN`, y la variable en `.env.example` vacía); 2) guarda los posts en `contracts/fixtures/facebook_posts.json`; 3) por cada post llama a `bot POST /ai/extraer` con `X-Internal-Token`; 4) manda el resultado a `POST /eventos/importar` con `origen.canal="facebook"`, `origen.url` del post e `importado_auto=true`. Opción `--desde-json` para repetirlo sin red. Si el bot no responde, el post se queda en el JSON y no se inventa nada. |
| H3 · CP3 | sáb 19:00 | - [ ] **A3.** Decidir **D1** con Francisco antes de que se congelen los contratos a las 19:00 (quitar o no el `required` de `telefono` en `schemas/notificacion.json` para avisar a quien solo usa Telegram). |
| H4 · CP4 | dom 00:00 | - [ ] **A4.** `GET /estadisticas`: que el % de importadas cuente las de Facebook (ya llegan con `importado_auto`). Revisar la PR de C3 (nginx y túnel). |
| H5 | dom 07:00 | - [ ] **A5.** Arreglos `fix/*` de los ensayos y repasar la sección del backend del README. |

**Francisco (flujo B) · bot e IA**

| Hito | Hasta | Tarea |
|---|---|---|
| H2 · CP2 | sáb 13:00 | - [ ] **B1.** Los tres hallazgos sin IA (apartado «hallazgos» de abajo), que afectan a los pasos 1, 3 y 5: título por reglas, pregunta por chat privado y post de spam sin fecha. |
| H3 · CP3 | sáb 19:00 | - [ ] **B2.** **NVIDIA NIM como proveedor del `llm_router`**, en el orden Gemini → NIM → FreeLLM → Claude → reglas. NIM es compatible con OpenAI, así que basta con otra instancia como la de `FreeLLM` en `app/llm/proveedores.py`, con `NIM_URL`, `NIM_API_KEY` y `NIM_MODELO` en `.env.example` (vacías). Que `/ai/extraer` lo use para A2 y que sus tokens salgan en `/metrics` y en `/metrics/tokens` de la API. |
| H3 · CP3 | sáb 19:00 | - [ ] **B3.** **Plan B de los audios** fuera de su portátil (por ejemplo, la transcripción de Gemini o la de NIM si la tiene) y ensayar el paso 7 con la máquina de Adán. |
| H3 · CP3 | sáb 19:00 | - [ ] **B4.** Decidir **D1** con Benas (ver A3). |
| H4 · CP4 | dom 00:00 | - [ ] **B5.** Solo si sobra tiempo: `POST /ai/frase` (primero en el contrato) y pedir nombre, DNI y residencia en el alta de asociaciones. |
| H5 | dom 07:00 | - [ ] **B6.** Escribir la sección del bot del README y tener las claves de IA de la demo en el `.env` de Adán (por privado). |

#### ⏰ Puesta en común · sáb 13:00 (CP2), llamada de 30 min

Los tres, a las 13:00. Orden del día:

1. Adán enseña los pasos 1–3 en Docker con Telegram (C1). Si salen, se pone `v0.2`.
2. Cada uno dice en una frase cómo va con su tarea y si algo le bloquea más de 20 minutos (si es así, se recorta).
3. Benas y Francisco confirman cómo va la ingesta de Facebook (A2 + B2) y quedan para cerrar D1 antes de las 19:00.
4. Se actualiza este apartado: se marca lo hecho y se mueve lo que no llegue.

Siguientes puntos fijos: **CP3 sáb 19:00** (pasos 4–7, contratos congelados, `v0.3`), **CP4 dom 00:00** (feature freeze, `v0.9`), **REL dom 07:00** (`v1.0` en `main`). La entrega a la organización es el domingo a las 11:00.

### Flujo A · API (Benas)

Todas las rutas de `contracts/openapi.yaml` que usan la web y el bot ya existen en la API (ninguna queda con `x-implementado: false`).

- **Frase de portada automática:** `frase_portada` ya se guarda y se devuelve (`POST`/`PATCH /eventos`, confirmar). Si llega vacía, la API se la pedirá al bot cuando exista `POST /ai/frase` (ver flujo B); mientras, la web pone una frase fija por tipo de plan.
- **Una propuesta de un vecino sin asociación:** entra en revisión y el moderador ve sus `datos_ayuntamiento`, pero el vecino solo los ve en la respuesta del alta (la API no guarda quién propuso el plan si no es un publicador).

- **Ingesta de Facebook (A2), primera descarga real:** el script `scripts/importar_facebook.py` ya está hecho y probado sin red (`--desde-json`). Para descargar de verdad faltan dos cosas: el **token de Apify** (`FB_SCRAPER_TOKEN` en el `.env`, por privado) y las **URL de las páginas de Facebook** de los Ayuntamientos de Uleila del Campo, Lucainena de las Torres y Senés, y de Monte-Sión (`FUENTES.md` las nombra pero no da las direcciones). Lo mejor es darlas de alta como fuentes de su publicador (`POST /publicadores/{id}/fuentes`), y así cada post queda asociado a su ayuntamiento; también valen `--pagina` o `FB_PAGINAS`. **A decidir el equipo:** los ayuntamientos están en «automática», así que lo que se importe de sus páginas se publica sin pasar por el moderador (la API decide igual que con un post enviado por el bot). Si preferís que todo lo importado automáticamente pase por la bandeja, es un cambio de dos líneas en la API (`decidir_estado`), sin tocar el contrato.
- **Revisar la PR de la URL pública (C3):** Adán cambia el `nginx.conf` de la web y añade un segundo túnel en `infra/docker-compose.yml` porque Benas no puede ejecutar Docker. Como el compose es de A, la mira Benas antes de fusionarla.

### Flujos A y B · a acordar (Benas + Francisco)

- **Avisos a quien solo usa Telegram (paso 6 de la demo):** el bot ya lee `contacto` en `POST /notify`, pero el contrato (`schemas/notificacion.json`) y el modelo del bot siguen exigiendo `telefono`. Un vecino que entró por Telegram sin «Compartir mi número» no tiene teléfono y la API deja su aviso como `fallida` («sin telefono»). Quitar el `required` no es un cambio aditivo: hay que decidirlo juntos. Mientras tanto, en la demo, todos los inscritos tienen que haber compartido su número.

- **Código de acceso por mensajería (Telegram y WhatsApp):** `POST /auth/whatsapp/codigo` tiene que pedir al bot (`POST /notify`) que mande el código. El nombre de la ruta no se cambia (el contrato no renombra), pero vale para los dos canales. Con Telegram, el bot no puede escribir a un móvil que nunca le ha hablado. Hace falta acordar el paso previo: por ejemplo, que la web enseñe el enlace `t.me/HackeMate_bot?start=alta` y el vecino comparta su número con «Compartir mi número» (`POST /usuarios/vincular`) antes de pedir el código. Si hace falta un campo `canal` en la petición, se añade como opcional con `contract-change`.

### Todos · Telegram ahora, WhatsApp más adelante

Regla en `CLAUDE.md` § «Canales de mensajería». Cómo se elige el canal hoy, sin tocar código:
- **Bot (B):** Telegram se activa con `TELEGRAM_TOKEN`, y los contactos `tg:<chat_id>` salen por ahí. WhatsApp sale por `CANAL` (`meta`, `twilio` o `console`). Los dos pueden funcionar a la vez.
- **API (A):** guarda los dos contactos (`telefono` E.164 y `telegram_id`) y los distingue en `services/api/app/canales.py`. Nada de la API puede dar por hecho un canal concreto.
- **Web (C):** `VITE_CANAL=telegram|whatsapp` (en `.env.example`, el compose y el `Dockerfile`) elige qué canal nombra la web en el alta y en los avisos (`apps/web/src/canal.ts`).

### Flujo C · web (Adán)

- **URL pública de la web (C3):** hoy la web solo funciona en la máquina de la demo (`VITE_API_URL=http://localhost:8000` y el túnel solo al bot). Lo necesitan el jurado, el APK (C5) y cualquiera que pruebe desde fuera.
- **«Para ti» (C2):** la API ya da `GET /recomendaciones`; falta enseñarlo en la agenda para el paso 4.

Lo que pide el bot:
- Opcional, como plan C de la demo: un chat simulado en la web que llame a `bot POST /dev/mensaje`.

### Flujo B · bot (Francisco), NVIDIA NIM y audios

- **NIM en el `llm_router` (B2):** lo usa la ingesta de Facebook de Benas (A2) a través de `/ai/extraer`, y C enseña sus tokens en el panel (C6).
- **Audios sin depender del portátil de Fran (B3):** hoy la transcripción solo va por FreeLLM. Lo necesita el paso 7 de la demo en la máquina de Adán.

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

- **Solo dos modos de publicación (a mano y automática), sin semiautomático** (decisión del equipo, 21/11): la API ya no usa el nivel 1 (si llega, lo guarda como 0) ni sube de nivel sola; la migración 0008 pasa a «a mano» los que estaban en 1, y en el seed las asociaciones son «a mano» y los ayuntamientos y el bar, «automática». Un posible duplicado de una asociación «a mano» llega a la bandeja con el motivo «Posible duplicado de…». La web ya manda `nivel_confianza: 0` para «a mano» (`cambiarRevision` en `apps/web/src/api/admin.ts`).

- La web (flujo C, H2) ya usa la API real en la zona del ayuntamiento: bandeja (`/moderacion/*`), publicadores (`/aprobar`, `/pausar`, `/verificar-identidad`), planes con JWT, `GET /estadisticas`, panel del bot y «Proponer un plan» con `datos_ayuntamiento`. Los botones de la demo en `/admin` entran con `POST /auth/demo`, así que la API tiene que arrancar con `DEMO_MODE=true` en el `.env` (si no, la web vuelve a los mocks y lo marca como «modo demo»).

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
| `MODERACION_UMBRAL_SPAM` | `0.7` | Umbral del antispam. (`MODERACION_APROBACIONES_SUBIR_NIVEL` ya no se usa: no hay subida automática de nivel.) |
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

Modos de publicación: solo dos, **a mano** (`nivel_confianza` 0, todo pasa por el moderador) y **automática** (2, se publica salvo spam alto o pausa). No hay semiautomático ni subida automática: a automática solo pasa un moderador y solo si se cumplen las reglas. El nivel 1 está obsoleto (si llega, se guarda como 0). La `actividad` se cuenta por la fecha en que se propuso cada plan (`creado_en`); «aprobados» son los `publicado` y `finalizado`.

### Sembrar y reiniciar la demo

- `python scripts/seed.py`: crea/actualiza tablas y carga los fixtures. Repetible; omite los eventos que ya han terminado y solo toca los datos de `contracts/fixtures`.
- **Reinicio completo** (borra todo lo creado en el ensayo y vuelve al estado inicial; ~1–2 s, no hace falta reiniciar la api):
  - Docker: `scripts/demo_reset.sh`
  - Sin Docker (Linux/Git Bash): `scripts/demo_reset.sh --local`
  - Windows: `.\scripts\demo_reset.ps1`

### Ingesta de Facebook (A2)

`scripts/importar_facebook.py` (solo Python, sin Docker ni dependencias): páginas de Facebook → «Facebook Posts Scraper» (Apify) → `bot POST /ai/extraer` → `POST /eventos/importar` (origen `facebook`, URL del post, `importado_auto`) → `POST /eventos/{id}/confirmar` (la API decide: asociación «a mano» → bandeja).

```bash
python scripts/importar_facebook.py                    # descarga (FB_SCRAPER_TOKEN) e importa; guarda contracts/fixtures/facebook_posts.json
python scripts/importar_facebook.py --desde-json       # repite con los posts guardados, sin red ni créditos
python scripts/importar_facebook.py --solo-descargar   # solo guarda los posts
python scripts/importar_facebook.py --pagina https://www.facebook.com/<pagina>   # página suelta (sin asociación: va a revisión)
```

- Páginas: las fuentes de Facebook activas de los publicadores aprobados (así el post queda asociado) más `--pagina` y `FB_PAGINAS`.
- Del post solo se guarda la URL, la página, la fecha, el texto y el texto de las fotos (carteles); nada de comentarios ni de quién reacciona.
- La fecha de publicación va al final del texto para que la IA entienda «este sábado». Si el bot no responde, el post queda guardado y no se crea nada; si falta la fecha, el evento se queda en `pendiente_confirmacion`. Volver a ejecutarlo no duplica: la API reconoce la URL del post.
- Resultado por post: `publicado`, `en_revision`, `pendiente`, `duplicado`, `no_es_evento` o `error`, y un resumen final.

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
