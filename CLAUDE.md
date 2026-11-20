# HackeMate · Reactiva tu pueblo

Hackathon UAL para el Desarrollo del Interior, **reto 1 «Reactiva tu pueblo»** (20–22 nov 2026).
Prioridad absoluta: **una demo que funcione**. Entre una funcionalidad pulida y dos que funcionan, elegimos las dos.

Documentos que mandan (léelos antes de tocar nada):
- `docs/PLAN.md`: plan general, arquitectura, contratos, ramas y cronograma.
- `docs/PLAN_FLUJO_A.md`: hitos y criterios de aceptación del flujo A (backend, datos, infra).
- `docs/PLAN_FLUJO_B.md`: bot, canales de mensajería e IA. Qué expone el bot, qué decisiones se tomaron y qué necesita de A y C.
- `docs/PLAN_FLUJO_C.md`: hitos y criterios de aceptación de la app web/PWA y el panel (flujo C).
- `docs/PROGRESO.md`: checklist de avance. Se marca en el mismo commit que la tarea.

## Qué construimos

Una plataforma con tres puertas sincronizadas para cinco pueblos de Almería (Lucainena de las Torres, Senés, Velefique, Uleila del Campo y Tahal):
- **Bot de mensajería con IA**: publicadores, vecinos y moderador pueden hacerlo todo por ahí. **Canal activo: Telegram** (`@HackeMate_bot`, gratis y sin límites). WhatsApp Cloud API está programado pero Meta bloquea el envío hasta que una entidad verifique su negocio (ver `PLAN_FLUJO_B.md` §3). Donde el plan dice «por WhatsApp», hoy es «por Telegram».
- **App Ionic React** (web/PWA + APK Android con Capacitor): agenda, mapa, ficha, inscripción, chat del evento.
- **Panel** del moderador y de estadísticas.

Guion de la demo (lo que TIENE que funcionar): post/audio → ficha · el publicador confirma por WhatsApp · el moderador aprueba uno y el antispam para otro · a una vecina le llega la recomendación y se apunta · pregunta en el chat del evento · cambio de hora → aviso a los inscritos · una persona mayor lo usa solo con audios.

## Stack y responsables

| Servicio | Carpeta | Flujo | Stack | Puerto |
|---|---|---|---|---|
| `api` | `services/api/` | A · Benas (+ Juan Carlos) | FastAPI + SQLAlchemy + Alembic + PostgreSQL (pgvector) / SQLite en local | 8000 |
| `bot` | `services/bot/` | B · Francisco | FastAPI · Telegram Bot API (activo) · WhatsApp Cloud API de Meta y Twilio (alternativas) · `llm_router` (Gemini → FreeLLMAPI → Claude → reglas) | 8001 |
| `web` | `apps/web/` | C · Adán | Ionic React + Vite + react-leaflet, Capacitor | 8080 |
| `db` | — | A | `pgvector/pgvector:pg16` | 5432 |
| `tunnel` | — | A | `cloudflare/cloudflared` (HTTPS público para el webhook) | — |

**Nadie edita la carpeta de otro flujo** sin avisar y sin PR. Los stubs de `infra/stubs/` existen solo para que el compose arranque hasta que B y C integren sus servicios en `develop`.

## Reglas de arquitectura (nadie las rompe)

- Solo `api` toca la base de datos. `bot` y `web` hablan con `api` por HTTP.
- Solo `bot` habla con los canales de mensajería (Telegram, WhatsApp/Meta, Twilio) y con los proveedores de IA. Si `api` necesita IA, llama a `bot` en `POST /ai/...`.
- Coste 0 en desarrollo: no se añaden servicios de pago como predeterminados. No se inventan datos para verificaciones de cuentas (Meta u otras).
- Solo `api` decide estados. La IA propone, la API valida, una persona decide lo importante.
- Toda notificación saliente la pide `api` a `bot` con `POST /notify`. Si el bot está caído, se guarda en cola.
- Entre servicios: cabecera `X-Internal-Token: ${INTERNAL_TOKEN}`. Usuarios: `Authorization: Bearer <jwt>`.

## Contratos (`contracts/`) · contract-first

