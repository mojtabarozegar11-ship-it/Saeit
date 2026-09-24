import pytest

from core.health_gate import RuntimeHealthGate


class Metrics:
    def __init__(self, failed=0, stale_running=0):
        self.failed = failed
        self.stale_running = stale_running


class StubObservability:
    def __init__(self, metrics):
        self.metrics = metrics
        self.calls = []

    def snapshot(self, stale_after_seconds):
        self.calls.append(stale_after_seconds)
        return self.metrics


def test_health_gate_is_ready_when_thresholds_are_clear():
    obs = StubObservability(Metrics())
    result = RuntimeHealthGate(obs).evaluate(
        stale_after_seconds=300, max_failed=0, max_stale=0
    )

    assert result.healthy is True
    assert result.ready is True
    assert result.reasons == ()
    assert obs.calls == [300]


def test_health_gate_blocks_failed_threshold():
    result = RuntimeHealthGate(
        StubObservability(Metrics(failed=1))
    ).evaluate(max_failed=0)

    assert result.healthy is False
    assert result.ready is False
    assert "failed task threshold exceeded" in result.reasons


def test_health_gate_blocks_stale_threshold():
    result = RuntimeHealthGate(
        StubObservability(Metrics(stale_running=2))
    ).evaluate(max_stale=1)

    assert result.healthy is False
    assert result.ready is False
    assert "stale running task threshold exceeded" in result.reasons


@pytest.mark.parametrize("kwargs", [
    {"max_failed": -1},
    {"max_stale": -1},
    {"max_failed": True},
    {"max_stale": "0"},
])
def test_health_gate_rejects_invalid_thresholds(kwargs):
    with pytest.raises(ValueError):
        RuntimeHealthGate(StubObservability(Metrics())).evaluate(**kwargs)
