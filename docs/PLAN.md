# PLAN.md · Reto 1 «Reactiva tu pueblo»

> Hackathon UAL para el desarrollo del interior · 20–22 nov 2026
> Equipo: **Dev A · Benas** (Flujo A), **Dev B · Francisco** (Flujo B), **Dev C · Adán** (Flujo C)
> Entrega oficial: **domingo 22 nov, 11:00**. Objetivo interno: **todo acoplado y probado el domingo a las 07:00**.
> Fuente: presentación oficial https://marcoslupion.github.io/hackathon-ual-retos/ (copia en `docs/Hackathon_UAL_Retos.pdf`).

---

## 0. Resumen en 30 segundos

- Construimos **una plataforma con 3 puertas de entrada sincronizadas**: chatbot de **WhatsApp**, **app Ionic React** (web/PWA + APK Android con Capacitor) y **panel de gestión**.
- Todo se levanta con **`docker compose up`** (API + bot/IA + web + base de datos + túnel HTTPS para el webhook de WhatsApp). Las mismas imágenes se pueden desplegar después en Render/Railway sin cambios.
- Tres flujos de trabajo independientes: **A · Backend y datos**, **B · WhatsApp e IA**, **C · Web, PWA y panel**.
- Se trabaja **contra contratos congelados** (`contracts/`) y **datos de ejemplo** (`contracts/fixtures/`), así nadie espera a nadie.
- **Una rama por flujo**, integración en `develop`, `main` solo recibe versiones probadas.
- El avance se controla en **[`PROGRESO.md`](PROGRESO.md)** (checklist por flujo, checkpoints, demo y criterios del jurado).
- ⚠️ Si se elige la Opción 1, hay que actualizar `CLAUDE.md` del repo, que todavía describe el plan anterior (Streamlit + SQLite, equipo de 4).

---

## 1. Análisis del reto

### 1.1 Qué pide la organización

| Bloque | Requisito |
|---|---|
| Roles | **Moderador** (aprueba publicadores, revisa lo dudoso, pausa automatizaciones), **Publicador** (asociaciones, bares, ayuntamientos), **Vecino/visitante** (mira sin registrarse, se apunta, recibe avisos). **Cada rol puede hacerlo todo por WhatsApp.** |
| Alta de publicador | Pide ser publicador → verificación del WhatsApp con código → el moderador aprueba la entidad → conecta fuentes (Facebook/Instagram/web) → el sistema las vigila. |
| Ingesta automática | Post/cartel/audio → **la IA extrae la ficha** (título, fecha, hora, lugar, precio, categoría, campos que faltan) → el bot pregunta por WhatsApp lo que falta → confirma → antispam/moderación → publicado en calendario, mapa, app, web y bot. Sin duplicados (se guarda el origen). |
| Moderación | **Filtro antispam que aprende**: nivel 0 (todo a revisión), nivel 1 (lo habitual pasa), nivel 2 (casi todo pasa). El moderador ve el motivo, retira y pausa. |
| Participación | Recomendación por gustos, cercanía, fecha/plazas, historial · aviso por WhatsApp (texto o audio) · inscripción con un botón · `.ics` / Google Calendar · lista de espera. |
| Chat del evento | Tablón en la ficha (recomendado) con preguntas, respuestas y anuncios fijados; la IA responde lo que está en la ficha y filtra spam. Cambio de hora → aviso a todos los inscritos. |
| Mapa | Leaflet + OpenStreetMap, filtro por categoría, «cerca de mí». |
| Panel | Actividades, % importadas solas, inscripciones, asistencia real, ocupación por categoría, solapamientos entre pueblos. |
| Común | Login con Google, app + web multiplataforma, desplegado en la nube con URL pública, código en GitHub. |

### 1.2 Cómo puntúa el jurado (10 criterios)

**Qué hace:** funcionalidad requerida · funcionalidad extra · usabilidad y accesibilidad (personas mayores, voz, WCAG 2.1 AA) · utilidad para los pueblos · multiplataforma (web + móvil + WhatsApp sincronizados).
**Cómo está hecha:** coste en tokens (medido) · robustez (si falla una herramienta, se usa otra) · tiempo de respuesta (acuse inmediato) · APIs gratuitas con plan B · despliegue y código (URL pública + GitHub).

