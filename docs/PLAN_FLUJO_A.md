# PLAN_FLUJO_A.md · Backend, datos e infraestructura

> Hackathon UAL para el desarrollo del interior · Reto 1 «Reactiva tu pueblo» · 20–22 nov 2026
> Responsable del flujo A: **Benas Sapogas** (Dev A)
> Documento de dirección de proyecto. Complementa a `docs/PLAN.md` (plan general) y `docs/PROGRESO.md` (checklist). Si algo choca, manda `PLAN.md` y se corrige este archivo.
> Horas en **hora de Madrid**. Plan redactado el viernes 20 nov a las 17:05.

---

## 1. Objetivo del flujo A

**Ser la columna vertebral de la plataforma: la única fuente de verdad de los datos y de los estados.**

Todo lo que pasa en WhatsApp (flujo B) y en la app/web/panel (flujo C) acaba en la API del flujo A. Si A no funciona, no hay demo; si A funciona y B o C fallan, al menos se puede enseñar algo. Por eso el flujo A es la **ruta crítica** del equipo.

En concreto, el flujo A tiene que:

1. **Definir y custodiar los contratos** (`contracts/`): schemas, enums, OpenAPI y fixtures. Los demás trabajan contra ellos desde el minuto 1.
2. **Levantar la infraestructura**: `docker compose up` arranca `db`, `api`, `bot`, `web` y `tunnel` y da una URL HTTPS pública.
3. **Construir la API REST** (`services/api/`) con toda la lógica de reglas: eventos, publicadores, usuarios, moderación con niveles de confianza, duplicados, inscripciones con lista de espera, chat del evento, `.ics`, recomendador y estadísticas.
4. **Decidir los estados.** La IA (flujo B) propone; la API valida y aplica las reglas; una persona decide lo importante.
5. **Pedir los avisos**: cualquier notificación por WhatsApp la dispara la API llamando a `bot POST /notify`.

### Qué NO es del flujo A

- Hablar con Twilio, Claude, Gemini o Whisper (es de B). Si A necesita IA, llama a `bot /ai/*`.
- Pantallas (es de C).
- Editar `services/bot/` o `apps/web/` sin PR.

---

## 2. Entregables

| # | Entregable | Dónde | Lo consume | Prioridad |
|---|---|---|---|---|
| E1 | Contratos v1: `openapi.yaml`, `schemas/*.json`, `enums.md`, `fixtures/*.json` | `contracts/` | B y C | **Imprescindible** |
| E2 | `docker-compose.yml` con los 5 servicios, `/health` y túnel HTTPS | `infra/` | Todos | **Imprescindible** |
| E3 | `.env.example` con todas las variables | raíz | Todos | **Imprescindible** |
| E4 | Modelo de datos + migraciones Alembic | `services/api/` | — | **Imprescindible** |
| E5 | API de eventos (CRUD + filtros por pueblo, categoría, fechas y radio) | `services/api/` | C (agenda, mapa), B | **Imprescindible** |
| E6 | Ingesta: `POST /eventos/importar` + `POST /eventos/{id}/confirmar` + duplicados | `services/api/` | B | **Imprescindible** (demo pasos 1–2) |
| E7 | Moderación: niveles 0/1/2, bandeja con motivo, decisión, pausar | `services/api/` | B, C | **Imprescindible** (demo paso 3) |
| E8 | Publicadores y usuarios, `by-phone`, alta con código de WhatsApp | `services/api/` | B, C | **Imprescindible** |
| E9 | Inscripciones con plazas y lista de espera | `services/api/` | B, C | **Imprescindible** (demo paso 4) |
| E10 | Recomendador con motivo legible | `services/api/` | B, C | **Imprescindible** (demo paso 4) |
| E11 | Chat del evento (mensajes, anuncios fijados, permisos) | `services/api/` | B, C | **Imprescindible** (demo paso 5) |
| E12 | Cambio de hora → `/notify` a todos los inscritos | `services/api/` | B | **Imprescindible** (demo paso 6) |
| E13 | Login con Google (OAuth → JWT) y roles | `services/api/` | C | Importante (criterio jurado) |
| E14 | Exportación `.ics` por evento y por usuario | `services/api/` | C, B | Importante |
| E15 | `GET /estadisticas` y `POST /metrics/tokens` | `services/api/` | C (panel) | Importante (criterio «coste en tokens») |
| E16 | `seed.py` con los 5 pueblos y datos de demo realistas + `demo_reset.sh` | `scripts/` | Todos | **Imprescindible** |
| E17 | `smoke_test.sh` | `scripts/` | Todos | **Imprescindible** |
| E18 | Despliegue alternativo (Render/Railway + Neon/Supabase) | — | Jurado | Opcional |

