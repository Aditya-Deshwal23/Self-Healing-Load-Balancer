"""Bounded, in-memory fast-path telemetry and attenuation policy.

This module deliberately has no database or Elasticsearch dependency. It is
fed by HAProxy Runtime samples and returns recommendations to the durable
worker, which remains the only component allowed to mutate routing state.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass
class EWMA:
    alpha: float = 0.3
    value: float | None = None

    def update(self, sample_ms: float) -> float:
        if not isfinite(sample_ms) or sample_ms < 0:
            raise ValueError("latency sample must be a finite non-negative number")
        self.value = sample_ms if self.value is None else self.alpha * sample_ms + (1 - self.alpha) * self.value
        return self.value


@dataclass
class AttenuationState:
    weight: int = 100
    unhealthy_ticks: int = 0
    healthy_ticks: int = 0
    sample_count: int = 0


class FastPathController:
    """Dual-EWMA anomaly detection with hysteresis and a capacity guard."""

    def __init__(
        self,
        *,
        alpha: float = 0.3,
        baseline_alpha: float = 0.05,
        deviation_ratio: float = 2.5,
        error_rate_threshold: float = 0.20,
        unhealthy_ticks: int = 3,
        recovery_ticks: int = 8,
    ):
        if not 0 < alpha <= 1 or not isfinite(alpha):
            raise ValueError("alpha must be finite and in the interval (0, 1]")
        if not 0 < baseline_alpha <= 1 or not isfinite(baseline_alpha):
            raise ValueError("baseline alpha must be finite and in the interval (0, 1]")
        if not isfinite(deviation_ratio) or deviation_ratio <= 1:
            raise ValueError("deviation ratio must be finite and greater than 1")
        if not 0 <= error_rate_threshold <= 1 or not isfinite(error_rate_threshold):
            raise ValueError("error rate threshold must be finite and in the interval [0, 1]")
        if unhealthy_ticks < 1 or recovery_ticks < 1:
            raise ValueError("hysteresis tick counts must be positive")
        self.alpha = alpha
        self.baseline_alpha = baseline_alpha
        self.deviation_ratio = deviation_ratio
        self.error_rate_threshold = error_rate_threshold
        self.unhealthy_ticks_required = unhealthy_ticks
        self.recovery_ticks_required = recovery_ticks
        self.baselines: dict[str, EWMA] = {}
        self.current_latencies: dict[str, EWMA] = {}
        self.states: dict[str, AttenuationState] = {}

    def observe(self, key: str, *, latency_ms: float, error_rate: float, active_capacity: int, total_capacity: int) -> int | None:
        if not key or not key.strip():
            raise ValueError("observation key cannot be empty")
        if not isfinite(error_rate) or not 0 <= error_rate <= 1:
            raise ValueError("error rate must be finite and in the interval [0, 1]")
        if total_capacity < 1 or active_capacity < 0 or active_capacity > total_capacity:
            raise ValueError("capacity must satisfy total >= 1 and 0 <= active <= total")
        baseline = self.baselines.setdefault(key, EWMA(alpha=self.baseline_alpha))
        current = self.current_latencies.setdefault(key, EWMA(alpha=self.alpha))
        state = self.states.setdefault(key, AttenuationState())
        state.sample_count += 1
        baseline_value = baseline.update(latency_ms)
        current_value = current.update(latency_ms)
        latency_anomaly = current_value > baseline_value * self.deviation_ratio
        unhealthy = (
            state.sample_count >= 20
            and (
                (latency_anomaly and current_value - baseline_value > 15.0)
                or error_rate >= self.error_rate_threshold
            )
        )
        if unhealthy:
            state.unhealthy_ticks += 1
            state.healthy_ticks = 0
            if state.unhealthy_ticks < self.unhealthy_ticks_required:
                return None
            if active_capacity <= 0 or (active_capacity - 1) / total_capacity < (2 / 3):
                return None
            state.weight = 20 if state.weight > 20 else state.weight
            return state.weight
        state.unhealthy_ticks = 0
        state.healthy_ticks += 1
        if state.healthy_ticks < self.recovery_ticks_required:
            return None
        state.healthy_ticks = 0
        previous_weight = state.weight
        if state.weight < 25:
            state.weight = 25
        elif state.weight < 50:
            state.weight = 50
        elif state.weight < 100:
            state.weight = 100
        return state.weight if state.weight != previous_weight else None
