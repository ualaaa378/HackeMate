"""Carga los datos de la demo (5 pueblos, lugares, publicadores, usuarios y eventos futuros).

    python scripts/seed.py            # crea/actualiza tablas y carga (se puede repetir)
    python scripts/seed.py --reset    # vacía la base antes de cargar (estado inicial de la demo)

Usa DATABASE_URL del .env de la raíz. En Docker: docker compose -f infra/docker-compose.yml exec api python -m app.seed
La lógica vive en services/api/app/seed.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api"))

from app.seed import main  # noqa: E402

if __name__ == "__main__":
    main()
