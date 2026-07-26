"""Rendert een statusafbeelding (1072x1448, grijswaarden) voor de Kindle
Voyage e-inktschrijver, op basis van een `truenas_client.Snapshot`.

Puur grijswaarden (mode "L") — het Kindle-scherm heeft geen kleur, dus
ernst wordt uitgedrukt via donkerte + labeltekst (OK/WARN/CRIT), niet via
kleur. Geen emoji's: alleen tekens die DejaVu kent.
"""

from __future__ import annotations

import os
from datetime import datetime
from functools import cache
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

from .truenas_client import Snapshot

IMG_W, IMG_H = 1072, 1448
MARGIN = 28
CONTENT_W = IMG_W - 2 * MARGIN
FOOTER_H = 34
CONTENT_BOTTOM = IMG_H - FOOTER_H  # sectiehoogtes worden hierop geclipt ("+N meer")

# Grijswaarden (0 = zwart, 255 = wit). Alleen duidelijk te onderscheiden
# niveaus gebruiken — het paneel heeft 16 grijstinten.
WHITE = 255
BG = 255
INK = 16
MUTED = 110
LINE = 200
PANEL_BG = 235
HEADER_BG = 24
BAR_TRACK = 220
BAR_FILL = 60

MAX_CORE_BARS = 16
SPARK_HOURS_POINTS = 3600  # netdata levert ~1 punt/seconde over het laatste uur

_FONT_CANDIDATES = {
    False: [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ],
    True: [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ],
}


@cache
def load_font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    # Gecachet: één create_image()-aanroep vraagt dezelfde (size, bold) vaak
    # meerdere keren op, en elke miss zou anders opnieuw het kandidatenpad
    # scannen (os.path.isfile) en het TTF-bestand herparsen.
    for path in _FONT_CANDIDATES[bold]:
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Kleine helpers
# ---------------------------------------------------------------------------
def _fmt_bytes(n: float | None) -> str:
    if n is None:
        return "?"
    step = 1024.0
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(n) < step:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= step
    return f"{n:.1f} PiB"


def _fmt_kbit(n: float | None) -> str:
    if n is None:
        return "?"
    if n < 1000:
        return f"{n:.0f} kbit/s"
    return f"{n / 1000:.1f} Mbit/s"


def _truncate(draw: ImageDraw.ImageDraw, text: str, font, max_w: float) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "...", font=font) > max_w:
        text = text[:-1]
    return text + "..."


def _bar(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    fraction: float,
    *,
    track=BAR_TRACK,
    fill=BAR_FILL,
) -> None:
    fraction = max(0.0, min(1.0, fraction))
    draw.rectangle([x, y, x + w, y + h], fill=track, outline=MUTED)
    if fraction > 0:
        draw.rectangle([x, y, x + int(w * fraction), y + h], fill=fill)


def _sparkline(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    values: list[float],
    *,
    fill=INK,
    fixed_max: float | None = None,
) -> None:
    """Eenvoudige lijngrafiek van `values`, geschaald binnen (w, h)."""
    draw.rectangle([x, y, x + w, y + h], outline=LINE)
    if len(values) < 2:
        return
    vmax = fixed_max if fixed_max is not None else max(values)
    vmax = vmax or 1.0
    n = len(values)
    points = []
    for i, v in enumerate(values):
        px = x + round(i / (n - 1) * w)
        py = y + h - round(min(v, vmax) / vmax * h)
        points.append((px, py))
    draw.line(points, fill=fill, width=2)


def _sparkline_multi(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    series: list[tuple[list[float], int]],
) -> None:
    """Meerdere lijnen in één grafiek, geschaald op een gedeeld maximum (bv.
    inkomend + uitgaand netwerkverkeer, die anders elk hun eigen schaal
    zouden krijgen en dus niet onderling vergelijkbaar zouden zijn)."""
    draw.rectangle([x, y, x + w, y + h], outline=LINE)
    all_values = [v for values, _fill in series for v in values]
    if not all_values:
        return
    vmax = max(all_values) or 1.0
    for values, fill in series:
        if len(values) < 2:
            continue
        n = len(values)
        points = [
            (x + round(i / (n - 1) * w), y + h - round(min(v, vmax) / vmax * h))
            for i, v in enumerate(values)
        ]
        draw.line(points, fill=fill, width=2)


