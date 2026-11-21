# FreeLLMAPI en Docker (IA gratis para el bot)

[FreeLLMAPI](https://github.com/tashfeenahmed/freellmapi) junta los planes gratuitos de varios proveedores de IA (Google
AI Studio, Groq, OpenRouter, NVIDIA NIM, Z.ai, UnoRouter, ElectronHub…) detrás de **un único endpoint compatible con
OpenAI**. El bot lo usa para extraer fichas, leer carteles, transcribir notas de voz, hablar y traducir, **sin coste**.

Esta carpeta lo deja **replicable en cualquier máquina con Docker**: la configuración va en archivos, no en clics del
panel. En el repo solo están las plantillas; **las claves nunca se suben**.

| Archivo | ¿Se sube a git? | Qué es |
|---|---|---|
| `docker-compose.yml` | ✅ | El contenedor (imagen oficial `ghcr.io/tashfeenahmed/freellmapi`) |
| `freellmapi.config.example.json` | ✅ | Plantilla con los 7 proveedores y huecos para las claves |
| `.env.example` | ✅ | Plantilla de variables (`ENCRYPTION_KEY`, puerto) |
| `freellmapi.config.json` | ❌ | **Tus claves en claro.** Se pasa por privado, nunca por git ni por grupos |
| `.env` | ❌ | Tu `ENCRYPTION_KEY` |

## Ponerlo en marcha (5 minutos)

```powershell
cd services\bot\freellmapi
copy .env.example .env
copy freellmapi.config.example.json freellmapi.config.json
python -c "import secrets; print(secrets.token_hex(32))"   # pega el resultado en ENCRYPTION_KEY del .env
```

1. En `freellmapi.config.json`:
   - pon tus claves de cada proveedor;
   - **borra las líneas de los proveedores que no tengas**, para no cargar claves falsas;
   - cambia el email y la contraseña de `admin`, que es la cuenta del panel.
2. Arranca:
   ```powershell
   docker compose up -d
   ```
   **Crea siempre `freellmapi.config.json` antes de arrancar.** Si no existe, Docker crea en su lugar una carpeta con ese nombre y el contenedor falla.
3. Abre http://localhost:3001, entra con el email y la contraseña de `admin` y **copia la clave unificada**
   (`freellmapi-…`) que sale en la página *Keys*. Esa clave no se puede fijar por configuración: cada instalación
   tiene la suya.
4. Conecta el bot:

   | Dónde corre el bot | `FREELLM_URL` | `FREELLM_API_KEY` |
   |---|---|---|
   | En local (`uvicorn`, `services/bot/.env`) | `http://127.0.0.1:3001/v1` | la clave unificada |
   | En el compose principal (`infra/`, `.env` de la raíz) | `FREELLM_URL_DOCKER=http://host.docker.internal:3001/v1` | la clave unificada |

   El compose principal ya traduce `FREELLM_URL_DOCKER` a `FREELLM_URL` dentro del contenedor del bot, así que no hay que tocarlo.

Para comprobar que funciona: `docker compose ps` debe decir `healthy`, y en el panel cada proveedor debe salir como «correcto».

## Pasar de la app de escritorio a Docker

La app de escritorio usa el puerto **31415** y Docker el **3001**, así que pueden convivir mientras pruebas. Las claves de
la app de escritorio están cifradas en su base de datos (`%APPDATA%\FreeLLMAPI\`) y no se pueden sacar en claro: hay que
**volver a pegarlas** en `freellmapi.config.json` desde el panel de cada proveedor. Después, cambia en el bot
`FREELLM_URL` y `FREELLM_API_KEY` por los de Docker.

## Copias de seguridad y mover la instalación

- **Mover a otra máquina:** basta con llevar `freellmapi.config.json` y `.env`. Las claves se vuelven a cargar solas al arrancar. Las estadísticas de uso no viajan, pero no hacen falta.
- **Conservar también las estadísticas:** copia el volumen `hackemate-freellmapi_freellmapi-data`, que trae la base de datos cifrada. Para descifrarla hace falta la **misma `ENCRYPTION_KEY`**.

## Seguridad (léelo antes de compartir nada)

- `freellmapi.config.json` lleva **tus claves en claro**: trátalo como una contraseña. No lo metas en una imagen de Docker ni en el repo.
- **Cada persona, sus propias claves.** Si compartes las tuyas, los demás gastan tu cuota gratuita, bajo tu cuenta. Para replicarlo, cada uno rellena la plantilla con sus claves (todas son gratuitas).
- **No lo abras a internet.** Por defecto solo escucha en `127.0.0.1`. Es de un solo usuario y solo lo protege la clave unificada.
- FreeLLMAPI se presenta como **uso personal y experimental**, y cada proveedor tiene sus condiciones de uso. Para la demo del bot (un único despliegue) es adecuado. En producción, el ayuntamiento tendría sus propias cuentas.
