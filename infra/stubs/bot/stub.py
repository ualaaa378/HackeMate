"""Stub mínimo del bot: /health y /notify (solo lo imprime). Sin dependencias."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def _json(self, codigo, cuerpo):
        datos = json.dumps(cuerpo).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def do_GET(self):
        if self.path == "/health":
            return self._json(200, {"status": "ok", "version": "0.0.0-stub"})
        self._json(404, {"error": {"code": "no_encontrado", "message": "Stub del bot", "details": {}}})

    def do_POST(self):
        cuerpo = self.rfile.read(int(self.headers.get("Content-Length", 0) or 0))
        if self.path == "/notify":
            print("[notify]", cuerpo.decode(errors="replace"))
            return self._json(200, {"enviado": True})
        self._json(501, {"error": {"code": "no_implementado", "message": "Stub del bot", "details": {}}})


ThreadingHTTPServer(("0.0.0.0", 8001), Handler).serve_forever()
