"""Datos de solo lectura sacados de contracts/fixtures.

Provisional: sirve a la app web hasta que existan los modelos SQLAlchemy y el seed.
Cuando lleguen, las rutas cambian estas funciones por consultas a la base de datos.
"""

import json
from functools import lru_cache
from pathlib import Path

from app.config import get_settings


def _directorio() -> Path:
    configurado = get_settings().fixtures_dir
    if configurado:
        return Path(configurado)
    # Monorepo: services/api/app/fixtures.py -> raíz/contracts/fixtures
    return Path(__file__).resolve().parents[3] / "contracts" / "fixtures"


@lru_cache
def cargar(nombre: str) -> list[dict]:
    with open(_directorio() / f"{nombre}.json", encoding="utf-8") as f:
        return json.load(f)


def municipios() -> list[dict]:
    return cargar("municipios")


def eventos() -> list[dict]:
    return cargar("eventos")


def lugares() -> list[dict]:
    return cargar("lugares")