### 1.3 Guion de la demo (lo que TIENE que funcionar el domingo)

1. Un post de Facebook (o un audio) se convierte en ficha.
2. El publicador confirma por WhatsApp.
3. El moderador aprueba uno y el antispam para otro.
4. A una vecina le llega la recomendación y se apunta.
5. Pregunta en el chat del evento (responde la IA con la ficha).
6. Cambio de hora → aviso a los inscritos.
7. Una persona mayor lo usa solo con audios.

> **Regla de oro del equipo:** todo lo que no sirva a estos 7 pasos o a los 10 criterios es «extra» y solo se hace después del checkpoint CP3.

### 1.4 Riesgos principales

| Riesgo | Mitigación |
|---|---|
| WhatsApp Cloud API de Meta requiere verificación (horas/días) | Usar **Twilio WhatsApp Sandbox** (en minutos). Plan B: Telegram bot con la misma lógica (adaptador). Plan C: simulador de chat en la web. |
| Scraping de Facebook bloqueado | La demo usa **«pegar enlace/texto del post» o reenviar el cartel al bot** + un scraper de una web pública. Fixtures con posts reales guardados. |
| Cuotas de APIs de IA | Capa `llm_router` con **cadena de proveedores** (Claude → Gemini AI Studio → NVIDIA NIM → reglas) y caché. |
| Webhook necesita HTTPS público | Contenedor **cloudflared** (Cloudflare Tunnel) en el compose → URL pública sin desplegar. |
| Integración de madrugada | Contratos congelados, fixtures compartidos, checkpoints de integración cada ~5 h. |

---

## 2. Brainstorming: enfoques posibles

### Opción 1 · «Python de punta a punta» (RECOMENDADA)

- **API**: FastAPI + SQLAlchemy + **PostgreSQL con pgvector** (embeddings para recomendación y para que el asistente busque en la ficha).
- **Bot/IA**: servicio FastAPI aparte que recibe el webhook de Twilio, transcribe audio (Whisper vía API o `faster-whisper`), llama a la IA con salida JSON validada (Pydantic) y habla con la API.
- **App y web**: **Ionic React** (React + Vite por debajo) + **react-leaflet**. Un solo código para la web/PWA (servida en Docker con nginx) y, con **Capacitor**, un **APK de Android** → cumple «multiplataforma». Componentes táctiles y accesibles de serie. iOS solo si alguien tiene Mac.
- **Pros**: el equipo ya domina Python (curso GenAI: embeddings, SBERT, RAG); un solo lenguaje en back e IA; Docker sencillo.
- **Contras**: dos lenguajes en total (Python + TS); la web hay que hacerla desde cero.

### Opción 2 · «Supabase + Next.js» (BaaS)

- Supabase (Postgres, Auth con Google, Storage, pgvector) + Next.js (web y panel) + funciones serverless para el bot.
- **Pros**: login con Google y base de datos casi gratis; despliegue en Vercel en minutos.
- **Contras**: menos control en Docker (Supabase self-hosted es pesado); la lógica IA en TS es menos cómoda para el equipo; dependencia de un servicio externo durante la demo.

### Opción 3 · «Bot-first + panel mínimo»

- Casi todo ocurre en WhatsApp; la web es un panel Streamlit con mapa (folium) y calendario.
- **Pros**: lo más rápido de construir; muy bueno en accesibilidad (audios).
- **Contras**: flojo en **multiplataforma** y en la experiencia web/móvil del vecino, que el jurado puntúa; Streamlit no es una app instalable.

### Ideas creativas que suman puntos (para después de CP3)

- **Modo «abuela»**: si el usuario manda audio, el bot responde en audio (TTS) y con botones de 1 palabra.
- **Agenda en papel con QR** generada en PDF desde el panel (para el bar o el consultorio).
- **Aviso por el tiempo**: si AEMET prevé lluvia, sugiere al publicador avisar o aplazar.
- **«Plan del día»**: ruta + comida + visita entre pueblos.
- **Contador de tokens y euros en vivo** en el panel (criterio «coste en tokens»).
- **Botón «simular caída del LLM»** en el panel para enseñar el fallback en la demo (criterio «robustez»).

