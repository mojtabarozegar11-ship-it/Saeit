import io
import json
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.economic_tool_pack import revenue_verify
from core.models import (
    Agent, AgentCapability, AgentTask, AuditLog, LedgerEntry,
    NewsletterPublication, NewsletterStory, Order,
)


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
        self.successor, _ = Agent.objects.update_or_create(
            code="content-director",
            defaults={"name": "Content Director", "mission": "Consolidated newsletter",
                      "active": True},
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
        history = AgentTask.objects.create(agent=self.legacy, action_type="old_review", status="completed")
        AgentTask.objects.filter(pk=history.pk).update(
            updated_at=timezone.now() - timedelta(days=60)
        )
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

    def test_missing_successor_blocks_legacy_retirement(self):
        self.successor.active = False
        self.successor.save(update_fields=["active"])
        result = self.run_command("--apply")
        self.legacy.refresh_from_db()
        assert self.legacy.active
        row = next(r for r in result["agents"] if r["code"] == self.legacy.code)
        assert row["decision"] == "hold_missing_successor"
        assert row["replacement_agent"] == "content-director"
        assert result["summary"]["missing_successor"] >= 1
        assert not AuditLog.objects.filter(action="legacy_agent_retired").exists()

    def test_approved_content_prevents_retirement(self):
        NewsletterStory.objects.create(
            agent=self.legacy, story_type="world", title="Important approved item",
            slug="agent-retirement-pending-approval", summary="Pending editorial item",
            body="Content needs publication workflow", fingerprint="audit-pending-approval",
            status="approved",
        )
        result = self.run_command("--apply")
        self.legacy.refresh_from_db()
        assert self.legacy.active
        row = next(r for r in result["agents"] if r["code"] == self.legacy.code)
        assert row["decision"] == "hold_for_dependency"

    def test_recent_legacy_output_is_held_for_value_review(self):
        AgentTask.objects.create(
            agent=self.legacy, action_type="recent_publication", status="completed"
        )
        result = self.run_command("--apply")
        self.legacy.refresh_from_db()
        assert self.legacy.active
        row = next(r for r in result["agents"] if r["code"] == self.legacy.code)
        assert row["decision"] == "review_recent_outputs"
        assert row["recent_completed_tasks"] == 1

    def test_income_prefix_alone_never_authorizes_retirement(self):
        AgentTask.objects.filter(agent=self.busy).delete()
        result = self.run_command("--apply")
        self.busy.refresh_from_db()
        assert self.busy.active
        row = next(r for r in result["agents"] if r["code"] == self.busy.code)
        assert row["review_only_prefix"] is True
        assert row["decision"] == "review_live_outcomes"

    def test_published_story_in_last_month_requires_manual_value_review(self):
        NewsletterStory.objects.create(
            agent=self.legacy, story_type="world", title="Recently published",
            slug="agent-retirement-recent-publication", summary="Existing newsletter",
            body="Previously published content", fingerprint="audit-recent-publication",
            status="published", published_at=timezone.now(),
        )
        result = self.run_command("--apply")
        self.legacy.refresh_from_db()
        assert self.legacy.active
        row = next(r for r in result["agents"] if r["code"] == self.legacy.code)
        assert row["decision"] == "review_recent_outputs"
        assert row["recent_publications"] == 1

    def test_queued_distribution_blocks_deactivation_of_published_story(self):
        story = NewsletterStory.objects.create(
            agent=self.legacy, story_type="world", title="Older newsletter",
            slug="agent-retirement-distribution", summary="Pending distribution",
            body="Story ready to distribute", fingerprint="audit-distribution",
            status="published", published_at=timezone.now() - timedelta(days=60),
        )
        NewsletterPublication.objects.create(story=story, channel="site", status="queued")
        result = self.run_command("--apply")
        self.legacy.refresh_from_db()
        assert self.legacy.active
        row = next(r for r in result["agents"] if r["code"] == self.legacy.code)
        assert row["decision"] == "hold_for_dependency"
        assert row["pending_distributions"] == 1

    def test_exclusive_active_capability_cannot_be_silently_retired(self):
        cap = AgentCapability.objects.create(
            code="exclusive-legacy-feed", name="Unique legacy feed",
            description="Possible external dependency", active=True,
        )
        cap.agents.add(self.legacy)
        result = self.run_command("--apply")
        self.legacy.refresh_from_db()
        assert self.legacy.active
        row = next(r for r in result["agents"] if r["code"] == self.legacy.code)
        assert row["decision"] == "review_unique_capability"
        assert row["unique_active_capabilities"] == [cap.code]


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
