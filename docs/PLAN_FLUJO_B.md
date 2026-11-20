# PLAN_FLUJO_B.md · Bot de mensajería, IA y automatizaciones

> Hackathon UAL para el desarrollo del interior · Reto 1 «Reactiva tu pueblo» · 20–22 nov 2026
> Responsable del flujo B: **Francisco Sánchez** (Dev B) · Rama: `Flujo-B` · Carpeta: `services/bot/`
> Complementa a `docs/PLAN.md` (plan general) y `docs/PROGRESO.md` (checklist). Si algo choca, manda `PLAN.md`.
> Escrito para que las personas **y sus Claudes** sepan qué hace el bot, qué se ha decidido y cómo integrarse.
> Última actualización: viernes 20 nov, 23:45 (Hito 3).

---

## 0. Resumen en 30 segundos

- `services/bot/` es un servicio FastAPI en el **puerto 8001**. Recibe mensajes de **Telegram** (canal activo) y de **WhatsApp**, usa la IA y habla con `api` por HTTP. Nunca toca la base de datos.
- **Canal activo: Telegram** (`@HackeMate_bot`): es gratis, no tiene límite de mensajes y no pide verificar ningún negocio.
- **WhatsApp Cloud API (Meta)** está programado y probado contra la API real, pero **Meta bloquea el envío** hasta que una entidad verifique su negocio y añada un método de pago (§3). Queda listo para producción.
- **IA gratis primero:** Gemini → FreeLLMAPI → Claude (solo si hay clave) → reglas sin IA. Si se cae todo, el bot sigue funcionando con reglas.
- **Ya funciona de punta a punta contra la API real:** un post, **una foto del cartel o una nota de voz** en Telegram → la IA saca la ficha → `POST /api/v1/eventos/importar` (queda asociado al publicador por su número) → el bot pregunta lo que la API dice que falta → botones [Sí, publicar] [No] → `POST /eventos/{id}/confirmar`. Si la api no está, queda en cola.

---

## 1. Qué hace el bot y qué NO hace

**Hace:**
- Recibir mensajes (texto, botones, notas de voz, fotos y ubicación) de Telegram, WhatsApp (Meta) y Twilio.
- Contestar al momento (el acuse) y procesar en segundo plano.
- Toda la IA del proyecto: extraer eventos, antispam, preferencias y responder con la ficha (`POST /ai/*`).
- Enviar los avisos que pide la `api` con `POST /notify`.
- Registrar los tokens de cada llamada a la IA (`POST /api/v1/metrics/tokens`) para el criterio «coste en tokens».

**No hace** (reglas de `CLAUDE.md`):
- No guarda datos de negocio ni decide estados: eso es de la `api` (Flujo A). La IA propone y la `api` decide.
- No tiene pantallas: eso es de la `web` (Flujo C). La web puede usar `POST /dev/mensaje` como simulador de chat.

---

## 2. Arquitectura del servicio

```
Telegram ──▶ POST /webhook/telegram ┐
WhatsApp ──▶ POST /webhook/meta     ├─▶ conversacion.py ──▶ agentes/extractor.py ──▶ llm/router.py ──▶ Gemini / FreeLLMAPI / Claude / reglas
Twilio   ──▶ POST /webhook/twilio   ┘          │                                            │
                                               ▼                                            ▼
                                     api_cliente.py ──▶ api POST /api/v1/eventos/importar   metrics.py ──▶ api POST /api/v1/metrics/tokens
api ──▶ POST /notify ──▶ canales.py ──▶ telegram.py / Graph API (Meta) / Twilio / consola
```

