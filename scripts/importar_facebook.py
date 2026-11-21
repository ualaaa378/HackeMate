"""Ingesta de Facebook (A2): posts de las páginas de los pueblos → IA del bot → API → bandeja del moderador.

    python scripts/importar_facebook.py                          # páginas de las fuentes de la API + FB_PAGINAS
    python scripts/importar_facebook.py --pagina https://www.facebook.com/AytoUleila
    python scripts/importar_facebook.py --desde-json             # repite con los posts guardados (sin red ni créditos)
    python scripts/importar_facebook.py --solo-descargar         # solo guarda los posts, no importa nada
    python scripts/importar_facebook.py --sin-confirmar          # deja los eventos en pendiente_confirmacion

Recorrido de cada post:
1. «Facebook Posts Scraper» (actor de Apify) devuelve los posts públicos de cada página. Se guardan en
   contracts/fixtures/facebook_posts.json solo con lo necesario (url, página, fecha, texto y el texto que
   Facebook lee en las fotos); nada de comentarios, reacciones ni datos de quien comenta.
2. `bot POST /ai/extraer` (la IA de Francisco) decide si es un plan y saca la ficha. El script no habla con
   ninguna IA: si el bot no responde, el post se queda guardado y no se inventa nada.
3. `api POST /eventos/importar` con origen facebook, la URL del post e importado_auto. La API asocia la
   asociación (por la fuente o por publicador_id), detecta duplicados por la URL y valida cada campo.
4. `api POST /eventos/{id}/confirmar`: la API decide el estado (asociación «a mano» → bandeja del moderador).
   Si faltan datos obligatorios (p. ej. la fecha), se queda en pendiente_confirmacion y se informa.

Configuración (entorno o .env de la raíz; las claves nunca en *.example):
  FB_SCRAPER_TOKEN   token de Apify. Sin él solo funciona --desde-json.
  FB_SCRAPER_ACTOR   actor (por defecto apify~facebook-posts-scraper).
  FB_PAGINAS         URLs de páginas separadas por comas (además de las fuentes de la API).
  FB_MAX_POSTS       posts por página (por defecto 10).  FB_DESDE  antigüedad máxima (por defecto «30 days»).
  API_URL, BOT_URL, INTERNAL_TOKEN  como el resto del proyecto (los nombres de Docker se cambian por localhost).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
JSON_POSTS = RAIZ / "contracts" / "fixtures" / "facebook_posts.json"
APIFY_URL = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
# run-sync de Apify corta a los 300 s; se espera un poco más para leer su respuesta de error
TIMEOUT_APIFY_S = 320
TIMEOUT_IA_S = 90
TIMEOUT_API_S = 30


# ---------- configuración ----------

def leer_env(ruta: Path = RAIZ / ".env") -> dict[str, str]:
    """Variables del .env de la raíz; las del entorno mandan sobre ellas."""
    valores: dict[str, str] = {}
    if ruta.is_file():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            valores[clave.strip()] = valor.strip().strip('"').strip("'")
    valores.update({k: v for k, v in os.environ.items() if v})
    return valores


def url_local(url: str | None, por_defecto: str) -> str:
    """Fuera de Docker, http://api:8000 y http://bot:8001 no existen: se usan en localhost."""
    if not url:
        return por_defecto
    partes = urllib.parse.urlsplit(url)
    if partes.hostname in ("api", "bot"):
        partes = partes._replace(netloc=f"localhost:{partes.port}" if partes.port else "localhost")
    return urllib.parse.urlunsplit(partes).rstrip("/")


# ---------- HTTP ----------

class ErrorHttp(Exception):
    def __init__(self, estado: int | None, cuerpo: Any, mensaje: str = ""):
        super().__init__(mensaje or f"HTTP {estado}")
        self.estado = estado
        self.cuerpo = cuerpo