**Regla de recorte:** si vamos tarde, se recorta de abajo a arriba en «Importante» y «Opcional»; nunca algo que pida un paso de la demo.

---

## 3. Hitos

Cada hito termina en un checkpoint de equipo (CP) de `PLAN.md`. Al terminar un hito, avisas en el hilo y reviso el repositorio contra los **criterios de aceptación**. Si no se cumplen todos los marcados como imprescindibles, el hito no se da por cerrado y decidimos juntos si se recorta o se arregla.

### H0 · Arranque y contratos congelados (vie 17:30 → 18:30 · CP0)

**Tareas**
- [x] H0.1 Confirmar enfoque (Opción 1 de `PLAN.md` §2) y el reparto de personas (ver §6, punto 1).
- [~] H0.2 Crear ramas `main` (protegida) y `develop`; estructura de carpetas del monorepo. *(Ramas y carpetas hechas; falta proteger `main` en GitHub.)*
- [~] H0.3 `infra/docker-compose.yml` con `db` (pgvector/pg16), `api`, `bot`, `web`, `tunnel`. Un `/health` mínimo en `api` (y stubs vacíos para `bot` y `web` si los otros aún no han empezado). *(Escrito; falta validarlo con Docker en otra máquina.)*
- [x] H0.4 `.env.example` con todas las variables conocidas (`DATABASE_URL`, `INTERNAL_TOKEN`, `JWT_SECRET`, `GOOGLE_CLIENT_ID`, `BOT_URL`, `API_URL`, claves IA, Twilio…).
- [x] H0.5 Con B y C: `contracts/openapi.yaml` v1, `schemas/*.json` (evento, extraccion_evento, usuario, publicador, inscripcion, mensaje_evento, notificacion), `enums.md`, `fixtures/*.json`.
- [~] H0.6 Commit `chore: esqueleto` y `contract: v1` en `develop`. *(Commits hechos en `Flujo-A`; falta push y PR a `develop`.)*

#### Cómo probar H0 (lo hace otra persona del equipo con Docker; el portátil de Benas no puede ejecutarlo)

**Requisitos:** Git, Docker con Compose **2.24 o superior** (`docker compose version`; el compose usa `env_file` con `path`/`required`), Python 3.11+ y `curl`.

**1. Descargar la rama del flujo A** (hasta que esté en `develop`):
```bash
git clone https://github.com/ualaaa378/HackeMate.git && cd HackeMate   # o: git fetch origin
git checkout Flujo-A && git pull
```

**2. Tests de contratos y de `/health`** (sin Docker):
```bash
cd services/api
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m pytest -q                # esperado: 23 passed
deactivate && cd ../..
```

**3. Arrancar todo con Docker en limpio:**
```bash
cp .env.example .env               # Windows: copy .env.example .env  (no hace falta rellenar claves para H0)
docker compose -f infra/docker-compose.yml down -v
docker compose -f infra/docker-compose.yml up --build -d
docker compose -f infra/docker-compose.yml ps   # db "healthy"; api, bot, web y tunnel "running"
```

**4. Comprobar cada servicio:**
```bash
curl localhost:8000/health   # api        → {"status":"ok","version":"0.0.1"}
curl localhost:8001/health   # bot (stub) → {"status":"ok","version":"0.0.0-stub"}
curl localhost:8080/health   # web (stub) → {"status":"ok","version":"0.0.0-stub"}
docker compose -f infra/docker-compose.yml logs tunnel | grep trycloudflare   # una URL https://…trycloudflare.com
```

**5. Comprobar que no hay claves en el repositorio:**
```bash
git grep -nE "sk-ant-|AIza[0-9A-Za-z_-]{20}|AC[0-9a-f]{32}|-----BEGIN"   # esperado: sin resultados
```

**6. Apagar:** `docker compose -f infra/docker-compose.yml down -v`