| Archivo | Para qué |
|---|---|
| `app/main.py` | Endpoints, webhooks y comprobación de firmas o secretos |
| `app/conversacion.py` | Entrada de todos los mensajes: publicador, moderador e identidad; decide la intención y deriva |
| `app/vecino.py` | Vecino: buscar planes, gustos, [Apuntarme], [Más info] y preguntas sobre un evento |
| `app/agentes/intencion.py`, `busqueda.py`, `preferencias.py`, `asistente.py` | Intención (reglas), filtros de búsqueda, gustos y asistente con la ficha |
| `app/agentes/extractor.py` | Post → `ExtraccionEvento`. Incluye las reglas sin IA (plan C) |
| `app/llm/router.py`, `app/llm/proveedores.py` | Cadena de proveedores de IA con timeout, fallback y registro de tokens |
| `app/canales.py` | Salida: decide si el mensaje va por Telegram, Meta, Twilio o consola |
| `app/telegram.py`, `app/meta.py` | Adaptadores de entrada y salida de cada canal |
| `app/api_cliente.py` | Cliente HTTP de la `api`, con cola en memoria si la `api` está caída |
| `app/metrics.py` | Tokens y latencia por llamada (`GET /metrics` y envío a la `api`) |

**Identidad del usuario:** en WhatsApp es el teléfono E.164 (`+34600000000`). En Telegram es `tg:<chat_id>`, porque Telegram no da el teléfono. Para casar las dos, el bot pedirá el número con el botón «Compartir mi número» (§5).

---

## 3. Decisiones tomadas (y por qué)

| Decisión | Motivo |
|---|---|
| **Telegram como canal activo** | Gratis, sin límite de mensajes, sin verificar negocio. Tiene botones, notas de voz y ubicación |
| **WhatsApp Cloud API (Meta) como canal de producción** | Es la vía oficial y la más barata para un ayuntamiento: responder a quien escribe es gratis y solo se pagan las plantillas que inicia el bot fuera de las 24 h. **Bloqueado ahora:** la API de Meta devuelve `141010` (negocio sin verificar), `141006` (sin método de pago) y `131031` (cuenta bloqueada). Verificar exige documentos reales de una entidad (CIF…); **no se inventan datos**. Si la Diputación o la UAL tienen un portfolio verificado, basta con poner `CANAL=meta` |
| Twilio y otros sandboxes, solo como alternativa | 100 mensajes (Twilio), 100 al mes (Vonage) o 25 (360dialog): se quedan cortos. El adaptador de Twilio sigue en el código (`CANAL=twilio`) |
| **IA: gratis primero** | Somos estudiantes, coste 0. Claude solo entra si alguien pone `ANTHROPIC_API_KEY` |
| FreeLLMAPI con varios modelos en orden y 8 s por intento | Los planes gratuitos van a tirones (0,5–12 s, 429). Primero `qwen3.8-27b` (Groq, ~1 s) |
| Validación tolerante de la salida de la IA | Los modelos gratuitos se saltan a veces el esquema (`"9€"`, `"Gastronomía"`): mejor normalizar que perder la ficha |
| Ficha y primera pregunta en un solo mensaje | Menos mensajes (coste en WhatsApp) y más fácil de leer |
| Botones nativos para confirmar (uno por fila en Telegram) | Accesibilidad para personas mayores |
| Voz y carteles → texto → el extractor de siempre | Transcripción (Whisper) y visión (`gemini-flash-lite`) gratis por FreeLLMAPI, ~1–3 s. El bot repite lo que ha entendido («🎙️ He entendido: …») para que la persona lo compruebe. Tolerante a errores de la voz: «Belefique» → Velefique |
| Identidad en Telegram con «Compartir mi número» | Telegram no da el teléfono; con el botón, la API asocia el chat al vecino o al publicador (`/usuarios/vincular`) |

---

## 4. Endpoints del bot (puerto 8001)