### Decisión

> **Propuesta del Tech Lead: Opción 1.** Debatid 15 minutos en el kickoff; si no hay objeción fuerte, se congela y no se vuelve a discutir.
> Decisión final: ☑ Opción 1 ☐ Opción 2 ☐ Opción 3 · Firmado: Benas / Francisco / Adán (vie 20 nov)
> Cuarta persona: **Juan Carlos** hace pareja con el flujo A (seed y datos de demo, `.ics`, estadísticas, smoke test y despliegue).

---

## 3. Arquitectura (Opción 1)

```
        WhatsApp (Twilio)            Navegador / PWA móvil
              │  webhook HTTPS               │
              ▼                              ▼
   ┌──────────────────┐   REST    ┌──────────────────┐
   │  bot  :8001      │──────────▶│  api  :8000      │◀── web (nginx :8080)
   │  WhatsApp + IA   │◀──────────│  datos y reglas  │
   │  llm_router      │  /notify  │  auth, eventos,  │
   └──────────────────┘           │  inscripciones   │
              │                   └────────┬─────────┘
       Claude / Gemini / NIM               │
       Whisper (voz)                ┌──────▼───────┐
                                    │ db Postgres  │
   cloudflared (túnel HTTPS) ──▶ bot│ + pgvector   │
                                    └──────────────┘
```

**Reglas de responsabilidad (nadie las rompe):**
- Solo **`api`** toca la base de datos. `bot` y `web` hablan con `api` por HTTP.
- Solo **`bot`** habla con Twilio y con los proveedores de IA. Si `api` necesita IA (p. ej. responder en el chat del evento desde la web), llama a `bot` en `POST /ai/...`.
- Solo **`api`** decide estados (pendiente, publicado, etc.). La IA **propone**, la app **valida**, una persona **decide** lo importante.
- Toda notificación saliente (WhatsApp) la pide `api` a `bot` con `POST /notify`.

---

## 4. División en 3 flujos de trabajo

Cada flujo tiene su carpeta. **Nadie edita la carpeta de otro** sin avisar (y entonces por PR).

### Flujo A · Backend, datos e infraestructura (Dev A) → `services/api/`, `infra/`

1. Modelo de datos y migraciones (Alembic) según `contracts/schemas/`.
2. Endpoints REST de `contracts/openapi.yaml`: eventos, publicadores, fuentes, usuarios/preferencias, inscripciones (con plazas y lista de espera), chat del evento, moderación, estadísticas.
3. Login con Google (OAuth → JWT propio) + login por WhatsApp (código de un solo uso) + roles.
4. Lógica de reglas: niveles de confianza del antispam (0/1/2), detección de duplicados por `origen_url` y similitud, solapamientos entre pueblos, lista de espera.
5. Recomendador: puntuación = gustos + distancia (haversine) + fecha/plazas + historial + embeddings (pgvector); devuelve el **porqué**.
6. Exportación `.ics` por evento y por usuario.
7. `docker-compose.yml`, `.env.example`, `seed.py` con los pueblos (Lucainena, Senés, Velefique, Uleila, Tahal) y datos de demo.
8. Despliegue alternativo (Render/Railway) el sábado por la noche si da tiempo.

### Flujo B · WhatsApp, IA y automatizaciones (Dev B) → `services/bot/`