**7. Informar del resultado:**
- Todo bien → en `docs/PROGRESO.md`, CP0, cambiar la línea del compose de `[~]` a `[x]` y avisar a Benas.
- Algo falla → apuntarlo en «Bloqueos» de `docs/PROGRESO.md` con el paso, el comando y el error (por ejemplo, `docker compose -f infra/docker-compose.yml logs api`), y avisar a Benas.

**Alcance de los fixtures en H0:** solo datos base válidos contra los schemas (5 municipios, publicadores, usuarios, eventos publicados, la extracción de la Ruta Solidaria, inscripciones, mensajes y notificaciones). Los escenarios de moderación y antispam no entran en H0: se definen en H2 junto con su lógica.

**Criterios de aceptación**
- ✅ `docker compose -f infra/docker-compose.yml up --build` arranca sin errores en una máquina limpia.
- ✅ `curl localhost:8000/health` devuelve `{"status":"ok","version":"…"}`.
- ✅ Los 7 schemas existen y **todos los fixtures validan** contra ellos (un test `jsonschema` lo comprueba).
- ✅ Cada endpoint de la tabla de `PLAN.md` §5.2 aparece en `openapi.yaml`, aunque sea sin implementar.
- ✅ B y C confirman que pueden empezar con los fixtures sin preguntar nada más.
- ✅ No hay ninguna clave en el repo (`git grep -i "key\|secret"` solo encuentra `.env.example`).

### H1 · Datos y CRUD básico (vie 18:30 → 23:30 · CP1 · `v0.1`)

**Tareas**
- [ ] H1.1 Modelos SQLAlchemy y migración inicial con Alembic (eventos, publicadores, fuentes, usuarios, preferencias, inscripciones, mensajes, métricas).
- [ ] H1.2 Formato común de error y paginación (middleware/utilidades).
- [ ] H1.3 `GET /eventos` con filtros: `municipio`, `categoria`, `desde`, `hasta`, `lat`+`lon`+`radio_km` (haversine). `GET/POST/PATCH /eventos/{id}`.
- [ ] H1.4 CRUD de publicadores y usuarios, `GET /usuarios/by-phone/{e164}`, `PATCH /usuarios/me`.
- [ ] H1.5 Protección entre servicios con `X-Internal-Token`.
- [ ] H1.6 `scripts/seed.py`: Lucainena de las Torres, Senés, Velefique, Uleila del Campo y Tahal con coordenadas; 3–4 publicadores (Amigos de Velefique, Bar La Plaza…); 15–25 eventos realistas de las 6 categorías repartidos en las próximas 2 semanas, incluida la **II Ruta Solidaria** del guion.
- [ ] H1.7 Sync a las 21:00 con B y C (10 min).

**Criterios de aceptación**
- ✅ `alembic upgrade head` sobre una base vacía crea todas las tablas sin errores.
- ✅ Tras `seed.py`, `GET /api/v1/eventos` devuelve `{items, total, page, size}` con los eventos de demo.
- ✅ Filtro por radio: `GET /eventos?lat=<Senés>&lon=<Senés>&radio_km=10` devuelve los de Senés y pueblos cercanos y no los lejanos.
- ✅ Un `GET /eventos/<uuid-inexistente>` devuelve 404 con el formato `{"error":{"code":"evento_no_encontrado",…}}`.
- ✅ Las respuestas validan contra `contracts/schemas/evento.json` (test automático).
- ✅ **Integración CP1:** la web de C lista eventos reales de la API y un mensaje de WhatsApp de B crea un evento en la API.
- ✅ Etiqueta `v0.1` en `develop`.

### H2 · Del post a la agenda: ingesta y moderación (sáb 08:00 → 13:00 · CP2 · `v0.2`)

**Tareas**
- [ ] H2.1 `POST /eventos/importar`: recibe `ExtraccionEvento` + origen, la asocia al publicador (fuente → publicador → WhatsApp), crea el evento en `pendiente_confirmacion` y devuelve los campos que faltan.
- [ ] H2.2 Detección de duplicados: mismo `origen.url` → devuelve el existente; si no, similitud de título + fecha + municipio por encima de un umbral → se marca como posible duplicado.
- [ ] H2.3 `POST /eventos/{id}/confirmar` con los campos completados → pasa a moderación.
- [ ] H2.4 Niveles de confianza: nivel 0 todo a `en_revision`; nivel 1 pasa si es «lo habitual» (misma categoría que publicaciones ya aprobadas y `score_spam` bajo); nivel 2 pasa salvo spam alto. Subida de nivel automática tras N aprobaciones (N configurable, p. ej. 3).
- [ ] H2.5 `GET /moderacion/pendientes` (con `motivo`) y `POST /moderacion/{id}/decision` (aprobar, rechazar, retirar). Pausar publicador y pausar automatizaciones.
- [ ] H2.6 Alta de publicador: `POST /publicadores` → `POST /auth/whatsapp/codigo` + `/verificar` → `POST /publicadores/{id}/aprobar` → `POST /publicadores/{id}/fuentes`. El moderador recibe aviso vía `/notify`.
- [ ] H2.7 Seed con un publicador de nivel 2 (Bar La Plaza, «Menú del domingo») y uno de nivel 0 para la demo del antispam.