| Ruta | Quién la llama | Estado |
|---|---|---|
| `GET /health` | todos | ✅ |
| `POST /webhook/telegram` | Telegram. Cabecera `X-Telegram-Bot-Api-Secret-Token` | ✅ funcionando |
| `GET/POST /webhook/meta` | Meta (verificación `hub.challenge` y firma `X-Hub-Signature-256`) | ✅ programado · envío bloqueado por Meta |
| `POST /webhook/twilio` | Twilio (TwiML) | ✅ alternativa |
| `POST /notify` | `api` (`X-Internal-Token`). Cuerpo: `Notificacion` (`contacto` `+34…`/`tg:…`, `plantilla`, `parametros`) | ✅ envío · ⏳ usar `contacto` (H3) |
| `POST /ai/extraer` | `api` (`X-Internal-Token`) → `ExtraccionEvento` | ✅ |
| `POST /ai/spam` | `api` (`X-Internal-Token`) → `{score_spam, es_spam, motivo, proveedor_ia}`. Reglas primero; IA solo si duda (0,3–0,7) | ✅ |
| `POST /ai/responder-ficha` | `api` → `{puede_responder, respuesta, proveedor_ia}`. Solo con la ficha; reglas para hora/precio/lugar/plazas, IA para lo demás | ✅ |
| `POST /ai/preferencias` | `api` → `{gustos, etiquetas_interes, municipio, formato_aviso}` | ✅ |
| `POST /dev/mensaje` | web o tests: `{"de": "+34…", "texto": "…"}` → `{"respuestas": […]}` | ✅ simulador de chat |
| `GET /metrics` | panel (Flujo C) | ✅ tokens, fallos y eventos en cola |

### Lo que el bot envía a la `api` (cumple el contrato v1)

- `POST /api/v1/eventos/importar` con `ImportarEvento`: `{extraccion, contacto_publicador, origen: {canal, url, importado_auto}}`.
- `POST /api/v1/eventos/{id}/confirmar` con `{campos, confirmado_por}`. **Mientras A no lo implemente**, el bot guarda los campos con `PATCH /api/v1/eventos/{id}` y el evento sigue en `pendiente_confirmacion`.
- `GET /api/v1/usuarios/by-contacto/{contacto}` (saludar por el nombre, saber si es moderador) y `POST /api/v1/usuarios/vincular` («Compartir mi número»).
- `GET /api/v1/moderacion/pendientes` y `POST /api/v1/moderacion/{id}/decision` (bandeja del moderador por chat).
- `POST /api/v1/metrics/tokens` con `MetricaTokens`: `{proveedor, modelo, tarea, tokens_entrada, tokens_salida, latencia_ms, ok, ts}`.

---

## 5. Lo que B necesita de los demás

### Del Flujo A (Benas): cambios de contrato

✅ **Hechos por A en la PR #12** (con su propio diseño: componente `Contacto`, `contacto_publicador`, `by-contacto` y `vincular`). El bot ya los usa. Lo que se pidió:

1. **Enum `canal`:** añadir `telegram`. El bot ya marca así el origen de los eventos de Telegram.
2. **`Usuario.telegram_id`** (string, opcional). El bot pedirá el teléfono con el botón «Compartir mi número» de Telegram. Así **`telefono` E.164 sigue siendo la identidad** en `ImportarEvento` y `Notificacion`, y el bot sabe a qué chat de Telegram mandar cada aviso.
3. **`Notificacion.plantilla` y `Notificacion.parametros`** (opcionales): WhatsApp exige plantillas aprobadas para los avisos fuera de la ventana de 24 h. En Telegram se ignoran.
4. **Documentar en `openapi.yaml`** `POST /webhook/telegram`, `GET/POST /webhook/meta` y `POST /dev/mensaje` (contract-first).

### Del Flujo A: integración

- `infra/docker-compose.yml`: cambiar el stub por `build: ../services/bot` (ya tiene Dockerfile y `/health`).
- El túnel debe apuntar al bot. Con túnel rápido, la URL cambia en cada arranque y hay que volver a registrar el webhook de Telegram (§7). Con `CLOUDFLARE_TUNNEL_TOKEN` la URL es fija.
- ✅ `POST /eventos/importar`, `by-contacto` y `vincular` implementados y probados con el bot.
- ⏳ **Pendiente para H2 de la demo:** `POST /eventos/{id}/confirmar` (con la moderación automática que llame a `bot POST /ai/spam`), `GET /moderacion/pendientes` y `POST /moderacion/{id}/decision`. El bot ya los llama; en cuanto existan, funcionan sin tocar nada.
- ⏳ `POST /api/v1/metrics/tokens` (ahora 404): el bot ya envía cada llamada a la IA.
- ⏳ **Para H3 de la demo** (el bot ya los llama): `POST /eventos/{id}/inscripciones` (con `usuario_id` y `X-Internal-Token`), `POST /eventos/{id}/mensajes` y `GET /recomendaciones`. Mientras no existan, el bot enlaza a la ficha de la web.
- 🆕 **Propuesta de contrato:** `PATCH /api/v1/usuarios/{id}` con `X-Internal-Token` (mismo cuerpo que `UsuarioEditar`) para que el bot guarde gustos, pueblo y formato de aviso. Hoy solo existe `PATCH /usuarios/me` con login de usuario.

