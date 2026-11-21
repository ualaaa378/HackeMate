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

El proyecto está **en sus primeras fases**. Iremos actualizando este README a medida que avancemos.

## 🔗 Pendiente entre flujos

Revisado el 21/11/2026 a las 00:15. Todo esto ya lo usa la app web (flujo C) o el bot (flujo B), pero depende de otro flujo. Mientras no esté, **la web vuelve sola a los datos de prueba (mocks) y el bot guarda la petición en cola**, así que nada se rompe, pero la demo no usa datos reales. Al cerrar cada punto, se borra de esta lista.

> **Regla del equipo (ver `CLAUDE.md`):** cada flujo apunta aquí, bajo el flujo responsable, lo que necesita de los demás. Antes de empezar una tarea, revisa tu apartado.

### Flujo A · API (Benas)

Rutas que ya están en `contracts/openapi.yaml` pero la API aún no tiene:

| Ruta | La usa | Para qué en la demo |
|---|---|---|
| `GET /moderacion/pendientes` · `POST /moderacion/{id}/decision` | web `/admin` (Bandeja) y bot | El moderador aprueba un plan y el antispam frena otro |
| `POST /publicadores/{id}/aprobar` · `POST /publicadores/{id}/pausar` | web `/admin` (Asociaciones) | Dar de alta o pausar a una asociación |
| `POST /eventos/{id}/confirmar` | bot | El publicador confirma la ficha por Telegram |
| `GET/POST /eventos/{id}/inscripciones` | web (Ficha) y bot | La vecina se apunta |
| `GET/POST /eventos/{id}/mensajes` | web (chat del evento) y bot | Pregunta en el chat del evento |
| `GET /recomendaciones` | bot | A la vecina le llega la recomendación |
| `POST /auth/whatsapp/codigo` · `POST /auth/whatsapp/verificar` | web (crear cuenta) | Alta con nombre + móvil + código |
| `GET/PATCH /usuarios/me` | web (Perfil) | Sesión del vecino y sus gustos |
| `GET /estadisticas` | web `/admin` (Panel) | Panel de estadísticas para el jurado |

Otros puntos de la API:
- **Moderación automática al confirmar:** `POST /eventos/{id}/confirmar` tiene que llamar a `bot POST /ai/spam` y aplicar los niveles de confianza y `MODERACION_UMBRAL_SPAM` (antispam del paso 3 de la demo).
- **Aviso de cambio de hora:** cuando `PATCH /eventos/{id}` cambia la hora, la API llama a `bot POST /notify` para cada inscrito, con `formato: "audio"` si el usuario lo pidió (pasos 6 y 7 de la demo).
- **`POST /metrics/tokens`:** el bot ya manda el coste de cada llamada a la IA y hoy recibe 404. Sin esto, `GET /estadisticas` no puede mostrar los tokens.
- **Panel de robustez (lo pide la web, pasando por la API):** que la API exponga el interruptor `bot POST /admin/simular-caida` y las cifras de `bot GET /metrics`, para no poner el `INTERNAL_TOKEN` en el navegador.
- **Permisos de `POST /eventos` y `PATCH /eventos/{id}`:** hoy solo aceptan `X-Internal-Token`. La web (Proponer y `/admin`) llama con el JWT del usuario, así que tienen que aceptar `Authorization: Bearer` con rol de vecino, publicador o moderador.
- **Imagen del plan (`imagen_url`):** la web manda la foto opcional como *data URL* WebP comprimida dentro de `imagen_url`. La API tiene que aceptarla (puede ocupar cientos de KB) o, mejor, ofrecer una ruta de subida de archivos que devuelva la URL. Si se añade esa ruta, primero va al contrato.
- **Planes terminados (inscripción cerrada, fotos y comentarios):** contrato ya actualizado. La web oculta «Apuntarme» y las preguntas en un plan pasado y deja ver fotos y comentar. La API tiene que: rechazar `POST /eventos/{id}/inscripciones` con 409 `evento_finalizado` si el plan ya terminó; en `POST /eventos/{id}/mensajes`, admitir solo `tipo: comentario` (si no, 409 `evento_finalizado`); y aceptar el nuevo campo opcional `imagen_url` del mensaje solo si quien escribe se inscribió al plan, lo organiza o es moderador (si no, 403 `sin_permiso`). Lo usa la ficha y la pestaña Recuerdos.
- **Planes terminados para «Recuerdos»:** la pestaña pide `GET /eventos?hasta=<ahora>`, pero el seed omite los eventos ya terminados, así que con la API real sale vacía. Hace falta sembrar algunos planes pasados (estado `finalizado`) o que el seed no los borre.
- **Datos para el ayuntamiento al proponer un plan** (responsable, teléfono, público, necesidades, seguro): la web los tiene en `DatosAyuntamiento` (`apps/web/src/api/types.ts`), pero no están en el contrato. Hay que añadirlos como objeto opcional y privado (PR con etiqueta `contract-change`).

