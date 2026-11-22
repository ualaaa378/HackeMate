# bot · Flujo B (WhatsApp, IA y automatizaciones)

Servicio FastAPI en el puerto **8001**. Recibe WhatsApp (Twilio), usa la IA y habla con `api`.

## Arrancar en local

```powershell
cd services/bot
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # rellenar claves (sin claves funciona con reglas)
uvicorn app.main:app --port 8001 --reload
```

- Chat por terminal sin WhatsApp: `python -m app.consola`
- Tests: `pytest -q`

## Endpoints

| Ruta | Para qué |
|---|---|
| `GET /health` | `{"status":"ok","version":…}` |
| `POST /webhook/telegram` | Entrada de Telegram (canal activo en desarrollo y demo). Comprueba `X-Telegram-Bot-Api-Secret-Token` |
| `GET /webhook/meta` | Verificación del webhook de WhatsApp Cloud API (`hub.challenge`) |
| `POST /webhook/meta` | Entrada de WhatsApp (Meta). Comprueba la firma, contesta 200 al momento y procesa en segundo plano |
| `POST /webhook/twilio` | Entrada alternativa por Twilio (TwiML) |
| `POST /dev/mensaje` | Simulador para desarrollar y probar: `{"de":"+34…","texto":"…"}` → `{"respuestas":[…]}` |
| `POST /ai/extraer` | Texto → `ExtraccionEvento` (requiere `X-Internal-Token`) |
| `POST /notify` | La api pide enviar un aviso. Con `plantilla` + `parametros` usa una plantilla aprobada de WhatsApp (requiere `X-Internal-Token`) |
| `GET /metrics` | Tokens y llamadas por proveedor, eventos en cola |

## Cómo funciona

- `app/llm/router.py`: prueba los proveedores de `LLM_CADENA` en orden. Por defecto, **gratis primero**:
  Gemini (AI Studio) → FreeLLMAPI (proxy local de planes gratuitos, `http://127.0.0.1:31415/v1`; prueba los
  modelos de `FREELLM_MODELOS` en orden con 8 s por intento, porque los planes gratuitos van a tirones) → Claude
  (de pago, solo si hay clave) → reglas. Un proveedor sin clave se salta solo. Cada intento
  registra tokens y latencia en `app/metrics.py`, que además los manda a `POST /api/v1/metrics/tokens`.
  `LLM_SIMULAR_CAIDA=true` hace fallar las IAs para enseñar el fallback en la demo.
- `app/agentes/extractor.py`: post → `ExtraccionEvento` (PLAN.md §5.2). Las reglas sin IA son el último recurso.
- `app/conversacion.py`: el publicador manda un post, el bot pregunta lo que falta, confirma con SÍ/NO
  y lo entrega a `POST /api/v1/eventos/importar`. Si la api está caída, lo guarda en cola.
- `app/canales.py`: `CANAL=meta` (WhatsApp Cloud API, el canal de producción, con botones nativos y
  plantillas), `CANAL=twilio` (alternativa) o `CANAL=console` (imprime, para desarrollar y tests).
- `app/meta.py`: firma `X-Hub-Signature-256` y conversión del JSON de Meta (texto, botones, audio, imagen,
  ubicación). Los reenvíos del webhook se descartan por id de mensaje.

## Telegram

Canal activo hoy: gratis, sin límite de mensajes y sin verificar negocio. Botones en línea, notas de voz,
fotos y ubicación. El usuario se identifica como `tg:<chat_id>` (Telegram no da el teléfono).

1. Crear el bot con @BotFather (`/newbot`) y poner el token en `TELEGRAM_TOKEN`.
2. Registrar el webhook (una vez por URL del túnel):
   `python -c "from app import telegram; print(telegram.configurar_webhook('https://<túnel>/webhook/telegram'))"`

Los destinos `tg:` siempre salen por Telegram, así que Telegram y WhatsApp pueden convivir.

## WhatsApp en producción

Bloqueado durante la hackathon: Meta exige verificación de negocio y método de pago (errores 141010, 141006
y 131031). El adaptador está hecho y probado contra la API real.

- Número propio del ayuntamiento o la Diputación registrado en WhatsApp Cloud API (requiere verificar el negocio en Meta).
- Responder a quien escribe al bot (ventana de 24 h) es gratis. Los avisos que inicia el bot fuera de esa
  ventana necesitan **plantillas aprobadas** por Meta y se cobran por mensaje según la tarifa de Meta para España.
- En desarrollo usamos el número de prueba de Meta (gratis, hasta 5 teléfonos verificados).

## Pendiente de acordar con Flujo A (contratos)

Cuerpo de `POST /api/v1/eventos/importar` que envía el bot:

```json
{ "extraccion": { "campos": {…}, "faltan": […], "es_evento": true, "proveedor_ia": "…", "tokens": {…} },
  "telefono_publicador": "+34…",
  "origen": { "canal": "whatsapp", "url": null, "importado_auto": false } }
```

Cuerpo de `POST /api/v1/metrics/tokens`: `proveedor, modelo, tarea, tokens_entrada, tokens_salida, latencia_ms, ok, ts`.
