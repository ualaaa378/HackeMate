# PROGRESO.md · Control de avance del reto 1

> Cómo usarlo: marca `[x]` al terminar una tarea y súbelo en el mismo commit que la tarea (`docs(progreso): …`).
> Si una tarea se bloquea, cámbiala a `[!]` y escribe el motivo en «Bloqueos». Si se recorta, `[-]`.
> Plan completo y reglas: [`PLAN.md`](PLAN.md).

**Leyenda:** `[ ]` pendiente · `[~]` en curso · `[x]` hecha · `[!]` bloqueada · `[-]` recortada

## Tablero

| Flujo | Responsable | Rama actual | Estado | Última actualización |
|---|---|---|---|---|
| A · Backend, datos e infra | Dev A: Benas | `Flujo-A` | 🟢 / 🟡 / 🔴 | vie __:__ |
| B · Bot (Telegram/WhatsApp) e IA | Dev B: Francisco | `Flujo-B` | 🟢 | vie 20/11 20:00 |
| C · App Ionic, web/PWA y panel | Dev C: Adán | `feat/web-docker` | 🟢 | vie 20/11 |

🟢 en plazo · 🟡 riesgo de no llegar al próximo checkpoint · 🔴 bloqueado

---

## Checkpoints (hora de Madrid)

| # | Cuándo | Hito | Etiqueta | Hecho |
|---|---|---|---|---|
| CP0 | vie 18:30 | Esqueleto del repo + contratos v1 congelados | — | [ ] |
| CP1 | vie 23:30 | Primera integración: web lee la API, WhatsApp crea evento | `v0.1` | [ ] |
| CP2 | sáb 13:00 | Demo pasos 1–3 (post → ficha → confirma → moderación) | `v0.2` | [ ] |
| CP3 | sáb 19:00 | Demo pasos 4–7 + contratos v2 congelados | `v0.3` | [ ] |
| CP4 | dom 00:00 | Feature freeze (solo `fix/*` a partir de aquí) | `v0.9` | [ ] |
| E2E | dom 05:00 | Prueba en limpio en otro portátil, demo 2 veces | — | [ ] |
| REL | dom 07:00 | `develop` → `main`, release final | `v1.0` | [ ] |

### Checklist de integración (repetir en cada CP)

- [ ] Las tres ramas rebasadas sobre `origin/develop` y con sus tests en verde
- [ ] PR revisadas y mergeadas en orden A → B → C
- [ ] `docker compose down -v && docker compose up --build` sin errores
- [ ] `scripts/smoke_test.sh` en verde
- [ ] Pasos de la demo de este CP probados a mano
- [ ] Etiqueta creada y README actualizado con lo que funciona

---

## CP0 · Arranque (vie 17:00–18:30) · los 3

- [x] Enfoque decidido y firmado en `PLAN.md` §2 (Opción 1; Juan Carlos en pareja con el flujo A)
- [x] Nombres asignados a Dev A / B / C (tablero de arriba)
- [ ] Cuentas creadas: Twilio WhatsApp Sandbox, Google OAuth, clave de Claude, clave de Gemini (AI Studio)
- [~] Ramas `main` y `develop` creadas (falta activar la protección de `main` en GitHub)
- [x] Estructura de carpetas del monorepo creada
- [~] `infra/docker-compose.yml` con `db`, `api`, `bot`, `web`, `tunnel` y `/health` respondiendo (escrito; falta validarlo con Docker en otra máquina: pasos y resultado esperado en `PLAN_FLUJO_A.md` H0, «Cómo probar H0»). **Responsable de la prueba: por asignar en la reunión** (alguien con Docker)
- [x] `.env.example` con todas las variables (incluidas las `META_*` del canal WhatsApp Cloud API de `Flujo-B`)
- [x] `contracts/openapi.yaml` v1
- [x] `contracts/schemas/*.json` v1 (evento, extraccion_evento, usuario, publicador, inscripcion, mensaje_evento, notificacion, lugar)
- [x] `contracts/enums.md` y `contracts/fixtures/*.json`
- [ ] **B (Francisco) confirma los contratos v1 de `Flujo-A`.** Revisar que:
  - `services/bot/app/schemas.py` (`ExtraccionEvento`, `Campo`, `Tokens`) encaja con `contracts/schemas/extraccion_evento.json` y su fixture valida con el modelo Pydantic.
  - El cuerpo que manda `api_cliente.importar_evento` (`extraccion`, `telefono_publicador`, `origen`) encaja con `ImportarEvento` de `openapi.yaml`.
  - `POST /notify` acepta `contracts/schemas/notificacion.json` (lo mínimo: `telefono`, `tipo`, `texto`) y `metrics.registrar` envía lo que pide `MetricaTokens`.
  - Los endpoints `/ai/*` de `openapi.yaml` son los que va a implementar.
  - Dónde confirmar: aprobación (o comentarios) en la PR `Flujo-A` → `develop`, y marcar esta casilla.
  - *Revisión previa del flujo A (vie 19:10, contra `origin/Flujo-B`):* el cuerpo de `importar`, `MetricaTokens` y la forma de `ExtraccionEvento` encajan. Por decidir con B: `POST /webhook/meta` (y `GET`) no está en `openapi.yaml` → añadirlo por PR `contract-change`; `/ai/spam`, `/ai/responder-ficha` y `/ai/preferencias` aún no existen en el bot (los necesita A en H2/H3).
