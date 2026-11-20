# PLAN_FLUJO_C.md · App Ionic, web/PWA y panel

> Hackathon UAL para el desarrollo del interior · Reto 1 «Reactiva tu pueblo» · 20–22 nov 2026
> Responsable del flujo C: **Adán** (Dev C) · Ramas: `feat/web-<tarea>` → `develop` · Carpeta: `apps/web/`
> Complementa a `docs/PLAN.md` (plan general, §Flujo C) y `docs/PROGRESO.md` (checklist). Si algo choca, manda `PLAN.md`.
> Escrito para que las personas **y sus Claudes** sepan qué hace la app, en qué hito está y qué necesita de A y B.
> Última actualización: viernes 20 nov, 22:20.

---

## 0. Resumen en 30 segundos

- `apps/web/` es una app **Ionic React + Vite** con `react-leaflet`. Un solo código para la web/PWA (nginx en el **puerto 8080**) y el **APK de Android** (Capacitor).
- **Ya funciona:** agenda con filtros, mapa con «cerca de mí», ficha del evento con contador de apuntados, tema visual de la plantilla municipal, imagen Docker y tipos generados desde `openapi.yaml`.
- **Lee la API real** (`VITE_API_URL`, `VITE_USE_MOCKS=false`). Si la API no responde o una ruta aún no existe, **vuelve sola a los mocks** (`src/mocks/`), así la demo no se cae.
- La app **nunca** habla con la base de datos ni con la IA: solo con `api` por HTTP (`src/api/client.ts` es la única puerta).

---

## 1. Qué hace la app y qué NO hace

**Hace** (PLAN §Flujo C):
1. **Vecino** sin registro: agenda, mapa, ficha, inscribirse, `.ics` y chat del evento.
2. **Perfil:** login con Google, gustos, pueblo, tipo de aviso (texto/audio), vincular WhatsApp o Telegram.
3. **Publicador:** alta, fuentes, crear/editar/cancelar evento, ver inscritos, anuncios.
4. **Moderador:** bandeja con el **motivo de la IA**, aprobar/rechazar, niveles de confianza, pausar automatizaciones.
5. **Panel de estadísticas:** actividades, % importadas, inscripciones vs asistencia, solapamientos, **tokens y coste**.
6. **Accesibilidad**, **PWA** y **APK**.

**No hace:** decidir estados ni guardar datos (es de A), ni llamar a la IA o a la mensajería (es de B). Si una pantalla necesita IA, la pide a la `api`.

---

## 2. Cómo trabaja el flujo C

- Una rama por tarea (`feat/web-<tarea>`), PR a `develop` y merge en orden **A → B → C** en cada checkpoint.
- Antes de cada PR: `npx tsc --noEmit`, `npm run test:unit` y `npm run build` en verde. El lint tiene 4 errores heredados (§6).
- Si cambia `contracts/openapi.yaml`: `npm run api:tipos` y commit del `openapi.d.ts` regenerado.
- Cada pantalla nueva funciona primero con mocks y luego contra la API. Si la API de ese hito no está, la pantalla sale igual con mocks.
- Al terminar un hito: marcar `PROGRESO.md`, escribir «H<n> del flujo C terminado» y revisar los criterios de aceptación. Si falta algo imprescindible, se arregla o se recorta, pero no se da por cerrado.

---

## 3. Hitos

### H0 · Arranque (vie 17:00 → 18:30 · CP0) ✅

- [x] H0.1 Proyecto Ionic React con pestañas Agenda · Mapa · Perfil.
- [x] H0.2 Capa de datos única (`src/api/client.ts`) con mocks sacados de `contracts/fixtures`.
- [x] H0.3 Contratos v1 revisados (evento con `inscritos`, lugares y datos reales de los pueblos en `contracts/fixtures`).

**Criterios de aceptación**
- ✅ `npm run dev` arranca y muestra la agenda con mocks.
- ✅ Ninguna pantalla hace `fetch` fuera de `client.ts`.

### H1 · Ver la agenda real (vie 18:30 → 23:30 · CP1 · `v0.1`) ✅

