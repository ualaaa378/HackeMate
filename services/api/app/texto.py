"""Normalización de textos para comparar lo que escribe la IA o la gente con lo que hay en la base."""

import re
import unicodedata


def plegar(texto: str) -> str:
    """Sin tildes ni mayúsculas: la IA puede escribir «Senes» o «SENÉS»."""
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)).casefold().strip()


def normalizar(texto: str) -> str:
    """Plegado y además sin signos ni espacios repetidos («II Ruta, Solidaria!» -> «ii ruta solidaria»)."""
    return " ".join(re.sub(r"[^\w]+", " ", plegar(texto)).replace("_", " ").split())