1. Webhook de Twilio (texto, audio, imagen, ubicación) con **acuse inmediato** (<1 s) y trabajo pesado en segundo plano.
2. Máquina de estados de conversación por rol (vecino, publicador, moderador) con botones/respuestas rápidas.
3. `llm_router`: cadena de proveedores con timeout, reintento y fallback a reglas; **registro de tokens de entrada/salida** por llamada (`POST /api/v1/metrics/tokens`).
4. Agentes pequeños: **extractor de eventos** (texto/cartel/audio → `ExtraccionEvento` JSON validado), **antispam** (reglas baratas primero, IA solo si es dudoso), **intérprete de preferencias** («me gustan las rutas»), **asistente del evento** (responde solo con la ficha; si no está, deriva al organizador).
5. Transcripción de audio (Whisper) y, como extra, respuesta en audio (TTS).
6. Ingesta: «vigilante» de fuentes (scraper de web pública / Graph API si hay token) + entrada manual «pega aquí el enlace del post».
7. `POST /notify`: envío de avisos (recomendación, cambio de hora, anuncios) respetando preferencias.
8. Adaptador de canal (`channels/twilio.py`, `channels/console.py`) para probar sin WhatsApp.

### Flujo C · App Ionic, web/PWA y panel (Dev C) → `apps/web/`

> Stack: **Ionic React** (`ionic start web tabs --type=react`, Vite), `react-leaflet`, tipos desde `openapi.yaml`. Se desarrolla y se hace la demo en el navegador; el APK con Capacitor es tarea del bloque 4 y, si se complica, no bloquea nada.

1. Vecino (sin registro para mirar): **agenda**, **mapa Leaflet** con filtros y «cerca de mí», **ficha del evento** (inscribirse, `.ics`, chat del evento).
2. Perfil: login con Google, gustos, pueblo, tipo de avisos (texto/audio), vincular WhatsApp.
3. Publicador: alta, conectar fuentes, crear/editar/cancelar evento, ver inscritos, publicar anuncios.
4. Moderador: bandeja de pendientes con **motivo de la IA**, aprobar/rechazar publicadores y eventos, niveles de confianza, **pausar automatizaciones**.
5. Panel de estadísticas: actividades, % importadas solas, inscripciones vs asistencia, ocupación por categoría, solapamientos, **tokens y coste**.
6. Accesibilidad: letra grande, contraste AA, botones grandes, navegación por teclado, `aria-label`, textos alternativos.
7. PWA: `manifest.json`, service worker, icono.
8. **Capacitor → APK de Android** (bloque 4). Instalar Android Studio + JDK **el viernes por la noche o el sábado por la mañana** (tarda 1–2 h) para no perder tiempo después. La URL de la API se configura por variable de entorno (`VITE_API_URL`) para que el APK apunte a la URL pública del túnel.
9. Trabaja desde el minuto 1 con **mocks** (`contracts/fixtures/` servidos por MSW o un `json-server`).

### Reparto de carga (aprox.)

| | Flujo A | Flujo B | Flujo C |
|---|---|---|---|
| Horas efectivas estimadas | ~24 h | ~24 h | ~24 h |
| Dependencia de los demás | Ninguna (es el dueño de los contratos de datos) | Usa la API → mientras no exista, usa `contracts/fixtures` y un stub | Usa la API → mientras no exista, usa mocks |

---

## 5. Estrategia de acoplamiento y compatibilidad

### 5.1 Estructura del repositorio (monorepo)

```
/
├── README.md                    # cómo arrancar en 3 comandos
├── docs/
│   ├── PLAN.md                  # este archivo
│   └── Hackathon_UAL_Retos.pdf
├── contracts/                   # ⚠️ ZONA CONGELADA (solo por PR aprobada por los 3)
│   ├── openapi.yaml             # API REST de api (y de bot: /notify, /ai/*)
│   ├── schemas/                 # JSON Schema de cada entidad
│   │   ├── evento.json
│   │   ├── extraccion_evento.json
│   │   ├── usuario.json
│   │   ├── publicador.json
│   │   ├── inscripcion.json
│   │   ├── mensaje_evento.json
│   │   └── notificacion.json
│   ├── fixtures/                # datos de ejemplo válidos contra los schemas
│   └── enums.md                 # valores permitidos (categorías, estados, roles…)
├── services/
│   ├── api/   (Flujo A)  Dockerfile, app/, tests/
│   └── bot/   (Flujo B)  Dockerfile, app/, tests/
├── apps/
│   └── web/   (Flujo C)  Ionic React: Dockerfile, src/, public/, capacitor.config.ts, android/ (generado)
├── infra/
│   ├── docker-compose.yml
│   └── docker-compose.override.example.yml
├── scripts/  seed.py, smoke_test.sh, demo_reset.sh
└── .env.example                 # TODAS las variables, sin valores secretos
```

