import kindle_dashboard.main as main_mod
from kindle_dashboard.config import Config
from kindle_dashboard.truenas_client import TrueNasError


def _config(tmp_path, **overrides):
    defaults = dict(
        truenas_url="ws://example.invalid/api/current",
        truenas_api_key="1-test",
        truenas_verify_ssl=True,
        poll_interval_seconds=300,
        timezone="Europe/Amsterdam",
        data_dir=str(tmp_path),
        http_host="127.0.0.1",
        http_port=0,
        max_alerts=4,
        run_once=True,
        run_on_start=True,
    )
    defaults.update(overrides)
    return Config(**defaults)


def test_build_dashboard_returns_false_on_fetch_error(tmp_path, monkeypatch):
    def boom(_url, _key, **_kwargs):
        raise TrueNasError("nope")

    monkeypatch.setattr(main_mod, "fetch_snapshot", boom)
    assert main_mod.build_dashboard(_config(tmp_path)) is False
    assert not (tmp_path / "dashboard.png").exists()


def test_build_dashboard_returns_false_on_render_error(tmp_path, monkeypatch):
    monkeypatch.setattr(main_mod, "fetch_snapshot", lambda _url, _key, **_kwargs: object())

    def boom(*_args, **_kwargs):
        raise ValueError("bad snapshot")

    monkeypatch.setattr(main_mod, "create_image", boom)
    assert main_mod.build_dashboard(_config(tmp_path)) is False
    assert not (tmp_path / "dashboard.png").exists()


def test_build_dashboard_writes_png_on_success(tmp_path, monkeypatch):
    monkeypatch.setattr(main_mod, "fetch_snapshot", lambda _url, _key, **_kwargs: object())
    monkeypatch.setattr(main_mod, "create_image", lambda _snapshot, **_kw: b"\x89PNG\r\n\x1a\nfake")

    assert main_mod.build_dashboard(_config(tmp_path)) is True
    assert (tmp_path / "dashboard.png").read_bytes() == b"\x89PNG\r\n\x1a\nfake"


def _set_run_once_env(monkeypatch, tmp_path):
    monkeypatch.setenv("KD_TRUENAS_URL", "ws://example.invalid/api/current")
    monkeypatch.setenv("KD_TRUENAS_API_KEY", "1-test")
    monkeypatch.setenv("KD_RUN_ONCE", "true")
    monkeypatch.setenv("KD_DATA_DIR", str(tmp_path))


def test_main_run_once_returns_nonzero_on_failure(tmp_path, monkeypatch):
    _set_run_once_env(monkeypatch, tmp_path)

    def boom(_url, _key, **_kwargs):
        raise TrueNasError("nope")

    monkeypatch.setattr(main_mod, "fetch_snapshot", boom)
    assert main_mod.main() == 1


def test_main_run_once_returns_zero_on_success(tmp_path, monkeypatch):
    _set_run_once_env(monkeypatch, tmp_path)
    monkeypatch.setattr(main_mod, "fetch_snapshot", lambda _url, _key, **_kwargs: object())
    monkeypatch.setattr(main_mod, "create_image", lambda _snapshot, **_kw: b"\x89PNG\r\n\x1a\nfake")

    assert main_mod.main() == 0


def test_main_returns_error_when_not_configured(monkeypatch):
    monkeypatch.delenv("KD_TRUENAS_URL", raising=False)
    monkeypatch.delenv("KD_TRUENAS_API_KEY", raising=False)
    assert main_mod.main() == 1
