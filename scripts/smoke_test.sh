#!/usr/bin/env bash
# Smoke test de la API (solo HTTP). Comprueba las rutas que sostienen el guion de la demo.
#
#   scripts/smoke_test.sh
#   API_URL=http://localhost:8000 INTERNAL_TOKEN=... BOT_URL=http://localhost:8001 scripts/smoke_test.sh
#
# Variables: API_URL (por defecto http://localhost:8000), INTERNAL_TOKEN (si no está en el entorno se lee
# del .env de la raíz; por defecto "cambia-esto") y BOT_URL (opcional: si está, también se mira su /health).
# Necesita los datos de la demo cargados (scripts/demo_reset.sh). Sale con código 1 si algo falla.
set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_URL="${API_URL:-http://localhost:8000}"
API_URL="${API_URL%/}"
if [ -z "${INTERNAL_TOKEN:-}" ] && [ -f "$RAIZ/.env" ]; then
  INTERNAL_TOKEN="$(grep -E '^INTERNAL_TOKEN=' "$RAIZ/.env" | tail -1 | cut -d= -f2- | tr -d '\r"')"
fi
INTERNAL_TOKEN="${INTERNAL_TOKEN:-cambia-esto}"
BOT_URL="${BOT_URL:-}"

RUTA_SOLIDARIA="1e5d0000-0000-4000-8000-000000000001"
CARMEN="5a5e0000-0000-4000-8000-000000000001"

# Python solo para leer JSON (python3 en Linux; python en Git Bash, donde python3 puede ser el acceso de la Store)
PY=""
for candidato in python3 python; do
  if command -v "$candidato" >/dev/null 2>&1 && "$candidato" -c "import json" >/dev/null 2>&1; then
    PY="$candidato"; break
  fi
done
if [ -z "$PY" ]; then
  echo "ERROR: hace falta python3 (o python) para leer las respuestas JSON" >&2
  exit 2
fi

fallos=0
CUERPO="$(mktemp)"
ERRORES="$(mktemp)"
trap 'rm -f "$CUERPO" "$ERRORES"' EXIT

ok()    { printf '  [OK]    %s\n' "$1"; }
fallo() { printf '  [FALLO] %s\n' "$1"; fallos=$((fallos + 1)); }

# pedir URL [cabecera...] -> deja el cuerpo en $CUERPO y el código HTTP en $CODIGO y el Content-Type en $TIPO
pedir() {
  local url="$1"; shift
  local salida
  salida="$(curl -sS --max-time 15 -o "$CUERPO" -w '%{http_code} %{content_type}' "$@" "$url" 2>"$ERRORES")" || {
    CODIGO="000"; TIPO=""; cat "$ERRORES" > "$CUERPO"; return
  }
  CODIGO="${salida%% *}"
  TIPO="${salida#* }"
}

# json EXPRESION -> evalúa la expresión Python sobre d (el JSON de $CUERPO); vacío si no se puede leer
json() {
  "$PY" -c "import json,sys
try:
    d = json.load(open(sys.argv[1], encoding='utf-8'))
    print($1)
except Exception as e:
    print('')" "$CUERPO" 2>/dev/null | tr -d '\r'
}

INT=(-H "X-Internal-Token: $INTERNAL_TOKEN")

echo "Smoke test contra $API_URL"

# 1. /health
pedir "$API_URL/health"
if [ "$CODIGO" = "200" ] && [ "$(json "d.get('status')")" = "ok" ]; then
  ok "GET /health → ok (versión $(json "d.get('version')"))"
else
  fallo "GET /health → HTTP $CODIGO $(head -c 200 "$CUERPO")"
fi

# 2. Agenda
pedir "$API_URL/api/v1/eventos"
total="$(json "d.get('total', len(d.get('items', [])))")"
if [ "$CODIGO" = "200" ] && [ "${total:-0}" -gt 0 ] 2>/dev/null; then
  ok "GET /api/v1/eventos → $total eventos"
else
  fallo "GET /api/v1/eventos → HTTP $CODIGO, total='${total}' (¿falta sembrar? scripts/demo_reset.sh)"
fi

# 3. Ficha de la Ruta Solidaria
pedir "$API_URL/api/v1/eventos/$RUTA_SOLIDARIA"
if [ "$CODIGO" = "200" ] && [ "$(json "d.get('id')")" = "$RUTA_SOLIDARIA" ]; then
  ok "GET /api/v1/eventos/{ruta} → $(json "d.get('titulo')") [$(json "d.get('estado')")]"
else
  fallo "GET /api/v1/eventos/$RUTA_SOLIDARIA → HTTP $CODIGO $(head -c 200 "$CUERPO")"
fi

# 4. Municipios
pedir "$API_URL/api/v1/municipios"
n="$(json "len(d['items'] if isinstance(d, dict) else d)")"
if [ "$CODIGO" = "200" ] && [ "${n:-0}" -ge 5 ] 2>/dev/null; then
  ok "GET /api/v1/municipios → $n pueblos"
else
  fallo "GET /api/v1/municipios → HTTP $CODIGO, pueblos='${n}' (se esperaban 5)"
fi

# 5. Bandeja de moderación con token interno
pedir "$API_URL/api/v1/moderacion/pendientes" "${INT[@]}"
if [ "$CODIGO" = "200" ]; then
  ok "GET /api/v1/moderacion/pendientes (X-Internal-Token) → $(json "d.get('total')") pendientes"
else
  fallo "GET /api/v1/moderacion/pendientes → HTTP $CODIGO (¿INTERNAL_TOKEN distinto del de la api?) $(head -c 200 "$CUERPO")"
fi

# 6. Recomendaciones de Carmen: la Ruta Solidaria primera
pedir "$API_URL/api/v1/recomendaciones?usuario_id=$CARMEN" "${INT[@]}"
primera="$(json "d['items'][0]['evento']['id']")"
if [ "$CODIGO" = "200" ] && [ "$primera" = "$RUTA_SOLIDARIA" ]; then
  ok "GET /api/v1/recomendaciones (Carmen) → Ruta Solidaria primera: $(json "d['items'][0]['motivo']")"
else
  fallo "GET /api/v1/recomendaciones (Carmen) → HTTP $CODIGO, primera='${primera}' (se esperaba la Ruta Solidaria)"
fi

# 7. Calendario .ics
pedir "$API_URL/api/v1/eventos/$RUTA_SOLIDARIA/ics"
if [ "$CODIGO" = "200" ] && [[ "$TIPO" == text/calendar* ]] && grep -q "BEGIN:VCALENDAR" "$CUERPO"; then
  ok "GET /api/v1/eventos/{ruta}/ics → $TIPO"
else
  fallo "GET /api/v1/eventos/$RUTA_SOLIDARIA/ics → HTTP $CODIGO, Content-Type '$TIPO'"
fi

# 8. (Opcional) /health del bot
if [ -n "$BOT_URL" ]; then
  BOT_URL="${BOT_URL%/}"
  pedir "$BOT_URL/health"
  if [ "$CODIGO" = "200" ] && [ "$(json "d.get('status')")" = "ok" ]; then
    ok "GET $BOT_URL/health → ok"
  else
    fallo "GET $BOT_URL/health → HTTP $CODIGO $(head -c 200 "$CUERPO")"
  fi
else
  echo "  [--]    BOT_URL sin definir: no se comprueba el bot"
fi

echo
if [ "$fallos" -eq 0 ]; then
  echo "SMOKE TEST EN VERDE"
  exit 0
fi
echo "SMOKE TEST EN ROJO: $fallos comprobaciones fallidas"
exit 1
