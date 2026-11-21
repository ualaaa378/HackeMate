# Flujo A (Benas) · qué se ha hecho y qué tenéis que revisar

*Sábado 21/11/2026, por la tarde. Benas se va y no estará conectado: este documento es el traspaso. Todo lo que aparece aquí está en `develop` (última PR del flujo A: #85).*

## 1. Lo primero, en cada máquina

```bash
git checkout develop && git pull origin develop
docker compose --env-file .env -f infra/docker-compose.yml up -d --build   # SIN -v: no se borran los datos
python scripts/url_publica.py                                              # solo en la máquina con Telegram
```

- **Nunca `down -v` ni `demo_reset` en la demo**: borran la base. Al arrancar, la API aplica sola las migraciones (incluida la **0009**) y el seed solo añade lo que falta.
- **`.env`**: comparadlo con `.env.example`, sin variables repetidas. Lo nuevo de hoy:
  - `NIM_*` y `LLM_CADENA=gemini,nim,freellm,claude,reglas`. **La clave de NVIDIA lleva un guion** (`…DvB-Y9…`, 70 caracteres): el PDF lo corta y, si se copia sin él, NVIDIA la rechaza.
  - `FB_PAGINAS` con Velefique: `https://www.facebook.com/ayuntamientodevelefique.velefique`.
  - `MODERACION_IMPORTADOS_A_BANDEJA=true`, `ADMIN_USUARIO=admin` y `ADMIN_CONTRASENA=1234`. Si no están, valen esos valores por defecto.
  - `VITE_API_URL=/` y `CORS_ORIGENES` con `,https://localhost,capacitor://localhost`.

## 2. Qué ha hecho el flujo A hoy (por PR)

| PR | Qué | Qué cambia para vosotros |
|---|---|---|
| #43 | **Solo dos modos de publicación**: a mano (0) y automática (2); el nivel 1 pasa a 0 (migración 0008) | La asociación nunca sube de nivel sola: la pasa a automática un moderador |
| #49 | **Ingesta de Facebook (A2)**: `scripts/importar_facebook.py`, Apify → IA del bot → bandeja, con revisión diaria | Servicio `ingesta` del compose, **apagado por defecto** (gasta crédito de Apify). Ver §4 |
| #53 | `--env-file .env` en todos los comandos del compose | Sin él, el bot va sin IA en Docker |
| #61 | **A6/A7**: la API detrás del nginx y del túnel (`--proxy-headers`) y CORS para el APK | — |
| #63 | **Lo que hace la gente ya no se pierde al reiniciar** (`seed --solo-nuevos`), `restart: unless-stopped` y cola del bot en volumen | Reconstruir sin miedo con `up -d --build` |
| #70 | **A4**: lo importado de Facebook cuenta en `pct_importadas_auto` de `/estadisticas` | Adán (C6): basta con mostrar ese campo |
| #71 | **D4**: lo importado de Facebook **pasa siempre por la bandeja**, aunque la asociación sea automática | Se cambia con `MODERACION_IMPORTADOS_A_BANDEJA=false` |
| #75 | Los Aytos. de **Senés, Uleila, Lucainena y Velefique** son publicadores con su Facebook como fuente; el script reconoce la misma página con otra URL | Sus posts llegan con su nombre a la bandeja |
| #79 | **D1 (A8, A9, A10)**: avisos de planes nuevos solo a quien los acepta, también a quien solo usa Telegram, y la API los manda al publicarse un plan | Ver §3 (Fran) |
| #81 | **Contrato de N7**, alineado con el `/ai/sugerir-eventos` de Fran (N8) | — |
| #83 | **N7**: `GET /admin/sugerencias` y `POST /admin/sugerencias/borrador` | Ver §3 (Adán) |
| #84 | **N6**: plazas libres = aforo − inscripciones confirmadas (seed y migración 0009) | La Ruta Solidaria pasa de 8 libres (inventadas) a **39** |
| #85 | **Acceso de la moderación con usuario y contraseña** (`admin` / `1234`): `POST /auth/admin` y puerta de `/admin` | **Adán tiene que probar la parte web** (§3) |

API: **644 tests en verde** (`cd services/api && python -m pytest -q`).

## 3. Qué tiene que revisar cada uno

### Adán (flujo C)
1. **⚠️ Probar el acceso con contraseña de `/admin` (#85).** Se mergeó **sin compilar**, porque en el portátil de Benas no hay Node.
   - `npm run lint` y `npm run test:unit` en `apps/web` (hay un test nuevo en `src/api/admin.test.ts`).
   - En `/admin`: con `admin` / `1234` entra como moderación; con una contraseña mala sale «Usuario o contraseña incorrectos.»; «Entrar con mi móvil» y el botón de asociación de la demo siguen funcionando.
   - Archivos: `src/admin/PaginaAdmin.tsx`, `ProveedorAcceso.tsx`, `acceso.ts`, `api/admin.ts` y `theme/app.css`.
2. **Panel (N5/C6): sugerencias de N7.** `GET /api/v1/admin/sugerencias` → tarjetas con `items[i].titulo`, `municipio`, `fecha_aproximada` y `motivo`.
   - [Crear borrador] pide la fecha y llama a `POST /api/v1/admin/sugerencias/borrador` con la propuesta y `fecha_inicio`; el plan aparece en la bandeja.
   - [Descartar] lo oculta en la web.
   - La IA puede tardar: mostrad «pensando…». Si el bot no responde, la API propone por reglas (`proveedor_ia: "reglas"`).
3. **Panel: % de Facebook.** `pct_importadas_auto` de `/estadisticas` ya cuenta lo importado de Facebook (cuando el moderador lo aprueba).
4. **«Para ti» y fichas: plazas reales (N6).** Ya no hay «últimas 8 plazas» en la Ruta Solidaria. Para enseñar «últimas plazas» en la demo hay que apuntar gente de verdad durante el ensayo.

### Francisco (flujo B)
1. **Avisos de planes nuevos (A10).** Cuando un plan pasa a `publicado`, la API manda `POST /notify` con `tipo: "recomendacion"` y `evento_id` (tu bot ya pone [Apuntarme] [Más info]) a quien:
   - acepta avisos (`acepta_avisos`, que ahora es **`false` por defecto** para los usuarios nuevos: lo activa tu «Sí, avísame»);
   - le gusta la categoría o una etiqueta del plan, **o ya fue a planes de esa categoría o con esas etiquetas**;
   - vive en el pueblo o dentro de su radio (30 km por defecto).

   Como mucho un aviso por persona y plan. Comprobad en un ensayo que llegan y que los botones funcionan.
2. **Avisos sin teléfono (A9).** El contrato de `notificacion` pide `telefono` **o** `contacto`; a quien solo usa Telegram le llega por `contacto: tg:…`, sin `telefono` en el cuerpo.
3. **N7 llama a tu `/ai/sugerir-eventos`** con `{planes, maximo}`. Está probado contra tu código real: acepta los planes tal como los manda la API. Las propuestas con un pueblo o una categoría que no existen se descartan en la API.

### Los tres
- **T1** (antes de las 00:00): máquina de la demo encendida y los tres móviles **con datos** (no la wifi de la uni). Revisad:
  - URL pública, agenda, ficha, inscripción y chat;
  - `/admin` con `admin` / `1234`;
  - los 7 pasos por Telegram;
  - un plan nuevo aprobado en la bandeja → que llegue el aviso a quien acepta avisos.
- **T2**: reinicio en frío cronometrado (`down` sin `-v`, `up -d`, `url_publica.py`) y comprobar que todo sigue ahí.
- Lo que falle en T1/T2 del lado de la API va a **A5** (arreglos de los ensayos, hasta las 07:00). Si Benas no está, cualquiera puede abrir un `fix/*`: los tests de la API dicen si se rompe algo.

## 4. Facebook (ingesta)

- Se revisan 5 páginas:

  | Página | Facebook |
  |---|---|
  | Ayto. de Uleila del Campo | https://www.facebook.com/profile.php?id=100064568389094 |
  | Ayto. de Lucainena de las Torres | https://www.facebook.com/profile.php?id=100064636603636 |
  | Ayto. de Senés | https://www.facebook.com/profile.php?id=61551352857893 |
  | Ayto. de Velefique | https://www.facebook.com/ayuntamientodevelefique.velefique |
  | Monte-Sión (Lucainena) | https://www.facebook.com/MonteSionLucainenaDeLasTorres |

  Tahal no tiene página. **La de Velefique no se ha descargado todavía.**
- **Para que salgan en la app de la demo** (solo la máquina de la demo):
  - **Sin token de Apify:** `python scripts/importar_facebook.py --desde-json` (los posts guardados).
  - **Con token, revisión diaria:** `docker compose --env-file .env -f infra/docker-compose.yml --profile ingesta up -d ingesta`. Hay que volver a encenderla cada vez que se levanta el compose desde cero.
  - Los planes llegan a la **bandeja**: aparecen en la agenda cuando el moderador los aprueba (y entonces avisan a los interesados).
- Probado hoy: Apify en vivo (5 páginas, solo los posts nuevos) y la IA de **NVIDIA NIM**: 20 posts, ninguna llamada fallida. Por ejemplo, la «Sesión de Cuentos para Adultos» de Senés llega a la bandeja como «Ayto. de Senés».

## 5. Avisos de seguridad

- **Las claves circularon en PDF** (Telegram, Meta, FreeLLM, Apify, NVIDIA, Gemini, Groq…). Después de la hackathon hay que **regenerarlas todas** y poner un límite de gasto en Apify.
- **`admin` / `1234` es provisional.** En la máquina de la demo se puede cambiar con `ADMIN_CONTRASENA=…` en el `.env` y `up -d --build`. Con `DEMO_MODE=true`, `POST /auth/demo` aún da sesión de moderador a quien llame directamente a la API (la web ya no lo usa para la moderación).

## 6. Lo que queda (según el README)

- **Adán**: C9 (APK) o C4 (PWA), C6 (panel), C10 (entrar con el código), N1–N4 y C7 (vídeo, capturas y `v1.0` en `main`).
- **Francisco**: B5b `/ai/frase`, solo si sobra tiempo. Ya no puede entrar en el contrato, que se congeló a las 19:00.
- **Flujo A**: N5 (revisar el panel con Adán) y A5 (arreglos de los ensayos y repaso de la sección del backend del README).
