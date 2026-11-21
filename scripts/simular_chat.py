"""Simula el guion de la demo por el chat sin Telegram ni WhatsApp (bot con CANAL=console).

    python scripts/simular_chat.py                    # guion de la demo
    python scripts/simular_chat.py +34600000201 "¿Qué hay este finde?"   # un solo mensaje

Necesita la api (8000) y el bot (8001) levantados y la demo sembrada (scripts/demo_reset.sh --local).
Usa `POST bot /dev/mensaje`, que devuelve las respuestas en vez de enviarlas. BOT_URL cambia la dirección del bot.
"""

import json
import os
import sys
import urllib.error
import urllib.request

BOT_URL = os.environ.get("BOT_URL", "http://localhost:8001").rstrip("/")

PUBLICADOR = "+34600000101"
CARMEN = "+34600000201"

GUION = [
    ("Publicador manda el post", PUBLICADOR,
     "Taller de esparto en Senés el sábado 28 de noviembre a las 11:00 en la plaza. Gratis, 15 plazas."),
    ("Publicador confirma", PUBLICADOR, "sí"),
    ("Carmen pide planes", CARMEN, "¿Qué planes hay este finde?"),
    ("Carmen pregunta por la ficha", CARMEN, "¿Hay que llevar agua a la ruta solidaria?"),
]


def enviar(de: str, texto: str) -> list[str]:
    peticion = urllib.request.Request(
        BOT_URL + "/dev/mensaje",
        json.dumps({"de": de, "texto": texto}).encode("utf-8"),
        {"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(peticion, timeout=60) as respuesta:
        return json.load(respuesta).get("respuestas", [])


def mostrar(titulo: str, de: str, texto: str) -> None:
    print(f"\n── {titulo}\n{de} > {texto}")
    for linea in enviar(de, texto):
        print("   bot > " + linea.replace("\n", "\n         "))


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        if len(sys.argv) == 3:
            mostrar("Mensaje suelto", sys.argv[1], sys.argv[2])
        else:
            for titulo, de, texto in GUION:
                mostrar(titulo, de, texto)
    except urllib.error.URLError as e:
        print(f"ERROR: el bot no responde en {BOT_URL} ({e})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