### 5.2 Contratos de datos (se congelan en CP0, a las 18:30 del viernes)

**Convenciones obligatorias**
- JSON en **snake_case**, claves en español sin tildes (`fecha_inicio`, `municipio`).
- IDs: **UUID v4** como string.
- Fechas: **ISO 8601 con zona** (`2026-11-30T09:00:00+01:00`). Zona por defecto `Europe/Madrid`.
- Dinero: `precio_eur` número decimal; `null` = gratis o desconocido (ver `es_gratuito`).
- Coordenadas: `lat`, `lon` (números, WGS84).
- Enums en minúsculas con guion bajo (ver `contracts/enums.md`).
- Rutas versionadas: `/api/v1/...`.
- Paginación: `?page=1&size=20` → `{ "items": [...], "total": 123, "page": 1, "size": 20 }`.
- Errores, siempre así:
  ```json
  { "error": { "code": "evento_no_encontrado", "message": "Texto legible", "details": {} } }
  ```
- Autenticación: `Authorization: Bearer <jwt>`. Entre servicios: cabecera `X-Internal-Token: ${INTERNAL_TOKEN}`.

**Enums iniciales (`contracts/enums.md`)**
- `rol`: `vecino`, `publicador`, `moderador`
- `categoria`: `deportiva`, `cultural`, `fiestas`, `gastronomia`, `ludica`, `comercio`
- `estado_evento`: `borrador`, `pendiente_confirmacion`, `en_revision`, `publicado`, `rechazado`, `cancelado`, `finalizado`, `archivado`
- `estado_publicador`: `solicitado`, `whatsapp_verificado`, `aprobado`, `rechazado`, `pausado`
- `nivel_confianza`: `0`, `1`, `2`
- `estado_inscripcion`: `confirmada`, `lista_espera`, `cancelada`, `asistio`, `no_asistio`
- `canal`: `whatsapp`, `web`, `panel`, `facebook`, `instagram`, `web_externa`, `manual`
- `tipo_notificacion`: `recomendacion`, `cambio_evento`, `anuncio`, `respuesta`, `moderacion`, `confirmacion`
- `formato_aviso`: `texto`, `audio`

**Entidad `Evento` (resumen; el JSON Schema completo vive en `contracts/schemas/evento.json`)**
```json
{
  "id": "6f1c…",
  "titulo": "II Ruta Solidaria Sierra de Velefique",
  "descripcion": "Ruta benéfica de 12 km…",
  "categoria": "deportiva",
  "etiquetas": ["senderismo", "solidario"],
  "municipio": "Velefique",
  "lugar": "Plaza de la iglesia",
  "lat": 37.195, "lon": -2.402,
  "fecha_inicio": "2026-11-30T09:00:00+01:00",
  "fecha_fin": null,
  "precio_eur": 5.0, "es_gratuito": false,
  "plazas_totales": 40, "plazas_libres": 8,
  "estado": "publicado",
  "publicador_id": "a12b…",
  "origen": { "canal": "facebook", "url": "https://facebook.com/…", "importado_auto": true },
  "moderacion": { "motivo": null, "score_spam": 0.04, "revisado_por": null },
  "creado_en": "…", "actualizado_en": "…"
}
```

**Entidad `ExtraccionEvento` (lo que devuelve la IA; la valida Pydantic antes de usarla)**
```json
{
  "campos": {
    "titulo":       { "valor": "II Ruta Solidaria", "confianza": "alta" },
    "fecha_inicio": { "valor": "2026-11-30T09:00:00+01:00", "confianza": "alta" },
    "municipio":    { "valor": "Velefique", "confianza": "alta" },
    "categoria":    { "valor": "deportiva", "confianza": "alta" },
    "precio_eur":   { "valor": 5.0, "confianza": "media" },
    "plazas_totales": { "valor": null, "confianza": "falta" },
    "lugar":        { "valor": null, "confianza": "falta" }
  },
  "faltan": ["plazas_totales", "lugar"],
  "es_evento": true,
  "proveedor_ia": "gemini-flash",
  "tokens": { "entrada": 812, "salida": 143 }
}
```

