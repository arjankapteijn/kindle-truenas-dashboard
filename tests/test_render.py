from kindle_dashboard.render import IMG_H, IMG_W, create_image
from kindle_dashboard.truenas_client import (
    AlertItem,
    AppStatus,
    DiskStatus,
    GraphSeries,
    PoolStatus,
    Snapshot,
)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _minimal_snapshot(**overrides) -> Snapshot:
    defaults = dict(
        hostname="truenas",
        version="25.10.4",
        model="test-model",
        cores=2,
        physical_cores=2,
        physmem=16_000_000_000,
        uptime="1 day",
        uptime_seconds=86400,
        loadavg=(0.1, 0.2, 0.3),
        server_time=None,
        disks=(),
        pools=(),
        apps=(),
        alerts=(),
        graphs={},
        interface_names=(),
    )
    defaults.update(overrides)
    return Snapshot(**defaults)


def test_create_image_returns_valid_png():
    png = create_image(_minimal_snapshot())
    assert png.startswith(PNG_SIGNATURE)


def test_create_image_handles_full_data_without_crashing():
    snapshot = _minimal_snapshot(
        disks=tuple(
            DiskStatus(
                name=f"sd{c}", model="x", size=1_000_000_000_000, pool="data", temperature=30
            )
            for c in "abcdef"
        ),
        pools=(
            PoolStatus(
                name="data",
                status="ONLINE",
                healthy=False,
                warning=True,
                size=1000,
                allocated=800,
                free=200,
                fragmentation="10",
                scan={"function": "SCRUB", "state": "FINISHED", "percentage": 100, "errors": 0},
            ),
        ),
        apps=tuple(
            AppStatus(
                name=f"app{i}",
                state="RUNNING" if i % 2 else "STOPPED",
                upgrade_available=False,
            )
            for i in range(8)
        ),
        alerts=(AlertItem(level="CRITICAL", text="iets ergs"),),
        graphs={
            "cpu": GraphSeries(
                legend=("time", "cpu", "cpu0", "cpu1"),
                points=((1, 50, 40, 60),),
                aggregations={},
            ),
            "cputemp": GraphSeries(
                legend=("time", "cpu0", "cpu1", "cpu"), points=((1, 40, 41, 42),), aggregations={}
            ),
            "memory": GraphSeries(
                legend=("time", "available"), points=((1, 8_000_000_000),), aggregations={}
            ),
            "arcsize": GraphSeries(
                legend=("time", "size"), points=((1, 4_000_000_000),), aggregations={}
            ),
            "interface:eth0": GraphSeries(
                legend=("time", "received", "sent"), points=((1, 100, 200),), aggregations={}
            ),
        },
        interface_names=("eth0",),
    )
    png = create_image(snapshot)
    assert png.startswith(PNG_SIGNATURE)


def test_create_image_handles_empty_graphs():
    """Ontbrekende metrics (bv. een mislukte netdata-call) mogen niet crashen."""
    png = create_image(_minimal_snapshot(cores=0))
    assert png.startswith(PNG_SIGNATURE)


def test_image_dimensions_match_kindle_voyage():
    from io import BytesIO

    from PIL import Image

    png = create_image(_minimal_snapshot())
    img = Image.open(BytesIO(png))
    assert img.size == (IMG_W, IMG_H)
    assert IMG_W == 1072 and IMG_H == 1448
