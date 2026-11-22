"""Chat por terminal para probar el bot sin WhatsApp:  python -m app.consola"""

from app import conversacion
from app.schemas import MensajeEntrante


def main() -> None:
    telefono = "+34600000000"
    print("Simulador de WhatsApp. Escribe un mensaje (Ctrl+C para salir).")
    while True:
        try:
            texto = input("\n[tú] ")
        except (EOFError, KeyboardInterrupt):
            break
        if texto.strip():
            conversacion.procesar(MensajeEntrante(canal="console", de=telefono, texto=texto))


if __name__ == "__main__":
    main()
