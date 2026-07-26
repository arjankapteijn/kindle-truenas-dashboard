#!/usr/bin/env python3
"""Rendert een voorbeeld-dashboard met verzonnen data — zonder TrueNAS nodig.

Handig om layout-wijzigingen visueel te checken:

    python scripts/render_preview.py [output.png]

Schrijft standaard naar preview.png in de huidige map.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from kindle_dashboard.render import create_image  # noqa: E402
from kindle_dashboard.truenas_client import (  # noqa: E402
    AlertItem,
    AppStatus,
    DiskStatus,
    GraphSeries,
    PoolStatus,
    Snapshot,
)


def _series(legend: tuple[str, ...], n: int, *funcs) -> GraphSeries:
    points = tuple((float(i),) + tuple(f(i) for f in funcs) for i in range(n))
    return GraphSeries(legend=legend, points=points, aggregations={})


def build_fixture_snapshot() -> Snapshot:
    cpu = _series(
        ("time", "cpu", "cpu0", "cpu1"),
        200,
        lambda i: 30 + (i % 40),
        lambda i: 20 + (i % 50),
        lambda i: 40 + (i % 30),
    )
    cputemp = _series(
        ("time", "cpu0", "cpu1", "cpu"),
        200,
        lambda i: 40 + (i % 10),
        lambda i: 42 + (i % 8),
        # Laatste punt bewust 0: netdata's allerlaatste per-seconde sample kan
        # nog niet bijgewerkt zijn voor traag pollende sensoren (zie
        # _last_nonzero_value in render.py) -- dit fixture-punt bewijst dat de
        # renderer daar niet in trapt.
        lambda i: 0 if i == 199 else 44,
    )
    memory = _series(("time", "available"), 200, lambda i: 2_100_000_000 - i * 1000)
    arcsize = _series(("time", "size"), 200, lambda i: 7_500_000_000 + i * 1000)
    iface = _series(
        ("time", "received", "sent"), 200, lambda i: 490 + (i % 300), lambda i: 116 + (i % 900)
    )
    iface_unused = _series(("time", "received", "sent"), 200, lambda _i: 0, lambda _i: 0)

    return Snapshot(
        hostname="truenas",
        version="25.10.4",
        model="AMD Opteron(tm) X3216 APU",
        cores=2,
        physical_cores=2,
        physmem=16_204_578_816,
        uptime="39 days, 4:01:08",
        uptime_seconds=3384068,
        loadavg=(0.62, 0.46, 0.43),
        server_time=None,
        disks=(
            DiskStatus("sda", "H7230AS60SUN3.0T", 3_000_592_982_016, "data", 32),
            DiskStatus("sdb", "H7230AS60SUN3.0T", 3_000_592_982_016, "data", 33),
            DiskStatus("sdc", "H7230AS60SUN3.0T", 3_000_592_982_016, "data", 31),
            DiskStatus("sdd", "H7230AS60SUN3.0T", 3_000_592_982_016, "data", None),
            DiskStatus("sde", "SSD", 500_000_000_000, "apps", 38),
            DiskStatus("sdf", "SSD", 500_000_000_000, "apps", 39),
        ),
        pools=(
            PoolStatus(
                "data",
                "ONLINE",
                healthy=False,
                warning=True,
                size=9_000_000_000_000,
                allocated=6_500_000_000_000,
                free=2_500_000_000_000,
                fragmentation="39",
                scan={"function": "SCRUB", "state": "FINISHED", "percentage": 99.99, "errors": 0},
            ),
            PoolStatus(
                "apps",
                "ONLINE",
                healthy=True,
                warning=False,
                size=296_352_743_424,
                allocated=108_099_194_880,
                free=188_253_548_544,
                fragmentation="12",
                scan=None,
            ),
        ),
        apps=(
            AppStatus("headscale", "RUNNING", False),
            AppStatus("lovebox", "RUNNING", True),
            AppStatus("vaultwarden", "RUNNING", False),
            AppStatus("immich", "RUNNING", True),
            AppStatus("adguard-home", "RUNNING", True),
            AppStatus("kindle-dashboard", "STOPPED", False),
        ),
        alerts=(
            AlertItem("CRITICAL", "Pool data state is ONLINE: one or more devices had an error."),
            AlertItem("INFO", "Updates are available for 5 applications."),
        ),
        graphs={
            "cpu": cpu,
            "cputemp": cputemp,
            "memory": memory,
            "arcsize": arcsize,
            "interface:enp2s0f0": iface,
            "interface:enp2s0f1": iface,
            # Ongebruikte poort (geen kabel aangesloten) -- hoort niet in de
            # weergave te verschijnen, zie _has_traffic() in render.py.
            "interface:enp3s0": iface_unused,
        },
        interface_names=("enp2s0f0", "enp2s0f1", "enp3s0"),
    )


def main() -> int:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("preview.png")
    png_bytes = create_image(build_fixture_snapshot())
    out_path.write_bytes(png_bytes)
    print(f"{out_path} ({len(png_bytes) / 1024:.1f} kB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
