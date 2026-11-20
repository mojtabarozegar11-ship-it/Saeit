"""Contract tests for the pure MOJ PROP staging preflight."""

import sys
from pathlib import Path

# The source-sync bundle is intentionally outside the production import root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mojprop_staging_preflight import (  # noqa: E402
    MOJPROP_DB_ALIAS,
    MOJPROP_ROUTER_IMPORT,
    evaluate_staging_preflight,
)


def _ready_config():
    return {
        "MPW_MOJPROP_DB_ALIAS_ENABLED": True,
        "DATABASES": {
            "default": {"NAME": "factory"},
            MOJPROP_DB_ALIAS: {"NAME": "mojprop"},
        },
        "DATABASE_ROUTERS": (MOJPROP_ROUTER_IMPORT,),
        "MPW_MOJPROP_IDENTITY_DIGEST_SECRET": "staging-only-secret",
        "MPW_MOJPROP_RECONCILIATION_SOURCE_ALIAS": "default",
        "MPW_MOJPROP_PLAN1_ROUTE_ENABLED": False,
        "MPW_MOJPROP_PLAN1_LIVE_INVOICE_ENABLED": False,
        "MPW_MOJPROP_ENGLISH_ROUTE_ENABLED": False,
    }


def test_closed_defaults_are_not_ready():
    result = evaluate_staging_preflight({})
    assert result.ready is False
    assert "MOJ PROP database alias switch is not enabled for staging" in result.blockers
    assert "DATABASES[mojprop] is not configured" in result.blockers
    assert "fail-closed MojPropDatabaseRouter is not wired in DATABASE_ROUTERS" in result.blockers
    assert "identity digest secret is not configured for staging" in result.blockers


def test_ready_requires_both_privilege_evidence_inputs():
    result = evaluate_staging_preflight(_ready_config())
    assert result.ready is False
    assert "migration administrator privilege evidence is missing" in result.blockers
    assert "runtime DML privilege evidence is missing" in result.blockers

    result = evaluate_staging_preflight(
        _ready_config(),
        migration_admin_verified=True,
        runtime_dml_verified=True,
    )
    assert result.ready is True
    assert result.blockers == ()


def test_reconciliation_cannot_target_mojprop():
    config = _ready_config()
    config["MPW_MOJPROP_RECONCILIATION_SOURCE_ALIAS"] = MOJPROP_DB_ALIAS
    result = evaluate_staging_preflight(
        config,
        migration_admin_verified=True,
        runtime_dml_verified=True,
    )
    assert result.ready is False
    assert "reconciliation source alias cannot equal mojprop" in result.blockers


def test_public_mojprop_route_flags_remain_closed():
    config = _ready_config()
    config["MPW_MOJPROP_PLAN1_ROUTE_ENABLED"] = True
    result = evaluate_staging_preflight(
        config,
        migration_admin_verified=True,
        runtime_dml_verified=True,
    )
    assert result.ready is False
    assert "MPW_MOJPROP_PLAN1_ROUTE_ENABLED must remain false during staging preflight" in result.blockers
