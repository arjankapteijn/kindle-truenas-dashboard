"""Self-scheduling loop: ververst de dashboard-PNG periodiek.

Anders dan lovebox (die op een vast tijdstip per dag verstuurt) draait dit
op een vast interval — elke `interval_seconds` opnieuw ophalen/renderen.
Elke tick wordt een heartbeat-bestand aangeraakt zodat de Docker
HEALTHCHECK kan zien dat het proces leeft, ook als een TrueNAS-call net
mislukt (dat mag de container niet ongezond maken; zie `main.build_dashboard`).
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from datetime import datetime

TICK_SECONDS = 5


def _touch_heartbeat(data_dir: str) -> bool:
    """Raak het heartbeat-bestand aan. Geeft False als schrijven niet lukt."""
    try:
        os.makedirs(data_dir, exist_ok=True)
        path = os.path.join(data_dir, "heartbeat")
        with open(path, "w", encoding="utf-8") as f:
            f.write(datetime.now().isoformat())
        return True
    except OSError:
        return False  # heartbeat is best-effort; nooit de loop laten crashen


def run_forever(
    job: Callable[[], None],
    *,
    interval_seconds: int,
    data_dir: str,
    run_on_start: bool = True,
    tick_seconds: int = TICK_SECONDS,
    _sleep: Callable[[float], None] = time.sleep,
    _monotonic: Callable[[], float] = time.monotonic,
    _max_iterations: int | None = None,
) -> None:
    """Draai `job` elke `interval_seconds`. `_sleep`/`_monotonic`/`_max_iterations` zijn testseams.

    `last_run` wordt bijgewerkt VOORDAT `job()` wordt aangeroepen (niet erna),
    zodat de duur van `job()` zelf niet elke ronde bovenop het interval wordt
    opgeteld — anders zou een trage job (websocket-call + render + schrijven)
    het echte interval structureel oprekken i.p.v. bij benadering
    `interval_seconds` te blijven.
    """
    if not _touch_heartbeat(data_dir):
        print(
            f"[scheduler] WAARSCHUWING: kan niet schrijven in {data_dir!r}. "
            "De healthcheck zal falen en de app blijft ongezond. Zorg dat deze "
            "mount schrijfbaar is voor uid 10001 (bijv. een named volume i.p.v. tmpfs).",
            flush=True,
        )

    last_run = _monotonic() - interval_seconds if run_on_start else _monotonic()
    iterations = 0
    while _max_iterations is None or iterations < _max_iterations:
        iterations += 1
        _touch_heartbeat(data_dir)
        if _monotonic() - last_run >= interval_seconds:
            last_run = _monotonic()
            _safe_run(job)
        _sleep(tick_seconds)


def _safe_run(job: Callable[[], None]) -> None:
    try:
        job()
    except Exception as exc:  # noqa: BLE001 — één mislukte ronde mag de loop niet stoppen
        print(f"[scheduler] job faalde: {exc!r}", flush=True)
