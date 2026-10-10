"""Read-only, evidence-linked view model for the command center UI."""
from datetime import datetime, timezone
from typing import Iterable, Mapping
from .health import Observation, summarize, progress

def build_overview(observations: Iterable[Observation], workstreams: Mapping[str, Mapping[str, int]], now: datetime = None) -> dict:
    now = now or datetime.now(timezone.utc)
    health = summarize(observations, now)
    streams = {}
    for name, counters in workstreams.items():
        if not name:
            raise ValueError("Workstream name required")
        streams[name] = progress(counters["completed"], counters["total"], counters["verified"])
    return {"generated_at": now.isoformat(), "health": health, "workstreams": streams,
            "data_quality": {"observations": health["total"],
                             "unknown_or_stale": sum(x["state"] in ("unknown", "stale") for x in health["components"])},
            "live_connected": False}
