import pytest

from shlb_api.fastpath import EWMA, FastPathController


def test_ewma_uses_bounded_alpha():
    ewma = EWMA(alpha=0.3)
    assert ewma.update(100) == 100
    assert ewma.update(200) == 130


def test_fast_path_requires_hysteresis_and_preserves_capacity():
    controller = FastPathController(unhealthy_ticks=3)
    for _ in range(19):
        assert controller.observe("checkout/inst-a", latency_ms=100, error_rate=0, active_capacity=3, total_capacity=3) is None
    for _ in range(2):
        assert controller.observe("checkout/inst-a", latency_ms=1000, error_rate=0, active_capacity=3, total_capacity=3) is None
    assert controller.observe("checkout/inst-a", latency_ms=1000, error_rate=0, active_capacity=3, total_capacity=3) == 20
    assert controller.observe("checkout/inst-a", latency_ms=1000, error_rate=0, active_capacity=2, total_capacity=3) is None


def test_fast_path_recovers_in_stages_after_cooldown():
    controller = FastPathController(unhealthy_ticks=1, recovery_ticks=2)
    for _ in range(19):
        controller.observe("checkout/inst-a", latency_ms=100, error_rate=0, active_capacity=3, total_capacity=3)
    assert controller.observe("checkout/inst-a", latency_ms=1000, error_rate=0, active_capacity=3, total_capacity=3) == 20
    assert controller.observe("checkout/inst-a", latency_ms=100, error_rate=0, active_capacity=3, total_capacity=3) is None
    assert controller.observe("checkout/inst-a", latency_ms=100, error_rate=0, active_capacity=3, total_capacity=3) == 25
    assert controller.observe("checkout/inst-a", latency_ms=1, error_rate=0, active_capacity=3, total_capacity=3) is None
    assert controller.observe("checkout/inst-a", latency_ms=1, error_rate=0, active_capacity=3, total_capacity=3) == 50
    assert controller.observe("checkout/inst-a", latency_ms=1, error_rate=0, active_capacity=3, total_capacity=3) is None
    assert controller.observe("checkout/inst-a", latency_ms=1, error_rate=0, active_capacity=3, total_capacity=3) == 100


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"alpha": 0}, "alpha"),
        ({"alpha": 1.1}, "alpha"),
        ({"deviation_ratio": 1}, "deviation"),
        ({"unhealthy_ticks": 0}, "tick"),
    ],
)
def test_controller_rejects_invalid_configuration(kwargs, message):
    with pytest.raises(ValueError, match=message):
        FastPathController(**kwargs)


def test_observe_rejects_invalid_samples_and_capacity():
    controller = FastPathController()
    with pytest.raises(ValueError, match="key"):
        controller.observe("", latency_ms=1, error_rate=0, active_capacity=1, total_capacity=1)
    with pytest.raises(ValueError, match="error rate"):
        controller.observe("node", latency_ms=1, error_rate=2, active_capacity=1, total_capacity=1)
    with pytest.raises(ValueError, match="capacity"):
        controller.observe("node", latency_ms=1, error_rate=0, active_capacity=2, total_capacity=1)
    with pytest.raises(ValueError, match="finite"):
        controller.observe("node", latency_ms=float("nan"), error_rate=0, active_capacity=1, total_capacity=1)


def test_observations_are_isolated_by_key():
    controller = FastPathController(unhealthy_ticks=1)
    for _ in range(19):
        controller.observe("a", latency_ms=100, error_rate=0, active_capacity=3, total_capacity=3)
    assert controller.observe("a", latency_ms=1000, error_rate=0, active_capacity=3, total_capacity=3) == 20
    assert controller.observe("b", latency_ms=1, error_rate=0, active_capacity=3, total_capacity=3) is None
    assert controller.states["a"].weight == 20
    assert controller.states["b"].weight == 100
