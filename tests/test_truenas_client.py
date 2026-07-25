from unittest.mock import patch

import pytest

from kindle_dashboard.truenas_client import TrueNasError, fetch_snapshot


class _FakeClient:
    """Minimale stand-in voor `truenas_api_client.Client`: retourneert per
    methodnaam een vast antwoord, zodat we fetch_snapshot kunnen testen
    zonder een echte TrueNAS-server."""

    def __init__(self, responses):
        self._responses = responses

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def call(self, method, *_args):
        if method == "auth.login_with_api_key":
            return True
        return self._responses[method]


_MINIMAL_RESPONSES = {
    "system.info": {
        "hostname": "truenas",
        "version": "25.10.4",
        "loadavg": [0.1, 0.2, 0.3],
    },
    "disk.query": [],
    "pool.query": [],
    "app.query": [],
    "alert.list": [],
    "interface.query": [],
    "reporting.netdata_get_data": [],
}


def _fetch_with(responses):
    with patch("kindle_dashboard.truenas_client.Client", lambda uri: _FakeClient(responses)):
        return fetch_snapshot("ws://example.invalid/api/current", "1-test")


def test_fetch_snapshot_happy_path():
    snapshot = _fetch_with(_MINIMAL_RESPONSES)
    assert snapshot.hostname == "truenas"
    assert snapshot.version == "25.10.4"


def test_fetch_snapshot_wraps_keyerror_from_malformed_pool_response():
    """Een pool-object zonder het verplichte 'status'-veld (API-versiedrift,
    een onvolledige/gedegradeerde entry) moet een TrueNasError opleveren,
    geen rauwe KeyError — anders verrast dat elke caller die alleen
    TrueNasError afvangt (zie main.build_dashboard)."""
    responses = dict(_MINIMAL_RESPONSES)
    responses["pool.query"] = [{"name": "data", "healthy": True, "warning": False}]  # mist "status"

    with pytest.raises(TrueNasError):
        _fetch_with(responses)


def test_fetch_snapshot_wraps_keyerror_from_malformed_app_response():
    responses = dict(_MINIMAL_RESPONSES)
    responses["app.query"] = [{"name": "immich"}]  # mist "state"

    with pytest.raises(TrueNasError):
        _fetch_with(responses)


def test_fetch_snapshot_rejects_invalid_api_key():
    class _RejectingClient(_FakeClient):
        def call(self, method, *_args):
            if method == "auth.login_with_api_key":
                return False
            return self._responses[method]

    with (
        patch(
            "kindle_dashboard.truenas_client.Client",
            lambda uri: _RejectingClient(_MINIMAL_RESPONSES),
        ),
        pytest.raises(TrueNasError),
    ):
        fetch_snapshot("ws://example.invalid/api/current", "1-bad")
