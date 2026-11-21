"""URL pública de la demo (tarea F1): lee la URL del túnel rápido de Cloudflare y deja todo apuntando a ella.

El túnel rápido (servicio `tunnel` del compose) da una URL https://<algo>.trycloudflare.com que CAMBIA cada vez
que se reinicia. Este script, en la máquina de la demo y desde la raíz del repo:

  1. lee la URL de `docker compose … logs tunnel` (espera a que el túnel la publique y responda);
  2. la escribe en el .env de la raíz como PUBLIC_URL (webhook de Telegram) y, si el túnel ya entra por la web
     (C8 y C8b: /api/ responde a través de la URL), también como WEB_URL (enlaces de las fichas que manda el bot);
  3. recrea el bot, que al arrancar registra solo el webhook en PUBLIC_URL/webhook/telegram;
  4. comprueba en Telegram que el webhook apunta a la URL nueva y la escribe en pantalla para el grupo y el APK.

Uso (con el compose ya en marcha):
    python scripts/url_publica.py            # lo hace todo
    python scripts/url_publica.py --ver      # solo enseña la URL actual del túnel, sin tocar nada
    python scripts/url_publica.py --forzar   # recrea el bot aunque la URL no haya cambiado

Solo biblioteca estándar. No escribe ninguna clave en pantalla.
"""

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ENV = RAIZ / ".env"
COMPOSE = ["docker", "compose", "--env-file", str(ENV), "-f", str(RAIZ / "infra" / "docker-compose.yml")]
PATRON_URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
BOT_LOCAL = "http://localhost:8001"


def leer_env() -> dict[str, str]:
    if not ENV.exists():
        sys.exit(f"ERROR: no existe {ENV}. Copia .env.example a .env y rellénalo.")
    valores = {}
    for linea in ENV.read_text(encoding="utf-8-sig").splitlines():
        if "=" in linea and not linea.lstrip().startswith("#"):
            clave, valor = linea.split("=", 1)
            valores[clave.strip()] = valor.strip()
    return valores


def escribir_env(cambios: dict[str, str]) -> None:
    """Cambia solo esas claves y conserva el resto del archivo (comentarios y orden). UTF-8 sin BOM."""
    lineas = ENV.read_text(encoding="utf-8-sig").splitlines()
    pendientes = dict(cambios)
    for i, linea in enumerate(lineas):
        clave = linea.split("=", 1)[0].strip()
        if "=" in linea and not linea.lstrip().startswith("#") and clave in pendientes:
            lineas[i] = f"{clave}={pendientes.pop(clave)}"
    lineas += [f"{clave}={valor}" for clave, valor in pendientes.items()]
    ENV.write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")


