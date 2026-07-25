"""Wrapper rond truenas_api_client (JSON-RPC 2.0 over websocket).

Haalt in één websocket-sessie alle gegevens op die het dashboard nodig heeft:
systeeminfo, CPU/geheugen/ARC/netwerk-metrics (via reporting.netdata_get_data),
disks + temperaturen, pool-status (scrub/resilver/degraded), apps en actieve
alerts (SMART- en pool-waarschuwingen komen hier binnen, niet als los
"SMART-status"-veld).

LET OP (versie-afhankelijkheid): `auth.login_with_api_key` is in TrueNAS
25.10 al deprecated en wordt in v27 verwijderd (geverifieerd tegen de
middleware-broncode). Bij een upgrade naar v27+ moet dit overstappen op
`auth.login_ex` met `{"mechanism": "API_KEY_PLAIN", "username": ..., "api_key": ...}`
— dat vereist de gebruikersnaam van de key-eigenaar, die dan bv. als aparte
env-variabele moet worden meegegeven.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from truenas_api_client import Client

# Systeembrede netdata-grafieken (geen identifier nodig). ARC-hitrate
# ("arcrate"/"arcactualrate"/"arcresult") bleek op de geteste server geen
# geldige netdata-plugin te zijn (KeyError in middleware) — alleen "arcsize"
# is betrouwbaar beschikbaar, dus ARC-hitrate wordt niet getoond.
_SYSTEM_GRAPHS = ("cpu", "cputemp", "memory", "arcsize", "load")


class TrueNasError(RuntimeError):
    """Verbinding met of authenticatie bij TrueNAS is mislukt."""


@dataclass(frozen=True)
class GraphSeries:
    legend: tuple[str, ...]
    points: tuple[tuple[float, ...], ...]  # (tijdstip, *waarden volgens legend[1:])
    aggregations: dict[str, dict[str, float]]

    def latest(self) -> tuple[float, ...] | None:
        return self.points[-1] if self.points else None

    def latest_value(self, field: str) -> float | None:
        point = self.latest()
        if point is None or field not in self.legend:
            return None
        return point[self.legend.index(field)]


@dataclass(frozen=True)
class DiskStatus:
    name: str
    model: str | None
    size: int | None
    pool: str | None
    temperature: int | None


@dataclass(frozen=True)
class PoolStatus:
    name: str
    status: str
    healthy: bool
    warning: bool
    size: int | None
    allocated: int | None
    free: int | None
    fragmentation: str | None
    scan: dict[str, Any] | None  # scrub/resilver-info; None = geen actieve taak


@dataclass(frozen=True)
class AppStatus:
    name: str
    state: str
    upgrade_available: bool


@dataclass(frozen=True)
class AlertItem:
    level: str
    text: str


@dataclass(frozen=True)
class Snapshot:
    hostname: str
    version: str
    model: str
    cores: int
    physical_cores: int
    physmem: int
    uptime: str
    uptime_seconds: float
    loadavg: tuple[float, float, float]
    server_time: datetime | None
    disks: tuple[DiskStatus, ...]
    pools: tuple[PoolStatus, ...]
    apps: tuple[AppStatus, ...]
    alerts: tuple[AlertItem, ...]
    graphs: dict[str, GraphSeries]  # key: "graphnaam" of "graphnaam:identifier"
    interface_names: tuple[str, ...]


def _graph_key(name: str, identifier: str | None) -> str:
    """TrueNAS geeft voor systeembrede grafieken (cpu, cputemp, memory,
    arcsize, load) de identifier terug als gelijk aan de naam zelf (bv.
    `{"name": "cpu", "identifier": "cpu"}`) in plaats van `null`, ook al is
    er bij het opvragen `identifier: None` meegegeven. Zonder deze check
    zouden deze grafieken onder sleutels als "cpu:cpu" belanden terwijl de
    renderer op de kale naam ("cpu") zoekt."""
    if identifier is None or identifier == name:
        return name
    return f"{name}:{identifier}"


def _extract_datetime(value: Any) -> datetime | None:
    """TrueNAS geeft datums soms als extended-JSON `{"$date": ms}`, soms als
    ISO-string, afhankelijk van transport. Beide afvangen; bij twijfel None
    (dan valt de renderer terug op de lokale containertijd).

    Geeft altijd een timezone-aware datetime terug (UTC als er geen offset
    bekend is) — de renderer rekent 'm zelf om naar de geconfigureerde
    KD_TZ. Zonder dit zou `datetime.fromtimestamp()` de systeemtijdzone van
    de container gebruiken (doorgaans UTC), wat afwijkt van KD_TZ.
    """
    if isinstance(value, dict) and "$date" in value:
        try:
            return datetime.fromtimestamp(value["$date"] / 1000, tz=UTC)
        except (TypeError, ValueError, OSError):
            return None
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
    return None


def fetch_snapshot(url: str, api_key: str, *, verify_ssl: bool = True) -> Snapshot:
    """Open één websocket-sessie, log in met de API-key en haal alles op.

    LET OP: TrueNAS trekt een API-key automatisch in zodra die succesvol
    gebruikt wordt over een verbinding die de middleware niet als
    "secure transport" (echte TLS, rechtstreeks naar TrueNAS' eigen HTTPS-
    poort) herkent -- een reverse proxy die zelf TLS termineert en intern
    over plain HTTP doorstuurt telt daar NIET voor. Gebruik dus `wss://`
    rechtstreeks naar TrueNAS' eigen HTTPS-poort, niet via een tussenliggende
    proxy of TrueNAS' interne plain-HTTP-poort.
    """
    try:
        with Client(uri=url, verify_ssl=verify_ssl) as c:
            if not c.call("auth.login_with_api_key", api_key):
                raise TrueNasError(
                    "TrueNAS API-key werd geweigerd (ongeldig, verlopen of ingetrokken)"
                )

            info = c.call("system.info")
            disks_raw = c.call("disk.query")
            disk_names = [d["name"] for d in disks_raw]
            temps: dict[str, int | None] = (
                c.call("disk.temperatures", disk_names, False) if disk_names else {}
            )
            pools_raw = c.call("pool.query")
            apps_raw = c.call("app.query")
            alerts_raw = c.call("alert.list")
            interfaces_raw = c.call("interface.query")
            interface_names = [i["name"] for i in interfaces_raw]

            graph_requests: list[dict[str, str | None]] = [
                {"name": g, "identifier": None} for g in _SYSTEM_GRAPHS
            ]
            graph_requests += [{"name": "disktemp", "identifier": n} for n in disk_names]
            graph_requests += [{"name": "interface", "identifier": n} for n in interface_names]
            graphs_raw = c.call(
                "reporting.netdata_get_data",
                graph_requests,
                {"aggregate": True, "unit": "HOUR"},
            )
        # De omzetting hieronder blijft bewust binnen dezelfde try/except als
        # de websocket-calls hierboven: een onverwacht ontbrekend veld in een
        # TrueNAS-response (API-versiedrift, een gedegradeerd apparaat zonder
        # het gebruikelijke veld, etc.) moet ook een TrueNasError worden i.p.v.
        # een rauwe KeyError die alle callers verrast.
        graphs: dict[str, GraphSeries] = {}
        for g in graphs_raw:
            key = _graph_key(g["name"], g.get("identifier"))
            graphs[key] = GraphSeries(
                legend=tuple(g.get("legend", [])),
                points=tuple(tuple(p) for p in g.get("data", [])),
                aggregations=g.get("aggregations", {}),
            )

        disk_by_name = {d["name"]: d for d in disks_raw}
        disks = tuple(
            DiskStatus(
                name=name,
                model=disk_by_name[name].get("model"),
                size=disk_by_name[name].get("size"),
                pool=disk_by_name[name].get("pool"),
                temperature=temps.get(name),
            )
            for name in disk_names
        )

        pools = tuple(
            PoolStatus(
                name=p["name"],
                status=p["status"],
                healthy=p["healthy"],
                warning=p["warning"],
                size=p.get("size"),
                allocated=p.get("allocated"),
                free=p.get("free"),
                fragmentation=p.get("fragmentation"),
                scan=p.get("scan"),
            )
            for p in pools_raw
        )

        apps = tuple(
            AppStatus(
                name=a["name"], state=a["state"], upgrade_available=bool(a.get("upgrade_available"))
            )
            for a in apps_raw
        )

        alerts = tuple(
            AlertItem(level=a["level"], text=a.get("formatted") or a.get("text", ""))
            for a in alerts_raw
            if not a.get("dismissed")
        )

        loadavg_raw = info.get("loadavg") or [0.0, 0.0, 0.0]

        return Snapshot(
            hostname=info["hostname"],
            version=info["version"],
            model=info.get("model", ""),
            cores=info.get("cores", 0),
            physical_cores=info.get("physical_cores", 0),
            physmem=info.get("physmem", 0),
            uptime=info.get("uptime", ""),
            uptime_seconds=info.get("uptime_seconds", 0.0),
            loadavg=(loadavg_raw[0], loadavg_raw[1], loadavg_raw[2]),
            server_time=_extract_datetime(info.get("datetime")),
            disks=disks,
            pools=pools,
            apps=apps,
            alerts=alerts,
            graphs=graphs,
            interface_names=tuple(interface_names),
        )
    except TrueNasError:
        raise
    except Exception as exc:  # noqa: BLE001 -- alle verbindings-/data-/protocolfouten worden TrueNasError
        raise TrueNasError(f"Kon geen verbinding maken met TrueNAS op {url}: {exc}") from exc
