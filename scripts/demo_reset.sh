#!/usr/bin/env bash
# Deja la base de datos en el estado inicial de la demo (vacía y vuelve a sembrar). Tarda pocos segundos.
#
#   scripts/demo_reset.sh            # Docker: dentro del contenedor api (el compose debe estar levantado)
#   scripts/demo_reset.sh --local    # sin Docker: python scripts/seed.py --reset con el DATABASE_URL del entorno/.env
#
# OJO: --reset borra TODO lo creado durante el ensayo (eventos, inscripciones, mensajes, usuarios nuevos).
# No hace falta reiniciar la api: lee la base en cada petición.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

modo="docker"
case "${1:-}" in
  --local) modo="local" ;;
  "") ;;
  -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
  *) echo "Opción desconocida: $1 (usa --local o nada)" >&2; exit 2 ;;
esac

inicio=$(date +%s)
if [ "$modo" = "docker" ]; then
  echo "==> Reiniciando la demo en el contenedor api (docker compose)…"
  docker compose -f infra/docker-compose.yml exec -T api python -m app.seed --reset
else
  # python3 en Linux/macOS; python en Windows (Git Bash). Se comprueba que funcione de verdad
  # (en Windows "python3" puede ser el acceso directo de la Microsoft Store).
  PY=""
  for candidato in python3 python; do
    if command -v "$candidato" >/dev/null 2>&1 && "$candidato" -c "import sys" >/dev/null 2>&1; then
      PY="$candidato"; break
    fi
  done
  if [ -z "$PY" ]; then
    echo "ERROR: no encuentro python3 ni python" >&2
    exit 1
  fi
  echo "==> Reiniciando la demo en local ($PY scripts/seed.py --reset)…"
  "$PY" scripts/seed.py --reset
fi
fin=$(date +%s)
echo "==> Demo reiniciada en $((fin - inicio)) s"
