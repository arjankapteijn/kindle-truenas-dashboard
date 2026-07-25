"""Minimale HTTP-server die de laatst gerenderde PNG serveert.

De Kindle *haalt* de afbeelding op (pull, elke 5 minuten via een KUAL-
scriptlet) i.p.v. dat deze container 'm ergens naartoe stuurt — vandaar dit
kleine endpoint in plaats van lovebox's push-naar-API aanpak.
"""

from __future__ import annotations

import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HEARTBEAT_MAX_AGE_SECONDS = 150


def make_handler(data_dir: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format_: str, *args: object) -> None:
            pass  # stil: een poll elke 5 min hoeft niet gelogd te worden

        def do_GET(self) -> None:  # noqa: N802 — verplichte naam vanuit BaseHTTPRequestHandler
            if self.path in ("/", "/dashboard.png"):
                self._serve_png()
            elif self.path == "/healthz":
                self._serve_health()
            else:
                self.send_error(404)

        def _serve_png(self) -> None:
            path = os.path.join(data_dir, "dashboard.png")
            try:
                with open(path, "rb") as f:
                    data = f.read()
            except OSError:
                self.send_error(503, "Nog geen dashboard gerenderd")
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _serve_health(self) -> None:
            heartbeat = os.path.join(data_dir, "heartbeat")
            try:
                age = time.time() - os.path.getmtime(heartbeat)
            except OSError:
                age = None
            healthy = age is not None and age < HEARTBEAT_MAX_AGE_SECONDS
            self.send_response(200 if healthy else 503)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok" if healthy else b"stale")

    return Handler


def serve_forever(data_dir: str, host: str, port: int) -> None:
    handler = make_handler(data_dir)
    httpd = ThreadingHTTPServer((host, port), handler)
    httpd.serve_forever()
