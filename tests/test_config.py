from kindle_dashboard.config import is_configured, load_config


def test_defaults():
    config = load_config({})
    assert config.poll_interval_seconds == 300
    assert config.timezone == "Europe/Amsterdam"
    assert config.data_dir == "/data"
    assert config.http_port == 8000
    assert config.run_on_start is True
    assert not is_configured(config)


def test_configured_with_url_and_key():
    config = load_config(
        {
            "KD_TRUENAS_URL": "wss://truenas.example.com/api/current",
            "KD_TRUENAS_API_KEY": "1-secret",
        }
    )
    assert is_configured(config)


def test_overrides():
    config = load_config(
        {
            "KD_POLL_INTERVAL_SECONDS": "60",
            "KD_HTTP_PORT": "9000",
            "KD_MAX_ALERTS": "2",
            "KD_RUN_ONCE": "true",
            "KD_RUN_ON_START": "false",
        }
    )
    assert config.poll_interval_seconds == 60
    assert config.http_port == 9000
    assert config.max_alerts == 2
    assert config.run_once is True
    assert config.run_on_start is False
