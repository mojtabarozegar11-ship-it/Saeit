"""Evidence-first operating review for the Zomorod/MojPlayWin business.

The review is deterministic and deliberately makes no external changes.  A
missing sensor is *unknown*, never healthy, successful, or zero revenue.
Priorities are management heuristics, not empirical probabilities.
"""

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class Finding:
    code: str
    department: str
    priority: int
    observation: str
    action: str
    execution: str = "autonomous_diagnostic"

    def as_dict(self):
        return {
            "code": self.code,
            "department": self.department,
            "priority": self.priority,
            "observation": self.observation,
            "action": self.action,
            "execution": self.execution,
        }


def observed(value: Any, source: str, captured_at: str) -> dict:
    if not source or not captured_at:
        raise ValueError("Observed metrics must carry a source and timestamp")
    return {"state": "observed", "value": value, "source": source, "captured_at": captured_at}


def unknown(reason: str) -> dict:
    return {"state": "unknown", "value": None, "reason": reason}


def _value(metrics: Mapping[str, dict], key: str):
    metric = metrics.get(key, {})
    if metric.get("state") != "observed" or not metric.get("source") or not metric.get("captured_at"):
        return None
    return metric.get("value")


def review_business(metrics: Mapping[str, dict]) -> dict:
    """Diagnose the constraint, keep evidence and action authority separate."""
    findings = []

    def add(code, department, priority, observation, action, execution="autonomous_diagnostic"):
        findings.append(Finding(code, department, priority, observation, action, execution))

    blocked = _value(metrics, "blocked_tasks")
    queued = _value(metrics, "queued_tasks")
    if isinstance(blocked, int) and blocked > 0:
        add("blocked_work", "operations", 95,
            f"{blocked} blocked tasks in the operational database",
            "Classify each blocker by missing evidence, capability, or owner approval; do not release approvals automatically")
    if isinstance(queued, int) and queued > 0:
        add("execution_backlog", "operations", 82,
            f"{queued} queued tasks, without verified throughput or age measurements",
            "Measure queue age and completed units by stage before changing worker concurrency")

    valid_market = _value(metrics, "independently_validated_market")
    if valid_market is None:
        add("market_evidence_unknown", "strategy", 89,
            "Independent buyer-demand and competitor evidence is not connected",
            "Gather attributable customer interviews, paid tests, or public third-party market evidence")
    elif valid_market is False:
        add("market_evidence_missing", "strategy", 90,
            "Connected market evidence does not yet validate an offer",
            "Test a specific buyer problem and willingness to pay before scaling")

    active = _value(metrics, "active_products")
    orders = _value(metrics, "orders")
    if isinstance(active, int) and active > 0 and orders == 0:
        add("no_recorded_orders", "sales", 87,
            f"{active} active products but no orders in the connected database",
            "Audit checkout, source traffic, offer quality and conversion; check other sales systems separately")
    elif active == 0:
        add("no_active_catalog", "sales", 85,
            "No active products in the connected database",
            "Verify product completeness and secure delivery before activating an approved listing")

    if _value(metrics, "verified_collected_cash") is None:
        add("cash_unverified", "finance", 93,
            "Settled funds were not independently reconciled",
            "Reconcile payment provider, payment reference, ledger and delivery by currency; do not infer revenue from orders")

    if _value(metrics, "accepted_factory_products") is None:
        add("factory_quality_unknown", "factory", 88,
            "Independent end-to-end factory acceptance is not connected",
            "Connect build, QA, specialist approval, repair and delivery receipts per product")

    if _value(metrics, "site_health") is None:
        add("site_health_unknown", "technology", 76,
            "No timestamped, authenticated multi-site health evidence is connected",
            "Collect read-only HTTP and runtime health checks, then correlate with deployment revisions")

    pending = _value(metrics, "pending_approvals")
    if isinstance(pending, int) and pending > 0:
        add("owner_decisions", "governance", 74,
            f"{pending} decisions await recorded approval",
            "Present the exact scope, risk, evidence, expiry and rollback plan to the owner",
            "owner_approval")

    findings.sort(key=lambda finding: (-finding.priority, finding.code))
    unknown_metrics = sorted(key for key in metrics if _value(metrics, key) is None)
    return {
        "framework": "PDCA + Theory of Constraints + evidence-gated unit economics",
        "status": "needs_evidence" if unknown_metrics else "observed",
        "unknown_metrics": unknown_metrics,
        "findings": [finding.as_dict() for finding in findings],
        "next_constraint": findings[0].code if findings else None,
        "execution_policy": {
            "automatic": "read-only diagnosis and authorized reversible internal work",
            "owner_gate": "money, contracts, identity, production release, irreversible or legally sensitive action",
            "success_metric": "independently_verified_collected_cash_and_customer_outcome",
        },
    }
