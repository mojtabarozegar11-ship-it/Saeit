"""Hard, read-only commercial admission gate for new English Starter30 invoices.

A successful wallet/RPC preflight is NOT contract compliance or funded reward
settlement capacity. Fail closed on stale 32%/70:30 historical policy, absent
effective evaluator, incomplete approved rules, or missing externally reviewed
reserve and real disbursement evidence.

This module never emails, writes a database, signs, transfers, or trades.
All hold reasons are stable machine codes; no credentials/evidence refs leaked.
Existing historical paid invoices/refunds MUST be reconciled separately rather
than denied by the new-buyer admission gate.
"""
from __future__ import annotations

from decimal import Decimal
import re

from django.conf import settings

from .simulation_policy import SIMULATION_POLICY


class Starter30PaidAdmissionHold(ValueError):
    """Current source and attested business capacity cannot sell Starter30."""


_EVIDENCE_REF_PATTERN = re.compile(r"[A-Za-z0-9._:/-]{16,128}\Z")
_OWNER_GATES = (
    ("MPW_MOJPROP_PAID_RULES_FINALLY_APPROVED", "accepted_paid_rules_not_approved"),
    # 50% best-day consistency remains a proposal; generic terms approval is
    # insufficient. Only explicit, separately evidenced owner adoption may
    # authorize this scoring condition for NEW customer invoices.
    ("MPW_MOJPROP_BEST_DAY_50_FINALLY_APPROVED", "best_day_50_not_approved"),
    ("MPW_MOJPROP_WRITTEN_PAID_TERMS_VERIFIED", "accepted_terms_not_verified"),
    ("MPW_MOJPROP_QUALIFIED_PAYOUT_RESERVE_VERIFIED", "real_reward_reserve_unverified"),
    ("MPW_MOJPROP_REAL_REWARD_SETTLEMENT_VERIFIED", "real_payout_rail_unverified"),
)
_SETTLEMENT_MODES = frozenset(("manual_owner", "automatic_provider"))


_EXPECTED_POLICY = (
    ("starting_balance_usd", Decimal("1000")),
    ("challenge_window_days", 60),
    ("daily_loss_limit_pct", Decimal("6")),
    ("max_risk_per_trade_pct", Decimal("3")),
    ("max_open_risk_pct", Decimal("4")),
    ("canonical_best_day_share_pct", Decimal("50")),
    ("trader_eligible_profit_share_pct", Decimal("100")),
    ("company_eligible_profit_share_pct", Decimal("0")),
    ("first_payout_min_activity_days", 14),
    ("subsequent_payout_interval_days", 14),
    ("minimum_payout_request_usd", Decimal("10")),
    ("transfer_network_fees_paid_by_company", True),
    ("entry_fee_refund_with_first_successful_profit_withdrawal", True),
)
_EFFECTIVE_SCORER = (
    ("best_day_share_pct", Decimal("50")),
    ("trader_profit_share_pct", Decimal("100")),
    ("company_profit_share_pct", Decimal("0")),
    ("max_daily_loss_pct", Decimal("6")),
    ("order_risk_pct", Decimal("3")),
    ("aggregate_risk_pct", Decimal("4")),
    ("completion_deadline_days", 60),
    ("account_mode", "simulated"),
    ("payout_mode", "real_performance_reward"),
    ("real_orders_enabled", False),
)


def paid_admission_defects(*, check_attestations: bool = True) -> tuple[str, ...]:
    """Deterministic proof checklist, without requesting customer/payment data."""
    defects = []

    for name, expected in _EXPECTED_POLICY:
        if getattr(SIMULATION_POLICY, name, None) != expected:
            defects.append("new_offer_" + name + "_mismatch")

    # Main source historically has no legacy rules.py, while the effective
    # cPanel runtime DOES, and it still computes 32% consistency / 70:30 cash.
    # Absent source or import drift must block billing, not be overlooked.
    try:
        from prop_firm.rules import POLICY as effective
    except (ImportError, AttributeError):
        defects.append("effective_scoring_contract_unavailable")
    else:
        for name, expected in _EFFECTIVE_SCORER:
            if getattr(effective, name, None) != expected:
                defects.append("effective_scorer_" + name + "_mismatch")
        if getattr(effective, "version", None) != SIMULATION_POLICY.contract_version:
            defects.append("scoring_contract_version_mismatch")

    try:
        from .simulation_payout import PAYOUT_PERCENT
    except (ImportError, AttributeError):
        defects.append("verified_profit_commitment_calculator_unavailable")
    else:
        if PAYOUT_PERCENT != 100:
            defects.append("verified_profit_commitment_not_100_percent")

    if check_attestations:
        settlement_mode = getattr(settings, "MPW_MOJPROP_REWARD_SETTLEMENT_MODE", "")
        if settlement_mode not in _SETTLEMENT_MODES:
            defects.append("reward_settlement_mode_invalid")
        for name, reason in _OWNER_GATES:
            if getattr(settings, name, False) is not True:
                defects.append(reason)
        reference = getattr(settings, "MPW_MOJPROP_PAID_TERMS_EVIDENCE_REF", "")
        if (type(reference) is not str
                or _EVIDENCE_REF_PATTERN.fullmatch(reference) is None):
            defects.append("private_paid_terms_evidence_reference_missing")
        reserve_ref = getattr(settings, "MPW_MOJPROP_REWARD_RESERVE_EVIDENCE_REF", "")
        if (type(reserve_ref) is not str
                or _EVIDENCE_REF_PATTERN.fullmatch(reserve_ref) is None):
            defects.append("private_reward_reserve_evidence_reference_missing")
        rail_ref = getattr(settings, "MPW_MOJPROP_REWARD_SETTLEMENT_EVIDENCE_REF", "")
        if (type(rail_ref) is not str
                or _EVIDENCE_REF_PATTERN.fullmatch(rail_ref) is None):
            defects.append("private_real_settlement_evidence_reference_missing")

    return tuple(dict.fromkeys(defects))


