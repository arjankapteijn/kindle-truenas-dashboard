"""Entrypoint: haalt TrueNAS-status op, rendert de dashboard-PNG en dient
'm aan voor de Kindle.

Twee modi:
  * scheduler + server (standaard): container blijft draaien, ververst
    periodiek en serveert de laatste PNG over HTTP zodat de Kindle 'm kan
    ophalen.
  * eenmalig (KD_RUN_ONCE=true): één keer renderen en stoppen — handig om
    lokaal te testen zonder de hele container-loop.
"""

from __future__ import annotations

import os
import sys
import threading

from .config import Config, is_configured, load_config
from .render import create_image
from .scheduler import run_forever
from .server import serve_forever
from .truenas_client import TrueNasError, fetch_snapshot


def build_dashboard(config: Config) -> bool:
    """Eén ronde: ophalen, renderen, schrijven. Geeft True bij succes.

    Zowel een mislukte fetch als een mislukte render/schrijf-stap loggen en
    geven False terug in plaats van te crashen — de bestaande (oudere) PNG
    blijft dan gewoon staan tot het weer lukt. Zo gedraagt deze functie zich
    identiek in scheduler-modus (waar `scheduler._safe_run` toch al elke
    Exception opvangt) en in KD_RUN_ONCE-modus (waar er geen vangnet omheen
    zit) — de aanroeper bepaalt zelf wat een `False` betekent: doorlopen
    (scheduler) of stoppen met een foutcode (`main()` bij RUN_ONCE).
    """
    print(f"[dashboard] TrueNAS-snapshot ophalen van {config.truenas_url}...", flush=True)
    try:
        snapshot = fetch_snapshot(
            config.truenas_url, config.truenas_api_key, verify_ssl=config.truenas_verify_ssl
        )
    except TrueNasError as exc:
        print(f"  ! Ophalen mislukt: {exc}. Dashboard wordt niet ververst.", flush=True)
        return False

    try:
        png_bytes = create_image(snapshot, timezone=config.timezone, max_alerts=config.max_alerts)
        os.makedirs(config.data_dir, exist_ok=True)
        out_path = os.path.join(config.data_dir, "dashboard.png")
        tmp_path = out_path + ".tmp"
        with open(tmp_path, "wb") as f:
            f.write(png_bytes)
        os.replace(tmp_path, out_path)  # atomisch: de Kindle ziet nooit een half geschreven bestand
    except Exception as exc:  # noqa: BLE001 -- render/schrijf-fouten mogen de oude PNG niet wissen
        print(f"  ! Renderen/schrijven mislukt: {exc!r}. Dashboard niet ververst.", flush=True)
        return False

    print(f"  -> {out_path} ({len(png_bytes) / 1024:.1f} kB)", flush=True)
    return True


def main() -> int:
    config = load_config()
    if not is_configured(config):
        print(
            "! Ontbrekende configuratie. Zet KD_TRUENAS_URL en KD_TRUENAS_API_KEY "
            "(zie README / .env.example).",
            file=sys.stderr,
        )
        return 1

    if config.run_once:
        return 0 if build_dashboard(config) else 1

    scheduler_thread = threading.Thread(
        target=run_forever,
        kwargs={
            "job": lambda: build_dashboard(config),
            "interval_seconds": config.poll_interval_seconds,
            "data_dir": config.data_dir,
            "run_on_start": config.run_on_start,
        },
        daemon=True,
    )
    scheduler_thread.start()

    print(
        f"HTTP-server actief op {config.http_host}:{config.http_port} "
        f"(ververst elke {config.poll_interval_seconds}s)",
        flush=True,
    )
    serve_forever(config.data_dir, config.http_host, config.http_port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
