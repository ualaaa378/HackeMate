# Enums · contratos v1

Valores permitidos en toda la plataforma. Minúsculas con guion bajo. Después de CP0 solo se **añaden** valores (PR `contract-change`).

| Enum | Valores | Dónde se usa |
|---|---|---|
| `rol` | `vecino`, `publicador`, `moderador` | `usuario.rol`, JWT |
| `categoria` | `deportiva`, `cultural`, `fiestas`, `gastronomia`, `ludica`, `comercio` | `evento.categoria`, `usuario.gustos` |
| `estado_evento` | `borrador`, `pendiente_confirmacion`, `en_revision`, `publicado`, `rechazado`, `cancelado`, `finalizado`, `archivado` | `evento.estado` |
| `estado_publicador` | `solicitado`, `whatsapp_verificado`, `aprobado`, `rechazado`, `pausado` | `publicador.estado` |
| `tipo_publicador` | `asociacion`, `ayuntamiento`, `bar_restaurante`, `comercio`, `otro` | `publicador.tipo` |
| `nivel_confianza` | `0`, `1`, `2` (entero) | `publicador.nivel_confianza` |
| `estado_inscripcion` | `confirmada`, `lista_espera`, `cancelada`, `asistio`, `no_asistio` | `inscripcion.estado` |
| `canal` | `whatsapp`, `web`, `panel`, `facebook`, `instagram`, `web_externa`, `manual`, `telegram` | `evento.origen.canal`, `inscripcion.canal`, `fuente.canal` |
| `tipo_notificacion` | `recomendacion`, `cambio_evento`, `anuncio`, `respuesta`, `moderacion`, `confirmacion` | `notificacion.tipo` |
| `formato_aviso` | `texto`, `audio` | `usuario.formato_aviso`, `notificacion.formato` |
| `tipo_mensaje` | `pregunta`, `respuesta`, `anuncio`, `comentario` | `mensaje_evento.tipo` |
| `confianza_campo` | `alta`, `media`, `baja`, `falta` | `extraccion_evento.campos.*.confianza` |
| `decision_moderacion` | `aprobar`, `rechazar`, `retirar`, `restaurar` | `POST /moderacion/{id}/decision` |
| `tipo_lugar` | `ruta`, `sitio_interes`, `comercio`, `alojamiento`, `servicio` | `lugar.tipo` |
| `modalidad_ruta` | `senderismo`, `btt`, `ciclismo`, `paseo` | `lugar.ruta.modalidad` |
| `estado_envio` | `pendiente`, `enviada`, `fallida` | `notificacion.estado_envio` (cola de avisos) |
| `entidad_propuesta` | `particular`, `asociacion`, `comercio`, `otra` | `evento.datos_ayuntamiento.entidad` (privado) |
| `publico_propuesta` | `todos`, `infantil`, `adultos`, `mayores` | `evento.datos_ayuntamiento.publico` (privado) |
| `necesidad_propuesta` | `espacio`, `calle`, `material`, `luz`, `musica`, `comida`, `seguridad`, `limpieza`, `difusion` | `evento.datos_ayuntamiento.necesidades` (privado) |
| `seguro_rc` | `si`, `no`, `nose` | `evento.datos_ayuntamiento.seguro_rc` (privado) |

## Canales de mensajería (contacto)

El bot habla con la gente por WhatsApp y por Telegram. Cada persona se identifica en su canal con una dirección de contacto (`Contacto` en `openapi.yaml`):

- WhatsApp: el teléfono E.164 (`+34600000000`), en `telefono`.
- Telegram: `tg:<chat_id>` (Telegram no da el teléfono), con el `chat_id` en `telegram_id`. El bot pide «Compartir mi número» y lo vincula con `POST /api/v1/usuarios/vincular`.

## Significado de los estados de evento

- `borrador`: creado a mano, sin enviar.
- `pendiente_confirmacion`: importado por la IA; faltan datos o la confirmación del publicador.
- `en_revision`: espera al moderador (nivel 0, spam alto o algo fuera de lo habitual). La bandeja muestra el `motivo`.
- `publicado`: visible en agenda, mapa, app, web y bot. **Solo estos salen en `GET /eventos` público.**
- `rechazado`, `cancelado`, `finalizado`, `archivado`: no visibles en la agenda.

## Niveles de confianza del publicador

**Solo hay dos modos de publicación** (decisión del equipo, sáb 21/11: no hay semiautomático):

- `0` · **a mano**: todo plan pasa por el moderador. Es el modo de toda asociación nueva.
- `2` · **automática**: se publica sin revisión, salvo spam alto, publicador pausado o automatizaciones pausadas.
- `1` · **obsoleto** (era «pasa si es su categoría habitual»). Se mantiene en el enum por compatibilidad (después de CP0 no se borra nada), pero la API ya no lo asigna: si llega en `POST /publicadores/{id}/aprobar`, se guarda como `0`, y si queda alguno en la base se trata como «a mano».
- **No hay subida automática.** `aprobaciones` sigue contando (estadísticas) y `MODERACION_APROBACIONES_SUBIR_NIVEL` ya no se usa. Solo un moderador pasa una asociación a automática.
- El moderador cambia el modo de un publicador ya aprobado con `POST /publicadores/{id}/aprobar` (`nivel_confianza` 0 o 2).
- Pasar a nivel 2 a mano exige las reglas de `apps/web/src/admin/confianza.ts`: responsable con DNI y residencia comprobados (`responsable.identidad_verificada`), al menos 3 planes aprobados en 60 días, ningún rechazo en 60 días y algún plan en los últimos 90 días (`actividad`). Si no, 409 `reglas_confianza_no_cumplidas` con `details.faltan` ⊂ {`identidad_verificada`, `planes_60_dias`, `rechazados_60_dias`, `ultimo_plan`}.

## Datos privados

- `evento.datos_ayuntamiento`: solo organizador del evento y moderadores (con sesión). Nunca en rutas públicas ni hacia el bot o la IA.
- `publicador.responsable` y `publicador.actividad`: solo moderadores (con sesión). `responsable.dni` es un dato personal: se guarda lo mínimo.

## Municipios (fixture `municipios.json`)

Lucainena de las Torres, Senés, Velefique, Uleila del Campo, Tahal. El nombre se escribe tal cual (con tilde en «Senés»).
