"""Exact migration admission for the simulation release.
This module validates a Django migration plan; it never applies DDL.
A successful plan is not a substitute for independent restore evidence,
production authorization, or source/Passenger identity verification.
"""
from django.db.migrations.executor import MigrationExecutor

APP = "prop_firm"
BASELINE = (
    "0001_initial", "0002_provisional_profit_ledger", "0003_social_evidence",
    "0004_four_week_challenge", "0005_trade_origin_and_position_id",
    "0006_ten_plan_enrollment", "0007_equity_broker_source",
    "0008_prospect_contact_intake", "0009_plan1_invoice_gateway",
    "0010_reward_reserve_ledger",
)
UPGRADE = (
    "0011_plan1_account_default", "0012_simulation_account",
    "0013_restore_legacy_account_default", "0014_simulation_invoice_owner",
    "0015_simulation_identity", "0016_simulation_event",
    "0017_simulation_event_head",
)
TARGET = (APP, UPGRADE[-1])

class UpgradePlanDenied(RuntimeError):
    """No execution permitted for an unexpected state or dependency."""

def validate_upgrade_plan(applied, disk_migrations, plan, leaves):
    """Require exact fresh 0010 baseline and forward-only reviewed operations.

    applied/disk_migrations contain (app, name) pairs; plan contains
    ((app, name), backwards) pairs. Reject partial execution for independent
    reconciliation: never silently retry a non-transactional DDL failure.
    """
    expected_baseline={(APP,n) for n in BASELINE}
    expected_disk={(APP,n) for n in BASELINE+UPGRADE}
    actual_applied={key for key in applied if key[0]==APP}
    actual_disk={key for key in disk_migrations if key[0]==APP}
    if actual_applied != expected_baseline:
        raise UpgradePlanDenied("legacy migration baseline differs")
    if actual_disk != expected_disk or set(leaves)!={TARGET}:
        raise UpgradePlanDenied("unreviewed simulation migration graph")
    expected_plan=[((APP,n),False) for n in UPGRADE]
    if list(plan)!=expected_plan:
        raise UpgradePlanDenied("migration plan includes missing, unrelated or reverse operations")
    return tuple(key for key,_ in expected_plan)

def reviewed_upgrade_plan(connection):
    """Read the actual MariaDB recorder and graph using the current connection.

    Deliberately no migrate(), fake(), schema_editor(), or writes. The caller
    must independently verify the database identity, backup restoration, source
    fingerprints, live worker routing and authorization before any execution.
    """
    if connection.vendor!="mysql":
        raise UpgradePlanDenied("MariaDB/MySQL backend required")
    executor=MigrationExecutor(connection)
    executor.loader.check_consistent_history(connection)
    plan=executor.migration_plan([TARGET])
    return validate_upgrade_plan(
        executor.loader.applied_migrations,
        executor.loader.disk_migrations,
        [( (migration.app_label,migration.name), backwards) for migration,backwards in plan],
        executor.loader.graph.leaf_nodes(APP),
    )
