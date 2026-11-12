import io
import json
from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.economic_tool_pack import revenue_verify
from core.approval import ApprovalService
from core.unified_bot_identity import BOT_CODE
from core.models import (
    Agent, AgentCapability, AgentTask, AuditLog, ApprovalRequest, LedgerEntry,
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
            code=BOT_CODE,
            defaults={"name": "Mojtaba.bot.ai", "mission": "Consolidated canonical bot",
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

    def _world_successor_proof(self):
        return NewsletterStory.objects.create(
            agent=self.successor, story_type="world",
            title="Accepted canonical successor world brief",
            slug="canonical-world-proof",
            summary="Credible content verified and published",
            body="Editorial evidence attributable to the sole bot",
            fingerprint="canonical-world-proof",
            status="published", published_at=timezone.now(),
            manager_action="NEWSROOM_QUALITY=96/100; checks=credible_source",
        )

    def _handoff_receipt(self):
        return AuditLog.objects.create(
            actor_type="owner", actor_id="approved-operator",
            action="single_bot_live_handoff_verified",
            target_type="Agent", target_id=str(self.legacy.pk),
            before_state={"legacy_code": self.legacy.code},
            after_state={
                "legacy_code": self.legacy.code,
                "canonical_bot_code": BOT_CODE,
                "canonical_successor_runtime_verified": True,
                "external_legacy_schedulers_stopped": True,
                "all_pending_tasks_reconciled": True,
                "historical_data_preserved": True,
                "rollback_ready": True,
                "live_inventory_receipt_id": "verified-inventory-20261112",
                "canonical_successor_receipt_id": "accepted-world-proof",
            },
            trace_id=f"handoff-audit-{self.legacy.pk}",
        )

    def _retirement_grant(self, receipt):
        user = get_user_model().objects.create_user(username="retire-owner")
        approval = ApprovalRequest.objects.create(
            requested_by=user, status="approved", risk="high",
            action_type="retire_legacy_agent",
            target_type="Agent", target_id=str(self.legacy.pk),
            reason="Single identified agent; verified handoff and audit retention",
        )
        return ApprovalService().issue_grant(
            approval.pk, user.pk, {
                "action": "retire_legacy_agent",
                "agent_code": self.legacy.code,
                "canonical_bot_code": BOT_CODE,
                "live_handoff_receipt": receipt.trace_id,
            },
        )

    def test_preview_never_modifies_agents(self):
        result = self.run_command()
        self.legacy.refresh_from_db()
        assert self.legacy.active
        decisions = {row["code"]: row["decision"] for row in result["agents"]}
        assert decisions[self.legacy.code] == "hold_unproven_successor_coverage"
        assert decisions[self.busy.code] == "hold_for_dependency"
        assert decisions[self.master.code] == "retain_required"
        assert decisions[self.unknown.code] == "review_live_outcomes"
        assert AuditLog.objects.filter(action="legacy_agent_retired").count() == 0

    def test_preview_does_not_request_database_row_locks(self):
        # A read-only status inspection must not block live agent dispatch.
        with patch("django.db.models.query.QuerySet.select_for_update",
                   side_effect=AssertionError("preview must not lock agent rows")):
            result = self.run_command()
        assert result["mode"] == "preview"
        assert result["summary"]["retired_now"] == 0

    def test_apply_deactivates_only_exact_approved_live_handoff_preserving_history(self):
        self._world_successor_proof()
        history = AgentTask.objects.create(
            agent=self.legacy, action_type="old_review", status="completed",
        )
        AgentTask.objects.filter(pk=history.pk).update(
            updated_at=timezone.now() - timedelta(days=60),
        )
        preview = self.run_command()
        row = next(x for x in preview["agents"] if x["code"] == self.legacy.code)
        assert row["decision"] == "retire_safe"
        assert row["retirement_readiness_scope"] == "source_only_not_live_verified"
        assert preview["summary"]["retired_now"] == 0
        assert preview["summary"]["source_only_retirement_candidates"] >= 1
        with self.assertRaisesRegex(CommandError, "EXACT_AGENT_AND_GRANT_REQUIRED"):
            self.run_command("--apply")
        self.legacy.refresh_from_db()
        assert self.legacy.active

        receipt = self._handoff_receipt()
        grant = self._retirement_grant(receipt)
        result = self.run_command(
            "--apply", "--agent-code", self.legacy.code,
            "--approval-grant-id", str(grant.pk),
        )
        self.legacy.refresh_from_db()
        self.busy.refresh_from_db()
        self.master.refresh_from_db()
        self.unknown.refresh_from_db()
        grant.refresh_from_db()
        assert not self.legacy.active
        assert self.busy.active and self.master.active and self.unknown.active
        assert result["summary"]["retired_now"] == 1
        assert grant.used_at is not None
        assert AgentTask.objects.filter(agent=self.legacy, status="completed").exists()
        assert AuditLog.objects.filter(
            action="legacy_agent_retired", target_id=str(self.legacy.pk)
        ).count() == 1
        previous_events = AuditLog.objects.filter(action="legacy_agent_retired").count()
        with self.assertRaises(CommandError):
            self.run_command(
                "--apply", "--agent-code", self.legacy.code,
                "--approval-grant-id", str(grant.pk),
            )
        assert AuditLog.objects.filter(action="legacy_agent_retired").count() == previous_events

    def test_evidence_without_grant_cannot_deactivate(self):
        self._world_successor_proof()
        self._handoff_receipt()
        with self.assertRaisesRegex(CommandError, "EXACT_AGENT_AND_GRANT_REQUIRED"):
            self.run_command("--apply", "--agent-code", self.legacy.code)
        self.legacy.refresh_from_db()
        assert self.legacy.active
        assert not AuditLog.objects.filter(action="legacy_agent_retired").exists()

    def test_grant_without_live_handoff_evidence_cannot_deactivate(self):
        self._world_successor_proof()
        fake_receipt = type("Receipt", (), {"trace_id": "unverified"})()
        grant = self._retirement_grant(fake_receipt)
        with self.assertRaisesRegex(CommandError, "LIVE_HANDOFF_RECEIPT_REQUIRED"):
            self.run_command(
                "--apply", "--agent-code", self.legacy.code,
                "--approval-grant-id", str(grant.pk),
            )
        self.legacy.refresh_from_db()
        grant.refresh_from_db()
        assert self.legacy.active
        assert grant.used_at is None

    def test_partial_handoff_receipt_never_deactivates_or_consumes_grant(self):
        self._world_successor_proof()
        receipt = self._handoff_receipt()
        receipt.after_state["external_legacy_schedulers_stopped"] = False
        receipt.save(update_fields=["after_state"])
        grant = self._retirement_grant(receipt)
        with self.assertRaisesRegex(CommandError, "LIVE_HANDOFF_RECEIPT_REQUIRED"):
            self.run_command(
                "--apply", "--agent-code", self.legacy.code,
                "--approval-grant-id", str(grant.pk),
            )
        self.legacy.refresh_from_db()
        grant.refresh_from_db()
        assert self.legacy.active and grant.used_at is None
        assert not AuditLog.objects.filter(action="legacy_agent_retired").exists()

    def test_other_agent_approval_cannot_be_reused_for_retirement(self):
        self._world_successor_proof()
        receipt = self._handoff_receipt()
        grant = self._retirement_grant(receipt)
        grant.approval.target_id = str(self.busy.pk)
        grant.approval.save(update_fields=["target_id"])
        with self.assertRaisesRegex(CommandError, "EXACT_OWNER_APPROVAL_REQUIRED"):
            self.run_command(
                "--apply", "--agent-code", self.legacy.code,
                "--approval-grant-id", str(grant.pk),
            )
        self.legacy.refresh_from_db()
        grant.refresh_from_db()
        assert self.legacy.active and grant.used_at is None

    def test_wrong_grant_scope_rolls_back_without_deactivation(self):
        self._world_successor_proof()
        receipt = self._handoff_receipt()
        grant = self._retirement_grant(receipt)
        grant.scope["canonical_bot_code"] = "noncanonical-content-director"
        grant.save(update_fields=["scope"])
        with self.assertRaisesRegex(CommandError, "APPROVAL_GRANT_REJECTED"):
            self.run_command(
                "--apply", "--agent-code", self.legacy.code,
                "--approval-grant-id", str(grant.pk),
            )
        self.legacy.refresh_from_db()
        grant.refresh_from_db()
        assert self.legacy.active and grant.used_at is None
        assert not AuditLog.objects.filter(action="legacy_agent_retired").exists()

    def test_noncanonical_successor_receipts_cannot_authorize_retirement(self):
        independent = Agent.objects.create(
            code="content-director", name="Old newsletter bot",
            mission="Noncanonical", active=True,
        )
        NewsletterStory.objects.create(
            agent=independent, story_type="world", title="Noncanonical published story",
            slug="noncanonical-old-news", summary="legacy story",
            body="This does not prove the canonical bot can deliver",
            fingerprint="noncanonical-news-proof",
            status="published", published_at=timezone.now(),
            manager_action="NEWSROOM_QUALITY=96/100; checks=credible_source",
        )
        result = self.run_command()
        self.legacy.refresh_from_db()
        assert self.legacy.active
        row = next(x for x in result["agents"] if x["code"] == self.legacy.code)
        assert row["replacement_agent"] == BOT_CODE
        assert row["decision"] == "hold_unproven_successor_coverage"

    def test_unknown_or_canonical_agent_is_never_retirement_target(self):
        with self.assertRaisesRegex(CommandError, "UNKNOWN_OR_PROTECTED_AGENT"):
            self.run_command("--apply", "--agent-code", BOT_CODE, "--approval-grant-id", "999")
        with self.assertRaisesRegex(CommandError, "UNKNOWN_OR_PROTECTED_AGENT"):
            self.run_command("--apply", "--agent-code", "site-purchase-delivery", "--approval-grant-id", "999")
    def test_active_but_unproven_successor_never_retires_legacy(self):
        result = self.run_command()
        self.legacy.refresh_from_db()
        assert self.legacy.active
        row = next(r for r in result["agents"] if r["code"] == self.legacy.code)
        assert row["decision"] == "hold_unproven_successor_coverage"
        assert row["missing_successor_coverage"] == ["world"]
        assert result["summary"]["unproven_successor_coverage"] >= 1

    def test_company_draft_does_not_cover_world_or_report_agents(self):
        NewsletterStory.objects.create(
            agent=self.successor, story_type="company", title="Company only",
            slug="successor-company-only", summary="Company content",
            body="Owner submitted company activity", fingerprint="successor-company-proof",
            status="draft", manager_action="NEWSROOM_QUALITY=92/100; checks=company",
        )
        result = self.run_command()
        self.legacy.refresh_from_db()
        assert self.legacy.active
        world = next(r for r in result["agents"] if r["code"] == self.legacy.code)
        assert world["missing_successor_coverage"] == ["world"]

    def test_missing_successor_blocks_legacy_retirement(self):
        self.successor.active = False
        self.successor.save(update_fields=["active"])
        result = self.run_command()
        self.legacy.refresh_from_db()
        assert self.legacy.active
        row = next(r for r in result["agents"] if r["code"] == self.legacy.code)
        assert row["decision"] == "hold_missing_successor"
        assert row["replacement_agent"] == BOT_CODE
        assert result["summary"]["missing_successor"] >= 1
        assert not AuditLog.objects.filter(action="legacy_agent_retired").exists()

    def test_approved_content_prevents_retirement(self):
        NewsletterStory.objects.create(
            agent=self.legacy, story_type="world", title="Important approved item",
            slug="agent-retirement-pending-approval", summary="Pending editorial item",
            body="Content needs publication workflow", fingerprint="audit-pending-approval",
            status="approved",
        )
        result = self.run_command()
        self.legacy.refresh_from_db()
        assert self.legacy.active
        row = next(r for r in result["agents"] if r["code"] == self.legacy.code)
        assert row["decision"] == "hold_for_dependency"

    def test_recent_legacy_output_is_held_for_value_review(self):
        AgentTask.objects.create(
            agent=self.legacy, action_type="recent_publication", status="completed"
        )
        result = self.run_command()
        self.legacy.refresh_from_db()
        assert self.legacy.active
        row = next(r for r in result["agents"] if r["code"] == self.legacy.code)
        assert row["decision"] == "review_recent_outputs"
        assert row["recent_completed_tasks"] == 1

    def test_income_prefix_alone_never_authorizes_retirement(self):
        AgentTask.objects.filter(agent=self.busy).delete()
        result = self.run_command()
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
        result = self.run_command()
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
        result = self.run_command()
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
        result = self.run_command()
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
