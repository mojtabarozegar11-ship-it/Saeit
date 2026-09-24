from dataclasses import dataclass
from decimal import Decimal

from .observability import RuntimeObservability


@dataclass(frozen=True)
class HealthResult:
    healthy: bool
    ready: bool
    reasons: tuple


class RuntimeHealthGate:
    """Read-only health/readiness gate for controlled production execution."""

    def __init__(self, observability=None):
        self.observability = observability or RuntimeObservability()

    def evaluate(self, *, stale_after_seconds=900, max_failed=0, max_stale=0):
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in (max_failed, max_stale)
        ):
            raise ValueError("health thresholds must be non-negative integers")

        metrics = self.observability.snapshot(stale_after_seconds)
        reasons = []
        if metrics.failed > max_failed:
            reasons.append("failed task threshold exceeded")
        if metrics.stale_running > max_stale:
            reasons.append("stale running task threshold exceeded")

        healthy = not reasons
        return HealthResult(
            healthy=healthy,
            ready=healthy,
            reasons=tuple(reasons),
        )
