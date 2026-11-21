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



def normalize_zomorod_registry(registry, *, captured_at_utc, now=None):
    """Normalize cPanel's immutable SQLite aggregate WITHOUT copying its DB.

    Existing site's deploy/mojtaba_live_topology_readonly.py produces this
    redacted shape. It cannot prove that 11 processes ran or generated output.
    """
    now = now or datetime.now(timezone.utc)
    if not isinstance(registry, dict) or registry.get("state") != "source_registry_snapshot_only":
        raise SiteFleetError("ZM_PRIVATE_REGISTRY_SOURCE_MISSING")
    if registry.get("read_only_immutable") is not True:
        raise SiteFleetError("ZM_REGISTRY_NOT_READ_ONLY")
    if registry.get("database_state_proves_live_workers") is not False:
        raise SiteFleetError("ZM_LIVE_WORKER_STATUS_UNTRUSTED")
    try:
        at = datetime.fromisoformat(captured_at_utc.replace("Z", "+00:00"))
        if at.tzinfo is None or not timedelta(0) <= now - at <= timedelta(minutes=20):
            raise ValueError("stale or future")
    except (ValueError, TypeError, AttributeError):
        raise SiteFleetError("ZM_REGISTRY_TIMESTAMP_INVALID")
    rows = registry.get("agent_roles")
    if not isinstance(rows, list) or len(rows) > len(ZM_ROUTES):
        raise SiteFleetError("ZM_AGENT_ROWS_UNSAFE")
    known, enabled = set(), 0
    for row in rows:
        if not isinstance(row, dict) or row.get("code") not in ZM_ROUTES:
            raise SiteFleetError("ZM_UNEXPECTED_SITE_ROLE")
        if row["code"] in known or type(row.get("enabled")) is not bool:
            raise SiteFleetError("ZM_DUPLICATE_OR_INVALID_ROLE")
        known.add(row["code"])
        enabled += int(row["enabled"])
    if registry.get("known_roles_found") != len(known):
        raise SiteFleetError("ZM_ROLE_COUNT_MISMATCH")
    if type(registry.get("unknown_code_records")) is not int or registry["unknown_code_records"] < 0:
        raise SiteFleetError("ZM_UNKNOWN_ROLE_COUNT_MISSING")
    raw = json.dumps(registry, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(raw) > 50_000:
        raise SiteFleetError("ZM_REGISTRY_TOO_LARGE")
    return {
        "canonical_bot": CANONICAL_BOT, "tenant": "zomorodmelal",
        "known_roles_observed": len(known),
        "declared_roles": len(ZM_ROUTES),
        "enabled_role_records": enabled,
        "other_legacy_codes": registry["unknown_code_records"],
        "registry_complete": len(known) == len(ZM_ROUTES)
                              and registry["unknown_code_records"] == 0,
        "source_snapshot_sha256": sha256(raw).hexdigest(),
        "source_is_cryptographically_authenticated": False,
        "actual_worker_executions_verified_by_import": 0,
        "legacy_retirement_approved": False,
        "historical_database_deleted": False,
    }
