# Guion de la exposición técnica · HackeMate (Reto 1 «Reactiva tu pueblo»)

> Versión visual (para ensayar e imprimir a PDF): [`GUION_DEFENSA.html`](GUION_DEFENSA.html).
> Guion para la exposición ante el jurado del domingo 22/11. Sigue el orden de la **rúbrica oficial** (Bloque I técnico, 70 %, y Bloque II visual, 30 %), para que cada criterio tenga su momento y no se nos quede nada sin decir.
> **Se mantiene vivo:** cuando algo nuevo llegue a `develop`, se añade a su criterio y se mueve de «Líneas de mejora» a «Hecho».

## 0. Cómo nos puntúan (para tenerlo delante)

| Criterio | Peso | Qué buscan | Dónde lo contamos |
|---|---|---|---|
| 1.1 Requisitos mínimos y lógica de negocio | **16 %** | Todo lo que pide el reto, en vivo y estable | §2, demo en directo |
| 1.2 Funcionalidades extra e innovación | **12 %** | Utilidad real y originalidad | §3 |
| 1.3 Arquitectura, APIs e IA | 10,5 % | Back-end, BD, sincronización entre canales, mapas, IA | §4 |
| 1.4 Eficiencia y recursos | 10,5 % | Tiempos, consumo, optimización, sostenible en el rural | §5 |
| 1.5 Seguridad, privacidad y código | 10,5 % | Repositorio limpio, credenciales, datos, roles, moderación | §6 |
| 1.6 Escalabilidad y despliegue municipal | 10,5 % | Que sirva a todos los pueblos y cueste poco mantenerlo | §7 |
| 2.1 Usabilidad y accesibilidad (UI/UX) | 10 % | Para vecinos de cualquier edad, comercios y ayuntamiento | §8 |
| 2.2 Funcionalidad del front-end | 10 % | Fluidez, paneles, mapa, asistente conversacional | §8 |
| 2.3 Multiplataforma y responsive | 10 % | Web, Android/APK, iOS, mensajería; móvil, tableta y escritorio | §8 |

**Lo que más pesa es 1.1 (16 %) y 1.2 (12 %): la demo en vivo tiene que salir entera.** Los otros siete criterios valen casi lo mismo (10–10,5 %): no se salta ninguno.

## 1. Preparación (antes de entrar)

- [ ] Portátil de Adán con el compose en marcha (`up -d`) y la URL fija **https://hackemate.rompelab.com** respondiendo.
- [ ] Tres móviles **con datos** (no la wifi de la uni): el de la vecina (Telegram + APK), el del publicador (Telegram) y uno para el jurado (web).
- [ ] Panel `/admin` abierto en el portátil, con la sesión de moderador ya iniciada.
- [ ] Un post de Facebook, un cartel y una nota de voz preparados para mandar al bot. También un post de **fraude** («paga por Bizum por adelantado…»).
- [ ] El vídeo de respaldo (C7) abierto en otra pestaña por si falla la red.
- [ ] Papeles repartidos: **quién cuenta** (portavoz: Adán), **quién lleva el móvil de la vecina** (audios), **quién lleva el panel del moderador** y **quién contesta las preguntas técnicas** (API: Benas; bot e IA: Francisco; web: Adán).

## 2. Apertura y requisitos mínimos · criterio 1.1 (16 %)

**Mensaje de entrada (30 s):** «En los pueblos del interior hay planes, pero nadie se entera: están en un cartel, en un post de Facebook o en el grupo del bar. HackeMate junta todo eso en un solo sitio sin pedirle a nadie que aprenda una app nueva: el que publica manda un mensaje, una foto o un audio al bot, y el vecino recibe el plan que le gusta y se apunta con un botón.»

**Tres puertas sincronizadas** (decirlo así): bot de mensajería con IA, app web/PWA + APK Android, y panel del ayuntamiento. Las tres leen y escriben la misma API: lo que pasa en una se ve al momento en las otras.

**Demo en vivo: los 7 pasos del guion** (en este orden; cada paso, una frase de lo que se ve):

1. **Post o audio → ficha.** Reenviamos un post de Facebook (o una nota de voz) al bot: la IA saca título, fecha, hora, lugar, precio y categoría, y pregunta solo lo que falta.
2. **El publicador confirma** por mensajería con un botón.
3. **Moderación:** el moderador aprueba uno en la bandeja y el antispam para otro (enseñar el chip **«⚠️ Posible fraude»** con el post de Bizum).
4. **Recomendación:** a la vecina le llega el plan por sus gustos, cercanía o pueblo favorito, con [✋ Apuntarme] [ℹ️ Más info], y se apunta con un botón. La plaza se descuenta en la web al momento.
5. **Chat del evento:** pregunta «¿hay que llevar agua?» y la IA contesta con los datos de la ficha.
6. **Cambio de hora:** el organizador lo cambia («quiero cambiar la hora de la ruta» por el bot, o «Modificar» en la web) y **todos los apuntados reciben el aviso** y un anuncio fijado en el chat.
7. **Persona mayor solo con audios:** pregunta por voz y el bot le contesta también con una nota de voz.

