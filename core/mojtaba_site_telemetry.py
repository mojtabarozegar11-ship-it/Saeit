"""Safe, lossy intake of an EXISTING MojPlayWin private telemetry snapshot.

The central bot sees *catalogue capabilities*, not 103 executable bots.
No raw private logs, file paths, payloads, credentials, or payment state survive
normalization. A source digest is a change detector, NOT a signature.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
from .mojtaba_site_fleet import MPW_NAMED_ROBOTS, ZM_ROUTES, CANONICAL_BOT, SiteFleetError

SITES = tuple(ZM_ROUTES)
MASTER_IDS = ("master_gen64", "agent_gen65")
OTHER_IDS = ("worker_quality", "worker_management")
EXPECTED_IDS = frozenset(
    MASTER_IDS + OTHER_IDS
    + tuple("role_" + x for x in SITES)
    + tuple("robot_" + x for x in MPW_NAMED_ROBOTS)
    + tuple("module_" + str(i) for i in range(1, 78))
)
STATES = frozenset(("healthy", "loaded_only", "stale", "unknown", "failed", "degraded"))


def normalize_mpw_telemetry(snapshot, *, now=None):
    """Reject ambiguous identities and unprovable claims, retain aggregate only."""
    now = now or datetime.now(timezone.utc)
    if not isinstance(snapshot, dict) or snapshot.get("tenant") != "mojplaywin-main":
        raise SiteFleetError("MPW_TENANT_MISMATCH")
    if snapshot.get("source") != "private_cpanel_reports":
        raise SiteFleetError("MPW_PRIVATE_TELEMETRY_SOURCE_MISSING")
    try:
        at = datetime.fromisoformat(snapshot["captured_at"].replace("Z", "+00:00"))
        if at.tzinfo is None or not timedelta(0) <= now - at <= timedelta(minutes=20):
            raise ValueError("untrusted timestamp")
    except (TypeError, AttributeError, KeyError, ValueError) as e:
        raise SiteFleetError("MPW_TELEMETRY_STALE_OR_INVALID") from e
    items = snapshot.get("items")
    if not isinstance(items, list) or len(items) != len(EXPECTED_IDS):
        raise SiteFleetError("MPW_ALL_103_SLOTS_REQUIRED")
    seen, counts = set(), {state: 0 for state in STATES}
    module_import_only, functional = 0, 0
    for item in items:
        if not isinstance(item, dict):
            raise SiteFleetError("MPW_ITEM_TYPE_INVALID")
        ident, state = item.get("id"), item.get("state")
        if ident not in EXPECTED_IDS or ident in seen or state not in STATES:
            raise SiteFleetError("MPW_UNKNOWN_OR_DUPLICATE_SLOT")
        if item.get("source") != "cpanel_private_report":
            raise SiteFleetError("MPW_ITEM_PROVENANCE_UNVERIFIED")
        seen.add(ident)
        counts[state] += 1
        if ident.startswith("module_"):
            metrics = item.get("metrics") or {}
            if not isinstance(metrics, dict) or metrics.get("functional_execution_verified") is not False:
                raise SiteFleetError("MPW_MODULE_RUNTIME_PROOF_UNTRUSTED")
            if state == "healthy":
                raise SiteFleetError("MPW_LOADED_MODULE_CANNOT_BE_HEALTHY_WORKER")
            module_import_only += int(state == "loaded_only")
        else:
            functional += 0  # telemetry status alone never establishes a receipt
    if seen != EXPECTED_IDS:
        raise SiteFleetError("MPW_MISSING_SLOT_IDENTITY")
    raw = json.dumps(snapshot, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(raw) > 950_000:
        raise SiteFleetError("MPW_TELEMETRY_TOO_LARGE")
    return {
        "canonical_bot": CANONICAL_BOT, "tenant": "mojplaywin",
        "declared_slots": len(EXPECTED_IDS),
        "observed_health_labels": counts,
        "module_loaded_only_slots": module_import_only,
        "functional_executions_verified_by_import": functional,
        "source_snapshot_sha256": sha256(raw).hexdigest(),
        "source_is_cryptographically_authenticated": False,
        "migration_or_legacy_cleanup_approved": False,
        "customer_data_imported": False,
    }