- [x] H1.1 Agenda por fecha con filtros de pueblo y categoría.
- [x] H1.2 Mapa Leaflet con pines por categoría y «cerca de mí».
- [x] H1.3 Ficha del evento: datos, contador de apuntados, «Cómo llegar», enlace al post original.
- [x] H1.4 Conexión con la API real (`VITE_API_URL`) con vuelta automática a mocks si falla.
- [x] H1.5 Tipos generados desde `openapi.yaml` (`npm run api:tipos`), regenerados con el contrato de Telegram (#12).
- [x] H1.6 Imagen Docker (node → nginx :8080) y servicio `web` del compose.
- [x] H1.7 Tema visual de la plantilla y base de accesibilidad (español, zoom permitido).
- [x] H1.8 Prueba del compose completo (`db` PostgreSQL + `api` con seed + `web` + stub del bot) con la API con base de datos (#10). *(vie 22:20: agenda y mapa con los 18 eventos de la base, ficha, 404 y «Apuntarme» cayendo a mocks porque la inscripción es de H3)*
- [x] H1.9 La vuelta a mocks también cubre las rutas que la API aún no implementa (responde `no_encontrado`), con tests en `src/api/client.test.ts`.
- [ ] H1.10 Etiqueta `v0.1` en `develop`, junto con A y B en el CP1.

**Criterios de aceptación**
- ✅ Con la API arrancada y el seed cargado, la agenda lista los eventos de la base de datos (18 en el seed del 20/11).
- ✅ Con la API parada, la agenda sale igual desde los mocks y la consola avisa `[api] usando mocks`.
- ✅ La ficha de un id inexistente muestra un mensaje de error, no una pantalla en blanco.
- ✅ `docker compose up --build` → `http://localhost:8080` muestra eventos de la API.
- ✅ Un botón cuya ruta aún no existe en la API (p. ej. «Apuntarme» antes de H3) funciona con mocks en lugar de dar error.

### H2 · Moderador y publicador (sáb 08:00 → 13:00 · CP2 · `v0.2`)

- [ ] H2.1 Rol en la app: selector de rol en modo demo (vecino, publicador, moderador) hasta que llegue el login en H3.
- [ ] H2.2 **Bandeja del moderador** (`GET /moderacion/pendientes`): cada evento con su **motivo** y `score_spam`; aprobar o rechazar (`POST /moderacion/{id}/decision`).
- [ ] H2.3 Publicadores: lista con nivel de confianza y estado, aprobar y **pausar** (`/publicadores/{id}/aprobar`, `/pausar`).
- [ ] H2.4 Vista del publicador: sus eventos por estado, crear y editar evento (`POST/PATCH /eventos`).
- [ ] H2.5 Ficha de un evento `pendiente_confirmacion` o `en_revision` visible solo para el publicador y el moderador.

**Criterios de aceptación**
- ✅ El moderador ve en la bandeja el caso «apuestas» de Bar La Plaza con su motivo, lo rechaza y desaparece de la bandeja.
- ✅ Aprobar un evento hace que aparezca en la agenda pública sin recargar a mano.
- ✅ Un publicador pausado sale marcado y la app no le deja publicar (muestra el error de la API).
- ✅ **Demo pasos 1–3** vistos desde la web: el evento que entra por el bot aparece en la bandeja y, aprobado, en la agenda.

**Depende de A (H2):** moderación, confirmar y publicadores. Mientras no estén, la bandeja usa `contracts/fixtures` (`eventos_moderacion`).

### H3 · La vecina (sáb 14:00 → 19:00 · CP3 · `v0.3`)

- [ ] H3.1 Login con Google (`POST /auth/google` → JWT) y pantalla de Perfil: gustos, pueblo, tipo de aviso, vincular WhatsApp/Telegram.
- [ ] H3.2 Inscribirse y cancelar con plazas y lista de espera; botón «Añadir a mi calendario» (`.ics`).
- [ ] H3.3 **Recomendaciones** en la agenda («Para ti») con el **motivo** legible.
- [ ] H3.4 **Chat del evento** en la ficha: preguntas, respuestas (también las del asistente IA) y anuncios fijados.
- [ ] H3.5 Aviso visible en la ficha cuando cambia la hora (anuncio fijado).
- [ ] H3.6 PWA: `manifest.json`, service worker e icono; se puede instalar desde el navegador del móvil.

**Criterios de aceptación**
- ✅ Carmen (Senés, senderismo) ve la II Ruta Solidaria **primera** en «Para ti», con el motivo.
- ✅ Se apunta, el contador sube, y con la última plaza ocupada el siguiente queda en lista de espera.
- ✅ Pregunta en el chat y aparece la respuesta sin recargar la página más de una vez.
- ✅ El `.ics` se importa en Google Calendar.
- ✅ Ningún teléfono aparece en el chat ni en la lista de inscritos.
- ✅ **Demo pasos 4–6** vistos desde la web.

**Depende de A (H3):** login, inscripciones, `.ics`, chat y recomendaciones. Plan B del login: selector de usuario en modo demo.

### H4 · Panel y criterios del jurado (sáb 20:00 → dom 00:00 · CP4 · `v0.9` feature freeze)

- [ ] H4.1 **Panel de estadísticas** (`GET /estadisticas`): actividades, % importadas solas, inscripciones vs asistencia, ocupación por categoría y **solapamientos**.
- [ ] H4.2 **Coste en tokens** por proveedor (de la API o de `GET /metrics` del bot).
- [ ] H4.3 Interruptor «Simular caída de la IA» (`LLM_SIMULAR_CAIDA` de B) para enseñar el fallback.
- [ ] H4.4 Accesibilidad WCAG 2.1 AA: contraste, teclado, `aria-label`, **modo letra grande**.
- [ ] H4.5 Capacitor: `npx cap add android` y APK de debug que apunta a la URL pública del túnel.
- [ ] H4.6 Opcional (plan C de la demo): chat simulado del bot en la web con `POST /dev/mensaje`.

**Criterios de aceptación**
- ✅ El panel muestra cifras coherentes con el seed y al menos un solapamiento.
- ✅ Tras hablar con el bot, el coste en tokens del panel sube.
- ✅ La agenda y la ficha se usan solo con teclado; el modo letra grande no rompe ninguna pantalla.
- ✅ El APK se instala en un móvil real y carga eventos de la URL pública.
- ✅ Etiqueta `v0.9`. A partir de aquí solo `fix/*`.

### H5 · Estabilización y entrega (dom 00:00 → 07:00 · E2E y REL `v1.0`)

- [ ] H5.1 Arreglar lo que salga del smoke test y de los ensayos.
- [ ] H5.2 Sección de la app en el README con capturas.
- [ ] H5.3 APK final instalado en el móvil de la demo y vídeo de respaldo.
- [ ] H5.4 Ensayo del guion entero dos veces en la máquina limpia.

**Criterios de aceptación**
- ✅ El guion de 7 pasos sale entero dos veces seguidas.
- ✅ `main` etiquetado `v1.0` antes de las **07:00**.

---

## 4. Dependencias con los otros flujos

| Qué necesita C | De quién | Para | Desde | Mientras tanto |
|---|---|---|---|---|
| `GET /eventos`, ficha, municipios, lugares | A | H1 | ✅ #10 | — |
| Moderación, confirmar, publicadores | A | H2 | CP2 | Fixtures |
| Login Google + JWT | A | H3 | CP3 | Selector de rol/usuario en modo demo |
| Inscripciones, `.ics`, chat, recomendaciones | A | H3 | CP3 | Mocks en `client.ts` |
| `/estadisticas` y tokens | A (y B lo alimenta) | H4 | CP4 | Panel con fixtures |
| `POST /dev/mensaje`, `GET /metrics`, `LLM_SIMULAR_CAIDA` | B | H4 | ✅ #11 | — |
| Bot real en el compose (hoy es el stub) | A/B | H1.8 | CP1 | Probar con el stub |

| Qué da C | A quién | Cuándo |
|---|---|---|
| Web pública en :8080 (y por el túnel) | Jurado y demo | CP1 en adelante |
| Panel de moderación y estadísticas | Moderador en la demo | CP2 / CP4 |
| Revisión de los cambios de contrato que tocan pantallas | A | En cada PR `contract-change` |

---

## 5. Riesgos del flujo C

| Riesgo | Señal | Respuesta |
|---|---|---|
| La API de un hito llega tarde | A las :30 del CP la ruta da 404 | La pantalla sigue con mocks (ya automático); se conecta en el siguiente CP |
| Login con Google se complica | Más de 45 min | Selector de usuario en modo demo |
| Capacitor/Android Studio da guerra | Más de 30 min sin APK | La demo se hace con la PWA instalada en el móvil |
| `VITE_API_URL` mal en el build Docker | La web de :8080 sale con mocks | Revisar `.env` (`VITE_USE_MOCKS=false`) y reconstruir |
| Lint en rojo bloquea un CI futuro | — | Arreglar los 4 errores heredados en una PR `fix/web-lint` |

---

## 6. Pendientes conocidos

- 4 errores de `eslint` heredados (orden de imports en `client.ts` y `Mapa.tsx`, tipo de retorno en `setToken`, `setState` dentro de un efecto en `Agenda.tsx`).
- El compose arranca el **stub** del bot (`infra/stubs/bot`); el bot real está en `services/bot` desde la #11.
- `infra/stubs/web` ya no se usa.
