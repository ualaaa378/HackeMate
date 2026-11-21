# Cómo probar la primera versión (v1) y qué revisar

Escrito el sábado 21/11 a las 09:20 por el flujo A. Probado en el portátil de Benas (Windows, **sin Docker**), con la API de `Flujo-A` (que ya integra `develop` hasta el PR #34) y el bot de `develop`.

## 0. ¿Podemos empezar las pruebas? **Sí.** Cómo empezar

La API está completa (todas las rutas del contrato), el bot de `develop` es compatible con ella y el guion funciona de punta a punta en local (§4). Lo que falta es probarlo **con Docker y Telegram de verdad**, y eso no se puede hacer en el portátil de Benas. Por eso empieza quien tenga Docker (Adán o Fran), en este orden:

1. **Mergear la PR de `Flujo-A` → `develop`** (la revisa cualquiera del equipo; está en verde) y hacer `git pull` de `develop`.
2. **Arrancar desde cero:** `docker compose -f infra/docker-compose.yml down -v` (borra la base de datos vieja para probar la migración 0007 en PostgreSQL), `cp .env.example .env` con las claves y `docker compose -f infra/docker-compose.yml up --build`.
3. **Smoke test:** `scripts/smoke_test.sh` → «SMOKE TEST EN VERDE». Si falla: `docker compose -f infra/docker-compose.yml logs api` y avisar a Benas con el error.
4. **Guion sin móvil:** `docker compose -f infra/docker-compose.yml exec bot python - < scripts/simular_chat.py`, o `python scripts/simular_chat.py` desde fuera (usa `localhost:8001`). Se compara con la tabla de §4.
5. **Guion con Telegram:** registrar el webhook con la URL del túnel (§3, opción B) y hacer los siete pasos del guion desde el móvil, con la web abierta en `http://localhost:8080`, y el panel con `DEMO_MODE=true`.
6. **Apuntar cada fallo** en `README.md` § «Pendiente entre flujos», bajo el flujo que lo tiene que arreglar (la API es del flujo A, el bot del B y la web del C), con el paso del guion y lo que se esperaba.
7. Entre ensayos: `scripts/demo_reset.sh` deja los datos como al principio en 1–2 s.

Mientras tanto, **sin Docker**, Benas puede repetir la prueba local de §3 (opción A) después de cada cambio de la API.

## 1. Estado de la sincronización

| Rama | Qué lleva | Estado |
|---|---|---|
| `develop` | Flujo B hasta el PR #34 (planes terminados → 409 `evento_finalizado`) y lo último de C | Al día en GitHub |
| `Flujo-A` | Toda la API del flujo A (H2–H5 y peticiones de B y C) **+ `develop` integrado** | Subida el 21/11 con su PR a `develop`, pendiente de merge |
| Ramas `claude/project-thread-*` de Adán | Tema verde y naranja, revisión a mano o automática, `VITE_CANAL` y planes pasados | Sin PR abierta: Adán decide si van a `develop` |

**Cuando se suba `Flujo-A`**, cada uno hace en su rama:

```bash
git fetch origin
git merge origin/develop        # después de que Benas mergee la PR de Flujo-A
```

No hay cambios incompatibles en el contrato: todo lo nuevo son campos o rutas opcionales (lista en `README.md` § «Pendiente entre flujos» → «Ya resuelto»).

## 2. Pruebas automáticas (cada uno en su carpeta)

| Servicio | Comando | Resultado hoy |
|---|---|---|
| api | `cd services/api && python -m pytest -q` | **566 en verde** (~3 min) |
| bot | `cd services/bot && python -m pytest -q` | **108 en verde** (hace falta `pip install -r requirements.txt`; sin `python-multipart` no arrancan) |
| web | `cd apps/web && npm ci && npm run test:unit` (y `npm run test:e2e` con Playwright) | Sin probar aquí: el portátil de Benas no tiene Node. **Que lo pase Adán** |

## 3. Prueba manual de todo el sistema

### Opción A · Sin Docker (Windows, como en el portátil de Benas)

Tres terminales, desde la raíz del repo:

```bash
# 1) Datos de la demo desde cero (~2 s)
bash scripts/demo_reset.sh --local            # o .\scripts\demo_reset.ps1

# 2) API apuntando al bot local (¡importante! el valor por defecto bot:8001 solo existe en Docker)
cd services/api && DEMO_MODE=true BOT_URL=http://localhost:8001 python -m uvicorn app.main:app --port 8000

# 3) Bot en modo consola (no hacen falta claves; sin IA usa reglas)
cd services/bot && CANAL=console API_URL=http://localhost:8000 python -m uvicorn app.main:app --port 8001
```

En PowerShell, las variables se ponen antes: `$env:BOT_URL='http://localhost:8001'; $env:DEMO_MODE='true'; python -m uvicorn app.main:app --port 8000`.

Después:

```bash
bash scripts/smoke_test.sh          # debe acabar en «SMOKE TEST EN VERDE»
python scripts/simular_chat.py      # el guion por el chat, sin Telegram
python scripts/simular_chat.py +34600000201 "¿Qué hay este finde?"   # un mensaje suelto
```

La web (quien tenga Node): `cd apps/web && npm ci && npm run dev` con `VITE_API_URL=http://localhost:8000` y `VITE_USE_MOCKS=false` en `apps/web/.env.local`.

### Opción B · Con Docker (Adán o Fran)

```bash
cp .env.example .env               # y rellenar TELEGRAM_TOKEN, INTERNAL_TOKEN, claves de IA (por privado)
docker compose -f infra/docker-compose.yml up --build
scripts/smoke_test.sh
docker compose -f infra/docker-compose.yml logs tunnel     # URL pública → registrar el webhook de Telegram
```

Con un túnel rápido, la URL cambia en cada arranque. Se registra sin reiniciar con `POST localhost:8001/admin/webhook-telegram` (ver `services/bot/PARA_FLUJO_A.md` §4). Así se prueba con `@HackeMate_bot` desde un móvil de verdad.

### Personas de la demo (fixtures)

| Quién | Contacto | Para qué |
|---|---|---|
| Publicador (asociación con confianza) | `+34600000101` | Pasos 1 y 2: su post se publica directamente |
| Carmen, vecina de Senés (aviso en audio) | `+34600000201` · id `5a5e0000-0000-4000-8000-000000000001` | Pasos 4 a 7 |
| Moderador | `POST /api/v1/auth/demo {"rol":"moderador"}` (con `DEMO_MODE=true`) | Paso 3 en el panel |
| II Ruta Solidaria | id `1e5d0000-0000-4000-8000-000000000001` | Recomendación, chat y cambio de hora |

## 4. Resultado de la prueba de hoy, paso a paso del guion

| Paso | Qué se hizo | Resultado |
|---|---|---|
| 1. Post → ficha | El publicador manda el post del taller de esparto | 🟡 La ficha sale con todos los campos, pero **sin IA el título es el post entero recortado** (bot, reglas) |
| 2. El publicador confirma | «sí» | 🟢 «¡Publicado!», sale en la agenda |
| 3. Moderador y antispam | `GET /moderacion/pendientes` | 🟢 Dos pendientes: el grafiti (publicador de nivel 0) y el de apuestas (`score_spam` 0,95). 🟡 Un post de apuestas **nuevo** mandado por el bot sin fecha se queda en «¿Qué día…?» y no llega al antispam |
| 4. Recomendación e inscripción | Carmen: «¿Qué planes hay este finde?» y apuntarse | 🟢 La Ruta Solidaria sale primera, con el motivo; inscripción `confirmada` |
| 5. Pregunta en el chat del evento | `POST /eventos/{ruta}/mensajes` | 🟢 Responde con la ficha (recorrido corto de 4 km). 🟡 La misma pregunta **por el chat privado del bot** no se responde: enseña la ficha |
| 6. Cambio de hora → aviso | `PATCH /eventos/{ruta}` con la nueva hora | 🟢 Anuncio fijado en el chat y `POST /notify` al bot (200). Con `BOT_URL` mal puesto, los avisos quedan en cola y salen solos en el siguiente reintento |
| 7. Persona mayor con audios | — | ⚪ Sin probar: hace falta Telegram real y claves de IA (transcripción) |
| Web y panel | — | ⚪ Sin probar aquí (no hay Node) |

## 5. Qué revisar para empezar a arreglar (por prioridad)

1. **🔴 Ensayo con Telegram real y claves de IA (B + quien tenga Docker).** Es lo único que no se ha probado de punta a punta: el webhook por el túnel, las notas de voz (paso 7), el aviso en audio para Carmen y los botones [Apuntarme] [Más info]. Hay que probarlo cuanto antes.
2. **🔴 Avisos a usuarios solo de Telegram (A + B, decisión).** El contrato de `/notify` exige `telefono`. Quien no haya compartido su número no recibe el aviso del cambio de hora. Para la demo basta con que los inscritos compartan su número; para después, hay que decidir el cambio de contrato.
3. **🟡 Web contra la API real (C).** Pasar `npm run test:unit` y `test:e2e` y recorrer la agenda, la ficha, la inscripción, el chat y el panel del moderador con `VITE_USE_MOCKS=false` contra la API de `Flujo-A` (cuando se suba).
4. **🟡 Calidad sin IA (B).** El título por reglas, la pregunta por el chat privado y el post de spam sin fecha (ver §4). Si la IA se cae en la demo, se notará.
5. **🟡 `BOT_URL` y `API_URL` en local.** Cualquiera que pruebe sin Docker tiene que ponerlos a `localhost` (ver §3). Si no, los avisos no salen y parece un fallo.
6. **⚪ PostgreSQL real.** La migración 0007 solo se ha probado con SQLite. Basta con levantar el compose una vez con la base vacía y ver que la API arranca.
7. **⚪ Dudas de Benas** (en `.claude/bucle-estado.md`): el código de verificación queda en claro en la cola de avisos y `/auth/demo` solo funciona con `DEMO_MODE=true`.

Para reiniciar después de cada ensayo: `scripts/demo_reset.sh --local` (o sin `--local` en Docker).