def _has_traffic(graph) -> bool:
    """Een fysieke poort die nergens op aangesloten is levert de hele
    opgevraagde periode 0 op -- die hoeft niet in de weergave (voegt niets
    toe, kost alleen ruimte). Bij een onbekend legend-formaat liever tonen
    dan onterecht verbergen."""
    if graph is None or not graph.points:
        return False
    if "received" not in graph.legend or "sent" not in graph.legend:
        return True
    rx_idx = graph.legend.index("received")
    tx_idx = graph.legend.index("sent")
    return any(p[rx_idx] or p[tx_idx] for p in graph.points)


def _section_title(draw: ImageDraw.ImageDraw, x: int, y: int, title: str, width: int) -> int:
    f = load_font(26, bold=True)
    draw.text((x, y), title, font=f, fill=INK)
    y += 34
    draw.line([(x, y), (x + width, y)], fill=LINE, width=2)
    return y + 10


def _last_nonzero_value(graph, field: str) -> float | None:
    """Sommige netdata-sensoren (bv. CPU-temperatuur via lm-sensors) pollen
    minder vaak dan 1x/seconde. Het allerlaatste punt in de per-seconde
    reeks kan dan nog niet bijgewerkt zijn en toont 0 i.p.v. de echte
    laatste meting. Scan daarom terug tot de laatste van-nul-verschillende
    waarde, i.p.v. blind `latest_value()` te gebruiken."""
    if graph is None or field not in graph.legend:
        return None
    idx = graph.legend.index(field)
    for point in reversed(graph.points):
        if point[idx]:
            return point[idx]
    return None


def _status_label(healthy: bool, warning: bool) -> str:
    if not healthy:
        return "CRIT"
    if warning:
        return "WARN"
    return "OK"