- `openapi.yaml`, `schemas/*.json` (JSON Schema 2020-12), `enums.md` y `fixtures/*.json`.
- Ningún endpoint se programa sin estar antes en `openapi.yaml`; ningún campo se usa sin estar en el schema.
- Después de CP0 solo se **añaden** campos opcionales, por PR a `develop` con etiqueta `contract-change`. Nunca se renombra ni se borra.
- `services/api/tests/test_contratos.py` valida todos los fixtures contra los schemas y comprueba que los endpoints de `PLAN.md` §5.2 están en `openapi.yaml`.

Convenciones de la API: JSON en snake_case y en español sin tildes (`fecha_inicio`); IDs UUID v4; fechas ISO 8601 con zona (`Europe/Madrid`); rutas bajo `/api/v1/`; paginación `{items, total, page, size}`; errores siempre `{"error": {"code", "message", "details"}}`.

## Cómo ejecutar

### En Windows (portátil de Benas): SIN Docker

**En este portátil no se puede ejecutar Docker Desktop ni WSL2. No ejecutes `docker` ni `docker compose` aquí.** Todo el desarrollo y las pruebas locales del flujo A van con Python nativo:

```powershell
cd services\api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
copy ..\..\.env.example ..\..\.env     # y ajustar DATABASE_URL
python ..\..\scripts\seed.py            # crea las tablas y carga los datos de la demo (repetible; --reset la vacía antes)
uvicorn app.main:app --reload --port 8000
python -m pytest -q
```

- Sin `.env`, la API usa SQLite en `services/api/hackemate.db` (da igual desde qué carpeta se lance).
- El seed carga los eventos con sus fechas reales y **omite los que ya han terminado**; si ya estaban en la base, los borra con sus inscripciones y mensajes. Volver a sembrar cada día deja la agenda al día. Solo toca los datos de `contracts/fixtures`, nunca lo creado por los usuarios (salvo con `--reset`).

- Base de datos local: `DATABASE_URL=sqlite:///./hackemate.db`, o una PostgreSQL externa (Neon/Supabase) en `.env`. El código no debe depender de nada exclusivo de PostgreSQL sin un camino alternativo para SQLite (p. ej. pgvector es opcional).
- **SQLAlchemy en este portátil:** el Control de aplicaciones de Windows bloquea sus extensiones compiladas (`DLL load failed while importing _util_cy`). Después de `pip install -r requirements-dev.txt`, reinstalarla en Python puro:
  ```powershell
  $env:DISABLE_SQLALCHEMY_CEXT='1'; python -m pip install --force-reinstall --no-deps --no-binary sqlalchemy sqlalchemy==2.1.9
  ```
  No cambia el código: SQLAlchemy funciona igual, solo algo más lento. En Docker (Linux) se usa el wheel normal.
- Python local: 3.15. PyYAML no tiene wheel para 3.15: para leer YAML se usa `ruamel.yaml`, y `uvicorn` va **sin** el extra `[standard]` (lo arrastraría). No añadas dependencias que necesiten PyYAML.

### Con Docker (otras máquinas, demo y E2E)

`infra/docker-compose.yml` y los `Dockerfile` se mantienen igualmente al día; los valida un compañero en su máquina.

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up --build
curl localhost:8000/health
```

## Convenciones de código

- Identificadores, comentarios y textos en **español**, sin tildes ni eñes en los identificadores (`publicacion`, `ano`, `municipio_id`).
- Configuración solo por variables de entorno (`pydantic-settings`), todas listadas en `.env.example`. Nada de URLs ni claves en el código.
- SQL siempre a través de SQLAlchemy o con parámetros, nunca con f-strings.
- Comentarios solo donde aporten algo que el código no dice.
- Cada servicio arranca aunque los demás estén caídos y expone `GET /health` → `{"status":"ok","version":"x.y.z"}`.

## Git

- `main`: solo versiones probadas y etiquetadas. `develop`: integración en los checkpoints. Trabajo del flujo A en `Flujo-A` o `feat/api-<tarea>`.
- Conventional Commits pequeños y frecuentes: `feat(api): …`, `fix(api): …`, `contract: …`, `chore: …`, `docs: …`.
- Merge en cada checkpoint en orden **A → B → C**.
- `.env` nunca se sube. Las claves se pasan por mensaje privado.
- Si algo bloquea más de ~20 minutos, se simplifica o se recorta.
