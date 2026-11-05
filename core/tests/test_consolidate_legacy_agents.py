import io
import json

from django.core.management import call_command
from django.test import TestCase
from django.contrib.auth import get_user_model

from core.economic_tool_pack import revenue_verify
from core.models import Agent, AgentTask, AuditLog, LedgerEntry, Order


class ConsolidateLegacyAgentsTests(TestCase):
    def setUp(self):
        self.legacy, _ = Agent.objects.update_or_create(
            code="newsletter-world-watch",
            defaults={"name": "Legacy newsletter watcher",
                      "mission": "Former split watcher", "active": True},
        )
        self.busy, _ = Agent.objects.update_or_create(
            code="income-legacy-sales",
            defaults={"name": "Busy old worker", "mission": "Historical", "active": True},
        )
        AgentTask.objects.create(agent=self.busy, action_type="old_job", status="blocked")
        self.master, _ = Agent.objects.update_or_create(
            code="economic-master-agent",
            defaults={"name": "Master", "mission": "Orchestrate", "active": True},
        )
        self.unknown, _ = Agent.objects.update_or_create(
            code="site-purchase-delivery",
            defaults={"name": "Delivery", "mission": "Fulfil orders", "active": True},
        )

    def run_command(self, *options):
        output = io.StringIO()
        call_command("consolidate_legacy_agents", *options, stdout=output)
        return json.loads(output.getvalue())

    def test_preview_never_modifies_agents(self):
        result = self.run_command()
        self.legacy.refresh_from_db()
        assert self.legacy.active
        decisions = {row["code"]: row["decision"] for row in result["agents"]}
        assert decisions[self.legacy.code] == "retire_safe"
        assert decisions[self.busy.code] == "hold_for_dependency"
        assert decisions[self.master.code] == "retain_required"
        assert decisions[self.unknown.code] == "review_live_outcomes"
        assert AuditLog.objects.filter(action="legacy_agent_retired").count() == 0

    def test_apply_deactivates_only_provably_safe_legacy_preserving_history(self):
        AgentTask.objects.create(agent=self.legacy, action_type="old_review", status="completed")
        result = self.run_command("--apply")
        self.legacy.refresh_from_db()
        self.busy.refresh_from_db()
        self.master.refresh_from_db()
        self.unknown.refresh_from_db()
        assert not self.legacy.active
        assert self.busy.active
        assert self.master.active
        assert self.unknown.active
        assert AgentTask.objects.filter(agent=self.legacy, status="completed").exists()
        assert result["summary"]["retired_now"] >= 1
        assert AuditLog.objects.filter(
            action="legacy_agent_retired", target_id=str(self.legacy.pk)
        ).count() == 1
        previous_events = AuditLog.objects.filter(action="legacy_agent_retired").count()

        # Re-running an idempotent cleanup cannot erase the past or create a
        # second retirement event.
        second = self.run_command("--apply")
        assert second["summary"]["retired_now"] == 0
        assert AuditLog.objects.filter(action="legacy_agent_retired").count() == previous_events


class RevenueEvidenceTests(TestCase):
    def test_payment_and_settlement_rows_cannot_be_mistaken_for_proven_cash(self):
        user = get_user_model().objects.create_user(username="agent_revenue_audit")
        order = Order.objects.create(customer=user, total="10.00", currency="TRX", status="paid")
        for kind in ("payment", "settlement"):
            LedgerEntry.objects.create(
                order=order, entry_type=kind, amount="10.00", currency="TRX",
                reference=f"audit:{kind}:1", metadata={"unverified": True},
            )
        other = Order.objects.create(customer=user, total="20.00", currency="USD", status="paid")
        LedgerEntry.objects.create(
            order=other, entry_type="payment", amount="20.00", currency="USD",
            reference="audit:payment:2",
        )

        result = revenue_verify({})
        assert result["verified_effect"] is True  # The inventory audit was performed.
        assert result["verified_revenue"] is None  # Cash was NOT independently proven.
        assert result["revenue_status"] == "external_settlement_evidence_required"
        assert "'payment_entries': 2" in result["evidence"]["value"]
        assert "'settlement_candidates': 1" in result["evidence"]["value"]
