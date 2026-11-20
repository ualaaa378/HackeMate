# PROGRESO.md · Control de avance del reto 1

> Cómo usarlo: marca `[x]` al terminar una tarea y súbelo en el mismo commit que la tarea (`docs(progreso): …`).
> Si una tarea se bloquea, cámbiala a `[!]` y escribe el motivo en «Bloqueos». Si se recorta, `[-]`.
> Plan completo y reglas: [`PLAN.md`](PLAN.md).

**Leyenda:** `[ ]` pendiente · `[~]` en curso · `[x]` hecha · `[!]` bloqueada · `[-]` recortada

## Tablero

| Flujo | Responsable | Rama actual | Estado | Última actualización |
|---|---|---|---|---|
| A · Backend, datos e infra | Dev A: Benas | `Flujo-A` | 🟢 / 🟡 / 🔴 | vie __:__ |
| B · WhatsApp e IA | Dev B: Francisco | `Flujo-B` | 🟢 / 🟡 / 🔴 | vie __:__ |
| C · App Ionic, web/PWA y panel | Dev C: Adán | `feat/web-…` | 🟢 / 🟡 / 🔴 | vie __:__ |

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
- [~] `infra/docker-compose.yml` con `db`, `api`, `bot`, `web`, `tunnel` y `/health` respondiendo (escrito; falta validarlo con Docker en otra máquina)
- [x] `.env.example` con todas las variables
- [x] `contracts/openapi.yaml` v1
- [x] `contracts/schemas/*.json` v1 (evento, extraccion_evento, usuario, publicador, inscripcion, mensaje_evento, notificacion)
- [x] `contracts/enums.md` y `contracts/fixtures/*.json`
- [ ] Preguntas enviadas a la organización por Telegram (PLAN §8)

---

## Flujo A · Backend, datos e infraestructura

**Bloque 1 (vie 18:30–23:30)**
- [ ] Modelos SQLAlchemy + migración inicial (Alembic)
- [ ] CRUD de eventos con filtros (municipio, categoría, fechas, radio)
- [ ] CRUD de publicadores y usuarios, `GET /usuarios/by-phone/{e164}`
- [ ] `seed.py` con los 5 pueblos y eventos de demo
- [ ] Formato de error y paginación comunes

**Bloque 2 (sáb 08:00–13:00)**
- [ ] `POST /eventos/importar` y `POST /eventos/{id}/confirmar`
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

## Flujo B · WhatsApp, IA y automatizaciones

**Bloque 1 (vie 18:30–23:30)**
- [ ] Webhook de Twilio con acuse inmediato (<1 s) y trabajo en segundo plano
- [ ] Adaptador de canal `console` para probar sin WhatsApp
- [ ] `llm_router` con cadena Claude → Gemini → NIM → reglas, timeout y registro de tokens
- [ ] Extractor de eventos desde texto → `ExtraccionEvento` validada

**Bloque 2 (sáb 08:00–13:00)**
- [ ] Extractor desde imagen (cartel) y desde audio (Whisper)
- [ ] Conversación del publicador: pregunta lo que falta y confirma (botones)
- [ ] Antispam: reglas baratas primero, IA solo si es dudoso
- [ ] Ingesta: «pega el enlace/texto del post» + scraper de una web pública
- [ ] Conversación del moderador: «enséñame lo pendiente», aprobar/rechazar

**Bloque 3 (sáb 14:00–19:00)**
- [ ] Conversación del vecino: gustos, pueblo/ubicación, «¿qué hay este finde cerca?»
- [ ] Inscripción desde WhatsApp con un botón
- [ ] `POST /notify`: recomendaciones, cambios de hora y anuncios (respetando preferencias)
- [ ] Asistente del evento: responde solo con la ficha, si no, deriva al organizador

**Bloque 4 (sáb 20:00–00:00)**
- [ ] Botón/flag «simular caída del LLM» para enseñar el fallback
- [ ] Respuesta en audio (TTS) para quien escribe con audios
- [ ] Respuestas en otros idiomas para visitantes

---

## Flujo C · App Ionic, web/PWA y panel

**Bloque 1 (vie 18:30–23:30)**
- [ ] Proyecto Ionic React (`ionic start web tabs --type=react`) con pestañas Agenda · Mapa · Perfil
- [ ] Tipos generados desde `openapi.yaml` y `VITE_API_URL` configurable
- [ ] Android Studio + JDK instalados (dejarlo descargando en segundo plano)
- [ ] Mocks con `contracts/fixtures` (MSW o json-server)
- [ ] Agenda (lista por fecha con filtros)
- [ ] Mapa Leaflet con pines por categoría y «cerca de mí»
- [ ] Ficha del evento

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
| | | | | [ ] |

## Cambios de contrato

| Hora | PR | Cambio | Aprobado por |
|---|---|---|---|
| | | | |

## Registro de checkpoints

| CP | Hora real | Qué funciona | Qué no | Decisión (recortar / seguir) |
|---|---|---|---|---|
| CP1 | | | | |
| CP2 | | | | |
| CP3 | | | | |
| CP4 | | | | |
