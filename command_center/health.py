"""Pure, fail-closed health aggregation; no network or database side effects."""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Iterable, Optional

VALID_STATES = frozenset({"healthy", "degraded", "failed", "stale", "unknown", "unauthorized"})
SEVERITY = {"healthy": 0, "degraded": 1, "stale": 2, "unknown": 3, "unauthorized": 4, "failed": 5}

@dataclass(frozen=True)
class Observation:
    component: str
    state: str
    observed_at: datetime
    source: str
    evidence_id: str
    detail: str = ""

    def __post_init__(self):
        if self.state not in VALID_STATES:
            raise ValueError("Unsupported health state")
        if self.observed_at.tzinfo is None:
            raise ValueError("Timezone-aware observed_at required")
        if not self.component or not self.source or not self.evidence_id:
            raise ValueError("component, source and evidence_id are mandatory")

def effective_state(item: Observation, now: Optional[datetime] = None, max_age_seconds: int = 300) -> str:
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Timezone-aware now required")
    age = (now - item.observed_at).total_seconds()
    if age < -60 or age > max_age_seconds:
        return "stale"
    return item.state

def summarize(observations: Iterable[Observation], now: Optional[datetime] = None) -> dict:
    """Never equate missing evidence to healthy; preserve source traceability."""
    items = list(observations)
    now = now or datetime.now(timezone.utc)
    if not items:
        return {"overall": "unknown", "components": [], "total": 0}
    components = [
        {"component": o.component, "state": effective_state(o, now),
         "reported_state": o.state, "observed_at": o.observed_at.isoformat(),
         "source": o.source, "evidence_id": o.evidence_id, "detail": o.detail}
        for o in items
    ]
    return {"overall": max((x["state"] for x in components), key=SEVERITY.__getitem__),
            "components": components, "total": len(components)}

def progress(completed: int, total: int, verified: int) -> dict:
    """Progress is acceptance-criterion based, never derived from execution count."""
    if total < 0 or completed < 0 or verified < 0 or verified > completed or completed > total:
        raise ValueError("Invalid progress counters")
    return {"total": total, "completed": completed, "verified": verified,
            "verified_percent": round(100 * verified / total, 2) if total else None,
            "unverified": completed - verified}
