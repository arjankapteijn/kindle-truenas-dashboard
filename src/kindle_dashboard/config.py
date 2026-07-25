"""Configuratie uit omgevingsvariabelen.

Credentials (API-key) horen alleen in .env / de container-omgeving, nooit in
de repo. Zie `.env.example` voor het formaat.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class Config:
    truenas_url: str  # bv. wss://truenas.example.com/api/current
    truenas_api_key: str
    poll_interval_seconds: int
    timezone: str
    data_dir: str
    http_host: str
    http_port: int
    max_alerts: int
    run_once: bool
    run_on_start: bool


def _get(env: Mapping[str, str], name: str, default: str = "") -> str:
    return (env.get(name) or default).strip()


def _get_bool(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = _get(env, name).lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "ja", "on")


def _get_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = _get(env, name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} moet een geheel getal zijn, kreeg {raw!r}") from exc


def _get_timezone(env: Mapping[str, str], name: str, default: str) -> str:
    """Valideer KD_TZ meteen bij het opstarten — anders faalt een typefout
    pas uren later, diep in de renderloop (ZoneInfoNotFoundError), i.p.v.
    direct en duidelijk bij het starten van de container."""
    raw = _get(env, name, default)
    try:
        ZoneInfo(raw)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"{name} is geen geldige IANA-tijdzone, kreeg {raw!r}") from exc
    return raw


def load_config(env: Mapping[str, str] | None = None) -> Config:
    """Lees de volledige configuratie uit de omgeving (default: os.environ)."""
    import os

    env = os.environ if env is None else env

    return Config(
        truenas_url=_get(env, "KD_TRUENAS_URL"),
        truenas_api_key=_get(env, "KD_TRUENAS_API_KEY"),
        poll_interval_seconds=_get_int(env, "KD_POLL_INTERVAL_SECONDS", 300),
        timezone=_get_timezone(env, "KD_TZ", "Europe/Amsterdam"),
        data_dir=_get(env, "KD_DATA_DIR", "/data"),
        http_host=_get(env, "KD_HTTP_HOST", "0.0.0.0"),
        http_port=_get_int(env, "KD_HTTP_PORT", 8000),
        max_alerts=_get_int(env, "KD_MAX_ALERTS", 4),
        run_once=_get_bool(env, "KD_RUN_ONCE", False),
        run_on_start=_get_bool(env, "KD_RUN_ON_START", True),
    )


def is_configured(config: Config) -> bool:
    """True als de verplichte TrueNAS-credentials aanwezig zijn."""
    return bool(config.truenas_url and config.truenas_api_key)
