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
- **Permisos de `POST /eventos` y `PATCH /eventos/{id}`:** hoy solo aceptan `X-Internal-Token`. La web (Proponer y `/admin`) llama con el JWT del usuario, así que tienen que aceptar `Authorization: Bearer` con rol de vecino, publicador o moderador.
- **Imagen del plan (`imagen_url`):** la web manda la foto opcional como *data URL* WebP comprimida dentro de `imagen_url`. La API tiene que aceptarla (puede ocupar cientos de KB) o, mejor, ofrecer una ruta de subida de archivos que devuelva la URL. Si se añade esa ruta, primero va al contrato.
- **Planes terminados para «Recuerdos»:** la pestaña pide `GET /eventos?hasta=<ahora>`, pero el seed omite los eventos ya terminados, así que con la API real sale vacía. Hace falta sembrar algunos planes pasados (estado `finalizado`) o que el seed no los borre.
- **Datos para el ayuntamiento al proponer un plan** (responsable, teléfono, público, necesidades, seguro): la web los tiene en `DatosAyuntamiento` (`apps/web/src/api/types.ts`), pero no están en el contrato. Hay que añadirlos como objeto opcional y privado (PR con etiqueta `contract-change`).

### Flujos A y B · a acordar (Benas + Francisco)

- **`PATCH /usuarios/{id}`:** el bot lo usa para guardar los gustos de la vecina (`services/bot/app/api_cliente.py`, `guardar_preferencias`), pero no está en el contrato, que solo tiene `PATCH /usuarios/me`. O se añade al contrato con `X-Internal-Token`, o el bot pasa a usar otra ruta.
- **Código de acceso por mensajería:** `POST /auth/whatsapp/codigo` tiene que pedir al bot (`POST /notify`) que mande el código. Hoy el canal activo es Telegram.

### Ya resuelto

- Docker compose arranca el bot real de `services/bot` (PR #23, probado en Docker).

---

<div align="center">

Hecho en la **Universidad de Almería**

</div>