- **Revisión a mano o automática de las asociaciones (lo pide la web `/admin` → Asociaciones):** solo hay dos modos. Toda asociación empieza **a mano** (`nivel_confianza` 0 o 1) y pasa a **automática** (`nivel_confianza` 2) cuando el moderador lo decide y cumple las reglas de `apps/web/src/admin/confianza.ts`: responsable identificado (DNI y residencia comprobados), al menos 3 planes aprobados en 60 días, ningún rechazo en 60 días y algún plan en los últimos 90 días. Hace falta en la API:
  - Objeto opcional y privado `responsable` en el publicador (`nombre`, `dni`, `residencia`, `identidad_verificada`), que solo vea el moderador (PR `contract-change`). Hoy está en `DatosResponsable` de `apps/web/src/api/types.ts`. Es un dato personal: guardar lo mínimo y no devolverlo nunca en las rutas públicas.
  - Una ruta para que el moderador marque la identidad como comprobada (por ejemplo `POST /publicadores/{id}/verificar-identidad`), primero en el contrato. Sin ella, el botón solo funciona en modo demo.
  - Actividad reciente en el publicador (`planes_60_dias`, `rechazados_60_dias`, `ultimo_plan`), calculada por la API. Hoy la web la tiene en `ActividadPublicador` con mocks.
  - Que `POST /publicadores/{id}/aprobar` acepte cambiar `nivel_confianza` en un publicador ya aprobado (la web lo usa para pasar a automática o volver a mano), y que la API rechace el nivel 2 si no se cumplen las reglas.

### Flujos A y B · a acordar (Benas + Francisco)

- **`PATCH /usuarios/{id}`:** el bot lo usa para guardar los gustos de la vecina (`services/bot/app/api_cliente.py`, `guardar_preferencias`), pero no está en el contrato, que solo tiene `PATCH /usuarios/me`. O se añade al contrato con `X-Internal-Token`, o el bot pasa a usar otra ruta.
- **Código de acceso por mensajería (Telegram y WhatsApp):** `POST /auth/whatsapp/codigo` tiene que pedir al bot (`POST /notify`) que mande el código. El nombre de la ruta no se cambia (el contrato no renombra), pero vale para los dos canales. Con Telegram, el bot no puede escribir a un móvil que nunca le ha hablado. Hace falta acordar el paso previo: por ejemplo, que la web enseñe el enlace `t.me/HackeMate_bot?start=alta` y el vecino comparta su número con «Compartir mi número» (`POST /usuarios/vincular`) antes de pedir el código. Si hace falta un campo `canal` en la petición, se añade como opcional con `contract-change`.

### Todos · Telegram ahora, WhatsApp más adelante

Regla en `CLAUDE.md` § «Canales de mensajería». Cómo se elige el canal hoy, sin tocar código:
- **Bot (B):** Telegram se activa con `TELEGRAM_TOKEN`, y los contactos `tg:<chat_id>` salen por ahí. WhatsApp sale por `CANAL` (`meta`, `twilio` o `console`). Los dos pueden funcionar a la vez.
- **API (A):** guarda los dos contactos (`telefono` E.164 y `telegram_id`) y los distingue en `services/api/app/canales.py`. Nada de la API puede dar por hecho un canal concreto.
- **Web (C):** `VITE_CANAL=telegram|whatsapp` (en `.env.example`, el compose y el `Dockerfile`) elige qué canal nombra la web en el alta y en los avisos (`apps/web/src/canal.ts`).

Pendiente: Benas y Francisco, que el aviso al vecino use el contacto que tenga (`telegram_id` si existe, si no `telefono`) en vez de suponer WhatsApp.

### Flujo C · web (Adán), lo que pide el bot

- Botón «Simular caída de la IA» y coste en tokens en `/admin/panel`, en cuanto la API los exponga (ver arriba).
- Opcional, como plan C de la demo: un chat simulado en la web que llame a `bot POST /dev/mensaje`.

### Flujo B · bot (Francisco), alta de asociaciones

- **Datos del responsable al dar de alta una asociación:** cuando alguien pide publicar por Telegram (y por WhatsApp cuando Meta lo permita, con el mismo flujo de conversación), el bot tiene que pedir el nombre, el DNI y el pueblo donde vive el responsable, y mandarlos a la API en el alta (cuando el campo `responsable` esté en el contrato, ver flujo A). Sin esos datos la asociación nunca podrá publicar sin revisión.

### Flujo B · bot (Francisco), opcional en el compose

- Volumen `bot_data` con `COLA_PATH` para que la cola sobreviva si se recrea el contenedor, y `PUBLIC_URL` en el `.env` si el túnel tiene URL fija (ver `services/bot/PARA_FLUJO_A.md` §4).

Detalle del flujo B, con los cuerpos exactos de cada llamada: [`services/bot/PARA_FLUJO_A.md`](services/bot/PARA_FLUJO_A.md) y [`docs/PLAN_FLUJO_B.md`](docs/PLAN_FLUJO_B.md) §5.

### Ya resuelto

- Docker compose arranca el bot real de `services/bot` (PR #23, probado en Docker).

---

<div align="center">

Hecho en la **Universidad de Almería**

</div>