**Criterios de aceptación**
- ✅ Importar el fixture de la Ruta Solidaria crea un evento `pendiente_confirmacion` y la respuesta lista `faltan: ["plazas_totales","lugar"]`.
- ✅ Importar **dos veces** el mismo `origen.url` no crea un segundo evento.
- ✅ Confirmar con un publicador de nivel 0 → `en_revision`; con nivel 2 y spam bajo → `publicado`.
- ✅ Un evento con `score_spam` alto (el caso «apuestas» de Bar La Plaza) va a revisión aunque el publicador sea de confianza, y en la bandeja aparece el **motivo**.
- ✅ Un publicador pausado no puede publicar (403 con código claro).
- ✅ Solo los eventos `publicado` salen en `GET /eventos` público.
- ✅ **Integración CP2 (demo pasos 1–3):** post/audio → ficha → confirma por WhatsApp → el moderador aprueba uno y el antispam para otro, todo de punta a punta.
- ✅ Etiqueta `v0.2`.

### H3 · La vecina: participación (sáb 14:00 → 19:00 · CP3 · `v0.3` + contratos v2 congelados)

**Tareas**
- [ ] H3.1 Login con Google: `POST /auth/google` valida el `id_token` y devuelve un JWT propio con `rol`. Login por WhatsApp con código (reutiliza H2.6). Dependencias de FastAPI para exigir rol.
- [ ] H3.2 Inscripciones: `POST /eventos/{id}/inscripciones` y `DELETE …/{insc_id}`. Si no hay plazas → `lista_espera`. Al cancelar, el primero de la lista sube a `confirmada` y se le avisa vía `/notify`. Control de concurrencia (transacción con bloqueo de fila) para no vender la misma plaza dos veces.
- [ ] H3.3 `.ics`: `GET /eventos/{id}/ics` y `GET /usuarios/me/ics` (librería `ics` o generación a mano, zona `Europe/Madrid`).
- [ ] H3.4 Chat del evento: `GET/POST /eventos/{id}/mensajes`, anuncios fijados, ocultar, silenciar, con los permisos de la tabla de la diapositiva 17. Sin teléfonos en las respuestas. Antes de publicar un mensaje, llamada a `bot /ai/spam`; si es una pregunta, `bot /ai/responder-ficha`.
- [ ] H3.5 `PATCH /eventos/{id}` con cambio de `fecha_inicio` → `/notify` a **todos** los inscritos (tipo `cambio_evento`) + anuncio fijado automático en el chat.
- [ ] H3.6 Recomendador `GET /recomendaciones?usuario_id=`: puntuación = gustos + distancia (haversine) + fecha y plazas libres + historial (+ embeddings si da tiempo). Cada resultado lleva un `motivo` legible («te gusta el senderismo y quedan plazas»).
- [ ] H3.7 Congelar contratos v2 con B y C.

**Criterios de aceptación**
- ✅ Un usuario sin token puede leer la agenda y la ficha, pero no inscribirse (401).
- ✅ Un vecino no puede fijar anuncios ni ver la lista de inscritos (403); el organizador y el moderador sí.
- ✅ Evento con 1 plaza: el primero queda `confirmada`, el segundo `lista_espera`; si el primero cancela, el segundo pasa a `confirmada` y se genera una notificación.
- ✅ El `.ics` se importa sin errores en Google Calendar (prueba manual con captura).
- ✅ Cambiar la hora de la Ruta Solidaria genera una notificación por inscrito (se ve en el adaptador `console` de B o en el log).
- ✅ Para la vecina de demo (Carmen, le gusta el senderismo, vive en Senés), la Ruta Solidaria sale **primera** en sus recomendaciones con un motivo que lo explica.
- ✅ Ningún mensaje del chat expone un número de teléfono.
- ✅ **Integración CP3 (demo pasos 4–7):** recomendación → se apunta → pregunta en el chat → cambio de hora → aviso.
- ✅ Etiqueta `v0.3` y contratos v2 congelados.