def peticion(metodo: str, url: str, cuerpo: Any = None, cabeceras: dict[str, str] | None = None,
             timeout: float = TIMEOUT_API_S) -> tuple[int, Any]:
    datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    req = urllib.request.Request(url, data=datos, method=metodo,
                                 headers={"Content-Type": "application/json", **(cabeceras or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            texto = resp.read().decode("utf-8")
            return resp.status, json.loads(texto) if texto else None
    except urllib.error.HTTPError as e:
        texto = e.read().decode("utf-8", errors="replace")
        try:
            detalle = json.loads(texto)
        except ValueError:
            detalle = texto
        raise ErrorHttp(e.code, detalle) from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ErrorHttp(None, None, f"sin respuesta ({e})") from None


# ---------- 1. páginas y posts ----------

def paginas_de_la_api(api_url: str, token: str) -> list[dict[str, str]]:
    """Fuentes de Facebook activas de los publicadores aprobados: [{url, publicador_id, publicador}]."""
    _, datos = peticion("GET", f"{api_url}/api/v1/publicadores?size=100", cabeceras={"X-Internal-Token": token})
    paginas = []
    for p in datos.get("items", []):
        if p.get("estado") != "aprobado":
            continue
        for f in p.get("fuentes") or []:
            if f.get("canal") == "facebook" and f.get("activa", True):
                paginas.append({"url": f["url"].rstrip("/"), "publicador_id": p["id"], "publicador": p["nombre"]})
    return paginas


def unir_paginas(de_api: list[dict[str, str]], extra: list[str]) -> list[dict[str, str]]:
    """Sin repetir URLs; las de la API (con su asociación) mandan sobre las sueltas."""
    vistas = {p["url"] for p in de_api}
    unidas = list(de_api)
    for url in extra:
        url = url.strip().rstrip("/")
        if url and url not in vistas:
            unidas.append({"url": url, "publicador_id": None, "publicador": None})
            vistas.add(url)
    return unidas


def descargar_posts(paginas: list[dict[str, str]], token: str, actor: str, max_posts: int, desde: str) -> list[dict]:
    entrada = {
        "startUrls": [{"url": p["url"]} for p in paginas],
        "resultsLimit": max_posts,
        "captionText": False,
        "onlyPostsNewerThan": desde,
    }
    _, items = peticion("POST", APIFY_URL.format(actor=actor), entrada,
                        {"Authorization": f"Bearer {token}"}, timeout=TIMEOUT_APIFY_S)
    return items or []


def resumir_post(item: dict, paginas: list[dict[str, str]]) -> dict | None:
    """Solo lo necesario de cada post de Apify. None si no tiene URL ni texto (no sirve para nada)."""
    url = item.get("url") or item.get("topLevelUrl")
    textos_fotos = [m.get("ocrText") for m in item.get("media") or [] if isinstance(m, dict) and m.get("ocrText")]
    texto = (item.get("text") or "").strip()
    if not url or not (texto or textos_fotos):
        return None
    entrada = (item.get("inputUrl") or item.get("facebookUrl") or "").rstrip("/")
    pagina = next((p for p in paginas if p["url"] == entrada), None) or next(
        (p for p in paginas if url.startswith(p["url"] + "/")), None
    )
    return {
        "url": url,
        "pagina_url": entrada or (pagina["url"] if pagina else None),
        "pagina": item.get("pageName") or (item.get("user") or {}).get("name"),
        "publicador_id": pagina["publicador_id"] if pagina else None,
        "fecha": item.get("time"),
        "texto": texto,
        "texto_fotos": textos_fotos,
    }


def guardar_posts(posts: list[dict], paginas: list[dict[str, str]], ruta: Path = JSON_POSTS) -> None:
    """Junta con lo ya guardado (por URL) para que --desde-json repita también descargas anteriores."""
    anteriores = {p["url"]: p for p in cargar_posts(ruta)} if ruta.is_file() else {}
    anteriores.update({p["url"]: p for p in posts})
    contenido = {
        "descripcion": "Posts públicos de Facebook de las páginas de los pueblos, descargados con "
                       "scripts/importar_facebook.py (Facebook Posts Scraper). Solo url, página, fecha, texto y "
                       "texto de las fotos. Se reimportan sin red con --desde-json.",
        "actualizado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "paginas": sorted({p["url"] for p in paginas} | {p.get("pagina_url") for p in anteriores.values()} - {None}),
        "posts": sorted(anteriores.values(), key=lambda p: p.get("fecha") or "", reverse=True),
    }
    ruta.write_text(json.dumps(contenido, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cargar_posts(ruta: Path = JSON_POSTS) -> list[dict]:
    return json.loads(ruta.read_text(encoding="utf-8")).get("posts", [])


# ---------- 2-4. IA del bot, importar y confirmar ----------

def texto_para_ia(post: dict) -> str:
    """El texto del post y el de sus fotos (carteles). La fecha de publicación va al final para que la IA
    entienda «este sábado» sin estropear el título que las reglas sacan de la primera línea."""
    partes = [post.get("texto") or ""]
    if post.get("texto_fotos"):
        partes.append("Texto del cartel: " + " · ".join(post["texto_fotos"]))
    pie = []
    if post.get("pagina"):
        pie.append(f"por {post['pagina']}")
    if post.get("fecha"):
        pie.append(f"el {post['fecha'][:10]}")
    if pie:
        partes.append("(Publicado en Facebook " + " ".join(pie) + ")")
    return "\n\n".join(p for p in partes if p).strip()


def procesar_post(post: dict, api_url: str, bot_url: str, token: str, confirmar: bool) -> dict:
    """Devuelve {resultado, ...}: creado, publicado, en_revision, pendiente, duplicado, no_es_evento o error."""
    cabeceras = {"X-Internal-Token": token}
    try:
        _, extraccion = peticion("POST", f"{bot_url}/ai/extraer", {"texto": texto_para_ia(post)}, cabeceras,
                                 timeout=TIMEOUT_IA_S)
    except ErrorHttp as e:
        return {"resultado": "error", "paso": "bot /ai/extraer", "detalle": str(e) if e.estado is None else e.cuerpo}
    if not extraccion or not extraccion.get("es_evento"):
        return {"resultado": "no_es_evento", "proveedor_ia": (extraccion or {}).get("proveedor_ia")}

    cuerpo = {
        "extraccion": extraccion,
        "origen": {"canal": "facebook", "url": post["url"], "importado_auto": True},
    }
    if post.get("publicador_id"):
        cuerpo["publicador_id"] = post["publicador_id"]
    try:
        estado, importado = peticion("POST", f"{api_url}/api/v1/eventos/importar", cuerpo, cabeceras)
    except ErrorHttp as e:
        return {"resultado": "error", "paso": "api importar", "detalle": e.cuerpo if e.estado else str(e)}
    evento = importado["evento"]
    base = {"evento_id": evento["id"], "titulo": evento["titulo"], "proveedor_ia": extraccion.get("proveedor_ia")}
    if estado == 200 and importado.get("duplicado"):
        return {"resultado": "duplicado", "estado": evento["estado"], **base}
    if not confirmar:
        return {"resultado": "creado", "estado": evento["estado"], "faltan": importado.get("faltan", []), **base}

    try:
        _, confirmado = peticion("POST", f"{api_url}/api/v1/eventos/{evento['id']}/confirmar", {"campos": {}},
                                 cabeceras)
    except ErrorHttp as e:
        detalle = e.cuerpo.get("error", {}) if isinstance(e.cuerpo, dict) else {}
        if e.estado == 422 and detalle.get("code") == "faltan_campos":
            return {"resultado": "pendiente", "estado": "pendiente_confirmacion",
                    "faltan": (detalle.get("details") or {}).get("faltan", []), **base}
        return {"resultado": "error", "paso": "api confirmar", "detalle": e.cuerpo if e.estado else str(e), **base}
    final = confirmado["evento"]
    return {"resultado": final["estado"], "estado": final["estado"],
            "motivo": (final.get("moderacion") or {}).get("motivo"), **base}


# ---------- programa ----------

def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Importa planes desde las páginas de Facebook de los pueblos.")
    parser.add_argument("--pagina", action="append", default=[], help="URL de una página (se puede repetir)")
    parser.add_argument("--desde-json", action="store_true", help="usa los posts guardados, sin descargar")
    parser.add_argument("--solo-descargar", action="store_true", help="descarga y guarda, sin importar")
    parser.add_argument("--sin-confirmar", action="store_true", help="deja los eventos en pendiente_confirmacion")
    parser.add_argument("--json", type=Path, default=JSON_POSTS, help="fichero de posts (por defecto el fixture)")
    args = parser.parse_args(argv)

    env = leer_env()
    api_url = url_local(env.get("API_URL"), "http://localhost:8000")
    bot_url = url_local(env.get("BOT_URL"), "http://localhost:8001")
    token = env.get("INTERNAL_TOKEN", "cambia-esto")

    if args.desde_json:
        if not args.json.is_file():
            print(f"ERROR: no existe {args.json}. Descarga antes sin --desde-json.", file=sys.stderr)
            return 2
        posts = cargar_posts(args.json)
        print(f"==> {len(posts)} posts guardados en {args.json.name}")
    else:
        scraper_token = env.get("FB_SCRAPER_TOKEN")
        if not scraper_token:
            print("ERROR: falta FB_SCRAPER_TOKEN en el .env (o usa --desde-json).", file=sys.stderr)
            return 2
        try:
            de_api = paginas_de_la_api(api_url, token)
        except ErrorHttp as e:
            print(f"AVISO: no se pudieron leer las fuentes de la API ({e}); solo las páginas indicadas.")
            de_api = []
        extra = args.pagina + [u for u in env.get("FB_PAGINAS", "").split(",") if u.strip()]
        paginas = unir_paginas(de_api, extra)
        if not paginas:
            print("ERROR: no hay páginas. Da de alta fuentes de Facebook en la API, usa --pagina o FB_PAGINAS.",
                  file=sys.stderr)
            return 2
        print(f"==> Descargando de {len(paginas)} páginas con {env.get('FB_SCRAPER_ACTOR', 'apify~facebook-posts-scraper')}…")
        try:
            items = descargar_posts(paginas, scraper_token, env.get("FB_SCRAPER_ACTOR", "apify~facebook-posts-scraper"),
                                    int(env.get("FB_MAX_POSTS", "10")), env.get("FB_DESDE", "30 days"))
        except ErrorHttp as e:
            print(f"ERROR del scraper: {e} {e.cuerpo or ''}", file=sys.stderr)
            return 1
        posts = [p for p in (resumir_post(i, paginas) for i in items) if p]
        guardar_posts(posts, paginas, args.json)
        print(f"==> {len(items)} posts descargados, {len(posts)} con texto. Guardados en {args.json}")
        if args.solo_descargar:
            return 0

    resumen: dict[str, int] = {}
    errores = 0
    for post in posts:
        r = procesar_post(post, api_url, bot_url, token, confirmar=not args.sin_confirmar)
        resumen[r["resultado"]] = resumen.get(r["resultado"], 0) + 1
        errores += r["resultado"] == "error"
        titulo = r.get("titulo") or (post.get("texto") or "")[:60].replace("\n", " ")
        extra = r.get("motivo") or (", ".join(r["faltan"]) if r.get("faltan") else "") or r.get("paso") or ""
        print(f"  [{r['resultado']:>13}] {titulo}" + (f"  ({extra})" if extra else ""))
        if r["resultado"] == "error":
            print(f"                  {r.get('detalle')}")
    print("==> Resumen: " + ", ".join(f"{k} {v}" for k, v in sorted(resumen.items())) if resumen else "==> Nada que importar")
    return 1 if errores and errores == len(posts) else 0


if __name__ == "__main__":
    sys.exit(main())
