# Para el flujo A (Benas): lo que el bot necesita de la API

> Escrito por el flujo B el viernes 20 nov, 23:55. **No se ha tocado nada de `services/api/`, `contracts/` ni `infra/`.**
> Todo lo de aquí es una propuesta: decides tú. El bot ya llama a estas rutas tal como dice el contrato.
> Mientras no existan, degrada con elegancia (enlaza a la web o guarda en cola) y en cuanto existan funcionan sin tocar el bot.

## 1. Endpoints que faltan, por orden de la demo

| # | Ruta | Paso de la demo | Qué manda el bot | Qué espera |
|---|---|---|---|---|
| 1 | `POST /api/v1/eventos/{id}/confirmar` | 2 y 3 | `{"campos": {"municipio": "Senés", …solo lo que completó el publicador}, "confirmado_por": "telegram"}` + `X-Internal-Token` | `ResultadoImportacion` con `evento.estado` = `publicado` o `en_revision`. El bot dice «¡Publicado!» o «El moderador lo revisará» según ese estado |
| 2 | Moderación automática al confirmar | 3 | — (la llama la API) | Que la API llame a `bot POST /ai/spam` `{"texto", "contexto": "evento"}` → `{score_spam, es_spam, motivo, proveedor_ia}` y aplique niveles 0/1/2 y `MODERACION_UMBRAL_SPAM` |
| 3 | `GET /api/v1/moderacion/pendientes?size=5` | 3 | `X-Internal-Token` | `{"items": [Pendiente]}` con `tipo: "evento"`, `motivo`, `score_spam`, `evento` |
| 4 | `POST /api/v1/moderacion/{id}/decision` | 3 | `{"decision": "aprobar"\|"rechazar", "motivo": "Decidido por chat (telegram)"}` | El `Evento` tras la decisión (el bot usa `titulo`) |
| 5 | `POST /api/v1/eventos/{id}/inscripciones` | 4 | `{"usuario_id", "plazas": 1, "canal": "telegram"}` + `X-Internal-Token` | `Inscripcion` con `estado` `confirmada` o `lista_espera` (+ `posicion_espera`). 409 si ya estaba apuntado |
| 6 | `PATCH /api/v1/eventos/{id}` con cambio de hora → `bot POST /notify` a cada inscrito | 6 | — (lo dispara la API) | Ver §2 |
| 7 | `POST /api/v1/eventos/{id}/mensajes` | 5 | `{"texto", "tipo": "pregunta", "usuario_id"}` + `X-Internal-Token` | 201. El bot solo lo usa cuando la respuesta **no** está en la ficha (lo que sí está lo responde él) |
| 8 | `GET /api/v1/recomendaciones?usuario_id=…&limite=3` | 4 | `X-Internal-Token` | `{"items": [Recomendacion]}` con `evento` y `motivo` legible («Te gusta el senderismo y está a 4 km») |
| 9 | `POST /api/v1/metrics/tokens` | Jurado | `MetricaTokens` de cada llamada a la IA (ya lo manda) | 202. Hoy da 404 |

**⚠️ Importante para que el bot distinga «no implementado» de «no existe»:** cuando una ruta **no existe**, la API devuelve
`404 {"error": {"code": "no_encontrado"}}` (el manejador genérico). Cuando la ruta existe pero **el evento no**, usad un código
propio (`evento_no_encontrado`, como ya hacéis). El bot se basa en eso.

## 2. Avisos (`POST bot:8001/notify`)

```json
{
  "telefono": "+34600000201",
  "contacto": "tg:6374766570",
  "tipo": "cambio_evento",
  "texto": "La Ruta por la sierra pasa a las 11:00 del sábado 28.",
  "evento_id": "…",
  "formato": "audio"
}
```