**Endpoints mínimos (detallados en `openapi.yaml`)**

| Servicio | Método y ruta | Uso |
|---|---|---|
| api | `GET /api/v1/eventos?municipio=&categoria=&desde=&hasta=&lat=&lon=&radio_km=` | agenda y mapa |
| api | `GET/POST/PATCH /api/v1/eventos/{id}` | ficha, crear, editar, cambiar hora |
| api | `POST /api/v1/eventos/importar` | el bot entrega una `ExtraccionEvento` + origen |
| api | `POST /api/v1/eventos/{id}/confirmar` | el publicador confirma (WhatsApp o web) |
| api | `POST /api/v1/eventos/{id}/inscripciones` · `DELETE …/{insc_id}` | apuntarse / cancelar |
| api | `GET/POST /api/v1/eventos/{id}/mensajes` | chat del evento |
| api | `GET /api/v1/eventos/{id}/ics` · `GET /api/v1/usuarios/me/ics` | calendario |
| api | `GET /api/v1/recomendaciones?usuario_id=` | lista con `motivo` legible |
| api | `GET /api/v1/moderacion/pendientes` · `POST …/{id}/decision` | bandeja del moderador |
| api | `POST /api/v1/publicadores` · `POST …/{id}/aprobar` · `POST …/{id}/fuentes` | alta |
| api | `POST /api/v1/auth/google` · `POST /api/v1/auth/whatsapp/codigo` · `…/verificar` | login |
| api | `GET /api/v1/usuarios/by-phone/{e164}` · `PATCH /api/v1/usuarios/me` | identidad y preferencias |
| api | `GET /api/v1/estadisticas` · `POST /api/v1/metrics/tokens` | panel y coste |
| bot | `POST /webhook/twilio` | entrada de WhatsApp |
| bot | `POST /notify` | `api` pide enviar un aviso (`Notificacion`) |
| bot | `POST /ai/extraer` · `POST /ai/spam` · `POST /ai/responder-ficha` · `POST /ai/preferencias` | IA bajo demanda |
| todos | `GET /health` | `{"status":"ok","version":"x.y.z"}` |

### 5.3 Reglas estrictas de integración

1. **Contract-first.** Ningún endpoint se programa sin estar antes en `openapi.yaml`. Ningún campo se usa sin estar en el schema.
2. **Cambiar un contrato = PR a `develop` con etiqueta `contract-change`**, aprobada por los otros dos. Solo se **añade** (campos opcionales nuevos); **nunca se renombra ni se borra** después de CP0. Si algo sobra, se ignora.
3. **Fixtures como verdad compartida.** Cada flujo tiene un test que valida que lo que produce/consume encaja con `contracts/fixtures/*.json` (Python: `jsonschema`; web: `ajv` o tipos generados con `openapi-typescript`).
4. **Tipos generados, no copiados.** C genera los tipos TS desde `openapi.yaml` (`npx openapi-typescript`). A y B usan modelos Pydantic alineados con los schemas.
5. **Configuración solo por variables de entorno**, todas listadas en `.env.example`. Nada de URLs ni claves escritas en el código.
6. **Puertos fijos:** api `8000`, bot `8001`, web `8080`, db `5432`. Nombres de servicio en compose: `api`, `bot`, `web`, `db`, `tunnel`.
7. **Cada servicio arranca solo** (aunque los demás estén caídos) y expone `/health`. El bot sin API responde «Estamos teniendo un problema, inténtalo en un minuto» y guarda el mensaje en cola.
8. **Nada de secretos en el repo.** `.env` en `.gitignore`. Las claves se pasan por mensaje privado.
9. **Smoke test** (`scripts/smoke_test.sh`) que se ejecuta antes de cada merge a `develop`: `docker compose up -d` → `/health` de todo → crear evento → listarlo → inscribirse → notificación por consola.

### 5.4 Ramas y commits

