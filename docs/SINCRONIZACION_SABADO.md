# Propuesta de sincronización · sábado 21/11

> Propuesta del flujo A (Benas), 09:45. **Es para revisarla entre los tres**: lo que no os encaje se cambia aquí mismo, por PR o comentándolo en el grupo.
> Cómo probar y qué salió en la primera prueba: [`PRUEBAS_V1.md`](PRUEBAS_V1.md). Reparto de tareas al momento: `README.md` § «🔗 Pendiente entre flujos».

## 1. Dónde estamos

- **Vamos por delante del cronograma** (`PLAN.md` §6). Lo que había que programar para CP2 (13:00) y CP3 (19:00) ya está en `develop`:
  - la API completa (#35);
  - el bot con Telegram (#34);
  - la web con el panel (#30–#33, #36).
- **Lo que falta no es programar, es probar y arreglar:** nada se ha probado todavía junto en Docker con Telegram real.
- **Etiquetas:** no se ha puesto ninguna (`v0.1`…). Las proponemos en cada checkpoint de hoy (§4).
- **Benas no está en la hackathon:** trabaja en remoto y **no puede ejecutar Docker**. Puede arreglar la API, probarla sin Docker y revisar PRs.

## 2. Papeles de hoy

| Quién | Papel | Lo que solo hace esa persona |
|---|---|---|
| **Adán (C)** | **Máquina de la demo**: Docker, túnel y web | El único con `PUBLIC_URL` en su `.env` (el que tiene el webhook de Telegram). Hace `down -v` / `up --build` y los ensayos |
| **Fran (B)** | Bot e IA | Mantiene FreeLLM en su portátil y las claves de IA. Arregla los hallazgos del bot. **Sin `PUBLIC_URL`** mientras Adán ensaya (si no, le quita el webhook) |
| **Benas (A)** | API y datos, en remoto | Arregla lo que salga de la API (avisado por el grupo o por el README) y repite la prueba local tras cada cambio. Revisa las PRs de A |

## 3. Cómo trabajamos hoy (reglas cortas)

1. **Fallos:** se apuntan en `README.md` § «Pendiente entre flujos», bajo el flujo que los arregla, con este formato:
   `- [paso N] Qué hice → qué esperaba → qué pasó (error o captura) · quién lo vio · hora`
   Si bloquea la demo, además se avisa en el grupo.
2. **Ramas:** cada uno en la suya (`Flujo-A`, `Flujo-B`, ramas de Adán) → **PR a `develop`**. Cambios pequeños y frecuentes; los arreglos, con `fix(...)`.
3. **Merge:** quien abre la PR la mergea en cuanto pasan sus tests y no toca la carpeta de otro. Si toca contratos (`contract-change`) o el compose, otro del equipo la mira antes. En los checkpoints el orden es **A → B → C**.
4. **Sincronizar:** `git pull origin develop` (o integrarlo en tu rama) **cada vez que alguien avise de un merge**, y como mínimo cada hora.
5. **`.env`:** nunca se sube. `INTERNAL_TOKEN` es el mismo para todos. Las claves van por privado. Resumen en `PRUEBAS_V1.md` § «Los `.env` del equipo».
6. **Si algo bloquea más de 20 minutos, se recorta** (lo dice `CLAUDE.md`). Antes de recortar algo del guion, se pregunta en el grupo.

## 4. Plan del día (ajustado al cronograma)

| Hora | Qué | Quién | Resultado |
|---|---|---|---|
| **10:00–10:30** | **Revisión conjunta de la v1** (§5) por llamada: repasar esta propuesta y la tabla de §5, y decidir lo de §6 | Los tres | Propuesta aceptada o cambiada; decisiones de §6 tomadas |
| 10:30–12:00 | **Prueba con Docker**: `down -v`, `up --build`, smoke test, `simular_chat.py` y guion con Telegram | Adán (Fran ayuda con el bot) | Tabla de §5 rellenada y fallos en el README |
| 10:30–13:00 | Arreglos según lo que salga | A, B y C cada uno lo suyo | PRs `fix` a `develop` |
| **13:00–14:00** | **CP2 · pasos 1–3** en Docker con Telegram: post o audio → ficha → confirmar → moderación (uno aprobado, otro parado) | Adán ejecuta, todos miran | Etiqueta `v0.2` en `develop` si sale bien |
| 14:00–19:00 | Arreglos de los pasos 4–7, panel (botón de caída de la IA y coste), APK con Capacitor y lo que esté en §6 | Según el reparto | PRs |
| **19:00–20:00** | **CP3 · pasos 4–7 + congelación de contratos v2**. Desde aquí **no se cambian contratos** | Los tres | Etiqueta `v0.3` |
| 20:00–00:00 | Criterios del jurado, extras y vídeo de respaldo | Según el reparto | — |
| **Dom 00:00** | **CP4 · feature freeze**: solo `fix/*` | Los tres | Etiqueta `v0.9` |

## 5. Revisión de la v1: qué tiene que funcionar (rellenar en la prueba)

Estado: ✅ funciona · 🟡 funciona con fallos · ❌ no funciona · ⚪ sin probar. La columna «Local» es la prueba de Benas sin Docker (bot sin IA ni Telegram).

| # | Paso del guion | Responsable | Local (Benas) | Docker + Telegram (Adán) |
|---|---|---|---|---|
| 0 | `down -v` + `up --build` arranca los 5 servicios; smoke test en verde | A (infra) / C (ejecuta) | ✅ smoke | ⚪ |
| 1 | Post o audio → ficha | B (extracción) · A (`importar`) | 🟡 título sin IA | ⚪ |
| 2 | El publicador confirma por el bot | B · A (`confirmar`) | ✅ | ⚪ |
| 3 | El moderador aprueba uno y el antispam para otro (bot y panel) | A · C (panel) | ✅ API · 🟡 spam sin fecha | ⚪ |
| 4 | A Carmen le llega la recomendación y se apunta (botón [Apuntarme]) | A (recomendador) · B (botones) | ✅ | ⚪ |
| 5 | Pregunta en el chat del evento (web) y respuesta con la ficha | A · C · B (`/ai/responder-ficha`) | ✅ API | ⚪ |
| 6 | Cambio de hora → aviso a los inscritos (en audio para Carmen) | A (`PATCH` + `/notify`) · B (audio) | ✅ texto | ⚪ |
| 7 | Una persona mayor lo hace todo solo con audios | B | ⚪ | ⚪ |
| W | Web: agenda, mapa, ficha, inscripción, chat, Recuerdos, panel | C | ⚪ (sin Node) | ⚪ |
| T | Tests: api 566 · bot 108 · web `npm test` | cada flujo | ✅ api y bot | ⚪ web |

## 6. Decisiones para la revisión de las 10:00

| # | Decisión | Opciones | Propuesta de A |
|---|---|---|---|
| D1 | **Avisos a quien solo usa Telegram** (`/notify` exige `telefono`) | a) Para la demo, que los inscritos compartan su número · b) Quitar el `required` del contrato (no es aditivo: lo tienen que aprobar los tres) | **a) hoy**; b) si da tiempo antes de CP3 (después, congelado) |
| D2 | **Código de acceso a la web por Telegram** | a) Enlace `t.me/HackeMate_bot?start=alta` + «Compartir mi número» antes de pedir el código · b) Para la demo, solo Google y el modo demo | **b) hoy** (`/auth/demo` con `DEMO_MODE=true`); a) si sobra tiempo |
| D3 | **IA en la máquina de la demo** | a) Clave gratis de Gemini en el `.env` de Adán · b) FreeLLM del portátil de Fran por la red local (`FREELLM_URL_DOCKER`) | **a) y b) a la vez**: si cae una, entra la otra y, al final, las reglas |
| D4 | **Etiquetas** `v0.2`/`v0.3`/`v0.9` en `develop` | En cada checkpoint, si su prueba sale bien | Sí; la pone quien ejecuta el checkpoint (Adán) |
| D5 | **Seguridad**: el código de verificación queda en claro en la cola de avisos | a) Dejarlo (caduca en 10 min y es de un solo uso) · b) Enmascararlo cuando se envíe | **a)** para la demo; queda anotado como deuda |
| D6 | **La «II Ruta Solidaria» ya viene publicada en el seed** | Si se importa la misma en directo, irá a revisión como duplicado | Usarlo en el paso 3 como «el moderador aprueba uno» |
| D7 | **El token de Telegram ha circulado en un PDF** | Regenerarlo con @BotFather y pasarlo por privado | Si el PDF ha estado en algún sitio compartido: **Fran lo regenera** |

## 7. Plan B si algo falla en directo

| Falla | Plan B (ya programado) |
|---|---|
| La IA (Gemini y FreeLLM) | El bot sigue con reglas. El botón «Simular caída» del panel lo enseña como fortaleza |
| Telegram o el túnel | `python scripts/simular_chat.py` o `bot /dev/mensaje` (chat simulado), y la web para el resto |
| El bot | La API guarda los avisos en cola y los reenvía sola cuando vuelve |
| Docker en la máquina de la demo | Arranque sin Docker (`PRUEBAS_V1.md` §3, opción A) y vídeo de respaldo |
| Los datos quedan sucios tras un ensayo | `scripts/demo_reset.sh` (1–2 s) |
