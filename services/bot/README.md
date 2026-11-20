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
| `POST /webhook/twilio` | Entrada de WhatsApp. Responde al momento con TwiML (acuse) y procesa en segundo plano |
| `POST /dev/mensaje` | Simulador: `{"de":"+34…","texto":"…"}` → `{"respuestas":[…]}` (plan C de la demo) |
| `POST /ai/extraer` | Texto → `ExtraccionEvento` (requiere `X-Internal-Token`) |
| `POST /notify` | La api pide enviar un aviso (requiere `X-Internal-Token`) |
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
- `app/canales.py`: `CANAL=console` imprime; `CANAL=twilio` envía WhatsApp de verdad.

## Pendiente de acordar con Flujo A (contratos)

Cuerpo de `POST /api/v1/eventos/importar` que envía el bot:

```json
{ "extraccion": { "campos": {…}, "faltan": […], "es_evento": true, "proveedor_ia": "…", "tokens": {…} },
  "telefono_publicador": "+34…",
  "origen": { "canal": "whatsapp", "url": null, "importado_auto": false } }
```

Cuerpo de `POST /api/v1/metrics/tokens`: `proveedor, modelo, tarea, tokens_entrada, tokens_salida, latencia_ms, ok, ts`.
