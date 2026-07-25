from kindle_dashboard.scheduler import run_forever


def _fake_clock(tick_seconds):
    """Een monotone klok die precies `tick_seconds` vooruitspringt bij elke
    `_sleep`-aanroep — zo simuleert de test echt tijdsverloop zonder te
    wachten, en blijft `_monotonic() - last_run` kloppen zoals in productie.
    `state` ligt open zodat een test 'm ook kan gebruiken om een trage job
    te simuleren (rechtstreeks de klok laten vooruitspringen tijdens `job()`)."""
    state = {"t": 0.0}

    def monotonic():
        return state["t"]

    def sleep(_seconds):
        state["t"] += tick_seconds

    return monotonic, sleep, state


def test_runs_immediately_when_run_on_start(tmp_path):
    calls = []
    monotonic, sleep, _state = _fake_clock(10)
    run_forever(
        job=lambda: calls.append(1),
        interval_seconds=100,
        data_dir=str(tmp_path),
        run_on_start=True,
        tick_seconds=10,
        _sleep=sleep,
        _monotonic=monotonic,
        _max_iterations=1,
    )
    assert calls == [1]


def test_waits_for_interval_when_not_run_on_start(tmp_path):
    calls = []
    monotonic, sleep, _state = _fake_clock(10)
    run_forever(
        job=lambda: calls.append(1),
        interval_seconds=100,
        data_dir=str(tmp_path),
        run_on_start=False,
        tick_seconds=10,
        _sleep=sleep,
        _monotonic=monotonic,
        _max_iterations=9,  # 9 * 10s = 90s, nog niet aan de interval van 100s
    )
    assert calls == []


def test_runs_again_once_interval_elapses(tmp_path):
    calls = []
    monotonic, sleep, _state = _fake_clock(10)
    run_forever(
        job=lambda: calls.append(1),
        interval_seconds=100,
        data_dir=str(tmp_path),
        run_on_start=False,
        tick_seconds=10,
        _sleep=sleep,
        _monotonic=monotonic,
        _max_iterations=21,  # 10x om de 100s-drempel te halen, dan nogmaals 10x
    )
    assert calls == [1, 1]


def test_slow_job_does_not_inflate_the_interval(tmp_path):
    """`last_run` wordt gezet VOOR `job()` draait, niet erna: een job die
    zelf 50s "kost" (rechtstreeks de klok laten vooruitspringen) mag de
    volgende ronde niet 100s+50s later laten starten, maar gewoon ~100s na
    het BEGIN van de vorige ronde."""
    starts = []
    monotonic, sleep, state = _fake_clock(10)

    def slow_job():
        starts.append(state["t"])
        state["t"] += 50  # simuleert een job die 50s in beslag neemt

    run_forever(
        job=slow_job,
        interval_seconds=100,
        data_dir=str(tmp_path),
        run_on_start=False,
        tick_seconds=10,
        _sleep=sleep,
        _monotonic=monotonic,
        _max_iterations=20,  # 200s aan ticks, dus zonder drift precies 2 starts
    )
    assert len(starts) == 2
    assert starts[1] - starts[0] == 100  # niet 150 (100 + de 50s "duur" van de job)


def test_touches_heartbeat_file(tmp_path):
    monotonic, sleep, _state = _fake_clock(10)
    run_forever(
        job=lambda: None,
        interval_seconds=100,
        data_dir=str(tmp_path),
        run_on_start=False,
        tick_seconds=10,
        _sleep=sleep,
        _monotonic=monotonic,
        _max_iterations=1,
    )
    assert (tmp_path / "heartbeat").exists()


def test_failing_job_does_not_stop_the_loop(tmp_path):
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")

    monotonic, sleep, _state = _fake_clock(10)
    run_forever(
        job=flaky,
        interval_seconds=10,
        data_dir=str(tmp_path),
        run_on_start=True,
        tick_seconds=10,
        _sleep=sleep,
        _monotonic=monotonic,
        _max_iterations=2,
    )
    assert calls == [1, 1]