def _has_unique_recipient_index(constraints: dict) -> bool:
    """Require single-column exact uniqueness, not only unique txid or a pair."""
    if type(constraints) is not dict:
        return False
    return any(
        record.get("unique") is True
        and record.get("columns") == ["recipient"]
        for record in constraints.values()
        if type(record) is dict
    )


def require_live_unique_invoice_recipient_schema() -> None:
    """Read-only SHOW/introspection on the EFFECTIVE isolated payment database.

    This runs only after the source, owner-terms, actual reserve and payout-rail
    holds pass. The new GitHub ORM field `unique=True` or an un-applied
    migration file is NEVER proof of a unique index on cPanel MariaDB.
    """
    try:
        from config.mojprop_db_router import MOJPROP_DB_ALIAS
        from django.db import connections
        from prop_firm.models import PropSimulationPayment

        conn = connections[MOJPROP_DB_ALIAS]
        with conn.cursor() as cursor:
            table_name = PropSimulationPayment._meta.db_table
            constraints = conn.introspection.get_constraints(cursor, table_name)
            if getattr(settings, "MPW_MOJPROP_SINGLE_RECEIVER_MODE", False) is True:
                columns = {
                    column.name
                    for column in conn.introspection.get_table_description(cursor, table_name)
                }
                if "payer_hex41" not in columns:
                    raise Starter30PaidAdmissionHold(
                        "single-receiver mode requires payer-wallet binding column"
                    )
                # One receive-only wallet is intentional; payer binding,
                # exact amount, dual-RPC finality and unique txid provide attribution.
                return
    except Exception as exc:
        raise Starter30PaidAdmissionHold(
            "Starter30 payment database uniqueness cannot be verified"
        ) from exc
    if not _has_unique_recipient_index(constraints):
        raise Starter30PaidAdmissionHold(
            "Starter30 requires a UNIQUE receiving address for every invoice"
        )



# Preserve historical customer records. An applied migration name does not
# establish that its legacy tables exist on the *isolated* MojProp database.
_LEGACY_INITIAL_MIGRATION = "0001_initial"
_LEGACY_SOURCE_TABLES = frozenset((
    "prop_firm_proptrader",
    "prop_firm_propaccount",
    "prop_firm_propexecution",
    "prop_firm_propequityobservation",
    "prop_firm_propdecisionlog",
))
_REQUIRED_ISOLATED_MIGRATIONS = frozenset((
    "0001_simulation_isolation",
    "0002_starter30_payment",
    "0003_payment_table_router_alignment",
    "0004_simulation_payout_commitment",
    "0005_optional_payer_wallet",
    "0006_unique_invoice_receivers",
))


def _isolated_migration_lineage_defects(
    *,
    applied_names: set[str],
    physical_tables: set[str],
) -> tuple[str, ...]:
    """Pure detector: history must match the schema; never repair history here."""
    if (type(applied_names) is not set
            or type(physical_tables) is not set
            or any(type(n) is not str for n in applied_names | physical_tables)):
        return ("isolated_migration_provenance_unavailable",)
    reasons = []
    if not _REQUIRED_ISOLATED_MIGRATIONS <= applied_names:
        reasons.append("isolated_native_trx_unique_receiver_migration_incomplete")
    if (_LEGACY_INITIAL_MIGRATION in applied_names
            and not _LEGACY_SOURCE_TABLES <= physical_tables):
        reasons.append("historical_migrations_not_backed_by_isolated_schema")
    if ("prop_firm_propsimulationpayment" not in physical_tables):
        reasons.append("isolated_native_trx_payment_table_missing")
    return tuple(reasons)


def require_live_isolated_migration_lineage() -> None:
    """Reject new paid invoices on orphaned historical/isolated DB migration state.

    Read-only physical-table introspection and a SELECT on the existing
    isolated django_migrations table. No MigrationExecutor, --fake, DDL, DML,
    migrations or restore operation. The UNIQUE index is checked by the
    separately required physical recipient schema gate.
    """
    try:
        from config.mojprop_db_router import MOJPROP_DB_ALIAS
        from django.db import connections

        conn = connections[MOJPROP_DB_ALIAS]
        with conn.cursor() as cursor:
            tables = set(conn.introspection.table_names(cursor))
            cursor.execute(
                "SELECT name FROM django_migrations WHERE app = %s",
                ["prop_firm"],
            )
            applied = {row[0] for row in cursor.fetchall()}
    except Exception as exc:
        raise Starter30PaidAdmissionHold(
            "Starter30 isolated migration history cannot be verified"
        ) from exc
    issues = _isolated_migration_lineage_defects(
        applied_names=applied, physical_tables=tables
    )
    if issues:
        raise Starter30PaidAdmissionHold(
            "Starter30 requires a coherent isolated migration and payment schema"
        )


def require_paid_admission_readiness() -> None:
    """Reject a NEW invoice before touching an identity, DB or blockchain."""
    errors = paid_admission_defects()
    if errors:
        raise Starter30PaidAdmissionHold(
            "Starter30 new payment admission is on hold until complete "
            "approved rules, a 100% trader reward engine, and verified "
            "reward funding plus manual-owner or provider settlement proof agree"
        )