- [ ] **C (Adán) confirma los contratos v1 de `Flujo-A`.** Revisar que:
  - `contracts/schemas/evento.json` (con `inscritos`), `lugar.json` y los fixtures `eventos.json`, `eventos_demo.json`, `lugares.json`, `municipios.json` y `FUENTES.md` son los de su PR de datos reales, sin cambios. `openapi.yaml` ya incluye `GET /lugares` y `GET /lugares/{id}`.
  - Su PR de datos reales se rebasa sobre `develop` cuando entre `Flujo-A` (los archivos de `contracts/` quedan idénticos y desaparecen del diff).
  - `npx openapi-typescript contracts/openapi.yaml -o apps/web/src/api/schema.d.ts` genera tipos sin errores.
  - Los fixtures de usuarios, publicadores, inscripciones, mensajes y notificaciones le bastan para las pantallas con mocks (los fixtures de moderación y antispam llegan en H2).
  - Dónde confirmar: aprobación (o comentarios) en la PR `Flujo-A` → `develop`, y marcar esta casilla.
  - *Nota del flujo A (vie 19:10):* la web ya lee `GET /eventos`, `/lugares` y `/municipios` de la API en `develop` (PR #4), así que en la práctica los contratos le sirven; falta solo su confirmación explícita.
- [x] Cerrar la PR #1 (`contract/v1`) **sin merge**: la sustituyen los contratos de `Flujo-A` (mismo `evento.json`). Si tenía algo que falte en `Flujo-A`, se añade por PR `contract-change`.
- [~] PR `Flujo-A` → `develop` revisada y mergeada (orden A → B → C); `main` protegida en GitHub *(Flujo-A en `develop` vía PR #3 y #4; falta proteger `main`)*
- [ ] Preguntas enviadas a la organización por Telegram (PLAN §8)

---

## Flujo A · Backend, datos e infraestructura

**Bloque 1 (vie 18:30–23:30)**
- [x] Modelos SQLAlchemy + migración inicial (Alembic)
- [x] CRUD de eventos con filtros (municipio, categoría, fechas, radio)
- [x] CRUD de publicadores y usuarios, `GET /usuarios/by-phone/{e164}`
- [x] `seed.py` con los 5 pueblos y eventos de demo (fechas reales; omite y borra los ya terminados)
- [x] Formato de error y paginación comunes

**Bloque 2 (sáb 08:00–13:00)**
- [~] `POST /eventos/importar` y `POST /eventos/{id}/confirmar` *(importar mínimo hecho en E1.6: pendiente_confirmacion, `faltan`, duplicado por origen.url; falta confirmar)*
- [ ] Niveles de confianza 0/1/2 y bandeja de moderación con motivo
- [ ] Detección de duplicados (origen_url + similitud)
- [ ] Alta de publicador: verificación de WhatsApp con código + aprobación

**Bloque 3 (sáb 14:00–19:00)**
- [ ] Login con Google (OAuth → JWT) y roles
- [ ] Inscripciones con plazas y lista de espera
- [ ] Exportación `.ics` (evento y usuario)
- [ ] Chat del evento (mensajes, anuncios fijados, permisos por rol)
- [ ] Cambio de hora → `POST /notify` a todos los inscritos
- [ ] Recomendador con motivo legible (gustos + distancia + fecha/plazas + historial + embeddings)

**Bloque 4 (sáb 20:00–00:00)**
- [ ] `GET /estadisticas` (actividades, % importadas, inscripciones vs asistencia, ocupación, solapamientos)
- [ ] `POST /metrics/tokens` y coste acumulado
- [ ] Despliegue alternativo en Render/Railway (opcional)

---

## Flujo B · Bot (Telegram / WhatsApp), IA y automatizaciones

> Plan y decisiones del flujo: [`PLAN_FLUJO_B.md`](PLAN_FLUJO_B.md). Canal activo: **Telegram** (@HackeMate_bot).
> WhatsApp Cloud API (Meta) está programado pero bloqueado por Meta (verificación de negocio + método de pago).

**Bloque 1 (vie 18:30–23:30)**
- [x] Webhooks con acuse inmediato y trabajo en segundo plano: Telegram, WhatsApp (Meta) y Twilio
- [x] Canal Telegram funcionando de punta a punta (botones, voz, fotos, ubicación)
- [x] Canal WhatsApp Cloud API (Meta) programado y probado contra la API real · [!] envío bloqueado por Meta
- [x] Simulador `POST /dev/mensaje` y consola para probar sin mensajería
- [x] `llm_router` Gemini → FreeLLMAPI → Claude (opcional) → reglas, con timeout y registro de tokens (probado con FreeLLMAPI real)
- [x] Extractor de eventos desde texto → `ExtraccionEvento` validada
- [ ] Integrar `services/bot` en `infra/docker-compose.yml` en lugar del stub (con Flujo A)
- [x] Flujo importar → confirmar según contrato: importa al recibir el post (`contacto_publicador`), pregunta lo que la API dice que falta y confirma (si `/confirmar` aún no existe, guarda con `PATCH`)

**Bloque 2 (sáb 08:00–13:00)**
- [x] Extractor desde imagen (cartel, visión de FreeLLMAPI/Gemini) y desde audio (Whisper vía FreeLLMAPI). Probado con la API real
- [x] Conversación del publicador: pregunta lo que falta y confirma con botones; identidad con «Compartir mi número» → `POST /usuarios/vincular`
- [x] Antispam `POST /ai/spam`: reglas baratas primero, IA solo si es dudoso (0,3–0,7). Falta que la API lo llame al confirmar (A, H2.4)
- [ ] Ingesta: «pega el enlace/texto del post» + scraper de una web pública
- [~] Conversación del moderador: «pendientes» → bandeja con motivo y botones Aprobar/Rechazar. Hecho en el bot; espera `GET /moderacion/pendientes` y `POST /moderacion/{id}/decision` (A)

**Bloque 3 (sáb 14:00–19:00)**
- [x] Conversación del vecino: «¿qué hay este finde (cerca / en Senés)?» → tarjetas con [Apuntarme] [Más info]; ubicación con «Enviar mi ubicación»; gustos («me gustan las rutas») y `POST /ai/preferencias`. Probado con la API real
- [x] Detección de intención sin tokens: publicar / buscar / gustos / apuntarse / preguntar. Las notas de voz de la vecina también buscan planes
- [~] Inscripción desde el chat con un botón (hecho en el bot; espera `POST /eventos/{id}/inscripciones` de A; mientras, enlace a la web)
- [x] `POST /notify` con `contacto` (`tg:`/`+34`) y botón [Apuntarme] en las recomendaciones
- [x] Asistente del evento: responde solo con la ficha (reglas o IA) y si no lo sabe lo pasa al organizador (`POST /ai/responder-ficha`; el chat del evento espera `/eventos/{id}/mensajes` de A)
- [!] Guardar los gustos en la API: `PATCH /usuarios/me` solo admite login de usuario. Propuesta a A: `PATCH /usuarios/{id}` con `X-Internal-Token`. Mientras, el bot los guarda en memoria

**Bloque 4 (sáb 20:00–00:00)**
- [~] «Simular caída del LLM»: la variable `LLM_SIMULAR_CAIDA` existe; falta el botón en el panel (Flujo C)
- [ ] Respuesta en audio (TTS) para quien escribe con audios
- [ ] Respuestas en otros idiomas para visitantes

---

## Flujo C · App Ionic, web/PWA y panel

> Hitos (H0–H5) y criterios de aceptación en [`PLAN_FLUJO_C.md`](PLAN_FLUJO_C.md).

**Bloque 1 (vie 18:30–23:30)**
- [x] Proyecto Ionic React (`ionic start web tabs --type=react`) con pestañas Agenda · Mapa · Perfil
- [x] Tipos generados desde `openapi.yaml` y `VITE_API_URL` configurable *(`src/api/openapi.d.ts` con openapi-typescript; se regenera con `npm run api:tipos`)*
- [x] Android Studio + JDK instalados *(el JDK va incluido en Android Studio)*
- [x] Mocks con `contracts/fixtures` *(JSON en `src/mocks`, activos con `VITE_USE_MOCKS=true` o sin `VITE_API_URL`)*
- [x] Agenda (lista por fecha con filtros)
- [x] Mapa Leaflet con pines por categoría y «cerca de mí»
- [x] Ficha del evento
- [x] App en Docker: `apps/web/Dockerfile` (node → nginx en 8080) y `web` del compose apuntando a `apps/web` *(validado con `docker compose up --build`: web en :8080 carga eventos de la API)*
- [x] **H1 cerrado** (vie 22:20): compose completo con PostgreSQL y la API de #10, la agenda y el mapa leen los 18 eventos de la base; las rutas aún sin implementar caen a mocks (ver `PLAN_FLUJO_C.md` H1)

**Bloque 2 (sáb 08:00–13:00)**
- [ ] Panel del moderador: bandeja con motivo de la IA, aprobar/rechazar
- [ ] Gestión de publicadores y niveles de confianza, pausar automatizaciones
- [ ] Vista del publicador: alta, fuentes, crear/editar/cancelar evento, ver inscritos

**Bloque 3 (sáb 14:00–19:00)**
- [ ] Login con Google y perfil (gustos, pueblo, tipo de aviso, vincular WhatsApp)
- [ ] Inscribirse / cancelar y añadir al calendario (`.ics`)
- [ ] Chat del evento en la ficha (preguntas, respuestas, anuncios fijados)
- [ ] PWA: `manifest.json`, service worker e icono

**Bloque 4 (sáb 20:00–00:00)**
- [ ] Panel de estadísticas y coste en tokens
- [ ] Accesibilidad WCAG 2.1 AA: contraste, teclado, `aria-label`, modo letra grande
- [ ] Capacitor: `npx cap add android`, APK de debug generado
- [ ] APK apunta a la URL pública del túnel y funciona en un móvil real

---

## Guion de la demo (debe estar todo en `[x]` el domingo a las 07:00)

- [ ] 1. Un post de Facebook (o un audio) se convierte en ficha
- [ ] 2. El publicador confirma por WhatsApp
- [ ] 3. El moderador aprueba uno y el antispam para otro
- [ ] 4. A una vecina le llega la recomendación y se apunta
- [ ] 5. Pregunta en el chat del evento
- [ ] 6. Cambio de hora → aviso a los inscritos
- [ ] 7. Una persona mayor lo usa solo con audios

## Criterios del jurado (comprobar en CP4)

- [ ] Funcionalidad requerida (los 3 roles)
- [ ] Funcionalidad extra (al menos 2 ideas del PLAN §2)
- [ ] Usabilidad y accesibilidad
- [ ] Utilidad para los pueblos (recorrido completo)
- [ ] Multiplataforma (web + APK Android/PWA + WhatsApp sincronizados)
- [ ] Coste en tokens medido y visible
- [ ] Robustez (fallback demostrable)
- [ ] Tiempo de respuesta (acuse inmediato)
- [ ] APIs gratuitas con plan B
- [ ] URL pública + repositorio en GitHub con README

## Entrega (dom 05:00–07:00)

- [ ] README: arranque en 3 comandos, capturas, arquitectura
- [ ] APK final instalado en un móvil para la demo
- [ ] Vídeo de respaldo de la demo
- [ ] Guion de presentación de 3 minutos
- [ ] `main` etiquetado `v1.0` y probado
- [ ] Entregado lo que pida la organización antes de las 11:00

---

## Bloqueos

| Hora | Flujo | Problema | Quién ayuda | Resuelto |
|---|---|---|---|---|
| vie 19:00 | B | Meta bloquea el envío de WhatsApp Cloud API (errores 141010 verificación de negocio, 141006 método de pago, 131031). Decisión: canal activo **Telegram**; WhatsApp queda para producción con una entidad verificada | Organización (¿portfolio de Meta verificado de la Diputación/UAL?) | [~] |

## Cambios de contrato

| Hora | PR | Cambio | Aprobado por |
|---|---|---|---|
| vie 20:00 | (propuesta B) | Añadir `telegram` al enum `canal`; `telegram_id` opcional en `Usuario` (el bot pide el teléfono con el botón «Compartir mi número», así `telefono` E.164 sigue valiendo en `ImportarEvento` y `Notificacion`); `plantilla`/`parametros` opcionales en `Notificacion`; documentar `/webhook/telegram`, `/webhook/meta` y `/dev/mensaje` en `openapi.yaml`. Detalle en `PLAN_FLUJO_B.md` §5 | pendiente (A y C) |

## Registro de checkpoints

| CP | Hora real | Qué funciona | Qué no | Decisión (recortar / seguir) |
|---|---|---|---|---|
| CP1 | | | | |
| CP2 | | | | |
| CP3 | | | | |
| CP4 | | | | |

## Avisos del flujo A para B y C (vie 20/11, 22:00)

Estado de las ramas del flujo A y lo que cambia para los demás. Orden de merge previsto: **#10 → #12 → #11 (B) → C**.

| PR | Rama | Qué trae | Qué tiene que hacer B / C |
|---|---|---|---|
| [#10](https://github.com/ualaaa378/HackeMate/pull/10) | `Flujo-A` | H1: la API lee de la base de datos (municipios, lugares, eventos con filtros y radio, ficha, POST/PATCH), publicadores, usuarios, `GET /usuarios/by-phone/{e164}` y `POST /eventos/importar` (crea en `pendiente_confirmacion`, devuelve `faltan`, no duplica por `origen.url`). El contenedor `api` carga el seed al arrancar. Ya lleva `develop` integrado y el `.env.example` y este archivo resueltos con `Flujo-B`, así que la #11 entra limpia después. | **C:** las lecturas públicas ya salen de la base (sin token solo eventos `publicado` y publicadores `aprobado`). Crear o editar eventos pide `X-Internal-Token` hasta el login (H3). **B:** `importar`, `by-phone`, `POST /usuarios` y `POST/PATCH /eventos` piden `X-Internal-Token`. |
| [#12](https://github.com/ualaaa378/HackeMate/pull/12) `contract-change` | `feat/api-canales` (encima de #10) | Respuesta a la propuesta de B: canal `telegram`, `telegram_id` en usuario y publicador, componente `Contacto` (`+34…` o `tg:<chat_id>`), `contacto_publicador` en `ImportarEvento`, `contacto`/`plantilla`/`parametros` en `Notificacion`, rutas `GET /usuarios/by-contacto/{contacto}` y `POST /usuarios/vincular`, y las rutas del bot documentadas. Solo añadidos. Migración `0002_canal_telegram`. | **B:** funciona ya con lo que manda el bot (`tg:` en `telefono_publicador`); cuando podáis, usad `contacto_publicador` y llamad a `POST /usuarios/vincular` al «Compartir mi número». **C:** regenerar tipos (`npm run api:tipos`); solo se añade `telegram` a los enums. **Aprobación de B y C pendiente.** |

Pendiente del flujo A tras el merge de #11: cambiar en `infra/docker-compose.yml` el stub del bot por `build: ../services/bot` y probar el compose en una máquina con Docker.
