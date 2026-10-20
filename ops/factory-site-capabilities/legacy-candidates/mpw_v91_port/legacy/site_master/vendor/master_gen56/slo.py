from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class SLODecision:
    allowed:bool; reasons:tuple[str,...]

class SLOGuard:
    """Gen55: fail-closed release/runtime guard for declared error-rate and p95 latency objectives."""
    def check(self,telemetry,max_error_rate=1.0,max_p95_ms=float('inf')):
        reasons=[]
        for name,row in telemetry.items():
            count=int(row.get('count',0)); failures=int(row.get('failures',0)); p95=float(row.get('p95_ms',0))
            if count and failures/count>float(max_error_rate): reasons.append(f'{name}:error_rate')
            if p95>float(max_p95_ms): reasons.append(f'{name}:p95')
        return SLODecision(not reasons,tuple(sorted(reasons)))