- `main`: solo versiones estables y etiquetadas (`v0.1`, `v0.2`, … `v1.0`). Protegida: nadie hace push directo.
- `develop`: rama de integración. Se actualiza **solo en los checkpoints** (o por PR revisada).
- Ramas de trabajo, **una por flujo y tarea**:
  - Flujo A: `feat/api-<tarea>` (p. ej. `feat/api-eventos`, `feat/api-auth`)
  - Flujo B: `feat/bot-<tarea>` (p. ej. `feat/bot-webhook`, `feat/bot-extractor`)
  - Flujo C: `feat/web-<tarea>` (p. ej. `feat/web-mapa`, `feat/web-panel`)
  - Contratos: `contract/<cambio>` · Infra: `infra/<cambio>` · Arreglos: `fix/<servicio>-<bug>`
- **Commits pequeños y frecuentes** (mínimo cada hora de trabajo), formato Conventional Commits:
  `feat(api): inscripción con lista de espera` · `fix(bot): timeout en Gemini` · `docs: actualizar README`.
- Antes de abrir PR: `git fetch && git rebase origin/develop` y pasar el smoke test.
- PR pequeñas (<400 líneas si se puede). Revisión rápida de otro dev (5 minutos, no más).
- Conflictos: los resuelve **quien abre la PR**. Si tocan `contracts/`, se resuelven en llamada entre los 3.

### 5.5 Docker (presentación) y despliegue alternativo

- `infra/docker-compose.yml` con los servicios `db` (imagen `pgvector/pgvector:pg16`), `api`, `bot`, `web` (build de Vite servido por nginx) y `tunnel` (`cloudflare/cloudflared`) que da la **URL HTTPS pública** para el webhook de Twilio y para que el jurado abra la web.
- Arranque: `cp .env.example .env` → rellenar claves → `docker compose --env-file .env -f infra/docker-compose.yml up --build`.
- `scripts/demo_reset.sh` deja la base de datos en el estado inicial de la demo (`seed.py`).
- **Plan B de despliegue** (sin cambiar código): cada servicio tiene su `Dockerfile` → se puede subir tal cual a Render/Railway (api y bot), Vercel/Netlify (web estática) y Supabase/Neon (Postgres con pgvector), cambiando solo variables de entorno.

---

## 6. Cronograma inverso (hora de Madrid)

> Ahora: viernes 16:30. Objetivo: domingo 07:00. Son ~38 h; **hay que dormir** (equipos que no duermen rompen la integración de madrugada). Reservado: **6 h el viernes** y **turnos de 2 h el sábado por la noche**.