def peticion(url: str, metodo: str = "GET", datos: dict | None = None, cabeceras: dict | None = None,
             timeout: float = 10) -> tuple[int, str]:
    cuerpo = json.dumps(datos).encode() if datos is not None else None
    req = urllib.request.Request(url, data=cuerpo, method=metodo,
                                 headers={"Content-Type": "application/json", **(cabeceras or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, ""


def url_del_tunel() -> str | None:
    res = subprocess.run(COMPOSE + ["logs", "--no-color", "tunnel"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", cwd=RAIZ)
    if res.returncode != 0:
        sys.exit("ERROR: no puedo leer los logs del túnel. ¿Está el compose en marcha?\n"
                 "  docker compose --env-file .env -f infra/docker-compose.yml up -d")
    urls = PATRON_URL.findall(res.stdout + res.stderr)
    return urls[-1] if urls else None


def esperar_tunel(espera_s: int) -> str:
    """La URL sale en los logs antes de que su DNS funcione: se espera a que responda de verdad."""
    limite = time.monotonic() + espera_s
    url = None
    while time.monotonic() < limite:
        url = url_del_tunel() or url
        if url and peticion(f"{url}/health", timeout=5)[0] == 200:
            return url
        time.sleep(3)
    if url:
        sys.exit(f"ERROR: el túnel publicó {url}, pero no responde tras {espera_s} s. Mira "
                 "`docker compose --env-file .env -f infra/docker-compose.yml logs tunnel`.")
    sys.exit("ERROR: el túnel no ha publicado ninguna URL todavía. ¿Está el servicio `tunnel` en marcha?")


def entra_por_la_web(url: str) -> bool:
    """C8 y C8b hechos: el túnel llega al nginx de la web y este pasa /api/ a la API."""
    estado, cuerpo = peticion(f"{url}/api/v1/municipios")
    if estado != 200:
        return False
    try:
        return isinstance(json.loads(cuerpo), (list, dict))
    except ValueError:
        return False


def recrear_bot() -> None:
    print("· Recreando el bot para que lea el .env nuevo…")
    res = subprocess.run(COMPOSE + ["up", "-d", "--no-deps", "--force-recreate", "bot"], cwd=RAIZ,
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        sys.exit("ERROR al recrear el bot:\n" + res.stderr[-2000:])
    limite = time.monotonic() + 90
    while time.monotonic() < limite:
        if peticion(f"{BOT_LOCAL}/health", timeout=3)[0] == 200:
            return
        time.sleep(2)
    sys.exit("ERROR: el bot no responde en :8001 tras recrearlo. Mira `… logs bot`.")


def comprobar_webhook(url: str, env: dict[str, str]) -> bool:
    """Pregunta a Telegram adónde manda los mensajes. Si no es la URL nueva, se lo pide al bot otra vez."""
    token = env.get("TELEGRAM_TOKEN")
    if not token:
        print("· Sin TELEGRAM_TOKEN en el .env: no hay webhook que comprobar.")
        return True
    esperado = f"{url}/webhook/telegram"
    for intento in range(2):
        estado, cuerpo = peticion(f"https://api.telegram.org/bot{token}/getWebhookInfo")
        info = json.loads(cuerpo).get("result", {}) if estado == 200 else {}
        if info.get("url") == esperado:
            error = info.get("last_error_message")
            print(f"· Webhook de Telegram: OK ({esperado})" + (f" · último error: {error}" if error else ""))
            return True
        if intento == 0:  # el bot lo registra al arrancar; si no lo hizo, se lo pedimos
            peticion(f"{BOT_LOCAL}/admin/webhook-telegram", "POST", {"public_url": url},
                     {"X-Internal-Token": env.get("INTERNAL_TOKEN", "")}, timeout=30)
    print(f"· AVISO: Telegram no apunta a {esperado}. Revisa `… logs bot`.")
    return False


def main() -> None:
    p = argparse.ArgumentParser(description="Deja la demo apuntando a la URL actual del túnel rápido.")
    p.add_argument("--ver", action="store_true", help="solo enseña la URL del túnel, sin tocar nada")
    p.add_argument("--forzar", action="store_true", help="recrea el bot aunque la URL no haya cambiado")
    p.add_argument("--espera", type=int, default=90, help="segundos máximos esperando al túnel (90)")
    args = p.parse_args()

    print("· Buscando la URL del túnel…")
    url = esperar_tunel(args.espera)
    if args.ver:
        print(url)
        return

    env = leer_env()
    por_la_web = entra_por_la_web(url)
    cambios = {"PUBLIC_URL": url}
    if por_la_web:
        cambios["WEB_URL"] = url
    else:
        print("· El túnel todavía entra directo al bot (faltan C8 y C8b): WEB_URL no se toca y la web\n"
              "  solo funciona en este equipo.")

    cambia = any(env.get(k) != v for k, v in cambios.items())
    if cambia:
        escribir_env(cambios)
        print("· .env actualizado: " + ", ".join(cambios))
    else:
        print("· El .env ya tenía esta URL.")
    if cambia or args.forzar:
        recrear_bot()
    ok = comprobar_webhook(url, leer_env())

    print()
    print("=" * 64)
    print(f"  URL PÚBLICA:  {url}")
    if por_la_web:
        print(f"  Web:          {url}")
        print(f"  Panel:        {url}/admin")
        print(f"  API:          {url}/api/v1/eventos")
        print("  APK:          pega esta URL en Ajustes → Dirección del servidor")
    print(f"  Telegram:     {'OK' if ok else 'REVISAR'}")
    print("=" * 64)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