### H4 · Criterios del jurado (sáb 20:00 → dom 00:00 · CP4 · `v0.9` feature freeze)

**Tareas**
- [ ] H4.1 `GET /estadisticas`: actividades del periodo, % importadas solas, inscripciones vs asistencia, ocupación por categoría, % de gente de otro pueblo, **solapamientos** entre pueblos (mismo día y franja, misma categoría o eventos grandes).
- [ ] H4.2 `POST /metrics/tokens` (B registra cada llamada) y acumulados de tokens y euros por proveedor en `/estadisticas`.
- [ ] H4.3 Marcar asistencia (`asistio`/`no_asistio`) para que el panel tenga datos reales; seed con eventos pasados para que las gráficas no salgan vacías.
- [ ] H4.4 URL pública estable: túnel de Cloudflare funcionando para el jurado. **Opcional:** despliegue alternativo en Render/Railway + Neon/Supabase.
- [ ] H4.5 Revisión de robustez: la API arranca aunque `bot` esté caído; si `/notify` falla, la notificación queda en cola (tabla) y se reintenta.

**Criterios de aceptación**
- ✅ `/estadisticas` devuelve cifras coherentes con el seed y detecta al menos un solapamiento de demo («Cine de verano en Uleila coincide con fiestas»).
- ✅ Después de una conversación con el bot, el coste en tokens del panel ha subido.
- ✅ Con el contenedor `bot` parado, la API sigue respondiendo y los avisos pendientes se envían al volver.
- ✅ La URL pública abre la web y el webhook de Twilio llega al bot.
- ✅ Etiqueta `v0.9`. A partir de aquí solo `fix/*`.

### H5 · Estabilización y entrega (dom 00:00 → 07:00 · E2E y REL `v1.0`)

**Tareas**
- [ ] H5.1 Arreglar lo que salga del smoke test y de los ensayos.
- [ ] H5.2 `scripts/demo_reset.sh` deja la base de datos en el estado inicial de la demo en menos de 1 minuto.
- [ ] H5.3 Prueba E2E en **otro portátil**: clonar, `cp .env.example .env`, rellenar claves, `docker compose up --build`, guion de la demo 2 veces.
- [ ] H5.4 Sección de backend en el README: arranque en 3 comandos, arquitectura, variables.
- [ ] H5.5 Merge `develop` → `main`, etiqueta `v1.0`, smoke test sobre `main`.

**Criterios de aceptación**
- ✅ El guion de 7 pasos sale entero **dos veces seguidas** en la máquina limpia, con `demo_reset.sh` entre una y otra.
- ✅ `smoke_test.sh` en verde sobre `main`.
- ✅ Etiqueta `v1.0` publicada antes de las **07:00**.

---

## 4. Dependencias con los otros flujos

### Lo que el flujo A da (y cuándo lo necesitan)

| Qué | Para quién | Lo necesitan desde | Mientras tanto usan |
|---|---|---|---|
| Contratos v1 + fixtures | B y C | **CP0 (18:30 vie)** | Nada: **bloquea a todos** |
| `docker-compose.yml` y `.env.example` | B y C | CP0 | Arrancar su servicio a mano |
| `GET /eventos`, ficha | C | CP1 | Mocks con fixtures |
| `POST /eventos` / `importar` / `confirmar` | B | CP1 / CP2 | Stub de la API |
| `by-phone`, auth por WhatsApp | B | CP2 | Usuario fijo de prueba |
| Bandeja de moderación | B (moderador por WhatsApp) y C (panel) | CP2 | Fixtures |
| Inscripciones, chat, recomendaciones | B y C | CP3 | Fixtures |
| Login Google + JWT | C | CP3 | Sin login (modo demo) |
| Estadísticas y tokens | C (panel) | CP4 | Fixtures |

### Lo que el flujo A necesita de B

