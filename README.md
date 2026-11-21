<div align="center">

#  HackeMate

### Equipo de la Hackathon UAL para el Desarrollo del Interior

*Reto 1 · Reactiva tu pueblo: comercio y turismo inteligente*

![Hackathon](https://img.shields.io/badge/Hackathon-UAL-0055A4?style=for-the-badge)
![Reto](https://img.shields.io/badge/Reto%201-Reactiva%20tu%20pueblo-2E7D32?style=for-the-badge)
![Estado](https://img.shields.io/badge/Estado-En%20desarrollo-F57C00?style=for-the-badge)

</div>

---

## 👥 Quiénes somos

<div align="center">

| 🧑‍💻 | 🧑‍💻 | 🧑‍💻 | 🧑‍💻 |
|:-:|:-:|:-:|:-:|
| **Adán Álvarez Amat** | **Francisco Sánchez López** | **Benas Sapogas** | **Juan Carlos Pascual Escañuela** |

</div>

## 🎯 El reto

Impulsar el **comercio y el turismo** de los pueblos del interior de Almería con tecnología, empezando por cuatro municipios:

<div align="center">

| 📍 Lucainena de las Torres | 📍 Senes | 📍 Velefique | 📍 Uleila del Campo |
|:-:|:-:|:-:|:-:|

</div>

## 💡 Nuestra idea

Una plataforma web que conecte a **negocios locales**, **ayuntamientos** y **visitantes**:

| | Qué queremos conseguir |
|:-:|:--|
| 🏪 **Negocios** | Publicar ofertas, promociones y eventos, con ayuda de IA para redactarlos. |
| 🏛️ **Ayuntamientos** | Moderar las publicaciones, con una IA que las preclasifica antes. |
| 🎒 **Visitantes** | Descubrir qué hacer según sus intereses, la fecha y la ubicación en un mapa. |
| 📅 **Calendario** | Reunir las actividades turísticas, culturales y deportivas. |
| 🤖 **Asistente** | Un chatbot que responda solo con la información de la plataforma. |

## 🛠️ Tecnologías previstas

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)
![OpenStreetMap](https://img.shields.io/badge/OpenStreetMap-7EBC6F?style=flat-square&logo=openstreetmap&logoColor=white)
![Claude](https://img.shields.io/badge/Claude-D97757?style=flat-square&logo=anthropic&logoColor=white)

## 🚧 Estado

> **📋 Traspaso del flujo A (Benas, sáb 21/11 por la tarde):** todo lo que se ha hecho hoy en la API, qué tiene que revisar cada uno (Adán: **probar el acceso con contraseña de `/admin`**, que se mergeó sin compilar; Fran: los avisos de planes nuevos) y cómo actualizar las máquinas → [`docs/RESUMEN_FLUJO_A.md`](docs/RESUMEN_FLUJO_A.md).

**Sáb 21/11, 16:00 (tras la #67).** `develop` tiene los tres flujos y la demo funciona de punta a punta por la URL pública del túnel, con Telegram e IA, en dos máquinas (Francisco y Adán; **solo una a la vez con Telegram**). Tests: api 602, bot 149. Cómo probar la v1: [`docs/PRUEBAS_V1.md`](docs/PRUEBAS_V1.md). Etiquetas: `v0.2` en `3496f65` (CP2 cerrado) y `v0.3` en `e698407` (CP3, con N1–N4 de la web).

**Próximos puntos fijos:** **CP3 sáb 19:00** (pasos 4–7, contratos congelados, `v0.3`) · **CP4 dom 00:00** (feature freeze, `v0.9`) · **REL dom 07:00** (`v1.0` en `main`) · entrega dom 11:00.

**Reglas de arranque para todos** (lo que más ha fallado):
1. Siempre desde la raíz: `docker compose --env-file .env -f infra/docker-compose.yml …` (también `exec`, `logs`, `--profile ingesta`). Sin `--env-file`, el bot va sin IA (#53).
2. Tras cada `up` o si cambia el túnel: `python scripts/url_publica.py` (pone `PUBLIC_URL` y `WEB_URL`, pasa la URL al bot en caliente y comprueba el webhook). Si dice «Telegram: REVISAR», `--forzar`.
3. `.env` sin variables repetidas (Docker usa la última) y con: `VITE_API_URL=/`, `DEMO_MODE=true`, `CORS_ORIGENES` con `https://localhost,capacitor://localhost`, `PUBLIC_URL=` vacío y `WEB_URL=http://localhost:8080` (los rellena el script), `FREELLM_URL_DOCKER=http://host.docker.internal:3001/v1` con **tu** clave de FreeLLM, `NIM_API_KEY` y la `LLM_CADENA` de `.env.example`.
4. En la demo, **ni `down -v` ni `demo_reset`** (borran la base). `up -d --build` conserva lo que hace la gente (#63). Qué conserva cada comando: «⚙️ Backend» → «Qué se guarda».
5. La red de la universidad (Fortinet) bloquea `npm`: la imagen `web` y el APK se construyen con datos del móvil. Claves solo por privado y en `.env`, nunca en `*.example`.

Arquitectura pública (decisión D3, túnel rápido de Cloudflare, gratis y sin cuenta; la URL cambia al reiniciar el túnel):

```
móvil / jurado / APK / Telegram ──> https://<algo>.trycloudflare.com ──> web:8080 (nginx)
                                     ├── /          → la web
                                     ├── /api/      → api:8000
                                     └── /webhook/  → bot:8001
```

## 🔗 Pendiente entre flujos

> **Regla del equipo (ver `CLAUDE.md`):** cada flujo apunta aquí, bajo el flujo responsable, lo que necesita de los demás, y lo borra al resolverlo. Cada uno marca `[x]` en el mismo commit en que termina. Mientras algo falte, la web cae a mocks y el bot guarda en cola: nada se rompe. Formato de los hallazgos: `docs/SINCRONIZACION_SABADO.md` §3.

### 🧭 Orden de trabajo de hoy (Adán, sáb 21/11 17:00)

**Primero lo establecido y después lo nuevo.** Hasta las 19:00 (CP3) cada uno cierra lo que ya tiene en su tabla. Después, hasta el freeze de las 00:00, el orden es este: 1) lo que queda de la demo (C9 APK o C4 PWA, C6, C10, A8, A10, T1 y T2) y 2) las tareas **N** de abajo. Lo que a las 00:00 no esté, se queda fuera: entre una funcionalidad pulida y dos que funcionan, elegimos las dos.

**Única excepción:** los cambios de contrato de las tareas N (N7 y N9) se proponen **antes de las 19:00**, porque después el contrato queda congelado. Solo se añaden campos o rutas opcionales, con `contract-change`. El código va después.

**IA de las tareas nuevas: siempre FreeLLM primero.** Cada tarea lleva su propia cadena (`freellm,nim,gemini,reglas`), sin cambiar la `LLM_CADENA` general, y si no hay IA cae a reglas. La IA propone y una persona decide.

| Orden | Quién | Tarea nueva (después de lo establecido, antes de las 00:00) |
|---|---|---|
| N1 ✅ | Adán (C) | *(sáb 21/11: hecho. Desde 1100 px de ancho (`utils/pantalla.ts`): a la izquierda, fija al bajar, «Tus planes» (solo si estás apuntado) y debajo «Sugeridos para ti» (primero `GET /recomendaciones`; si no hay nada o no hay sesión, parecidos calculados en la web por gustos, categoría y pueblo de tus planes, con el motivo). En el centro, Recuerdos (3 planes pasados con «Fotos y comentarios», «Ver más» hasta 9) y debajo la agenda de siempre. La pestaña Recuerdos se oculta en pantalla grande. Por debajo de 1100 px, móvil y APK, todo igual que antes.)* **Agenda en tres zonas, solo en pantalla grande (web de escritorio).** En el centro, la agenda con **Recuerdos** integrado (los planes pasados dejan de ser una pestaña aparte). A la izquierda, **tus planes** (solo si estás inscrito en alguno) y debajo **sugeridos para ti**: «Para ti» (C2), con tus gustos y los planes parecidos a los que ya fuiste. **En el móvil y en la APK no cambia nada:** la agenda se queda como está y **Recuerdos sigue siendo su pestaña aparte**, porque no hay sitio para tres zonas. El cambio se decide por ancho de pantalla, no por plataforma. |
| N2 ✅ | Adán (C) | *(sáb 21/11: hecho. Azulejo suave en SVG en línea (`--hm-mosaico` en `theme/app.css`): rombo, flor de cuatro pétalos y ramita de olivo en verde al 9 % y puntos naranjas al 10 %. Va en agenda, perfil, ficha, proponer, ajustes y `/admin`; no en los modales, el mapa ni Recuerdos. El texto suave sigue por encima de 6:1. La app no tiene tema oscuro, así que solo hay versión clara.)* **Fondo con vida.** Un mosaico o dibujo suave en SVG en línea (azulejo, monte, olivo), que no baje el contraste del texto y que se vea bien en claro y oscuro. |
| N3 ✅ | Adán (C) | *(sáb 21/11: hecho. El mapa quita los planes que ya pasaron o están finalizados y añade una fila de meses: «Todos los próximos», «Noviembre», «Diciembre»… solo con los meses que tienen planes. `src/utils/meses.ts` con tests.)* **Mapa solo con próximos.** Los planes pasados desaparecen del mapa, con un filtro por meses (este mes, el que viene, etc.). |
| N4 ✅ | Adán (C) | *(sáb 21/11: hecho. Al crear la cuenta salen los seis gustos como botones (opcionales) y se guardan con `PATCH /usuarios/me`; en «Mi perfil» se cambian y se guardan al tocarlos. Sin cambio de contrato ni nada pendiente de A.)* **Gustos al crear el perfil, opcionales:** 🥾 Deportiva · 🎭 Cultural · 🎉 Fiestas · 🍽 Gastronomía · 🎲 Lúdica · 🛍 Comercio. El contrato ya tiene `usuario.gustos` con estos seis valores: `PATCH /usuarios/me`. Se puede saltar. |
| N5 ✅ | Francisco (A) + Adán (C) | *(Repartida en N5a, Francisco, y N5b, Adán: las dos hechas, ver «🗂️ Lo que queda».)* **Revisar el panel de control.** Lista de cada botón y cifra del panel: si funciona, si no hace nada o si no tiene sentido. Se arregla lo que lo necesita para la demo y se quita lo que no aporta. Lo que falte de la API va al apartado del flujo A (Francisco). |
| N6 ✅ | Benas (A) | *(sáb 21/11: hecho. `app.inscripciones.recalcular_plazas`: `plazas_libres = plazas_totales − plazas de las inscripciones confirmadas` (web y bot), en el seed (también al arrancar el contenedor) y en la migración **0009** para las bases ya desplegadas. Solo planes con aforo que no han terminado: los finalizados guardan su ocupación para las estadísticas. La II Ruta Solidaria pasa de 8 libres (inventadas) a **39** (40 − 1 inscrita), así que en «Para ti» Carmen ya no ve «quedan las últimas 8 plazas».)* **Plazas libres reales.** `plazas_libres = plazas_totales − inscritos en nuestra plataforma`. Los inscritos inventados de los fixtures ya no cuentan: el seed y una migración recalculan el contador a partir de las inscripciones de la base. Sin cambio de contrato. **Decidido por Adán (sáb 17:05): cuentan las inscripciones de la web y del bot (Telegram).** Nadie se apunta dos veces al mismo plan: la API ya responde 409 `ya_inscrito` con `details.inscripcion_id`, y con eso se ofrece desapuntarse (`DELETE /eventos/{id}/inscripciones/{insc_id}`, que devuelve la plaza). |
| N6b | Francisco (B) | ✅ *(sáb 21/11: hecho. 409 `ya_inscrito` → «Ya estás apuntado/a a *{plan}*» con [❌ Desapuntarme] [👍 Vale]; el botón llama al `DELETE` con `details.inscripcion_id`. Escrito («desapúntame de la ruta», «ya no voy a…», «no voy a poder ir», «cancela mi plaza»): busca el plan por su nombre y la inscripción con `GET /eventos/{id}/inscripciones`. Probado contra la API real: la plaza vuelve (7 → 8).)* **Bot: apuntarse dos veces.** Si la API responde 409 `ya_inscrito`, contestar «Ya estás apuntado a *{plan}*» con los botones [Desapuntarme] [Vale]. [Desapuntarme] llama a `DELETE /eventos/{id}/inscripciones/{insc_id}` (el id va en `details.inscripcion_id`) y confirma que la plaza queda libre. Que también entienda «desapúntame de la ruta». |
| N6c ✅ | Adán (C) | *(sáb 17:15: hecho. Si la API dice `ya_inscrito`, la ficha guarda el id y enseña «Ya estás apuntado» + «Desapuntarme» con confirmación → `DELETE`.)* **Web: apuntarse dos veces.** La ficha, si ya estás apuntado (en este móvil o por 409 `ya_inscrito`), enseña «Ya estás apuntado» y un botón «Desapuntarme» (con confirmación) en vez de «Apuntarme». |
| N7 ✅ | Benas (A) | *(sáb 21/11: **hecho**, contrato (#81) y código (`app/sugerencias.py`, `app/rutas/sugerencias.py`). La participación cuenta inscritos, lista de espera, asistencias, ocupación y preguntas del chat; probado contra el `/ai/sugerir-eventos` real de Francisco. Las propuestas del bot con un pueblo o una categoría que no existen se descartan. `GET /admin/sugerencias` → `Sugerencias` {items: `SugerenciaPlan`[] (lo que devuelve el bot en `propuestas`), basado_en: `ParticipacionPlan`[], proveedor_ia}; si el bot no responde, propone por reglas (nunca falla por la IA). [Crear borrador] = `POST /admin/sugerencias/borrador` con la propuesta y la `fecha_inicio` que elija el moderador → evento `en_revision` en la bandeja; [Descartar] lo hace la web. Ejemplos en `services/api/tests/test_contrato_n7.py`. **Decidido por Adán (sáb 17:18): se queda el `/ai/sugerir-eventos` de Francisco**, ya programado: la API le manda `{planes, maximo}` y recibe `{propuestas, proveedor_ia}`; cada propuesta pasa tal cual a `items` (con `fecha_aproximada` en texto: la fecha exacta la pone el moderador al crear el borrador, sin inventarla).)* **IA que sugiere planes a los administradores.** Detecta los planes con mucha participación (ocupación, inscritos, lista de espera y preguntas en el chat) y pide al bot una propuesta («repetir la Ruta Solidaria en primavera: se llenó y hubo 6 en lista de espera»). Ruta nueva en el contrato antes de las 19:00 (p. ej. `GET /admin/sugerencias`). La web la enseña en el panel (N5) con [Crear borrador] [Descartar]. |
| N8 | Francisco (B) | ✅ *(sáb 21/11: hecho. Ruta en el contrato y en el bot (`app/agentes/sugerencias.py`), cadena propia `LLM_CADENA_TAREAS_N=freellm,nim,gemini,reglas`. Se descarta lo que no cuadre (pueblo o categoría que no existen, `basado_en` que no se mandó) y sin IA propone repetir lo que más se llenó con sus cifras. Probado con IA real: 3 propuestas en ~6 s. **Benas (N7):** ya puedes llamarla.)* **`POST /ai/sugerir-eventos`** para N7, con FreeLLM primero. Recibe los planes con más participación y devuelve 1 a 3 propuestas (título, categoría, pueblo, fecha aproximada y por qué) sin inventar datos. |
| N9 | Francisco (B) | ✅ *(sáb 21/11: hecho. `tipo` (`ninguno`/`spam`/`fraude`) opcional en el contrato de `/ai/spam`; `es_spam` sigue igual, así que la API no tiene que cambiar nada. Señales de fraude por reglas (pago por adelantado, Bizum o transferencia, datos bancarios o códigos, precios irreales, urgencia, pagar por privado, suplantar al ayuntamiento, enlaces de fuera); una sola señal de pago pasa siempre por la IA (FreeLLM primero), porque «inscripción por Bizum» puede ser legítima. Probado: los 20 posts reales de `facebook_posts.json` salen limpios, los dos fraudes de la demo salen `fraude`, y con IA real una inscripción o una reserva por Bizum del pueblo salen legítimas. SBERT, no: no sobra tiempo.)* **Filtro de spam y fraude con IA.** `/ai/spam` ya existe (primero reglas y, si dudan, IA). Hay que poner FreeLLM primero, añadir señales de **fraude** (pago por adelantado, Bizum o datos bancarios, precios irreales, enlaces de fuera, suplantación de un ayuntamiento) y devolver el tipo (`spam` o `fraude`) en un campo opcional del contrato antes de las 19:00. Probarlo con los posts reales de `facebook_posts.json` y con dos de fraude inventados para la demo. Solo si sobra tiempo: un clasificador local tipo SBERT, como en los cuadernos del curso. |

### 🎓 Lo que piden los profesores (sáb 21/11 21:41) · **va primero**

Los profesores nos piden cinco cosas para la nota. **Pasan por delante de todo lo demás** salvo T1 y T2, que se hacen al final **ya con esto dentro**. Mismas reglas de siempre: lo que no esté a las 00:00 se queda fuera; contrato antes que código (solo se **añade**, con `contract-change`, aunque esté congelado, porque lo piden los profesores); tests antes de la PR.

**Reparto**

| # | Quién | Tarea |
|---|---|---|
| P1 | Adán (C) | - [x] *(sáb 21/11 22:30: hecho. Buscador en la agenda (sin tildes, todas las palabras; título, descripción, lugar, pueblo y organizador), «Compartir este plan» en la ficha (menú del móvil, o en el ordenador enviar por el canal configurado o copiar el enlace), «Cómo llegar» abre la ruta en Google Maps, «Añadir a mi calendario» ya usaba el `.ics`, y la agenda recuerda el último pueblo y tipo de plan en el dispositivo.)* **Funciones cómodas en la web** (cosas básicas que se notan): buscador por texto en la agenda; **compartir** un plan (`navigator.share`, o enlace por WhatsApp o Telegram); **añadir al calendario** con el `.ics` que ya da la API (`GET /eventos/{id}/ics`); **cómo llegar** (enlace a Google Maps con `lat`/`lon`); recordar el último filtro de pueblo y tipo de plan en este dispositivo. Sin cambios en la API. |
| P2 | Adán (C) | - [x] *(sáb 21/11 22:25: hecho. El emblema «Pueblos Unidos» en la cabecera (sustituye al «HM»), el favicon y los iconos de la PWA (192, 512, maskable y Apple); el APK ya lo llevaba (#91). Caché del service worker a v2 para que los móviles cojan los iconos nuevos.)* **Logo de la web** (favicon, cabecera, iconos de la PWA y del APK). |
| P3a | Benas (A) | - [x] *(sáb 22:45: hecho, contrato #110 y código. También avisa del rechazo al vecino sin asociación que propuso el plan (`propuesto_por_id`), con `evento_id`, para que pueda apelar.)* **Apelaciones · API y contrato.** `POST /api/v1/eventos/{id}/apelacion` {`motivo`: texto de 10 a 500 caracteres}. Solo quien propuso el plan (su publicador o el vecino que lo propuso), solo si está `rechazado` y **solo una vez**: 409 `apelacion_usada` la segunda vez y 409 `estado_invalido` si no está rechazado. El plan vuelve a `en_revision` con el motivo de la bandeja «Apelación: {motivo}». Campo opcional nuevo en `Evento`: `apelacion` {`motivo`, `creada_en`}. El moderador decide con los botones de siempre ([Aprobar] / [Rechazar]); el segundo rechazo es definitivo. El aviso de rechazo al publicador lleva el motivo y `evento_id`, para que el bot ponga [Apelar]. |
| P3b | Francisco (B) | - [x] **Apelaciones · bot.** *(sáb 21/11 22:40: hecho, `app/apelacion.py`. El aviso de rechazo lleva [✍️ Apelar]; también «quiero apelar» o «que lo revisen otra vez», que busca sus planes rechazados sin apelar. Pide el motivo (10 letras o más) y llama a `POST /eventos/{id}/apelacion` con `usuario_id`; `apelacion_usada` → «la decisión es definitiva». 8 tests; bot 208. **Benas:** hoy el aviso de rechazo solo va al **publicador** (`notificar_publicador` en `rutas/moderacion.py`); un vecino sin asociación (`propuesto_por_id`) no se entera ni puede pulsar [Apelar]: que le llegue también a él, con `evento_id` y `tipo: moderacion`.)* Al aviso «Tu plan no se ha publicado: {motivo}» se le añade el botón [✍️ Apelar]. El bot pide «¿Por qué crees que debería publicarse?», llama a `POST /eventos/{id}/apelacion` y responde «Lo revisará otra vez el ayuntamiento». También vale escribir «apelar» o «quiero recurrir». |
| P3c | Adán (C) | - [x] *(sáb 21/11 22:40: hecho contra el contrato de #110. En «Mis planes propuestos», un plan rechazado (que no ha pasado y no se ha apelado) tiene «🔁 Pedir que lo revisen otra vez»: cuadro con el motivo (10 a 500 letras) y `POST /eventos/{id}/apelacion`; avisa si ya se apeló (`apelacion_usada`). Si está apelado y en revisión sale «🔁 Apelado, en revisión», y tras un segundo rechazo, que es definitivo. En la bandeja, chip «🔁 Apelación». **Benas:** funciona de verdad en cuanto esté P3a en la API.)* **Apelaciones · web.** En «Mis planes propuestos» (P5c), un plan `rechazado` muestra el motivo y el botón **«Pedir que lo revisen otra vez»**, que abre un cuadro para escribir el motivo. En la bandeja del moderador, chip **«🔁 Apelación»** cuando el motivo empiece por «Apelación:». |
| P4a | Benas (A) | - [x] *(sáb 22:45: hecho, contrato #110 y código. Migración 0011: `usuarios.edad` y la apelación del evento; la edad del responsable va en su JSON.)* **Edad · API y contrato.** `edad` (entero, opcional) en `Usuario`, en `POST /usuarios`, en `PATCH /usuarios/me` y en el alta de asociaciones (la del responsable). **Menos de 14 años: 422 `edad_minima`**, porque en España hace falta tener 14 para dar el consentimiento de datos (LOPDGDD, art. 7). Más de 120: 422 `validacion`. Los usuarios que ya existen se quedan en `null`. |
| P4b | Adán (C) + Francisco (B) | - [x] *(sáb 21/11 22:40: **parte web hecha.** Campo «Edad (opcional)» en el alta y en Mi perfil (se guarda al salir del campo); menos de 14 o más de 120 se avisa antes de enviar. Va en `PATCH /usuarios/me` con `edad`. Falta la pregunta en el bot, de Francisco, y P4a en la API, de Benas.)* **Pedir la edad al registrarse.** Adán: un campo «Edad» en el alta de la web y en «Mi perfil». Francisco: la pregunta «¿Cuántos años tienes?» en el alta por el bot, para vecinos y asociaciones; se puede saltar. *(Francisco, sáb 21/11 22:55: **hecho en el bot**. Vecinos: la primera vez que se identifican (comparten su número), «¿cuántos años tienes?» con [⏭️ Prefiero no decirlo]; se guarda con `PATCH /usuarios/{id}` `{edad}`. Si contesta otra cosa, se olvida la pregunta y sigue. Asociaciones: paso opcional «edad» del responsable al final del alta, que va en `responsable.edad`. Menos de 14 años: no se acepta. 212 tests del bot.)* |
| P4c | Benas (A) | - [ ] **Probar asociaciones y usuarios de punta a punta.** Alta de un vecino y de una asociación (con DNI) por la web y por el bot, con edad; entrar con el código; proponer un plan; rechazarlo; apelar; aprobarlo; inscribirse y desapuntarse. Lo que falle va a la tabla del flujo que lo arregla. |
| P5a | Francisco (A) | - [x] **Organizador · API.** *(sáb 21/11 22:05: hecho. **Fallaba:** un vecino sin asociación que proponía un plan (web o bot) lo dejaba sin dueño (`publicador_id` null): no podía verlo ni modificarlo. Ahora cada plan guarda quién lo propuso, **`propuesto_por_id`** (campo opcional nuevo en `Evento`, migración **0010**; por el bot se saca del contacto), y esa persona es su organizadora (ve sus datos privados, lo modifica con `PATCH /eventos/{id}`). **`GET /eventos?organizador_id={id del usuario}`** (parámetro opcional nuevo): sus planes y los de su entidad en todos los estados salvo `borrador` (o solo `estado=` si se manda), los más recientes primero; solo para él, un moderador o el bot. **Adán (P5c):** pide eso con el `usuario.id` de la sesión. **Benas (P3a):** «quien propuso el plan» es `es_organizador()` de `app/seguridad.py`, que ya mira `propuesto_por_id`; tu migración de apelaciones va como **0011** con `down_revision = '0010'`. 7 tests en `tests/test_organizador.py`.)*  «Mis planes propuestos» con lo que ya hay: `GET /eventos?publicador_id={el mío}` (el dueño ve todos sus estados) y `PATCH /eventos/{id}` para modificar. Comprobar que **un vecino sin asociación** que propone un plan también es su dueño (ve sus planes y puede editarlos). Si no, añadir `mios=true` a `GET /eventos` (opcional, con `contract-change`). |
| P5b | Francisco (B) | - [x] **Organizador · bot: «modificar plan».** *(sáb 21/11 22:05: hecho, `app/organizador.py`. «modificar plan», «mis planes» o «quiero cambiar la hora de la ruta»: lista sus planes con su estado; si nombra uno o solo tiene uno, va directo, y si dice qué («la hora», «el lugar», «las plazas»), pregunta solo eso. «a las 19:30» cambia la hora y deja el día. Los rechazados no se ofrecen (se apelan, P3). 10 tests; bot 200 en verde.)* El bot lista tus planes propuestos (con su estado), eliges uno y luego qué cambiar (fecha y hora, lugar, descripción, plazas) y llama a `PATCH /eventos/{id}`. Si cambia la hora, la API ya avisa a los inscritos. También vale «quiero cambiar la hora de la ruta». |
| P5c | Adán (C) | - [x] *(sáb 21/11 22:15: hecho. Perfil → «📝 Mis planes propuestos» (`/mis-planes`) y botón al terminar «Proponer»: pide `GET /eventos?organizador_id=` con el `usuario.id`; «Modificar» reutiliza el formulario del panel con `PATCH /eventos/{id}`. Falta el botón de apelar (P3c) cuando Benas acabe P3a.)* **Organizador · web: pestaña «Mis planes propuestos».** Para vecinos y asociaciones con sesión: tus planes con su estado (en revisión, publicado, rechazado con su motivo, ya hecho), cuántos apuntados tiene cada uno y el botón **«Modificar»** (formulario con `PATCH /eventos/{id}`). Desde aquí se apela (P3c). |

**Planning (sáb 21/11 → dom 22/11)**

| Hora | Qué |
|---|---|
| 21:45–22:15 | Reparto (este apartado). **Contrato** de P3a y P4a (y de P5a si hace falta) en una sola PR con `contract-change`, para que web y bot programen contra él. |
| 22:15–23:15 | Código. Primero las API (P3a, P4a y P5a) y, en paralelo, lo que no depende de ellas: P1, P2, P5b y P5c (contra la API que ya existe). |
| 23:15–23:35 | Lo que depende de la API: P3b, P3c y P4b. Cada uno con sus tests. PR y merge a `develop`. |
| 23:35–00:00 | En la máquina de la demo: reconstruir las imágenes, **T1** con todo esto dentro y P4c, **T2** cronometrado y `v0.9`. |
| 00:00–07:00 | Solo arreglos: A5 y C7, los dos ensayos del guion y `v1.0` en `main` (ver «🗂️ Lo que queda», bloque 2). |

### 🗂️ Lo que queda (Adán y Francisco, sáb 21/11 19:30)

**Hecho hasta ahora:** todo lo establecido de Adán (C2, C4, C6, C9, C10) y de Francisco (A4, A8, A9, A10, B3, B6, B7, B8), y de las tareas nuevas N1, N2, N3, N4 (#98–#101), N6, N7, N8 y N9. Quedan dos bloques. **Primero la prueba de lo que ya hay** y después lo que falta. Lo que a las 00:00 no esté, se queda fuera.

**Bloque 1 · hasta el freeze (dom 00:00, CP4, `v0.9`)**

| # | Quién | Tarea |
|---|---|---|
| 1 | Adán | - [x] *(sáb 21/11 19:40: hecho, `v0.3` en `e698407`.)* **Etiqueta `v0.3`** (CP3) en `develop` desde su PC (`git tag v0.3 && git push origin v0.3`): desde la nube el proxy no deja subir etiquetas. |
| 2 | Adán | - [ ] **Reconstruir la imagen `web` con datos del móvil** (la red de la uni bloquea npm) para que la demo lleve N1–N4. El APK solo hace falta rehacerlo si se quiere enseñar el mapa por meses y los gustos en el móvil. |
| 3 | Los dos | - [ ] **T1** (ver «Los tres»): los 7 pasos por Telegram, la web nueva (agenda de escritorio, mapa por meses, gustos en el alta) y el APK, con los móviles con datos. **Telegram solo en una máquina a la vez:** se decide aquí cuál es la de la demo. Lo que falle va a la tabla de quien lo arregla. |
| 4 | Francisco | - [x] **N5a · revisar el panel.** Lista de cada botón y cifra de `/admin/panel`: si funciona, si no hace nada o si sobra. Arreglar en la API lo que haga falta. La lista se apunta aquí debajo para que Adán haga N5b. | *(sáb 21/11 20:40: hecho. Revisado contra la API real con el seed. Lista para N5b debajo de esta tabla.)*
| 5 | Adán | - [x] *(sáb 21/11 20:15: hecho. «planes publicados o ya hechos», NIM en la tabla de proveedores y la línea «0 €: la demo usa solo proveedores gratuitos». Tarjeta **💡 Ideas de la IA** (`src/admin/IdeasIA.tsx`) debajo de las cifras: cada idea con su motivo y «Basado en: Migas…: se ocupó el 90 %»; [Crear borrador] pide día y hora y llama a `POST /admin/sugerencias/borrador` (queda en la bandeja), [Descartar] la oculta en ese navegador y se pueden recuperar; «Pedir otras ideas» vuelve a llamar.)* **N5b · panel en la web.** Quitar o arreglar lo que diga N5a y añadir la tarjeta **«Ideas de la IA»** con `GET /admin/sugerencias` (N7, ya en la API) y los botones [Crear borrador] (`POST /admin/sugerencias/borrador` con la fecha que elija el moderador) y [Descartar]. |
| 6 | Francisco | - [x] **N9b · que se vea el fraude en la bandeja.** *(sáb 21/11 20:05: hecho. Si el bot dice `tipo: fraude`, el motivo de la bandeja es «Posible fraude (0.55): IA (nim): pago por adelantado» y el plan va **siempre** a la bandeja, aunque la IA lo puntúe por debajo del umbral de spam (0,7) o la asociación esté en automática. Sin `tipo` (bot antiguo) todo sigue como antes. `PREFIJO_FRAUDE` y `es_motivo_fraude` en `app/moderacion.py`; 4 tests nuevos, 656 en verde. **Adán (N9c):** el chip sale cuando el motivo empieza por «Posible fraude».)* La API ya llama a `/ai/spam`, pero ignora el campo `tipo`: si llega `fraude`, el motivo de la bandeja debe empezar por «Posible fraude: …» (`app/moderacion.py`, `_llamar_bot_spam`). Sin cambio de contrato. |
| 7 | Adán | - [x] *(sáb 21/11 20:15: hecho. Chip «⚠️ Posible fraude» y borde de alerta cuando el motivo empieza por «Posible fraude»; un ejemplo en los mocks de la bandeja.)* **N9c · chip «⚠️ Posible fraude»** en la bandeja de la web cuando el motivo lo diga (después de N9b). |
| 8 | Los dos | - [ ] **T2.** Reinicio en frío cronometrado en la máquina de la demo. Después, Adán pone la etiqueta **`v0.9`**. |

**N5a · revisión del panel `/admin/panel` (Francisco, sáb 20:40).** Comprobado contra la API con el seed (`admin`/`1234`).

| Qué | Estado | Qué hacer |
|---|---|---|
| «planes publicados» (`actividades`) | ⚠️ Cifra bien, texto no | Cuenta publicados **y ya hechos** (26 = 18 + 8). **Adán:** «planes publicados o ya hechos». |
| «importados de Facebook y webs por la IA» | ✅ | 76 % con el seed. |
| «personas apuntadas» y «de los apuntados fueron» | ✅ | 23 apuntadas, 16 fueron. El % incluye la única inscrita a un plan que aún no ha pasado, así que baja muy poco (70 % en vez de 73 %). Se deja. |
| «vienen de otro pueblo» | ✅ | 87 %. |
| «coste de IA en N llamadas» y tabla «Coste de la IA» | ✅ | 0 € con Gemini, NIM y FreeLLM (gratis); solo Claude cuesta. Se llena cuando el bot habla con la API. **Adán:** falta `nim` en `PROVEEDORES` de `Panel.tsx` (sale «nim» a secas): «NVIDIA NIM (respaldo gratis)». Una línea debajo de la tabla, «0 €: la demo usa solo proveedores gratuitos», cuenta mucho para el jurado. |
| «Ocupación por tipo de plan» | ✅ | Plazas ocupadas del plan, incluidas las de antes de la plataforma (gastronomía 90 %). |
| «Planes que se pisan» | 🔧 **Arreglado en la API** | Sin periodo enseñaba choques de agosto y octubre, que ya han pasado. Ahora, sin `desde`, solo salen los que aún no han terminado (las dos **cabalgatas de Reyes** del 5 de enero: buen ejemplo para la demo). Con `desde` sigue saliendo el histórico. La web no tiene que cambiar nada. |
| «El bot en directo» y [Simular caída de la IA] | ✅ en los tests | Pasan por la API (`/admin/bot/metricas` y `/admin/bot/simular-caida`); sin bot, 503 `bot_no_disponible` y la web enseña su aviso. Con el bot de verdad se comprueba en T1. |
| Ideas de la IA (`GET /admin/sugerencias`, N5b) | 🔧 **Arreglado en la API** | Proponía repetir los planes en los que se habían apuntado 4 de 20 desde la plataforma, sin contar las plazas que el plan ocupó de verdad, así que no cuadraba con la ocupación del panel. Ahora `ocupacion` cuenta las plazas ocupadas (solo cambia la descripción del contrato, no su forma) y salen las migas (90 %), la ruta de Velefique (87 %) y el concierto (72 %), con el motivo «se ocupó el 90 % (18 de 20 plazas)». **Adán:** ya puedes pintar la tarjeta. |

**Bloque 2 · hasta la entrega (dom 07:00, REL, `v1.0` en `main`)**

| # | Quién | Tarea |
|---|---|---|
| 9 | Francisco | - [ ] **A5.** Arreglos `fix/*` de los ensayos y repaso de la sección del backend del README. ~~B5b~~ (`/ai/frase`): fuera (Francisco, sáb 19:30). |
| 10 | Adán | - [ ] **C7.** Vídeo de respaldo, capturas en la sección web del README y `v1.0` en `main`. |
| 11 | Los dos | - [ ] **Dos ensayos seguidos del guion** con papeles repartidos: quién cuenta, quién lleva el móvil de la vecina (audios) y quién el panel del moderador. |

### Adán (flujo C) · web, APK y entrega

| Hasta | Tarea |
|---|---|
| dom 00:00 | - [x] **Probar el acceso con contraseña de `/admin`** *(sáb 21/11 19:15: hecho. `admin`/`1234` entra en el APK por el túnel tras reconstruir Docker; `test:unit` 41/41 y prettier OK. Lint: arreglados `client.ts` y `Mapa.tsx`; el error previo de `Agenda.tsx` (setState en un efecto) se arregló con N3: `npm run lint` en verde.)* (Benas, sáb 21/11, en la misma PR). Cambia `src/admin/PaginaAdmin.tsx` (formulario usuario/contraseña), `ProveedorAcceso.tsx`, `acceso.ts`, `api/admin.ts` (`entrarAdmin`), un test en `api/admin.test.ts` y estilos en `theme/app.css`. **No se ha podido compilar** (no hay Node en el portátil de Benas): pasar `npm run lint` y `npm run test:unit` y probarlo con `admin` / `1234`. Con API, el botón viejo de moderador de la demo ya no deja entrar. |
| sáb 19:00 | - [x] **C2.** *(sáb 16:30: hecho. Sección «Para ti» en la agenda con sesión iniciada, `GET /recomendaciones` y el motivo debajo de cada tarjeta; se recarga al volver a la agenda o al deslizar. Sin API, planes con plazas de los mocks.)* Paso 4. |
| sáb 19:00 | - [x] **Refresco sin recargar** *(sáb 16:30: hecho. Ficha al entrar, al deslizar y cada 20 s; chat cada 12 s; bandeja cada 10 s salvo mientras se decide un plan. Solo con la pestaña visible.)* |
| sáb 19:00 | - [x] **B3 con Fran.** *(sáb 21/11: hecho, ver B3 en el apartado de Francisco.)* FreeLLMAPI en Docker en la máquina de Adán y ensayo del paso 7 (audios). |
| dom 00:00 | - [x] **C9.** APK de debug con Capacitor (`appId: 'es.hackemate.app'`), icono «Pueblos Unidos» y Ajustes → «Dirección del servidor». *(sáb 21/11 19:10: probado en el móvil de Adán contra el túnel, #87 #91 #92. Ojo: Android Studio trae JDK 25 y Gradle 8.14 necesita **JDK 21** aparte; pasos en § «APK de Android».)* |
| dom 00:00 | - [x] **C4.** *(sáb 18:05: hecho (rama `feat/web-pwa`). `public/sw.js` solo guarda estáticos; `/api/` y `/webhook/` siempre a la red; páginas primero a la red. Iconos HM 192/512/maskable y manifest a `/agenda`. Solo en producción. Falta probar a instalarla en un móvil real (T1).)* PWA instalable: service worker e icono (el `manifest.json` ya existe). **Sin caché de `/api/`**, solo estáticos. |
| dom 00:00 | - [x] **C6.** *(sáb 18:05: hecho. El panel ya pintaba `pct_importadas_auto` y los tokens por proveedor (NIM sale en cuanto el bot lo usa; añadido a los datos de prueba). Letra grande con el selector A A A y teclado con los botones nativos de Ionic.)* Panel: % de importados de Facebook y coste en tokens con NIM. Accesibilidad: teclado y letra grande en agenda y ficha. |
| dom 00:00 | - [x] **C10 (D2).** *(sáb 18:05: hecho. Si `POST /auth/whatsapp/codigo` responde `enviado: false`, el alta enseña 3 pasos, «Abrir el bot» (`t.me/HackeMate_bot?start=codigo`) y «Ya lo he hecho, pedir el código»; con `enviado: true` pasa al código como antes.)* Entrar con el código: la web pide el número y llama a `POST /auth/whatsapp/codigo`. Si responde `enviado: false` (aún no ha hablado con el bot), enseña el botón «Abrir el bot» → `https://t.me/HackeMate_bot?start=codigo` y, al volver, «Pedir el código otra vez». Luego `POST /auth/whatsapp/verificar`. |
| dom 00:00 | - [x] **Revisar tu `.env` (de B6, Francisco).** *(sáb 21/11 17:00: hecho. `NIM_*` y `LLM_CADENA=gemini,nim,freellm,claude,reglas` en el `.env` de Adán, y los audios del paso 7 funcionan en su máquina.)* Para que la IA de la demo funcione igual en tu máquina: `NIM_API_KEY` con tu clave de NVIDIA (la de `freellmapi.config.json` vale), `LLM_CADENA=gemini,nim,freellm,claude,reglas` y las cuatro `NIM_*` de `.env.example`. Compruébalo con `docker compose --env-file .env -f infra/docker-compose.yml exec bot printenv LLM_CADENA` y que `/ai/extraer` responda con `nim:…` en `GET /metrics`. Márcalo aquí cuando esté. |
| dom 00:00 | - [ ] **Imagen `web` y `v0.9`** (N5b, N9c y `v0.3` ya hechos). Ver «🗂️ Lo que queda» (#1, #2, #5, #7 y #8). N5b y N9c dependen de N5a y N9b de Francisco. |
| dom 07:00 | - [ ] **C7.** Vídeo de respaldo, sección web del README con capturas, dos ensayos seguidos del guion y `v1.0` en `main`. |

Opcional (lo pide el bot, plan C de la demo): un chat simulado en la web que llame a `bot POST /dev/mensaje`.

### Flujo A · API (antes Benas; desde el sáb 21/11 por la tarde lo lleva Francisco)

> **Benas se ha ido de la hackathon** (traspaso en [`docs/RESUMEN_FLUJO_A.md`](docs/RESUMEN_FLUJO_A.md)). Desde ahora Francisco se encarga también del flujo A: API, `contracts/`, `infra/` y `scripts/`. El contrato sigue congelado (solo se añade); los tests de la API se pasan en Docker (Python 3.12).

| Hasta | Tarea |
|---|---|
| sáb 21/11 | - [x] **Acceso de la moderación con usuario y contraseña** (pedido por Benas). `POST /auth/admin` {usuario, contrasena} → sesión del moderador; compara con `ADMIN_USUARIO` / `ADMIN_CONTRASENA` del `.env` (por ahora `admin` / `1234`; si se queda en 1234 sin DEMO_MODE, la API lo avisa en el log). En la web, la puerta de `/admin` pide usuario y contraseña en vez del botón «🏛️ Moderación del ayuntamiento» de la demo; las asociaciones siguen entrando con su móvil o con el botón de la demo. |
| dom 00:00 | - [x] **A4.** `GET /estadisticas`: que el % de importadas cuente las de Facebook (llegan con `importado_auto`). *(sáb 21/11: ya lo hacía, ahora con test de punta a punta. `pct_importadas_auto` = planes `publicado`/`finalizado` que llegaron solos (Facebook, Instagram, web externa) sobre el total del periodo. Lo de Telegram, la web y el panel no cuenta como importado. Un post de Facebook que va a la bandeja cuenta cuando el moderador lo aprueba. **Adán (C6):** basta con pintar `pct_importadas_auto`; no hace falta cambiar el contrato.)* |
| sáb 19:00 | - [x] **A9 (D1, contrato).** *(sáb 21/11: hecho.)* `schemas/notificacion.json` pide `telefono` **o** `contacto` (`anyOf`); sin ninguno, el contrato lo rechaza. La API ya no deja «fallida» un aviso a quien solo tiene Telegram: sale por su `contacto` (`tg:…`) y el cuerpo no lleva `telefono`. Sin destino → `fallida` con «sin destino». |
| dom 00:00 | - [x] **A8 (D1).** *(sáb 21/11: hecho.)* `acepta_avisos` vale `false` por defecto para los usuarios nuevos (el valor por defecto está en el modelo, no en la base: no hace falta migración y los usuarios que ya existen no cambian). Los del seed siguen en `true`. Un aviso `recomendacion` a quien no lo acepta no sale (`fallida`, «no acepta avisos»); los avisos de planes a los que ya está apuntado (cambio de hora, respuestas) salen siempre. |
| dom 00:00 | - [x] **A10 (D1).** *(sáb 21/11: hecho, `app/avisos_planes.py`.)* Cuando un plan pasa a `publicado` (asociación en automática, aprobado en la bandeja o creado por el moderador), aviso `recomendacion` con `evento_id` (el bot pone [Apuntarme] [Más info]) a quien: acepta avisos y tiene teléfono o Telegram; le gusta la categoría o una etiqueta del plan, **o ya fue a planes de esa categoría o con esas etiquetas** (quien fue a una liga de futbolín se entera de la siguiente aunque la IA la ponga en otra categoría); y vive en el pueblo o dentro de su `radio_km` (30 km si no tiene). No avisa a quien lo publica ni a quien ya está apuntado, y como mucho una vez por persona y plan. Texto con el motivo del recomendador y en su `formato_aviso` (texto o audio). |
| dom 00:00 | - [x] **N5a y N9b (Francisco).** *(sáb 20:40: los dos hechos.)* Ver «🗂️ Lo que queda» (#4 y #6). Adán espera la lista de N5a para hacer N5b y el motivo «Posible fraude» de N9b para el chip N9c. |
| dom 07:00 | - [ ] **A5 (ahora Francisco).** Arreglos `fix/*` de los ensayos y repaso de la sección del backend del README. |
| sáb 21/11 | - [x] **«Pueblo favorito» en las recomendaciones (Francisco, PR #88).** Quien ha ido a 2 o más planes distintos de un mismo pueblo seguramente vive allí o le encanta: los próximos planes de ese pueblo suben +3 (como un gusto) aunque nunca haya ido a uno de ese tipo, con el motivo «Has ido a 3 planes en Senés». Si es su propio pueblo no se repite (ya sale «es en tu pueblo»). También en los avisos de planes nuevos (A10): se avisa por pueblo favorito aunque quede fuera de su radio. Cambios en `app/recomendador.py` (`razon_pueblo`, `PESO_PUEBLO_FAVORITO`, `MIN_PLANES_PUEBLO`) y `app/avisos_planes.py`, con 3 tests nuevos; 638 tests en verde. Sin cambio de contrato. |
| sáb 21/11 | - [x] **Tareas programadas (Francisco)** (`app/tareas_programadas.py`, en el arranque de `app/main.py` junto al bucle de reintentos). Cada `TAREAS_CADA_MIN` (10) minutos: **1)** recordatorio 24 h antes («⏰ Mañana a las 9:00 tienes «Ruta…» en Velefique») a quien está `confirmada`; **2)** «¿Qué tal fue «…»?» a quien fue a un plan que terminó en las últimas 24 h (el bot pone botones y deja la respuesta como comentario del plan); **3)** resumen semanal por pueblo (`RESUMEN_DIA_SEMANA`/`RESUMEN_HORA`, lunes 9:00) con los planes de los 7 días siguientes, solo a quien acepta avisos (`tipo: recomendacion`). Cada aviso sale una vez por persona (se mira la marca del texto). La lista de espera ya avisaba sola (`promocionar`). Variables nuevas en `.env.example`; 5 tests nuevos, **652 en verde**. Probado de punta a punta en Docker: los tres avisos llegan y la valoración queda en el chat del plan. Sin cambio de contrato. |
| sáb 21/11 | - [x] **D4.** Lo importado solo (Facebook de los ayuntamientos, `importado_auto`) **pasa siempre por la bandeja**, aunque la asociación esté en automática (motivo «Importado automáticamente…»). Lo que publica la asociación por el bot o la web sigue saliendo solo. Se cambia sin tocar código con `MODERACION_IMPORTADOS_A_BANDEJA=false` en el `.env` (por defecto `true`). Sin cambio de contrato. *Comprobado además el scraping (sáb 21/11, 16:15): Apify en vivo (5 páginas, 7 posts, solo los nuevos) y los 20 posts guardados con la IA de NIM → 14 a la bandeja, 5 descartados, 1 pendiente sin título.* |

| sáb 21/11 | - [x] **Seguridad de `/admin` (Adán, auditoría sáb 21/11 23:00).** Hecho en la API, **Francisco: revísalo cuando puedas**: `POST /auth/demo` ya **nunca da sesión de moderador** (403 `demo_sin_moderador`; la web solo lo usa para «Asociación»); `POST /auth/admin` bloquea con 429 `demasiados_intentos` tras 5 fallos por IP (o 30 en total) en 10 min; el aviso del log por `JWT_SECRET`, `ADMIN_CONTRASENA` o `INTERNAL_TOKEN` de ejemplo sale también con `DEMO_MODE`. En infra: nginx borra `X-Internal-Token` en `/api/` y `/webhook/` (el bot llama a `api:8000` por dentro, no le afecta) y añade cabeceras de seguridad; el compose publica db, api y bot solo en `127.0.0.1` (`PUERTOS_IP=0.0.0.0` en el `.env` si otro ordenador necesita la API o el bot directamente). Contrato: solo se añaden las respuestas 403 y 429. **En la máquina de la demo:** `ADMIN_CONTRASENA`, `JWT_SECRET` e `INTERNAL_TOKEN` propios en el `.env`. |

| sáb 21/11 | - [x] **Seguridad de la API (Adán, auditoría sáb 21/11 23:55).** Hecho, **Francisco: revísalo cuando puedas**: un plan **publicado** que su organizador edita (título, descripción o foto) vuelve a pasar `/ai/spam`; si sale spam o fraude, vuelve a `en_revision` con «Editado después de publicarse…» y se avisa a los moderadores (`_remoderar_si_cambia_el_texto` en `rutas/eventos.py`). Los cambios de hora, lugar o plazas no se vuelven a moderar, ni los del moderador o el bot. `origen.url` solo sale si empieza por `http(s)://`. 5 tests nuevos, 690 en verde. Sin cambio de contrato. Queda para después de la entrega: límite de mensajes por usuario en el chat. |

Notas: `frase_portada` ya se guarda; si llega vacía, la web pone su frase fija por tipo de plan (B5b, `/ai/frase`, se ha quedado fuera). Un vecino sin asociación que propone un plan solo ve sus `datos_ayuntamiento` en la respuesta del alta.

### Francisco (flujo B) · bot e IA

| Hasta | Tarea |
|---|---|
| sáb 19:00 | - [x] **B3.** *(sáb 21/11: hecho. Configuración de FreeLLMAPI pasada por privado a Adán; con FreeLLMAPI en Docker en su máquina, las notas de voz por Telegram funcionan (paso 7): el bot las transcribe y responde. Los audios ya no dependen del portátil de Francisco.)* Pasar por privado a Adán `freellmapi.config.json` y `.env` de `services/bot/freellmapi/` y ensayar juntos el paso 7 en su máquina. |
| — | ~~**B5b.**~~ *(sáb 21/11 19:30: **fuera**, decidido por Francisco. Haría falta una ruta nueva en el contrato congelado y no aporta a la demo; la web se queda con su frase fija por tipo de plan. Idea para producción.)* Era: `POST /ai/frase` (primero en el contrato, antes de CP3): frase breve y alegre (≤ 90 letras, sin inventar datos) a partir de título, categoría y pueblo. Mientras, la web pone una frase fija por tipo de plan. |
| sáb 19:00 | - [x] **B7 (D1).** *(sáb 21/11: hecho. `/notify` acepta solo `contacto` (422 `sin_destino` si no hay ninguno); `app/avisos.py`: tras los gustos pregunta con botones [🔔 Sí, avísame] [No, gracias] una vez, y «no quiero avisos», «deja de avisarme», «avísame» cambian `acepta_avisos` con `PATCH /usuarios/{id}`; en Telegram sin vincular pide antes el número. Probado contra la API real: el campo cambia en la base.)* Bot: aceptar `/notify` sin `telefono` si viene `contacto`; tras decir sus gustos, preguntar «¿Quieres que te avise de planes nuevos que te puedan gustar?» [Sí] [No] y guardar `acepta_avisos`; entender «no quiero avisos» y «avísame». |
| sáb 19:00 | - [x] **B8 (D2).** *(sáb 21/11: hecho. `t.me/HackeMate_bot?start=codigo` pide «Compartir mi número» y luego dice «Vuelve a la web y pulsa *Pedir el código*»; si ya lo había compartido, lo dice directamente. De paso, `?start=alta` abre el alta de asociaciones.)* Bot: `/start codigo` (el enlace de la web) pide «Compartir mi número» y, al compartirlo, dice que ya puede pedir el código en la web. |
| dom 07:00 | - [x] **B6.** Sección del bot en el README y claves de IA de la demo en el `.env` de Adán (por privado). *(sáb 21/11: **sección del bot escrita** («🤖 Bot (flujo B)»: qué se puede hacer desde el chat, IA, canales, arranque, variables, rutas, robustez y privacidad). Claves: FreeLLMAPI ya pasado (B3). La revisión de `NIM_API_KEY` y `LLM_CADENA` en el `.env` de Adán la hace y la marca él (tarea «Revisar tu `.env`» en su apartado).)* |

**Idea apuntada, no se hace por ahora (decisión de Francisco, sáb 21/11): automatizar `url_publica.py`.** Comprobado que se puede: `cloudflared` con `--metrics 0.0.0.0:2000` responde en `GET /quicktunnel` `{"hostname": "<algo>.trycloudflare.com"}`, la misma URL de sus logs. Bastaría con una línea en el servicio `tunnel` de `infra/docker-compose.yml` (sin abrir puertos fuera) y una tarea en el bot que lo consulte cada ~15 s y, si cambia, registre el webhook y los enlaces en caliente, activada solo con `TUNEL_AUTO=true` en el `.env` de la máquina de la demo (para que nadie más le quite Telegram). Mientras, tras cada `up` o reinicio del túnel: `python scripts/url_publica.py` (vale desde cualquier carpeta).

Detalle de las llamadas: [`services/bot/PARA_FLUJO_A.md`](services/bot/PARA_FLUJO_A.md) y [`docs/PLAN_FLUJO_B.md`](docs/PLAN_FLUJO_B.md) §5.

### Los tres · prueba desde fuera (dom 00:00)

- [ ] **T1.** Máquina de la demo encendida y **los tres móviles con datos (sin wifi de la uni)**: URL pública, agenda con datos reales, ficha, inscripción, chat, `/admin`, los 7 pasos por Telegram y el APK. Lo que falle, a la tabla del flujo que lo arregla.
- [ ] **T2.** Reinicio en frío cronometrado: `down` (sin `-v`) y `up -d`, `url_publica.py`, y comprobar Telegram, enlaces del bot, web y APK (cambiando solo su dirección).

### Decisiones

- **✅ D1 · decidida por Francisco (sáb 21/11, 16:45): avisos por Telegram solo a quien los acepta.** A quien **ha aceptado** los avisos se le avisa por Telegram de las **actividades nuevas** y se le mandan **recomendaciones** según lo que ha dicho que le gusta (`gustos`) y los planes a los que ha ido. Consecuencias:
  - **Consentimiento de verdad:** `acepta_avisos` debe valer **`false` por defecto** (hoy es `true`, así que todos estarían apuntados sin que se lo hayamos preguntado). El bot lo pregunta tras decir sus gustos («¿Quieres que te avise…?») y entiende «no quiero avisos» / «avísame». Tareas A8 (Benas) y B7 (Francisco).
  - **Quien solo usa Telegram también recibe avisos:** `telefono` deja de ser obligatorio en `schemas/notificacion.json` cuando viene `contacto` (`tg:…`). No es un cambio aditivo: **contrato antes de las 19:00 (CP3)**. Tareas A9 (Benas) y B7 (Francisco).
  - **Alguien tiene que mandar esos avisos:** ✅ la API avisa al publicarse un plan (A10, `app/avisos_planes.py`). A8 y A9 también hechos (sáb 21/11).
- **✅ D2 · se mantiene (Francisco, sáb 21/11): el código por mensajería**, para comprobar que nadie mete mal su número. La API ya lo genera y lo manda (`POST /auth/whatsapp/codigo` → bot `/notify`); falta el camino para quien aún no ha hablado con el bot: la web lo manda a `t.me/HackeMate_bot?start=codigo`, el bot le pide «Compartir mi número» y le dice que ya puede pedir el código. Tareas C10 (Adán) y B8 (Francisco).

### Canales: Telegram ahora, WhatsApp intercambiable

Regla en `CLAUDE.md` § «Canales de mensajería». Bot: Telegram con `TELEGRAM_TOKEN` (contactos `tg:<chat_id>`), WhatsApp con `CANAL=meta|twilio|console`; pueden ir a la vez. API: guarda `telefono` y `telegram_id` (`services/api/app/canales.py`) sin suponer canal. Web: `VITE_CANAL=telegram|whatsapp` (`apps/web/src/canal.ts`).

### Hecho (resumen; el detalle está en cada PR)

- **Infra y despliegue:** URL pública por la web (C8 #59, C8b #60, A6/A7 #61, F1/F2 `url_publica.py`), cambio de túnel en caliente sin perder conversaciones, `--env-file .env` (#53), seed `--solo-nuevos`, `restart: unless-stopped` y volumen `bot_data` (#63), segunda máquina de demo (#65).
- **API:** todas las rutas del contrato; dos modos de publicación (a mano y automática, sin nivel 1, #43); restaurar un plan rechazado; duplicados a la bandeja; `contacto` en `/notify` (`tg:` o teléfono); filtro por estado en `GET /eventos` (Recuerdos); verificar identidad del responsable.
- **Ingesta de Facebook (A2, #49):** `scripts/importar_facebook.py`, 20 posts reales en `contracts/fixtures/facebook_posts.json`, servicio `ingesta` apagado por defecto (`--desde-json` sin red).
- **Bot:** hallazgos sin IA (B1), NVIDIA NIM en la cadena `gemini,nim,freellm,claude,reglas` (B2, #66), «este finde» filtrado (#52), alta de asociaciones por chat con nombre, DNI/NIE y residencia (B5, #67: «quiero dar de alta mi asociación»).
- **Web:** H0–H2 contra la API real, `/admin` con `/auth/demo`, Recuerdos, Proponer, inscripción, `.ics`, chat, rediseño de agenda y ficha (#64), cierre de sesión ante 401.

---

## ⚙️ Backend (flujo A)

API FastAPI + SQLAlchemy + Alembic en `services/api/`, con PostgreSQL (pgvector) en Docker o SQLite en local. Contratos en `contracts/` (`openapi.yaml`, schemas y fixtures): ningún endpoint ni campo existe sin estar antes ahí.

### Arranque con Docker (3 comandos)

```bash
cp .env.example .env                                   # y rellenar las claves (llegan por mensaje privado)
docker compose --env-file .env -f infra/docker-compose.yml up --build  # db, api, bot, web y tunnel
scripts/smoke_test.sh                                   # debe acabar en «SMOKE TEST EN VERDE»
```

El contenedor `api` crea las tablas y siembra la demo al arrancar. En la máquina: web en `http://localhost:8080`, API en `http://localhost:8000` (docs en `/docs`) y bot en `:8001`.

### URL pública (móviles, jurado, APK y Telegram)

Una sola URL, la del túnel rápido de Cloudflare (decisión D3), que entra por el `nginx` de la web: `/` → web, `/api/` → `api:8000`, `/webhook/` → `bot:8001`. La web llama a la API en su mismo dominio (`VITE_API_URL=/`), así que no hace falta CORS ni `localhost`.

```bash
python scripts/url_publica.py          # con el compose en marcha: lee la URL del túnel, la pone en PUBLIC_URL y WEB_URL,
                                       # se la pasa al bot sin reiniciarlo (webhook y enlaces) y la escribe para el grupo
python scripts/url_publica.py --ver    # solo enseña la URL actual
```

- **La URL cambia cada vez que se reinicia el túnel.** Reiniciarlo solo si hace falta y, cuando cambie, volver a ejecutar el script (y en el APK, cambiar la dirección en sus ajustes).
- Solo **una** máquina tiene el túnel y `PUBLIC_URL`: la de la demo (el bot de Telegram solo puede estar en una).
- La API va con `uvicorn --proxy-headers`: detrás del túnel ve `https` y el dominio público. CORS solo hace falta para el APK de Capacitor (`https://localhost` y `capacitor://localhost`, ya en `CORS_ORIGENES`); si tu `.env` es anterior, copia esa línea de `.env.example`.

### Arranque en Windows sin Docker

```powershell
cd services\api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
# Solo si sale «DLL load failed while importing _util_cy» (Control de aplicaciones de Windows): SQLAlchemy en Python puro
$env:DISABLE_SQLALCHEMY_CEXT='1'; python -m pip install --force-reinstall --no-deps --no-binary sqlalchemy sqlalchemy==2.1.9
copy ..\..\.env.example ..\..\.env       # opcional; sin .env se usa SQLite en services\api\hackemate.db
python ..\..\scripts\seed.py             # tablas + datos de la demo (repetible)
uvicorn app.main:app --reload --port 8000
```

Python 3.15: `uvicorn` va sin el extra `[standard]` y para YAML se usa `ruamel.yaml` (no hay wheel de PyYAML).

**Con el bot también en local (sin Docker):** el valor por defecto `BOT_URL=http://bot:8001` es el nombre del contenedor y fuera de Docker no existe; los avisos se quedan en cola (`pendiente`, `getaddrinfo failed`). Pon `BOT_URL=http://localhost:8001` en el `.env` (y en el del bot `API_URL=http://localhost:8000`). Guía completa de pruebas: [`docs/PRUEBAS_V1.md`](docs/PRUEBAS_V1.md).

### Arquitectura

```
WhatsApp/Telegram ──> tunnel (HTTPS) ──> bot :8001 ──HTTP + X-Internal-Token──> api :8000 ──> db :5432
                                          ^   │                                   ^
          Twilio/Meta/Telegram, IA  <─────┘   └─<── POST /notify, /ai/* ──────────┘
                                                        web :8080 ──HTTP + Bearer JWT──> api
```

- **Solo `api` toca la base de datos** y decide los estados. `bot` y `web` hablan con ella por HTTP.
- **Solo `bot` habla con Twilio/Meta/Telegram y con la IA.** Si la `api` necesita IA, llama a `bot` en `POST /ai/...`; los avisos los pide con `POST /notify` y, si el bot está caído, quedan en cola y se reintentan.
- Entre servicios: cabecera `X-Internal-Token: ${INTERNAL_TOKEN}`. Usuarios (app y panel): `Authorization: Bearer <jwt>` (login con Google, código por WhatsApp o `/auth/demo` en modo demo).
- Cada servicio arranca aunque los demás estén caídos y expone `GET /health` → `{"status":"ok","version":"x.y.z"}`.

### Variables de entorno del backend

La lista completa y comentada está en `.env.example` (manda sobre esta tabla).

| Variable | Ejemplo | Para qué |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./hackemate.db` | Base de datos. En Docker el compose la fija a PostgreSQL (`db`). |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` / `DB_PORT` | `hackemate` / … / `5432` | Contenedor `db`. |
| `INTERNAL_TOKEN` | `cambia-esto` | Cabecera `X-Internal-Token` entre api y bot. Cambiarlo en la demo (con el de ejemplo la api escribe un `WARNING`). Desde fuera no llega nunca: el nginx de la web la borra. |
| `JWT_SECRET` / `JWT_EXPIRA_MIN` | `cambia-esto-tambien` / `1440` | Firma y duración de las sesiones. Con el valor de ejemplo, la api arranca igual pero escribe un `WARNING` en el log (también con `DEMO_MODE`): pon un secreto aleatorio. |
| `PUERTOS_IP` | `127.0.0.1` | IP donde Docker publica db, api y bot. `127.0.0.1` = solo este ordenador (la web y el túnel van por el 8080). |
| `GOOGLE_CLIENT_ID` / `GOOGLE_TOKENINFO_URL` / `GOOGLE_TIMEOUT_S` | vacío / URL de Google / `5` | Login con Google (vacío → `/auth/google` responde 503). |
| `DEMO_MODE` | `false` | `true` habilita `POST /api/v1/auth/demo` (vecino o asociación; nunca moderador). Solo en la presentación. |
| `ADMIN_USUARIO` / `ADMIN_CONTRASENA` | `admin` / `1234` | Acceso de la moderación del ayuntamiento en la web (`POST /auth/admin`). Cambiar la contraseña en la máquina de la demo. 5 fallos por IP en 10 min → 429. |
| `BOT_URL` | `http://bot:8001` | Dónde están `/notify` y `/ai/*`. |
| `API_URL` | `http://api:8000` | La usa el bot para llamar a la api. |
| `APP_VERSION` | vacío | Versión de `/health` (vacío = la del código). |
| `ZONA_HORARIA` | `Europe/Madrid` | Zona de las fechas y del `.ics`. |
| `MODERACION_UMBRAL_SPAM` | `0.7` | Umbral del antispam. (`MODERACION_APROBACIONES_SUBIR_NIVEL` ya no se usa: no hay subida automática de nivel.) |
| `MODERACION_IMPORTADOS_A_BANDEJA` | `true` | D4: lo importado solo (Facebook) va siempre a la bandeja; `false` = se publica si la asociación está en automática. |
| `NOTIFICACIONES_TIMEOUT_S` / `NOTIFICACIONES_MAX_INTENTOS` | `3` / `5` | Cola de avisos hacia el bot: espera máxima a `/notify` e intentos antes de darlo por fallido. |
| `NOTIFICACIONES_REINTENTO_S` | `60` | Cada cuántos segundos la api reintenta en segundo plano los avisos pendientes (`0` = desactivado). |
| `PRECIOS_TOKENS_EUR_MTOK` | JSON por proveedor | Coste de la IA en `/estadisticas` (euros por millón de tokens; lo que no aparece cuenta como gratuito). |
| `CORS_ORIGENES` | `http://localhost:8080,…` | Orígenes permitidos. |
| `FIXTURES_DIR` | vacío | Carpeta de los fixtures del seed (vacío = `contracts/fixtures`). |

### Endpoints por hito (implementados)

Todos bajo `/api/v1/` salvo `/health`. Detalle, errores y ejemplos en `contracts/openapi.yaml`.

| Hito | Endpoints |
|---|---|
| H0 · Arranque | `GET /health` |
| H1 · Datos y CRUD | `GET /municipios` · `GET /lugares`, `GET /lugares/{id}` · `GET/POST /eventos` · `GET/PATCH /eventos/{id}` · `GET/POST /publicadores` · `GET /publicadores/{id}` · `POST /usuarios` · `GET /usuarios/by-phone/{e164}`, `/usuarios/by-contacto/{contacto}` · `POST /usuarios/vincular` |
| H2 · Ingesta y moderación | `POST /eventos/importar` · `POST /eventos/{id}/confirmar` · `GET /moderacion/pendientes` · `POST /moderacion/{id}/decision` · `POST /publicadores/{id}/aprobar`, `/pausar`, `/fuentes` · `POST /auth/whatsapp/codigo`, `/auth/whatsapp/verificar` |
| H3 · La vecina | `POST /auth/google` · `POST /auth/demo` · `GET/PATCH /usuarios/me` · `GET/POST /eventos/{id}/inscripciones` · `DELETE/PATCH /eventos/{id}/inscripciones/{insc_id}` · `GET/POST /eventos/{id}/mensajes` · `PATCH /eventos/{id}/mensajes/{msg_id}` (fijar, ocultar y silenciar al autor en ese chat con `silenciar_autor`) · `GET /eventos/{id}/ics` · `GET /usuarios/me/ics` · `GET /recomendaciones` |
| H4 · Jurado | `GET /estadisticas` (panel: actividades, inscripciones vs asistencia, ocupación, solapamientos y coste de la IA) · `POST /metrics/tokens` (el bot registra los tokens por proveedor) · `GET /admin/bot/metricas`, `POST /admin/bot/simular-caida` (panel de robustez: la API reenvía al bot con su `INTERNAL_TOKEN`; 503 `bot_no_disponible` si no responde en 3 s, 502 si responde con error) |
| Asociaciones (revisión a mano o automática) | `POST /publicadores/{id}/verificar-identidad` · `POST /publicadores/{id}/aprobar` sobre un publicador ya aprobado cambia `nivel_confianza` (el 2 exige las reglas de `apps/web/src/admin/confianza.ts`; si no, 409 `reglas_confianza_no_cumplidas` con `details.faltan`) · `responsable` y `actividad` solo con sesión de moderador · alta con `responsable` (422 `dni_invalido` si el DNI/NIE no es válido) |

Modos de publicación: solo dos, **a mano** (`nivel_confianza` 0, todo pasa por el moderador) y **automática** (2, se publica salvo spam alto o pausa). No hay semiautomático ni subida automática: a automática solo pasa un moderador y solo si se cumplen las reglas. El nivel 1 está obsoleto (si llega, se guarda como 0). La `actividad` se cuenta por la fecha en que se propuso cada plan (`creado_en`); «aprobados» son los `publicado` y `finalizado`.

### Qué se guarda (lo que hace uno lo ven todos)

Todo pasa por la misma API y la misma base de datos (PostgreSQL en el volumen `db_data` de la máquina de la demo): lo que hace una persona desde su móvil, la web, el panel o Telegram lo ven las demás en cuanto su pantalla vuelve a pedir los datos.

| Acción | ¿Se guarda? |
|---|---|
| `docker compose … restart`, `down` + `up`, `up --build` tras un `git pull`, que la API se caiga y vuelva | ✅ Sí: el seed del arranque solo añade lo que falte (`--solo-nuevos`) |
| Reiniciar el túnel | ✅ Los datos sí, pero **cambia la URL**: `python scripts/url_publica.py` y pasar la nueva |
| Cambiar la URL con `url_publica.py` | ✅ Todo: el bot no se reinicia (webhook y enlaces en caliente) |
| Recrear o reiniciar el bot (`--forzar`, `up --build`) | ✅ La cola sí (`bot_data`); las conversaciones a medias del bot, no |
| `docker compose … down -v` | ❌ **Borra la base entera** (y la cola del bot) |
| `scripts/demo_reset.sh` | ❌ **Borra todo lo creado** y vuelve a los datos iniciales de la demo |

En la demo: **ni `down -v` ni `demo_reset`**, salvo para empezar de cero antes del ensayo.

### Sembrar y reiniciar la demo

- `python scripts/seed.py`: crea/actualiza tablas y carga los fixtures. Repetible; omite los eventos que ya han terminado y solo toca los datos de `contracts/fixtures`. **Devuelve los datos de la demo a como están en los fixtures** (deshace lo hecho sobre ellos).
- `python scripts/seed.py --solo-nuevos` (lo que hace el contenedor `api` al arrancar): solo añade lo que falte; no toca lo que ya existe.
- **Reinicio completo** (borra todo lo creado en el ensayo y vuelve al estado inicial; ~1–2 s, no hace falta reiniciar la api):
  - Docker: `scripts/demo_reset.sh`
  - Sin Docker (Linux/Git Bash): `scripts/demo_reset.sh --local`
  - Windows: `.\scripts\demo_reset.ps1`

### Ingesta de Facebook (A2)

`scripts/importar_facebook.py` (solo Python, sin dependencias): páginas de Facebook → «Facebook Posts Scraper» (Apify) → `bot POST /ai/extraer` → `POST /eventos/importar` (origen `facebook`, URL del post, `importado_auto`) → `POST /eventos/{id}/confirmar` (la API decide el estado: lo importado va siempre a la bandeja, D4).

```bash
python scripts/importar_facebook.py --desde-json       # SIN token: importa los posts ya guardados (sin red ni créditos)
python scripts/importar_facebook.py                    # descarga (FB_SCRAPER_TOKEN) e importa
python scripts/importar_facebook.py --cada 24          # revisión diaria: se queda en marcha y solo pide los posts nuevos
python scripts/importar_facebook.py --solo-descargar   # solo guarda los posts, no importa
python scripts/importar_facebook.py --pagina https://www.facebook.com/<pagina>   # página suelta
```

- **Qué páginas:** las fuentes de Facebook activas de los publicadores aprobados (así el post queda asociado) más `--pagina` y `FB_PAGINAS`. En `.env.example` están las 5: Aytos. de Uleila del Campo, Lucainena de las Torres, Senés y Velefique, y Monte-Sión (Tahal no tiene página).
  Los Aytos. de **Senés, Uleila del Campo, Lucainena y Velefique** son publicadores de la demo con su Facebook como fuente, así que sus posts llegan con su nombre a la bandeja (antes llegaban «Sin publicador identificado»). La página se reconoce aunque cambie la forma de la URL (`profile.php?id=61551352857893` y `/p/Ayuntamiento-de-Senés-61551352857893/` son la misma y no se descarga dos veces). Con `--desde-json`, los posts guardados se asocian a su ayuntamiento por la página.
- **Para que se vean en la app de la demo:** en la máquina de la demo, con todo arrancado, `python scripts/importar_facebook.py --desde-json` (o la revisión diaria). Los planes llegan a la **bandeja** de `/admin` (D4) y aparecen en la agenda cuando el moderador los aprueba. Si ya ha pasado la fecha del plan, la agenda no lo muestra.
- **Qué se guarda:** `contracts/fixtures/facebook_posts.json` (en git) con solo la URL, la página, la fecha, el texto y el texto de las fotos. Tras importar se **quitan los posts que la IA dice que no son planes** (pésames, avisos de obras…), para no guardar datos personales; `--guardar-todo` los deja.
- **Solo lo nuevo:** el JSON apunta `ultima_descarga` y la revisión periódica pide a Apify solo lo publicado desde entonces (Apify cobra por post devuelto). A mano, la ventana es `FB_DESDE` (30 días).
- **Sin inventar nada:** si el bot no responde, el post queda guardado y no se crea nada; si falta la fecha, el evento queda en `pendiente_confirmacion`. Repetirlo no duplica: la API reconoce la URL del post. La fecha de publicación va al final del texto para que la IA entienda «este sábado».
- **Calidad:** sin IA (solo reglas) se cuelan avisos que no son planes y faltan categorías; con Gemini o NIM (tarea B2) sale mucho mejor. En la primera descarga (21/11, solo reglas) salieron 30 posts, 26 con texto, 20 guardados.

**Revisión diaria (una vez al día)**, solo en la máquina de la demo, que es la que tiene el token:
- Con Docker: el servicio `ingesta` del compose, **apagado por defecto** para no gastar crédito sin querer. Encenderlo:
  `docker compose --env-file .env -f infra/docker-compose.yml --profile ingesta up -d ingesta` (y `logs -f ingesta` para ver cada revisión).
- Sin Docker (Windows): una tarea diaria en el Programador de tareas, por ejemplo a las 8:00, con la API y el bot en marcha:
  `schtasks /Create /SC DAILY /ST 08:00 /TN HackeMateFacebook /TR "python C:\ruta\HackeMate\scripts\importar_facebook.py"`
  (cada ejecución a mano pide los últimos `FB_DESDE`; los repetidos no se duplican en la base).

**¿Quién necesita el token de Apify (`FB_SCRAPER_TOKEN`)?** Solo la máquina que descarga (la de la demo). El resto del equipo importa los posts del JSON que hay en git con `--desde-json`, sin token. Se pasa por privado, nunca en `*.example` ni en el grupo; el plan gratuito da unos 5 $ al mes y la revisión diaria de 4 páginas gasta céntimos.

### Tests y smoke test

```bash
cd services/api && python -m pytest -q        # tests unitarios y de contratos (sin Docker)
scripts/smoke_test.sh                         # o .\scripts\smoke_test.ps1 en Windows
```

El smoke test solo usa HTTP. Lee `API_URL` (por defecto `http://localhost:8000`), `INTERNAL_TOKEN` (del entorno o del `.env`) y, si se define, `BOT_URL`. Comprueba `/health`, la agenda, la ficha de la Ruta Solidaria, los municipios, la bandeja de moderación, que la Ruta Solidaria sale primera para Carmen y el `.ics`. Sale con código ≠ 0 si algo falla.

### Modo demo

Con `DEMO_MODE=true`, `POST /api/v1/auth/demo` con `{"rol": "publicador"}` o `{"usuario_id": "<uuid>"}` devuelve un JWT sin login (Carmen, la vecina de la demo, es `5a5e0000-0000-4000-8000-000000000001`). Nunca de moderador (403 `demo_sin_moderador`): la URL de la demo es pública, así que la moderación entra siempre con `POST /auth/admin`. Con `false` responde 404. No dejarlo activo fuera de la presentación.

### Guion de la demo y qué lo sostiene en la api

| Paso | Endpoint de la api |
|---|---|
| 1. Post o audio → ficha | El bot extrae (`/ai/extraer`) y llama a `POST /eventos/importar` (queda `pendiente_confirmacion`) |
| 2. El publicador confirma por WhatsApp | `POST /eventos/{id}/confirmar` → pasa a moderación |
| 3. El moderador aprueba uno; el antispam para otro | `GET /moderacion/pendientes` · `POST /moderacion/{id}/decision` (antispam con `MODERACION_UMBRAL_SPAM`) |
| 4. A una vecina le llega la recomendación y se apunta | `GET /recomendaciones?usuario_id=…` · `POST /eventos/{id}/inscripciones` |
| 5. Pregunta en el chat del evento | `POST /eventos/{id}/mensajes` (la api pide la respuesta a `bot /ai/responder-ficha`) |
| 6. Cambio de hora → aviso a los inscritos | `PATCH /eventos/{id}` → `bot /notify` a cada inscrito + anuncio fijado en el chat |
| 7. Una persona mayor solo con audios | El bot transcribe y usa los mismos endpoints (pasos 1, 2 y 4) |

## 🤖 Bot (flujo B)

El asistente de mensajería: **@HackeMate_bot** en Telegram (canal activo). Vecinos, publicadores y moderadores pueden hacerlo todo desde el chat, con texto, fotos o notas de voz, sin instalar nada. Código en `services/bot/` (FastAPI, puerto 8001).

### Qué se puede hacer desde el chat

| Quién | Ejemplo de mensaje | Qué hace el bot |
|---|---|---|
| Vecina | «¿Qué hay este finde?», «rutas en Velefique», «conciertos mañana» | Busca en la agenda (o usa las recomendaciones de la API) y enseña tarjetas con **✋ Apuntarme** y **ℹ️ Más info** |
| Vecina | «Apúntame a la ruta solidaria» o el botón | Inscripción en la API (`confirmada` o `lista_espera`); en Telegram pide antes «Compartir mi número» |
| Vecina | «¿A qué hora empieza la ruta solidaria?» | Responde con la ficha; si la respuesta no está, la deja en el chat del evento para el organizador |
| Vecina | «Me gustan las rutas y la música» | Guarda sus gustos y pregunta si quiere **avisos de planes nuevos** (D1); «no quiero avisos» / «avísame» lo cambian |
| Persona mayor | Solo **notas de voz** | Las transcribe, entiende lo que pide y le contesta **también con una nota de voz** |
| Publicador | Un texto, **la foto del cartel** o una nota de voz con el plan | Saca la ficha con IA, pregunta lo que falte (fecha, pueblo…) y, con «sí», la envía a la API para publicar o para el moderador |
| Asociación nueva | «Quiero dar de alta mi asociación» | Pide nombre, tipo, pueblo y responsable (nombre, DNI o NIE comprobado y residencia) y la da de alta en `POST /publicadores` (B5). El DNI solo vive en memoria durante el alta |
| Moderador | «pendientes» | La bandeja con el motivo de la IA y el `score_spam`, con botones **Aprobar** / **Rechazar** |
| Visitante | «What's on this weekend?» | Detecta el idioma y responde en el suyo (inglés, francés, alemán, italiano, portugués) |
| Cualquiera | «cancelar» | Borra lo que estaba a medias |

Además: el **antispam** para los posts de apuestas o enlaces sospechosos; los **avisos** que pide la API (cambio de hora, respuestas, moderación, recomendaciones con botones, el código de acceso) y, si la persona lo pidió, también en nota de voz; y los enlaces `t.me/HackeMate_bot?start=codigo` (entrar en la web con código, D2) y `?start=alta`.

### IA: gratis primero y nunca se queda sin responder

```
Gemini → NVIDIA NIM → FreeLLMAPI → Claude (solo con clave, de pago) → reglas (sin IA)
```

Orden en `LLM_CADENA`. Cada proveedor sin clave se salta, y si uno falla o tarda, se pasa al siguiente. **Sin ninguna IA el bot sigue funcionando** con reglas: título, fecha, pueblo, categoría y antispam por patrones. Se prueba en directo con «Simular caída de la IA» en el panel (`/admin/simular-caida`).

- **NVIDIA NIM** (B2): directo, `nvidia/nemotron-3.5-bolt-e4b`, 1–3 s por ficha con el plan gratuito.
- **FreeLLMAPI**: proxy local que junta los planes gratuitos de 7 proveedores. Además del texto, hace la **visión** (carteles), la **transcripción** (`whisper-large-v3`) y la **voz** (TTS). Va en su propio Docker, replicable en cualquier máquina: [`services/bot/freellmapi/`](services/bot/freellmapi/README.md).
- Cada llamada registra sus tokens por proveedor (`GET /metrics` y `POST /metrics/tokens` de la API) para el coste del panel.

### Canales: Telegram ahora, WhatsApp cambiando la configuración

| Canal | Cómo se activa | Estado |
|---|---|---|
| Telegram | `TELEGRAM_TOKEN` (y `PUBLIC_URL` para el webhook) | ✅ Activo, gratis y sin límites |
| WhatsApp Cloud API (Meta) | `CANAL=meta` + `META_*` | Programado y probado; Meta bloquea el envío hasta que una entidad verifique su negocio |
| WhatsApp por Twilio | `CANAL=twilio` + `TWILIO_*` | Alternativa programada |
| Consola | `CANAL=console` | Para pruebas: `POST /dev/mensaje` simula un chat |

Telegram y WhatsApp pueden ir a la vez: el contacto decide el canal (`tg:<chat_id>` o `+34…`). Nada del código supone un canal concreto.

### Arrancarlo

Con todo el proyecto: `docker compose --env-file .env -f infra/docker-compose.yml up -d` y, en la máquina de la demo, `python scripts/url_publica.py`, que registra el webhook de Telegram y los enlaces en caliente, sin reiniciar el bot. **Solo una máquina a la vez** puede tener Telegram (`PUBLIC_URL`).

Variables principales (todas en `.env.example` y `services/bot/.env.example`):

| Variable | Para qué |
|---|---|
| `TELEGRAM_TOKEN`, `TELEGRAM_SECRET` | Bot de Telegram (token de @BotFather; el secreto protege el webhook) |
| `PUBLIC_URL` | URL pública del túnel; vacío en todas las máquinas menos la de la demo |
| `WEB_URL` | Enlaces a las fichas que manda el bot (`{WEB_URL}/evento/{id}`) |
| `API_URL`, `INTERNAL_TOKEN` | Dónde está la API y el token entre servicios |
| `LLM_CADENA` | Orden de los proveedores de IA (`gemini,nim,freellm,claude,reglas`) |
| `GEMINI_API_KEY`, `NIM_API_KEY`, `FREELLM_URL` / `FREELLM_URL_DOCKER`, `FREELLM_API_KEY` | Claves de la IA (gratis). Cada persona, las suyas |
| `CANAL`, `META_*`, `TWILIO_*` | WhatsApp, cuando se active |
| `COLA_PATH` | Cola en disco: si la API está caída, lo que manda el bot se guarda y se reintenta cada 30 s |

Solo el bot, sin Docker (en Windows, mejor con Python 3.12: con 3.13 puede romperse con peticiones en paralelo):

```powershell
cd services\bot
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --port 8001
python -m pytest -q
```

### Rutas que expone

| Ruta | Quién la usa | Para qué |
|---|---|---|
| `POST /webhook/telegram`, `/webhook/meta`, `/webhook/twilio` | Telegram, Meta, Twilio | Mensajes entrantes |
| `POST /notify` | API | Avisos salientes (texto, botones y, si toca, nota de voz). `telefono` o `contacto` |
| `POST /ai/extraer` | API e ingesta de Facebook | Post o cartel → ficha del plan |
| `POST /ai/spam` | API (moderación) | `score_spam` y motivo |
| `POST /ai/responder-ficha` | API (chat del evento) | Respuesta solo con lo que dice la ficha |
| `POST /ai/preferencias` | API | Gustos a partir de un texto |
| `GET /metrics` · `GET`/`POST /admin/simular-caida` | Panel (a través de la API) | Tokens por proveedor y cola (sin datos personales) · caída simulada |
| `POST /admin/webhook-telegram` · `/admin/reintentar-cola` | `url_publica.py`, mantenimiento | Cambiar la URL pública en caliente; reintentar la cola |
| `POST /dev/mensaje` | Pruebas | Chat simulado, sin canal real |
| `GET /health` | Docker | `{"status":"ok","version":"0.1.0"}` |

`/notify`, `/ai/*` y `/admin/*` piden la cabecera `X-Internal-Token`; el de Telegram comprueba `TELEGRAM_SECRET` (Meta y Twilio, su firma si se configura `META_APP_SECRET` o `TWILIO_VALIDAR_FIRMA`); `/health`, `/metrics` y `/dev/mensaje` no piden nada.

### Robustez y privacidad

- **Si la API se cae**, el bot sigue contestando lo que puede y guarda en cola (en disco, volumen `bot_data`) lo que tenía que mandarle. **Si la IA se cae**, pasa a reglas. **Si cambia la URL del túnel**, `url_publica.py` se la pasa al bot sin reiniciarlo y no se pierden las conversaciones a medias.
- **Datos personales:** el bot no guarda nada en base de datos (solo la API toca la base). El DNI del alta no se escribe en los logs ni en la cola (en pantalla, solo enmascarado), y el token de Telegram tampoco sale en los logs. Con `CANAL=console` el bot imprime sus respuestas: es solo para pruebas.
- **162 tests** (`python -m pytest -q` en `services/bot`), sin red ni claves: la API y la IA están simuladas.

Más detalle: [`docs/PLAN_FLUJO_B.md`](docs/PLAN_FLUJO_B.md) (decisiones y canales) y [`services/bot/PARA_FLUJO_A.md`](services/bot/PARA_FLUJO_A.md) (los cuerpos exactos de cada llamada entre la API y el bot).

## 📱 App web y Android (flujo C)

### APK de Android (C9)

El proyecto Android está en `apps/web/android` (Capacitor 8, `appId` `es.hackemate.app`). Hace falta Android Studio con el SDK 36 instalado y un **JDK 21** aparte (Temurin; el `jbr` de Android Studio es Java 25 y Gradle 8.14 no lo admite), y **datos del móvil** (la red de la uni bloquea npm y Gradle).

```powershell
$env:JAVA_HOME = "C:\Users\aalva\Desktop\Hackaton\jdk21\<carpeta jdk-21…>"   # JDK 21 (Temurin); el jbr de Android Studio es 25 y no vale
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
cd apps\web
npm ci
npm run build:apk                 # build con .env.apk y copia a android/
cd android
.\gradlew.bat assembleDebug       # → app\build\outputs\apk\debug\app-debug.apk
copy app\build\outputs\apk\debug\app-debug.apk C:\Users\aalva\Desktop\Hackaton\HackeMate.apk
```

En el móvil: instalar el `.apk` (permitir orígenes desconocidos), ir a **Perfil → Ajustes → Dirección del servidor** y pegar la URL que da `python scripts/url_publica.py`. La app la comprueba, la guarda y se recarga. Cuando el túnel cambie de URL, se cambia ahí sin reinstalar. Sin dirección, la app enseña los datos de ejemplo.

---

<div align="center">

Hecho en la **Universidad de Almería**

</div>