| Cuándo | Hito | Qué se hace | Commit / etiqueta |
|---|---|---|---|
| **Vie 17:00–17:30** | Kickoff | Leer este plan, decidir enfoque (§2), asignar Dev A/B/C, crear cuentas: Twilio sandbox, Google OAuth, claves IA (Claude, Gemini AI Studio). | — |
| **Vie 17:30–18:30** | **CP0 · Contratos congelados** | A: esqueleto del repo, compose con `/health` de los 4 servicios. Los 3 juntos: `openapi.yaml`, schemas, enums y fixtures v1. | `chore: esqueleto` · `contract: v1` → `develop` |
| Vie 18:30–23:30 | Bloque 1 | **A:** modelos + CRUD eventos/publicadores/usuarios + seed. **B:** webhook Twilio + acuse + `llm_router` + extractor de eventos (texto). **C:** proyecto Ionic React (pestañas Agenda · Mapa · Perfil), agenda, mapa y ficha con mocks; dejar instalando Android Studio. | commits cada hora en `feat/*` |
| Vie 21:00 | Sync 10 min | ¿Bloqueos? ¿Cambio de contrato necesario? | — |
| **Vie 23:30–00:30** | **CP1 · Primera integración** | Merge de las 3 ramas a `develop`. `docker compose up` limpio. Prueba: la web lista eventos reales de la API; WhatsApp → bot → crea evento en la API. | tag `v0.1` |
| Sáb 00:30–07:30 | Dormir | Todos. Móviles cargando. | — |
| Sáb 08:00–13:00 | Bloque 2 · Flujo «Facebook → agenda» | **A:** `importar`, confirmar, niveles de confianza y moderación, duplicados. **B:** conversación del publicador (pregunta lo que falta, confirma por audio), Whisper, antispam. **C:** panel del moderador (bandeja con motivo) y vista del publicador. | commits cada hora |
| **Sáb 13:00–14:00** | **CP2 · Demo pasos 1–3** | Post/audio → ficha → confirma por WhatsApp → moderación (uno aprobado, otro parado). | tag `v0.2` |
| Sáb 14:00–19:00 | Bloque 3 · Flujo «vecina» | **A:** recomendador con motivo, inscripciones + lista de espera, `.ics`, chat del evento, cambio de hora → `/notify`. **B:** conversación del vecino (gustos, «qué hay cerca»), avisos, asistente del evento. **C:** perfil + login Google, inscribirse, chat del evento, PWA. | commits cada hora |
| **Sáb 19:00–20:00** | **CP3 · Demo pasos 4–7 + CONGELACIÓN DE CONTRATOS v2** | Recorrido completo de la demo. A partir de aquí **no se cambian contratos**. | tag `v0.3` |
| Sáb 20:00–00:00 | Bloque 4 · Criterios del jurado y extras | **A:** estadísticas, métricas de tokens, despliegue alternativo (opcional). **B:** fallback entre proveedores + botón «simular caída», respuesta en audio, idiomas. **C:** panel de estadísticas y coste, accesibilidad AA, modo letra grande, **APK con Capacitor** apuntando a la URL pública. | commits cada hora |
| **Dom 00:00–00:30** | **CP4 · Feature freeze** | Merge a `develop`. A partir de aquí **solo arreglos** (`fix/*`). | tag `v0.9` |
| Dom 00:30–03:00 | Estabilización (turnos) | Turno 1 (dos personas): bugs del smoke test y de la demo. La tercera duerme 2 h. | `fix/*` |
| Dom 03:00–05:00 | **Prueba E2E en limpio** | Clonar el repo en **otro portátil**, `docker compose up --build` desde cero, ejecutar el guion de la demo 2 veces. Turno de sueño rota. | `fix/*` |
| Dom 05:00–06:30 | Revisión final | README (arranque en 3 comandos), capturas, **APK final instalado en un móvil**, **vídeo de respaldo de la demo** (por si falla la red), guion de presentación de 3 min. | `docs: …` |
| **Dom 06:30–07:00** | **RELEASE** | Merge `develop` → `main`, etiqueta `v1.0`. Última prueba de humo sobre `main`. | tag `v1.0` ✅ |
| Dom 07:00–11:00 | Margen | Descansar, ensayar la demo, arreglos críticos solo si algo se rompe (en `hotfix/*` sobre `main`). | — |

### Checklist de cada checkpoint (CP1–CP4)

1. Cada dev hace `git rebase origin/develop` en su rama y pasa sus tests.
2. PR a `develop`, revisión cruzada rápida, merge en orden **A → B → C** (datos primero).
3. `docker compose down -v && docker compose up --build` en una máquina.
4. `scripts/smoke_test.sh` en verde.
5. Probar a mano los pasos de la demo que tocan en ese checkpoint.
6. Etiquetar y anotar en el README lo que funciona y lo que no.
7. Si algo no llega: **se recorta alcance, no se retrasa el checkpoint**.

---

## 7. Definition of Done (para cualquier tarea)

- Cumple el contrato y tiene al menos un test o una prueba manual documentada.
- Funciona dentro de Docker (no solo en el portátil).
- Sin claves en el código; variables nuevas añadidas a `.env.example`.
- Accesible: botones con texto, contraste correcto, funciona con teclado (web).
- Si usa IA: tiene timeout, fallback y registra tokens.

## 8. Preguntas abiertas para la organización (Telegram)

- ¿Qué hay que entregar exactamente el domingo a las 11:00 (repo, URL, vídeo, presentación)? ¿Dónde?
- ¿Se puede traer código o plantillas preparados antes del evento?
- ¿Cuánto dura la demo final y en qué formato?
- ¿Hay créditos de APIs de IA o cuentas de WhatsApp facilitadas por la organización?