### Del Flujo C (Adán)

- Opcional, como plan C de la demo: un chat simulado en la web que llame a `POST /dev/mensaje`.
- Panel: mostrar `GET /metrics` del bot (o `GET /api/v1/estadisticas` cuando la `api` guarde los tokens) y un interruptor de «simular caída del LLM» (variable `LLM_SIMULAR_CAIDA`).

---

## 6. Hitos del flujo B

| Hito | Cuándo | Qué | Estado |
|---|---|---|---|
| H1 · El bot entiende un post | CP1 (vie noche) | Webhooks, IA gratis con fallback, extractor, conversación del publicador, Telegram de punta a punta | 🟢 hecho (falta el bot en el compose, A) |
| H2 · Carteles, audios y moderación | CP2 (sáb 13:00) | Foto del cartel y nota de voz → ficha; antispam (`/ai/spam`); flujo importar → confirmar según contrato; el moderador por chat | 🟢 hecho en el bot y probado con la API real · espera `/confirmar` y `/moderacion/*` de A |
| H3 · La vecina | CP3 (sáb 19:00) | Gustos (`/ai/preferencias`), «qué hay cerca», inscribirse con botón, avisos de `/notify`, asistente con la ficha (`/ai/responder-ficha`), uso solo con audios | 🟢 hecho en el bot y probado con la API real · espera inscripciones, chat y recomendador de A |
| H4 · Extras para el jurado | CP4 (sáb noche) | Botón de caída del LLM en el panel, respuesta en audio (TTS), idiomas | ⏳ |

Checklist detallado: `docs/PROGRESO.md` → «Flujo B».

---

## 7. Cómo ejecutar y probar

```powershell
cd services\bot
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env            # rellenar TELEGRAM_TOKEN, FREELLM_API_KEY… (claves por privado)
uvicorn app.main:app --port 8001
python -m pytest -q               # 81 tests, sin red ni claves (la api se simula en tests/conftest.py)
python -m app.consola             # chat por terminal, sin Telegram
```

Con Telegram real:
1. Abrir el túnel: `cloudflared tunnel --url http://localhost:8001`. Copiar la URL `https://….trycloudflare.com`.
2. Registrar el webhook (una vez por URL):
   `python -c "from app import telegram; print(telegram.configurar_webhook('https://<túnel>/webhook/telegram'))"`
3. Escribir a `t.me/HackeMate_bot`.

**Ojo para los Claudes:** el bot lee `.env` desde la carpeta donde se arranca (`services/bot/`). En Docker, las variables llegan del `.env` de la raíz. Los tests ponen sus propias variables en `tests/conftest.py`: no dependen del `.env`.

---

## 8. Reglas para trabajar con el flujo B (personas y Claudes)

- **No edites `services/bot/`** si no eres del flujo B. Pide el cambio a Francisco o abre una PR.
- **No inventes datos para la verificación de Meta** ni para ningún otro registro. Si hace falta una cuenta verificada, se pide a la organización.
- **No subas claves.** `TELEGRAM_TOKEN`, `META_TOKEN`, `FREELLM_API_KEY`… van en `.env`, que no se versiona.
- **Coste 0:** no añadas proveedores de pago como predeterminados. Si algo cuesta dinero, se pregunta antes.
- Si cambias algo que el bot consume (`ImportarEvento`, `Notificacion`, `ExtraccionEvento`, el enum `canal`), avisa: el bot valida esos formatos.
