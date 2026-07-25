import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer

from kindle_dashboard.server import make_handler


def _start_server(data_dir):
    handler = make_handler(str(data_dir))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def test_serves_dashboard_png(tmp_path):
    (tmp_path / "dashboard.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    httpd = _start_server(tmp_path)
    try:
        port = httpd.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/dashboard.png") as resp:
            assert resp.status == 200
            assert resp.headers["Content-Type"] == "image/png"
            assert resp.read() == b"\x89PNG\r\n\x1a\nfake"
    finally:
        httpd.shutdown()


def test_returns_503_when_no_png_yet(tmp_path):
    httpd = _start_server(tmp_path)
    try:
        port = httpd.server_address[1]
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/dashboard.png")
            raise AssertionError("expected HTTPError")
        except urllib.error.HTTPError as exc:
            assert exc.code == 503
    finally:
        httpd.shutdown()


def test_healthz_ok_when_heartbeat_fresh(tmp_path):
    (tmp_path / "heartbeat").write_text("now")
    httpd = _start_server(tmp_path)
    try:
        port = httpd.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz") as resp:
            assert resp.status == 200
    finally:
        httpd.shutdown()


def test_healthz_fails_when_heartbeat_stale(tmp_path):
    heartbeat = tmp_path / "heartbeat"
    heartbeat.write_text("old")
    old_time = time.time() - 3600
    import os

    os.utime(heartbeat, (old_time, old_time))
    httpd = _start_server(tmp_path)
    try:
        port = httpd.server_address[1]
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz")
            raise AssertionError("expected HTTPError")
        except urllib.error.HTTPError as exc:
            assert exc.code == 503
    finally:
        httpd.shutdown()
