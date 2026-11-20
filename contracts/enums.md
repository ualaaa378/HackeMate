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
| `canal` | `whatsapp`, `web`, `panel`, `facebook`, `instagram`, `web_externa`, `manual` | `evento.origen.canal`, `inscripcion.canal`, `fuente.canal` |
| `tipo_notificacion` | `recomendacion`, `cambio_evento`, `anuncio`, `respuesta`, `moderacion`, `confirmacion` | `notificacion.tipo` |
| `formato_aviso` | `texto`, `audio` | `usuario.formato_aviso`, `notificacion.formato` |
| `tipo_mensaje` | `pregunta`, `respuesta`, `anuncio`, `comentario` | `mensaje_evento.tipo` |
| `confianza_campo` | `alta`, `media`, `baja`, `falta` | `extraccion_evento.campos.*.confianza` |
| `decision_moderacion` | `aprobar`, `rechazar`, `retirar` | `POST /moderacion/{id}/decision` |
| `tipo_lugar` | `ruta`, `sitio_interes`, `comercio`, `alojamiento`, `servicio` | `lugar.tipo` |
| `modalidad_ruta` | `senderismo`, `btt`, `ciclismo`, `paseo` | `lugar.ruta.modalidad` |
| `estado_envio` | `pendiente`, `enviada`, `fallida` | `notificacion.estado_envio` (cola de avisos) |

## Significado de los estados de evento

- `borrador`: creado a mano, sin enviar.
- `pendiente_confirmacion`: importado por la IA; faltan datos o la confirmación del publicador.
- `en_revision`: espera al moderador (nivel 0, spam alto o algo fuera de lo habitual). La bandeja muestra el `motivo`.
- `publicado`: visible en agenda, mapa, app, web y bot. **Solo estos salen en `GET /eventos` público.**
- `rechazado`, `cancelado`, `finalizado`, `archivado`: no visibles en la agenda.

## Niveles de confianza del publicador

- `0`: todo va a revisión.
- `1`: pasa si es «lo habitual» (misma categoría que publicaciones ya aprobadas y `score_spam` bajo).
- `2`: pasa todo salvo spam alto.
- Sube de nivel automáticamente tras `MODERACION_APROBACIONES_SUBIR_NIVEL` aprobaciones.

## Municipios (fixture `municipios.json`)

Lucainena de las Torres, Senés, Velefique, Uleila del Campo, Tahal. El nombre se escribe tal cual (con tilde en «Senés»).