**Resto de requisitos del reto que hay que nombrar (aunque no se enseñen todos):**
- Roles: **moderador, publicador y vecino**, y cada uno puede hacerlo todo por el bot.
- Alta de publicador: verificación del teléfono, datos del responsable (DNI/NIE, solo los ve el moderador), aprobación del ayuntamiento.
- Ingesta automática de Facebook de los ayuntamientos (Apify): **sin duplicados** (se guarda el origen y se detectan títulos parecidos). Lo importado **pasa siempre por la bandeja**.
- Moderación con **dos modos** por publicador (a mano / automática) y el motivo de cada decisión a la vista.
- Participación: **lista de espera** que sube sola, **`.ics` / Google Calendar**, desapuntarse, recordatorio 24 h antes.
- **Mapa** Leaflet + OpenStreetMap con filtro por tipo de plan y por meses (solo próximos).
- **Panel:** actividades, % importadas solas, inscripciones y asistencia real, ocupación por tipo de plan, **solapamientos entre pueblos** (p. ej. las dos cabalgatas del 5 de enero) y coste de la IA.
- Desplegado con **URL pública fija** (https://hackemate.rompelab.com) y código en GitHub.

## 3. Funcionalidades extra e innovación · criterio 1.2 (12 %)

Lo que hemos añadido más allá de los mínimos (decir **para qué sirve en el pueblo**, no solo qué es):

- **Antifraude**, no solo antispam: detecta pagos por adelantado, Bizum, datos bancarios, precios irreales o suplantar al ayuntamiento; en la bandeja sale «Posible fraude». Un plan aprobado que se edita para colar un timo **vuelve a revisión**.
- **Ideas de la IA para el ayuntamiento:** mira qué planes se llenaron (ocupación, lista de espera, preguntas en el chat) y propone repetirlos («las migas se ocuparon al 90 %: otra edición en octubre») con [Crear borrador].
- **Buscador en lenguaje natural:** «algo para ir con niños el domingo por la tarde cerca de Tahal».
- **Pueblo favorito:** si has ido a varios planes de un pueblo, te avisa de los siguientes aunque sean de otro tipo.
- **Tareas automáticas:** recordatorio 24 h antes, «¿qué tal fue?» al terminar (la respuesta queda como comentario del plan) y resumen semanal por pueblo.
- **Organizador:** pestaña «Mis planes propuestos» y «modificar plan» por el bot, también para **vecinos sin asociación**.
- **Apelaciones:** quien ve rechazado su plan puede pedir **una** revisión, desde la web o con el botón [✍️ Apelar] del aviso.
- **Asistente del moderador:** la bandeja le resume qué hay («1 posible fraude, 1 apelación…»), le sugiere qué hacer con cada plan y, al rechazar, **la IA redacta un mensaje amable** para quien lo propuso, que el moderador revisa antes de enviarlo.
- **«Quedan pocas plazas»:** cuando a un plan le quedan pocas plazas, avisa automáticamente a quien le puede interesar y aún no se ha apuntado, con [✋ Apuntarme].
- **Traducción automática:** si un visitante o un residente extranjero escribe en otro idioma, el bot lo entiende y le contesta en su idioma.
- **Robustez en directo:** botón «Simular caída de la IA» en el panel: el bot sigue funcionando con reglas.

## 4. Arquitectura, APIs e IA · criterio 1.3 (10,5 %)

Enseñar un diagrama de una diapositiva: **web/APK ↔ nginx ↔ API ↔ base de datos**, **bot ↔ API**, **bot ↔ Telegram/WhatsApp e IA**, todo detrás del túnel de Cloudflare.

- **Cinco servicios en Docker Compose:** `api` (FastAPI + SQLAlchemy + Alembic), `bot` (FastAPI), `web` (Ionic React + nginx), `db` (PostgreSQL con pgvector; SQLite en local) y `tunnel` (Cloudflare). Un solo `docker compose up`.
- **Reglas que nadie rompe:** solo la API toca la base de datos y decide estados; solo el bot habla con los canales y con la IA; la IA propone, la API valida y **una persona decide lo importante**.
- **Contract-first:** `contracts/openapi.yaml` + JSON Schema + datos de ejemplo. Los tres equipos programaron a la vez contra el contrato; los tests validan los fixtures contra los schemas.
- **IA con cadena de respaldo:** Gemini → NVIDIA NIM → FreeLLM → Claude → **reglas sin IA**. Si un proveedor falla, pasa al siguiente sin que el vecino lo note. Para las tareas nuevas, FreeLLM primero.
- **Qué hace la IA:** extraer la ficha de un post, cartel (visión) o audio (transcripción), antispam y antifraude, responder en el chat con los datos de la ficha, recomendar y proponer planes al ayuntamiento, y voz (texto a audio).
- **Sincronización entre canales:** webhook de Telegram → bot → API; la web refresca cada pocos segundos; los avisos salen de la API por `POST /notify` del bot (con cola si el bot está caído).
- **Mapas GIS:** Leaflet + OpenStreetMap, «cerca de mí» por radio y coordenadas de los cinco municipios.
- **Pruebas:** más de 650 tests de la API (en Docker, Python 3.12) y más de 200 del bot.

## 5. Eficiencia y recursos · criterio 1.4 (10,5 %)

- **Reglas antes que IA:** intención, antispam claro, fechas y búsquedas sencillas se resuelven sin gastar tokens; solo lo dudoso va a la IA.
- **Coste medido y a la vista:** el panel enseña llamadas, tokens y € por proveedor. **0 € en la demo**: todos los proveedores usados son gratuitos.
- **Acuse inmediato:** el bot contesta enseguida y lo lento (IA, avisos) va en segundo plano.
- **Si algo falla, no se pierde nada:** cola en disco de lo que el bot tenía que mandar a la API; «circuito abierto» que deja de llamar a un servicio caído durante un rato; reintentos de avisos.
- **Ligero para el rural:** la PWA guarda solo los estáticos (nada de datos viejos), las imágenes se validan y limitan, consultas paginadas, y el túnel va por HTTP/2 (TCP 443) para redes que bloquean UDP.
- **Funciona con mensajes y audios:** no hace falta buena cobertura ni un móvil potente para usarlo.

## 6. Seguridad, privacidad y calidad del código · criterio 1.5 (10,5 %)

- **Roles y permisos:** vecino, publicador, moderador. Sesiones con JWT; entre servicios, `X-Internal-Token` que nginx **borra si llega de fuera**. Base de datos, API y bot solo escuchan en `127.0.0.1`: desde fuera solo se entra por la web.
- **Acceso del moderador:** usuario y contraseña con **bloqueo tras 5 intentos**; el acceso «demo» ya no da sesión de moderador.
- **Datos personales mínimos:** el DNI/NIE del responsable de una asociación solo lo ven los moderadores, y el bot lo enseña enmascarado (•••••678Z); el teléfono no sale en lo público; los avisos de recomendación son **opt-in** (consentimiento expreso).
- **Edad mínima de 14 años** para registrarse (LOPDGDD art. 7, consentimiento de datos en España).
- **Moderación de contenidos:** antispam + antifraude en planes, en el chat de cada evento y al editar un plan publicado; el moderador puede retirar, pausar a un publicador o silenciar a alguien en el chat.
- **Credenciales:** todas por variables de entorno (`.env` nunca se sube; `.env.example` documentado); la API avisa en el log si se usa una clave de ejemplo.
- **Repositorio:** monorepo ordenado por servicio, ramas por flujo e integración por PR a `develop`, Conventional Commits, contratos versionados, migraciones Alembic y tests.

## 7. Escalabilidad y despliegue municipal · criterio 1.6 (10,5 %)

- **Un pueblo más = una fila más** en la tabla de municipios (con sus coordenadas). La Mancomunidad entera cabe en la misma instalación, con filtro y estadísticas por pueblo.
- **Coste casi cero:** Telegram es gratis y sin límite de mensajes; los proveedores de IA, en su plan gratuito con respaldo por reglas; el túnel de Cloudflare es gratis. Basta un ordenador del ayuntamiento o un servidor pequeño.
- **Las mismas imágenes Docker** se pueden llevar a la nube (Render, Railway, un VPS de la Diputación) sin cambiar código.
- **WhatsApp listo para producción:** el adaptador de la API de WhatsApp de Meta ya está programado. Meta pide que una entidad verifique su negocio: en cuanto el ayuntamiento o la Diputación lo haga, se activa **cambiando la configuración**, sin tocar código. Telegram y WhatsApp pueden funcionar a la vez.
- **Mantenimiento bajo:** el moderador decide con botones; lo importado y lo dudoso cae solo en la bandeja; las tareas (recordatorios, resúmenes) son automáticas.

## 8. Parte visual, front-end y multiplataforma · Bloque II (30 %)

**2.1 Usabilidad y accesibilidad**
- Pensado para **personas mayores:** todo se puede hacer por mensajes de voz, con respuestas también en audio; botones grandes en el bot; selector de **tamaño de letra** (A A A) en la cabecera de la web; textos con buen contraste.
- Cada perfil tiene su camino: **vecino** (agenda, «Para ti», apuntarse), **publicador** («Mis planes propuestos», modificar, apelar), **ayuntamiento** (bandeja, panel, ideas de la IA).
- Gustos y edad opcionales al registrarse: se puede saltar todo.

**2.2 Funcionalidad e interactividad**
- **Agenda** con buscador, compartir, «Cómo llegar» y el último filtro recordado; ficha con «Apuntarme» siempre a mano; **mapa** con filtro por meses; **Recuerdos** de los planes pasados.
- **Bandeja del moderador** con la acción que recomienda el antispam destacada, contador de pendientes y chips de fraude y apelación.
- **Panel** con cifras, barras de ocupación proporcionales, solapamientos, coste de la IA y el bot en directo.
- **Asistente conversacional:** el propio bot, con botones y lenguaje natural.

**2.3 Multiplataforma y responsive**
- **Web/PWA** instalable (iconos y manifest), **APK Android** (Capacitor) y **bot de Telegram**, todos con los mismos datos.
- **Responsive:** en escritorio la agenda pasa a tres zonas (tus planes y sugeridos, agenda, recuerdos); en móvil y en el APK se queda en una columna.
- **iOS:** la PWA se instala desde Safari («Añadir a pantalla de inicio»). Una app nativa de iOS es solo compilar el mismo proyecto Capacitor (ver líneas de mejora).
- **WhatsApp:** programado y a la espera de la verificación de Meta (ver §7).

## 9. Cierre (30 s)

«HackeMate no pide a los pueblos que cambien sus costumbres: usa el bot que ya tienen en el bolsillo, la voz para quien no escribe y un panel sencillo para el ayuntamiento. Coste cero, funciona aunque se caiga la IA y se puede instalar mañana en cualquier pueblo de la Mancomunidad.»

## 10. Líneas de mejora y expansión

> Se actualiza a medida que algo llega a `develop`: pasa a «Hecho» y se cuenta en su criterio.

| Línea | Criterio | Estado |
|---|---|---|
| Activar **WhatsApp** (Meta Cloud API) en cuanto una entidad verifique su negocio | 1.6 · 2.3 | Programado, a falta de la verificación |
| App nativa de **iOS** con el mismo proyecto Capacitor | 2.3 | Pendiente |
| **Login con Google** en la web | 1.1 | Comprobar antes de la exposición |
| Fuentes nuevas para la ingesta: **Instagram** y webs municipales | 1.2 | Pendiente |
| Clasificador antispam **local** (tipo SBERT) para gastar aún menos tokens | 1.4 | Pendiente |
| **Frase de portada** generada por la IA para cada plan (B5b) | 1.2 | Descartado por ahora |
| Asistente del moderador en el chat y calendario «Mis planes» compartible | 1.2 · 2.2 | Pendiente |
| Despliegue en la nube de la Diputación (VPS o Render) con copias de seguridad | 1.6 | Pendiente |
| Rotar todas las claves usadas durante la hackathon y cambiar la contraseña de moderación | 1.5 | Tras la hackathon |
| Asistente del moderador (resumen, sugerencias y motivo de rechazo con IA) | 1.2 · 1.5 | **Hecho** (dom 22/11) |
| Aviso automático «quedan pocas plazas» | 1.2 · 1.4 | **Hecho** (dom 22/11) |
| Aviso de choque entre pueblos al publicar, con fecha alternativa propuesta por la IA | 1.2 · 1.6 | **Hecho** (dom 22/11, Adán) |
| «La radio del pueblo»: resumen semanal en audio | 1.2 · 2.1 | **Hecho** (dom 22/11, Adán) |
| Compartir coche entre vecinos que van al mismo plan (con doble consentimiento) | 1.2 · 1.6 | **Hecho** (dom 22/11, Adán) |
| Informe mensual para el alcalde redactado por la IA | 1.2 · 1.6 | Propuesta |
| _(añadir aquí lo que se suba al repositorio después de las 00:00)_ | | |

## 11. Preguntas que nos pueden hacer (respuesta corta)

- **¿Y si se cae la IA?** Pasa al siguiente proveedor y, si caen todos, a reglas. Lo enseñamos con «Simular caída de la IA».
- **¿Cuánto cuesta?** 0 € en la demo; se mide por proveedor en el panel. En producción, unos pocos euros al mes como mucho, solo si se usa Claude.
- **¿Por qué Telegram y no WhatsApp?** Meta bloquea el envío hasta verificar un negocio; no inventamos datos para saltárnoslo. WhatsApp está programado y se activa con configuración.
- **¿Cómo evitáis los timos?** Antifraude con reglas + IA, todo lo importado y lo dudoso pasa por una persona, y editar un plan aprobado vuelve a pasar el filtro.
- **¿Protección de datos?** Mínimos datos, DNI solo para moderadores, consentimiento para avisos, edad mínima de 14 años y claves fuera del código.
- **¿Cómo se añade otro pueblo?** Una fila en la tabla de municipios; nada más.