| Qué | Para | Desde | Si no está |
|---|---|---|---|
| `POST /notify` | Avisos (moderador, lista de espera, cambio de hora) | CP2 | A guarda la notificación en una tabla y la registra en el log; se envía cuando B esté |
| `POST /ai/spam` | `score_spam` en moderación y chat | CP2 | Reglas simples en A (palabras prohibidas, enlaces, mayúsculas) |
| `POST /ai/responder-ficha` | Respuestas automáticas en el chat del evento | CP3 | El mensaje queda sin respuesta automática para el organizador |
| `POST /metrics/tokens` (B lo llama) | Coste en el panel | CP4 | El panel muestra 0 |

### Lo que el flujo A necesita del equipo

- **Cuenta de Google Cloud con OAuth Client ID** (H3). Pedirla en el kickoff porque tarda.
- **Cuenta de Cloudflare** para el túnel con nombre estable (o túnel rápido sin cuenta, que cambia de URL al reiniciar).

**Orden de merge en cada checkpoint: A → B → C.** A hace merge primero porque los demás dependen de sus datos.

---

## 5. Riesgos del flujo A

| Riesgo | Señal de alarma | Respuesta |
|---|---|---|
| Contratos tarde (H0) | A las 18:15 no hay `openapi.yaml` | Congelar solo `evento`, `extraccion_evento` y `usuario`; el resto, por PR en el bloque 1 |
| Una sola persona en el flujo más cargado | En CP1 falta algo imprescindible de H1 | Mover a la cuarta persona del equipo a A (ver §6) o recortar E13/E15/E18 |
| Login con Google se complica | Más de 45 min atascado | JWT emitido por login de WhatsApp o selector de usuario en modo demo. El jurado puntúa más la demo que el login |
| Recomendador con embeddings | Más de 30 min con pgvector | Solo reglas (gustos + distancia + fecha + plazas). El motivo legible es lo que se ve |
| Concurrencia en plazas | Plazas negativas en pruebas | `SELECT … FOR UPDATE` en la transacción de inscripción |
| Bot caído durante la demo | `/notify` falla | Cola de notificaciones en la tabla y reintento (H4.5) |

---

## 6. Puntos a resolver antes de empezar (kickoff)

1. **El equipo es de 4 y el plan tiene 3 flujos.** `README.md` lista a 4 personas (Adán, Francisco, Benas, Juan Carlos) y `PLAN.md` reparte en Dev A/B/C. Recomiendo que la cuarta persona haga **pareja con A** (el flujo crítico): seed y datos de demo, `.ics`, estadísticas, smoke test y despliegue. Así Benas se centra en contratos, modelos, moderación, inscripciones y recomendador.
2. **`CLAUDE.md` describe el plan anterior** (Streamlit + SQLite + equipo de 4). Si se elige la Opción 1, hay que actualizarlo; si no, cualquier asistente de código generará código con el stack equivocado. Es tarea de H0.
3. **Pueblos:** el folleto nombra 4 pueblos y la presentación añade Tahal. El seed usa los 5.
4. **Preguntas abiertas a la organización** (`PLAN.md` §8), sobre todo qué se entrega a las 11:00 del domingo.

---

## 7. Cómo vamos a revisar el avance

Al terminar cada hito:

1. Marca las tareas en `docs/PROGRESO.md` y haz el commit/etiqueta del checkpoint.
2. Escribe en este hilo «H<n> terminado».
3. Reviso el repositorio de la carpeta contra los criterios de aceptación del hito y respondo con:
   - 🟢 **Cerrado**: se cumplen todos los criterios.
   - 🟡 **Cerrado con deuda**: falta algo no imprescindible; queda anotado y se sigue.
   - 🔴 **No cerrado**: falta algo imprescindible; propongo arreglar o recortar, y decides.

Además, en cada checkpoint compruebo que el flujo A sigue a tiempo para el siguiente. Si va 🟡, propongo el recorte antes de que se convierta en 🔴.

### Resumen de fechas

| Hito | Termina | Checkpoint | Etiqueta |
|---|---|---|---|
| H0 · Contratos y esqueleto | vie 18:30 | CP0 | — |
| H1 · Datos y CRUD | vie 23:30 | CP1 | `v0.1` |
| H2 · Ingesta y moderación | sáb 13:00 | CP2 | `v0.2` |
| H3 · Participación | sáb 19:00 | CP3 | `v0.3` |
| H4 · Criterios del jurado | dom 00:00 | CP4 | `v0.9` |
| H5 · Estabilización y entrega | dom 07:00 | E2E + REL | `v1.0` |