def _max_rows(
    y: int, row_h: int, bottom: int = CONTENT_BOTTOM, *, overflow_h: int | None = None
) -> int:
    """Hoeveel rijen van `row_h` passen er nog tussen `y` en de onderkant,
    met ruimte voor een eventuele "+N meer"-regel erna. Die regel is meestal
    exact `row_h` hoog (compacte lijsten als Disks/Apps), maar bij rijen die
    zelf veel hoger zijn dan een enkele tekstregel (bv. Netwerk met sparklines)
    zou dat onterecht een hele extra rij reserveren -- geef dan `overflow_h`
    expliciet mee."""
    reserve = row_h if overflow_h is None else overflow_h
    return max(0, (bottom - reserve - y) // row_h)


# ---------------------------------------------------------------------------
# Kop
# ---------------------------------------------------------------------------
def _draw_header(draw: ImageDraw.ImageDraw, snapshot: Snapshot, timezone: str) -> int:
    header_h = 100
    draw.rectangle([0, 0, IMG_W, header_h], fill=HEADER_BG)
    f_host = load_font(38, bold=True)
    f_sub = load_font(20)
    draw.text((MARGIN, 14), snapshot.hostname, font=f_host, fill=WHITE)
    draw.text(
        (MARGIN, 62),
        f"TrueNAS {snapshot.version}  |  {snapshot.model}",
        font=f_sub,
        fill=200,
    )

    now = (
        snapshot.server_time.astimezone(ZoneInfo(timezone))
        if snapshot.server_time is not None
        else datetime.now(ZoneInfo(timezone))
    )
    time_str = now.strftime("%a %d %b  %H:%M")
    tw = draw.textlength(time_str, font=f_sub)
    draw.text((IMG_W - MARGIN - tw, 18), time_str, font=f_sub, fill=200)
    draw.text((IMG_W - MARGIN - tw, 46), f"up {snapshot.uptime}", font=f_sub, fill=200)
    return header_h + 14


# ---------------------------------------------------------------------------
# Alerts (bovenaan, alleen als er iets is)
# ---------------------------------------------------------------------------
def _draw_alerts(draw: ImageDraw.ImageDraw, snapshot: Snapshot, y: int, max_alerts: int) -> int:
    if not snapshot.alerts:
        return y
    order = {"CRITICAL": 0, "ERROR": 1, "WARNING": 2, "INFO": 3}
    alerts = sorted(snapshot.alerts, key=lambda a: order.get(a.level, 9))[:max_alerts]

    f_title = load_font(22, bold=True)
    f_body = load_font(20)
    row_h = 34
    box_h = 42 + len(alerts) * row_h
    draw.rectangle([MARGIN, y, IMG_W - MARGIN, y + box_h], fill=PANEL_BG, outline=INK, width=2)
    title = f"Actieve meldingen ({len(snapshot.alerts)})"
    draw.text((MARGIN + 14, y + 8), title, font=f_title, fill=INK)
    ay = y + 42
    for a in alerts:
        marker = "!!" if a.level in ("CRITICAL", "ERROR") else "!"
        text = _truncate(draw, f"{marker} [{a.level}] {a.text}", f_body, CONTENT_W - 28)
        draw.text((MARGIN + 14, ay), text, font=f_body, fill=INK)
        ay += row_h
    return y + box_h + 16


# ---------------------------------------------------------------------------
# CPU
# ---------------------------------------------------------------------------
def _draw_cpu_section(draw: ImageDraw.ImageDraw, snapshot: Snapshot, y: int) -> int:
    y = _section_title(draw, MARGIN, y, "CPU", CONTENT_W)

    cpu_graph = snapshot.graphs.get("cpu")
    temp_graph = snapshot.graphs.get("cputemp")
    total_pct = cpu_graph.latest_value("cpu") if cpu_graph else None
    total_temp = _last_nonzero_value(temp_graph, "cpu")

    f_big = load_font(44, bold=True)
    f_label = load_font(19)
    pct_text = f"{total_pct:.0f}%" if total_pct is not None else "?%"
    draw.text((MARGIN, y), pct_text, font=f_big, fill=INK)
    draw.text((MARGIN, y + 52), "gebruik", font=f_label, fill=MUTED)

    temp_x = MARGIN + 190
    draw.text(
        (temp_x, y),
        f"{total_temp:.0f}°C" if total_temp is not None else "? °C",
        font=f_big,
        fill=INK,
    )
    draw.text((temp_x, y + 52), "temperatuur", font=f_label, fill=MUTED)

    load_x = temp_x + 220
    la = snapshot.loadavg
    draw.text((load_x, y), f"{la[0]:.2f}", font=f_big, fill=INK)
    draw.text((load_x, y + 52), "load (1 min)", font=f_label, fill=MUTED)

    y += 92

    # Per-core gebruiksbalken (max MAX_CORE_BARS, anders alleen totaal hierboven)
    if cpu_graph and snapshot.cores and snapshot.cores <= MAX_CORE_BARS:
        core_fields = [f for f in cpu_graph.legend if f.startswith("cpu") and f != "cpu"]
        core_fields.sort(key=lambda f: int(f[3:]) if f[3:].isdigit() else 0)
        latest = cpu_graph.latest()
        if core_fields and latest:
            gap = 8
            bar_w = (CONTENT_W - gap * (len(core_fields) - 1)) // len(core_fields)
            bar_h = 40
            f_tiny = load_font(14)
            for i, field in enumerate(core_fields):
                pct = latest[cpu_graph.legend.index(field)] / 100.0
                bx = MARGIN + i * (bar_w + gap)
                fh = round(bar_h * pct)
                draw.rectangle([bx, y + bar_h - fh, bx + bar_w, y + bar_h], fill=BAR_FILL)
                draw.rectangle([bx, y, bx + bar_w, y + bar_h], outline=MUTED)
                label = field.replace("cpu", "")
                draw.text((bx + 2, y + bar_h + 3), label, font=f_tiny, fill=MUTED)
            y += bar_h + 20

    # Sparkline van het laatste uur CPU-gebruik ("iets grafisch")
    if cpu_graph and cpu_graph.points and "cpu" in cpu_graph.legend:
        idx = cpu_graph.legend.index("cpu")
        values = [p[idx] for p in cpu_graph.points]
        f_tiny = load_font(16)
        draw.text((MARGIN, y), "CPU-gebruik, laatste uur", font=f_tiny, fill=MUTED)
        y += 20
        _sparkline(draw, MARGIN, y, CONTENT_W, 54, values, fixed_max=100)
        y += 54

    return y + 18


# ---------------------------------------------------------------------------
# Geheugen + ARC
# ---------------------------------------------------------------------------
def _draw_memory_section(draw: ImageDraw.ImageDraw, snapshot: Snapshot, y: int) -> int:
    y = _section_title(draw, MARGIN, y, "Geheugen & ZFS ARC", CONTENT_W)

    f_label = load_font(20)
    bar_w = CONTENT_W
    bar_h = 34

    mem_graph = snapshot.graphs.get("memory")
    available = mem_graph.latest_value("available") if mem_graph else None
    physmem = snapshot.physmem or 1
    used = (physmem - available) if available is not None else None
    used_frac = (used / physmem) if used is not None else 0.0

    draw.text((MARGIN, y), "RAM", font=f_label, fill=INK)
    label = f"{_fmt_bytes(used)} / {_fmt_bytes(physmem)}" if used is not None else "onbekend"
    lw = draw.textlength(label, font=f_label)
    draw.text((MARGIN + CONTENT_W - lw, y), label, font=f_label, fill=MUTED)
    y += 26
    _bar(draw, MARGIN, y, bar_w, bar_h, used_frac)
    y += bar_h + 18

    arc_graph = snapshot.graphs.get("arcsize")
    arc_size = arc_graph.latest_value("size") if arc_graph else None
    arc_frac = (arc_size / physmem) if arc_size is not None else 0.0

    draw.text((MARGIN, y), "ZFS ARC", font=f_label, fill=INK)
    label = f"{_fmt_bytes(arc_size)}" if arc_size is not None else "onbekend"
    lw = draw.textlength(label, font=f_label)
    draw.text((MARGIN + CONTENT_W - lw, y), label, font=f_label, fill=MUTED)
    y += 26
    _bar(draw, MARGIN, y, bar_w, bar_h, arc_frac)
    y += bar_h

    return y + 18


# ---------------------------------------------------------------------------
# Pools
# ---------------------------------------------------------------------------
def _scan_summary(scan: dict | None) -> str | None:
    if not scan or not scan.get("function"):
        return None
    func = scan["function"]  # "SCRUB" of "RESILVER"
    state = scan.get("state", "")
    pct = scan.get("percentage")
    if state == "FINISHED":
        errors = scan.get("errors", 0)
        return f"{func.title()} voltooid ({errors} fout{'en' if errors != 1 else ''})"
    if pct is not None:
        return f"{func.title()} bezig: {pct:.1f}%"
    return f"{func.title()} bezig"


def _draw_pools_section(draw: ImageDraw.ImageDraw, snapshot: Snapshot, y: int) -> int:
    y = _section_title(draw, MARGIN, y, "Storage pools", CONTENT_W)
    f_name = load_font(23, bold=True)
    f_body = load_font(19)
    f_pct = load_font(26, bold=True)

    donut_d = 108
    donut_r = donut_d // 2
    inner_r = donut_r - 20  # ringdikte 20px: dun genoeg voor een "donut", dik genoeg om af te lezen
    gap_after_donut = 24
    text_x = MARGIN + donut_d + gap_after_donut
    text_w = CONTENT_W - donut_d - gap_after_donut
    row_gap = 18
    # Worst-case rijhoogte: het hoogste van (donut, tekstblok mét scanregel).
    # Altijd de scanregel meerekenen (niet gemiddeld) -- anders kan de
    # laatste pool die "past" alsnog voorbij CONTENT_BOTTOM tekenen zodra
    # er wél een actieve scrub/resilver is.
    text_block_h = 32 + 26 + 26
    row_h = max(donut_d, text_block_h) + row_gap

    pools = list(snapshot.pools)
    for shown, pool in enumerate(pools):
        if y + row_h > CONTENT_BOTTOM:
            remaining = len(pools) - shown
            draw.text((MARGIN, y), f"+ {remaining} meer pool(s)", font=f_body, fill=MUTED)
            y += 26
            break

        frac = (pool.allocated / pool.size) if pool.size and pool.allocated is not None else 0.0
        cx, cy = MARGIN + donut_r, y + donut_r
        bbox = [cx - donut_r, cy - donut_r, cx + donut_r, cy + donut_r]
        draw.ellipse(bbox, fill=BAR_TRACK, outline=MUTED)
        if frac > 0:
            # Start op 12 uur (-90 t.o.v. PIL's 3-uur-nulpunt), met de klok mee.
            draw.pieslice(bbox, -90, -90 + frac * 360, fill=BAR_FILL)
        draw.ellipse(
            [cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r], fill=BG, outline=MUTED
        )
        pct_text = f"{frac * 100:.0f}%"
        pw = draw.textlength(pct_text, font=f_pct)
        draw.text((cx - pw / 2, cy - 15), pct_text, font=f_pct, fill=INK)

        ty = y
        status = _status_label(pool.healthy, pool.warning)
        draw.text((text_x, ty), pool.name, font=f_name, fill=INK)
        status_text = f"[{status}] {pool.status}"
        sw = draw.textlength(status_text, font=f_body)
        draw.text((text_x + text_w - sw, ty + 3), status_text, font=f_body, fill=INK)
        ty += 32

        used_label = f"{_fmt_bytes(pool.allocated)} / {_fmt_bytes(pool.size)}"
        draw.text((text_x, ty), used_label, font=f_body, fill=MUTED)
        ty += 26

        scan_text = _scan_summary(pool.scan)
        if scan_text:
            draw.text((text_x, ty), scan_text, font=f_body, fill=MUTED)

        y += row_h

    return y + 4


# ---------------------------------------------------------------------------
# Netwerk
# ---------------------------------------------------------------------------
def _draw_network_section(draw: ImageDraw.ImageDraw, snapshot: Snapshot, y: int) -> int:
    y = _section_title(draw, MARGIN, y, "Netwerk", CONTENT_W)
    f_body = load_font(19)
    f_name = load_font(21, bold=True)
    f_tiny = load_font(14)

    # Interfaces zonder enig verkeer in het opgevraagde uur (bv. een
    # ongebruikte fysieke poort) voegen niets toe aan de weergave.
    ifaces = [
        n for n in snapshot.interface_names if _has_traffic(snapshot.graphs.get(f"interface:{n}"))
    ]
    if not ifaces:
        draw.text((MARGIN, y), "Geen actieve interfaces", font=f_body, fill=MUTED)
        return y + 26

    spark_h = 40
    gap = 14
    row_h = 30 + spark_h + gap

    draw.text((MARGIN, y), "in (donker) / uit (grijs), laatste uur", font=f_tiny, fill=MUTED)
    y += 18

    # De "+N meer interfaces"-regel is maar 26px hoog, niet een volle rij
    # (die inclusief sparkline ~84px is) -- anders wordt er onterecht een
    # hele extra rij gereserveerd en verdwijnen interfaces die prima passen.
    max_rows = _max_rows(y, row_h, overflow_h=26)
    shown = ifaces[:max_rows] if len(ifaces) > max_rows else ifaces
    for name in shown:
        graph = snapshot.graphs[f"interface:{name}"]
        rx = graph.latest_value("received")
        tx = graph.latest_value("sent")
        draw.text((MARGIN, y), name, font=f_name, fill=INK)
        draw.text(
            (MARGIN + 180, y + 1),
            f"in {_fmt_kbit(rx)}   uit {_fmt_kbit(tx)}",
            font=f_body,
            fill=MUTED,
        )
        y += 30

        if "received" in graph.legend and "sent" in graph.legend and graph.points:
            rx_idx = graph.legend.index("received")
            tx_idx = graph.legend.index("sent")
            rx_values = [p[rx_idx] for p in graph.points]
            tx_values = [p[tx_idx] for p in graph.points]
            _sparkline_multi(
                draw, MARGIN, y, CONTENT_W, spark_h, [(rx_values, INK), (tx_values, MUTED)]
            )
        else:
            draw.rectangle([MARGIN, y, MARGIN + CONTENT_W, y + spark_h], outline=LINE)
        y += spark_h + gap

    hidden = len(ifaces) - len(shown)
    if hidden > 0:
        draw.text((MARGIN, y), f"+ {hidden} meer interfaces", font=f_body, fill=MUTED)
        y += 26

    return y + 14


# ---------------------------------------------------------------------------
# Apps
# ---------------------------------------------------------------------------
def _draw_apps_section(draw: ImageDraw.ImageDraw, snapshot: Snapshot, y: int) -> int:
    y = _section_title(draw, MARGIN, y, "Apps", CONTENT_W)
    f_body = load_font(19)

    running = sum(1 for a in snapshot.apps if a.state == "RUNNING")
    draw.text(
        (MARGIN, y),
        f"{running} / {len(snapshot.apps)} draaien",
        font=load_font(20, bold=True),
        fill=INK,
    )
    y += 28

    row_h = 26
    col_w = CONTENT_W // 2
    not_running = [a for a in snapshot.apps if a.state != "RUNNING"]
    items = not_running if not_running else list(snapshot.apps)
    max_rows = _max_rows(y, row_h)
    max_items = max_rows * 2
    shown = items[:max_items] if len(items) > max_items else items
    for i, app in enumerate(shown):
        col = i % 2
        row = i // 2
        x = MARGIN + col * col_w
        row_y = y + row * row_h
        marker = "" if app.state == "RUNNING" else f" [{app.state}]"
        text = _truncate(draw, f"- {app.name}{marker}", f_body, col_w - 16)
        draw.text((x, row_y), text, font=f_body, fill=INK if app.state == "RUNNING" else MUTED)
    rows = (len(shown) + 1) // 2
    y += rows * row_h

    hidden = len(items) - len(shown)
    if hidden > 0:
        draw.text((MARGIN, y), f"+ {hidden} meer apps", font=f_body, fill=MUTED)
        y += row_h

    return y + 14


# ---------------------------------------------------------------------------
# Publieke entrypoint
# ---------------------------------------------------------------------------
def create_image(
    snapshot: Snapshot, *, timezone: str = "Europe/Amsterdam", max_alerts: int = 4
) -> bytes:
    from io import BytesIO

    img = Image.new("L", (IMG_W, IMG_H), BG)
    draw = ImageDraw.Draw(img)

    # Vaste kern (mag altijd tekenen, ook als dat tot aan de rand loopt): de
    # belangrijkste "in één oogopslag"-info staat bovenaan.
    y = _draw_header(draw, snapshot, timezone)
    y = _draw_alerts(draw, snapshot, y, max_alerts)
    y = _draw_cpu_section(draw, snapshot, y)
    y = _draw_memory_section(draw, snapshot, y)
    y = _draw_pools_section(draw, snapshot, y)

    # Laagste prioriteit: alleen tekenen als er nog echt ruimte over is, i.p.v.
    # overlappende tekst tegen de voettekst aan te drukken bij veel content.
    min_section_h = 70
    omitted = []
    if y + min_section_h <= CONTENT_BOTTOM:
        y = _draw_network_section(draw, snapshot, y)
    else:
        omitted.append("Netwerk")
    if y + min_section_h <= CONTENT_BOTTOM:
        y = _draw_apps_section(draw, snapshot, y)
    else:
        omitted.append("Apps")

    f_footer = load_font(16)
    footer = f"kindle-truenas-dashboard  |  bijgewerkt {datetime.now(ZoneInfo(timezone)):%H:%M:%S}"
    if omitted:
        footer += f"  |  weggelaten (geen ruimte): {', '.join(omitted)}"
    draw.text((MARGIN, IMG_H - FOOTER_H + 6), footer, font=f_footer, fill=MUTED)

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
