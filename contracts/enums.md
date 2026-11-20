# Enums compartidos (v1)

Valores permitidos en JSON. Minúsculas, sin tildes, con guion bajo. **Solo se añaden valores, nunca se renombran ni se borran** (PLAN §5.3).

| Enum | Valores |
|---|---|
| `rol` | `vecino`, `publicador`, `moderador` |
| `categoria` | `deportiva`, `cultural`, `fiestas`, `gastronomia`, `ludica`, `comercio` |
| `estado_evento` | `borrador`, `pendiente_confirmacion`, `en_revision`, `publicado`, `rechazado`, `cancelado`, `finalizado`, `archivado` |
| `estado_publicador` | `solicitado`, `whatsapp_verificado`, `aprobado`, `rechazado`, `pausado` |
| `nivel_confianza` | `0` (todo a revisión), `1` (lo habitual pasa), `2` (casi todo pasa) |
| `estado_inscripcion` | `confirmada`, `lista_espera`, `cancelada`, `asistio`, `no_asistio` |
| `canal` | `whatsapp`, `web`, `panel`, `facebook`, `instagram`, `web_externa`, `manual` |
| `tipo_notificacion` | `recomendacion`, `cambio_evento`, `anuncio`, `respuesta`, `moderacion`, `confirmacion`, `codigo_verificacion` |
| `formato_aviso` | `texto`, `audio` |
| `confianza_campo` | `alta`, `media`, `baja`, `falta` |
| `decision_moderacion` | `aprobar`, `rechazar` |
| `tipo_mensaje_evento` | `pregunta`, `respuesta`, `anuncio` |
| `autor_mensaje` | `vecino`, `organizador`, `moderador`, `asistente_ia` |
| `tipo_fuente` | `facebook`, `instagram`, `web_externa`, `calendario` |

## Ciclo de vida de un evento

```
(importado por IA) ──▶ pendiente_confirmacion ──(publicador confirma)──▶ ┐
(creado a mano) ───────────────────────────────────────────────────────▶ ├─▶ antispam/nivel de confianza
                                                                         │      ├─ pasa ──▶ publicado
                                                                         │      └─ dudoso ─▶ en_revision ──(moderador)──▶ publicado | rechazado
publicado ──(organizador)──▶ cancelado
publicado ──(fecha_fin pasada)──▶ finalizado ──(+7 días)──▶ archivado
```

Solo `api` cambia estados. La IA solo propone (`moderacion.motivo`, `score_spam`).
