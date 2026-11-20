"""Lo que el bot contesta: texto y, opcionalmente, botones o peticiones del canal
(compartir número o ubicación en Telegram)."""

from dataclasses import dataclass

Boton = tuple[str, str]  # (id que vuelve al pulsarlo, texto visible)


@dataclass
class Respuesta:
    texto: str
    botones: list[Boton] | None = None
    pedir_contacto: bool = False
    pedir_ubicacion: bool = False
    quitar_teclado: bool = False
