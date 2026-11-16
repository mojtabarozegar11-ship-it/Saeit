"""Two real DB receipts, not one fake response, are required for review."""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.models import Agent, AuditLog
from core.mojtaba_site_fleet import CANONICAL_BOT, ROUTES
from core.mojtaba_site_receipts import (
    ACTION, record_public_cycle, inspect_public_monitor_continuity
)


def public_report():
    obs = []
    for tenant, roles in ROUTES.items():
        for role in roles:
            obs.append({"bot": CANONICAL_BOT, "tenant": tenant, "role": role,
                        "state": "http_probe_ok", "http_status": 200,
                        "response_sha256": "a" * 64})
    return {"canonical_bot": CANONICAL_BOT, "public_checks_count": 14,
            "observations": obs}


class MonitorContinuityTests(TestCase):
    def setUp(self):
        Agent.objects.create(
            code="mojtaba-bot-ai", name="Canonical bot", mission="site monitor",
            active=True,
        )

    def test_no_receipts_is_not_ready(self):
        result = inspect_public_monitor_continuity()
        self.assertFalse(result["all_public_monitors_have_two_cycles"])
        self.assertFalse(result["legacy_host_cleanup_authorized"])
        for state in result["sites"].values():
            self.assertEqual(state["successful_public_observation_receipts_24h"], 0)

    def test_two_separate_receipts_spaced_five_minutes_count(self):
        record_public_cycle(public_report(), cycle_id="1" * 32)
        AuditLog.objects.filter(action=ACTION, trace_id="1"*32).update(
            created_at=timezone.now() - timedelta(minutes=10)
        )
        record_public_cycle(public_report(), cycle_id="2" * 32)
        result = inspect_public_monitor_continuity()
        self.assertTrue(result["all_public_monitors_have_two_cycles"])
        self.assertEqual(result["site_files_deleted"], 0)
        self.assertFalse(result["private_workers_migrated"])
        self.assertFalse(result["legacy_host_cleanup_authorized"])

    def test_two_fast_replays_do_not_qualify(self):
        record_public_cycle(public_report(), cycle_id="3" * 32)
        record_public_cycle(public_report(), cycle_id="4" * 32)
        self.assertFalse(inspect_public_monitor_continuity()[
            "all_public_monitors_have_two_cycles"
        ])

    def test_duplicate_target_record_invalidates_one_cycle(self):
        record_public_cycle(public_report(), cycle_id="5" * 32)
        AuditLog.objects.filter(action=ACTION, trace_id="5"*32).update(
            created_at=timezone.now() - timedelta(minutes=10)
        )
        AuditLog.objects.create(
            actor_type="system", actor_id="mojtaba-bot-ai",
            action=ACTION, target_type="site_native_public_monitor",
            target_id="mojplaywin", trace_id="5"*32,
            after_state={"all_public_routes_ok": True},
        )
        record_public_cycle(public_report(), cycle_id="6" * 32)
        result = inspect_public_monitor_continuity()
        self.assertFalse(result["sites"]["mojplaywin"][
            "two_distinct_spaced_cycles"
        ])
        self.assertFalse(result["all_public_monitors_have_two_cycles"])

    def test_one_site_unhealthy_not_promoted(self):
        first = public_report()
        first["observations"][0]["state"] = "unverified"
        first["observations"][0]["response_sha256"] = None
        record_public_cycle(first, cycle_id="7" * 32)
        AuditLog.objects.filter(action=ACTION, trace_id="7"*32).update(
            created_at=timezone.now() - timedelta(minutes=10)
        )
        record_public_cycle(public_report(), cycle_id="8" * 32)
        result = inspect_public_monitor_continuity()
        self.assertFalse(result["sites"]["zomorodmelal"]["two_distinct_spaced_cycles"])
        self.assertTrue(result["sites"]["mojplaywin"]["two_distinct_spaced_cycles"])
        self.assertFalse(result["legacy_host_cleanup_authorized"])
