# Puesta en común · sábado 21/11, 16:00 (15 min)

## 1. Dónde estamos (2 min)
- `develop` al día: hasta la #68, sin ramas ni PR pendientes. Tests: api 602, bot 149.
- Demo de punta a punta por la URL pública con Telegram e IA en dos máquinas (Francisco y Adán). Solo una a la vez con Telegram.
- Hecho hoy: URL pública (C8, C8b, A6, F1, F2), ingesta de Facebook (A2), NVIDIA NIM (B2), alta de asociaciones con DNI (B5), rediseño de agenda y ficha, datos que no se pierden al reiniciar.

## 2. Qué queda, por persona (1 frase cada uno: cómo va y si algo bloquea)
| Quién | Antes de CP3 (19:00) | Antes del freeze (00:00) | Entrega (07:00) |
|---|---|---|---|
| Adán (C) | C2 «Para ti» · refresco de ficha, chat y bandeja · B3 audios con Fran | C9 APK (plan B: C4 PWA) · C6 panel y accesibilidad | C7 vídeo, capturas, 2 ensayos, `v1.0` |
| Benas (A) | — | A4 % de Facebook en estadísticas | A5 arreglos de ensayos y README backend |
| Francisco (B) | B3 pasar config de FreeLLM a Adán y ensayar paso 7 | B5b `/ai/frase` solo si sobra (contrato antes de las 19:00) | B6 sección del bot y claves de la demo |
| Los tres | — | T1 prueba con móviles con datos · T2 reinicio en frío cronometrado | — |

## 3. Decisiones (5 min)
- **D1** (avisos a quien solo usa Telegram): sigue aplazada. Mientras, todos los inscritos comparten su número. ¿Se decide ya o se deja fuera de la demo?
- **D4** (nueva): lo importado de Facebook de los ayuntamientos ¿se publica solo o pasa siempre por la bandeja? Son dos líneas en la API.
- **D2** (código de acceso por Telegram): propuesta, recortar; la demo entra con `/auth/demo`.
- ¿`/ai/frase` (B5b) entra o se recorta? Si entra, el contrato tiene que estar antes de las 19:00.

## 4. Recordatorios
- Siempre `docker compose --env-file .env -f infra/docker-compose.yml …` y `python scripts/url_publica.py` tras cada `up`.
- En la demo, nunca `down -v` ni `demo_reset`.
- Red de la uni bloquea npm: datos del móvil para la imagen web y el APK.
- Todo el detalle: README § «Estado» y «Pendiente entre flujos».