- `contacto` manda sobre `telefono`: `tg:…` sale por Telegram y `+34…` por el canal de WhatsApp.
- `formato: "audio"` (del `usuario.formato_aviso`): el aviso llega también **en nota de voz**. Es el paso 7 de la demo.
- `tipo: "recomendacion"` con `evento_id` → el aviso lleva los botones **[Apuntarme] [Más info]** (paso 4).
- Si el bot está caído, que la API lo deje en `estado_envio = pendiente` como dice el contrato.

## 3. Propuesta de contrato (solo añadido)

`PATCH /api/v1/usuarios/{id}` con `X-Internal-Token` y cuerpo `UsuarioEditar`. Ahora solo existe `PATCH /usuarios/me`, que pide
el login del usuario, y el bot no puede guardar los gustos («me gustan las rutas»), el pueblo ni el formato de aviso.
Mientras tanto, el bot los guarda en memoria.

## 4. El bot en el `docker-compose` (tu archivo: lo cambias tú cuando quieras)

> **Actualización (sáb 21, 00:00):** Adán ha abierto el **PR #23**, que ya hace lo principal: `build: ../services/bot`,
> `FREELLM_URL_DOCKER` → `host.docker.internal`, `extra_hosts` y `WEB_URL`. Sobre ese PR solo quedarían dos añadidos
> opcionales del bloque de abajo: el **volumen `bot_data`** con `COLA_PATH` (para que la cola sobreviva si se recrea el
> contenedor) y **`PUBLIC_URL`** en el `.env` si hay túnel con URL fija. Falta probarlo con `docker compose up --build`.

Bloque completo de referencia para el servicio `bot` de `infra/docker-compose.yml`:

```yaml
  bot:
    <<: *env
    build: ../services/bot
    environment:
      API_URL: http://api:8000
      # FreeLLMAPI corre fuera de Docker, en el portátil de Francisco
      FREELLM_URL: ${FREELLM_URL_DOCKER:-http://host.docker.internal:31415/v1}
      COLA_PATH: /srv/data/cola_pendiente.json
    extra_hosts:
      - "host.docker.internal:host-gateway"   # para que también funcione en Linux
    volumes:
      - bot_data:/srv/data                    # la cola sobrevive a reinicios del contenedor
    ports:
      - "8001:8001"

volumes:
  db_data:
  bot_data:
```

- **FreeLLMAPI en Docker:** ya no hace falta la app de escritorio de Francisco. `services/bot/freellmapi/` lo levanta en cualquier máquina (README allí). Con ese compose, en el `.env` de la raíz: `FREELLM_URL_DOCKER=http://host.docker.internal:3001/v1` y su clave unificada en `FREELLM_API_KEY`. No hay que tocar `infra/`.
- **Nadie depende del bot para arrancar.** Si falla, `api` y `web` siguen funcionando.
- **Variables:** en Docker, el bot lee el `.env` de la raíz, así que ahí tienen que estar `TELEGRAM_TOKEN`, `TELEGRAM_SECRET`, `FREELLM_API_KEY` e `INTERNAL_TOKEN` (las claves, por privado).
- **Telegram necesita la URL pública del túnel:**
  - **Con `CLOUDFLARE_TUNNEL_TOKEN`** (URL fija): se pone `PUBLIC_URL=https://…` en el `.env` y el bot se registra solo al arrancar.
  - **Con túnel rápido** (la URL cambia): tras `docker compose logs tunnel`, una llamada basta, sin reiniciar:
    `curl -X POST localhost:8001/admin/webhook-telegram -H "X-Internal-Token: …" -H "Content-Type: application/json" -d '{"public_url": "https://….trycloudflare.com"}'`
- **El túnel tiene que apuntar al bot** (`--url http://bot:8001`), como ya está.

## 5. Para el panel (Adán), pasando por la API

- **Simular la caída de la IA:** `POST bot:8001/admin/simular-caida {"activa": true|false}` con `X-Internal-Token`. Mejor que lo llame la API, para no poner el token en el navegador.
- **Coste en tokens:** `GET bot:8001/metrics` (`totales` por proveedor, `ultimas` llamadas, `eventos_en_cola`, `caida_simulada`).
