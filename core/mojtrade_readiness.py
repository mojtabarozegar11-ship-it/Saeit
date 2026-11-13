"""Read-only operational evidence gates for the ONE Mojtaba.bot.ai trading module.

This is a snapshot of source-specific proofs, NOT a score invented from
commits, not a broker connection, and never an order / signal publisher.
"""
from __future__ import annotations

from django.utils import timezone

from core.management.commands.mojtrade_market_watch_export import fresh_canonical_drafts
from core.models import Agent, AgentTask, AuditLog
from core.mojtrade_signal_drafts import MarketWatchDraftError
from core.unified_bot_identity import BOT_CODE, MOJTRADE_DEMO_AUDIT_CAPABILITY


def _latest_canonical_demo(kind: str):
    return (
        AgentTask.objects.filter(
            agent__code=BOT_CODE, agent__active=True,
            action_type=MOJTRADE_DEMO_AUDIT_CAPABILITY,
            capability_code=MOJTRADE_DEMO_AUDIT_CAPABILITY,
            input_data__source_kind=kind,
        )
        .order_by("-created_at", "-pk")
        .first()
    )


def _audited_demo_task(task: AgentTask | None, action: str) -> bool:
    if task is None or task.status != "completed":
        return False
    output, inputs = task.output_data, task.input_data
    if not isinstance(output, dict) or not isinstance(inputs, dict):
        return False
    if output.get("verified_effect") is not True or output.get("orders") != 0:
        return False
    if output.get("profit_verified") is not False:
        return False
    if output.get("action_performed") != action:
        return False
    if not isinstance(inputs.get("source_sha256"), str):
        return False
    records = AuditLog.objects.filter(
        target_type="AgentTask", target_id=str(task.pk),
        actor_type="agent", actor_id=str(task.agent_id),
        action=(
            "mojtrade_demo_closed_deals_audited"
            if action == "canonical_ctrader_demo_deal_evidence_ingested"
            else "mojtrade_demo_two_source_statement_crosschecked"
        ),
    )
    if records.count() != 1:
        return False
    state = records.first().after_state
    if not isinstance(state, dict) or state.get("source_sha256") != inputs["source_sha256"]:
        return False
    if state.get("orders") != 0:
        return False
    if action == "canonical_ctrader_demo_deal_evidence_ingested":
        return (
            output.get("broker_statement_reconciled") is False
            and output.get("source_log_is_independently_authenticated") is False
            and isinstance(output.get("evidence"), dict)
            and output["evidence"].get("source_sha256") == inputs["source_sha256"]
        )
    return (
        output.get("two_unverified_exports_structurally_matched") is True
        and output.get("broker_statement_reconciled") is False
        and output.get("broker_connected") is False
        and state.get("broker_statement_authenticated") is False
    )


def trading_readiness_report(*, now=None) -> dict:
    """Return independently named release gates, never an invented 100%."""
    now = now or timezone.now()
    canonical = Agent.objects.filter(code=BOT_CODE, active=True).exists()
    watch = False
    watch_task_id = None
    if canonical:
        try:
            watch_task_id, _ = fresh_canonical_drafts(now=now)
            watch = True
        except (MarketWatchDraftError, ValueError, TypeError):
            pass

    demo = _latest_canonical_demo("ctrader_demo_audit_log") if canonical else None
    statement = _latest_canonical_demo("ctrader_demo_statement_crosscheck") if canonical else None
    demo_audited = _audited_demo_task(
        demo, "canonical_ctrader_demo_deal_evidence_ingested"
    )
    statement_audited = _audited_demo_task(
        statement, "canonical_ctrader_demo_statement_crosscheck_recorded"
    )
    linked = False
    if demo_audited and statement_audited:
        a, b = demo.input_data, statement.input_data
        linked = (
            a.get("source_sha256") == b.get("source_log_sha256")
            and a.get("account_alias") == b.get("account_alias")
            and a.get("symbol") == b.get("symbol")
            and demo.output_data.get("demo_trading_history", {}).get("mode") == "demo"
        )

    gates = {
        "canonical_bot_active_in_current_database": canonical,
        "fresh_canonical_private_watch_receipt": watch,
        "local_demo_closed_deal_log_audited": demo_audited,
        "local_two_unverified_demo_exports_matched_to_same_log": linked,
        # Local matching proves consistency of two extracts, NOT that the
        # exporting human and broker account were independently authenticated.
        "broker_authenticated_demo_execution_and_account": False,
        "canonical_approved_demo_order_control": False,
        "verified_customer_signal_delivery": False,
        "single_bot_live_cutover_and_legacy_retirement_verified": False,
        "production_trading_enabled": False,
        "settled_real_revenue_verified": False,
    }
    return {
        "schema": "mojtaba.bot.ai.mojtrade-readiness-v1",
        "owner": BOT_CODE,
        "read_only": True,
        "checked_at": now.isoformat(),
        "market_watch_task_id": watch_task_id,
        "demo_log_task_id": demo.pk if demo_audited else None,
        "statement_task_id": statement.pk if linked else None,
        "gates": gates,
        "local_demo_evidence_is_not_independently_authenticated": True,
        "public_signal_publication_authorized": False,
        "live_account_orders_authorized": False,
        "operational_completion_percent": None,
        "real_revenue_verified": False,
    }
