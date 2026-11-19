"""Recorded site receipts are real persisted observations, not simulated sales."""
from copy import deepcopy
import unittest

from django.test import TestCase

from core.models import Agent, AuditLog
from core.mojtaba_site_fleet import CANONICAL_BOT, ROUTES, SiteFleetError
from core.mojtaba_site_receipts import record_public_cycle, summarize_public_cycle, ACTION


def report():
    rows = []
    for tenant, roles in ROUTES.items():
        for role in roles:
            rows.append({
                "bot": CANONICAL_BOT, "tenant": tenant, "role": role,
                "state": "http_probe_ok", "http_status": 200,
                "response_sha256": "a" * 64,
            })
    return {"canonical_bot": CANONICAL_BOT,
            "public_checks_count": len(rows), "observations": rows}


class ReceiptTests(TestCase):
    def setUp(self):
        Agent.objects.create(code="mojtaba-bot-ai", name="Mojtaba.bot",
                             mission="two-site public observability", active=True)

    def test_actual_two_site_auditlog_records_and_idempotent_replay(self):
        payload = report()
        result = record_public_cycle(payload, cycle_id="f"*32)
        self.assertTrue(result["written"])
        self.assertEqual(result["site_receipts"], 2)
        self.assertEqual(AuditLog.objects.filter(action=ACTION).count(), 2)
        rows = list(AuditLog.objects.filter(action=ACTION))
        self.assertEqual({r.target_id for r in rows}, set(ROUTES))
        self.assertTrue(all(r.after_state["all_public_routes_ok"] for r in rows))
        self.assertTrue(all(r.after_state["payment_verified"] is False for r in rows))
        replay = record_public_cycle(payload, cycle_id="f"*32)
        self.assertFalse(replay["written"])
        self.assertEqual(AuditLog.objects.filter(action=ACTION).count(), 2)

    def test_replayed_id_with_changed_output_is_refused(self):
        payload = report()
        record_public_cycle(payload, cycle_id="e"*32)
        payload["observations"][0]["state"] = "unverified"
        payload["observations"][0]["response_sha256"] = None
        with self.assertRaises(SiteFleetError):
            record_public_cycle(payload, cycle_id="e"*32)
        self.assertEqual(AuditLog.objects.filter(action=ACTION).count(), 2)

    def test_missing_active_bot_blocks_database_write(self):
        Agent.objects.filter(code="mojtaba-bot-ai").update(active=False)
        with self.assertRaises(SiteFleetError):
            record_public_cycle(report(), cycle_id="d"*32)
        self.assertFalse(AuditLog.objects.filter(action=ACTION).exists())

    def test_duplicated_role_and_missing_tenant_fail_closed(self):
        payload = report()
        payload["observations"][-1] = deepcopy(payload["observations"][0])
        with self.assertRaises(SiteFleetError):
            summarize_public_cycle(payload)
        self.assertFalse(AuditLog.objects.filter(action=ACTION).exists())

    def test_customer_payload_is_discarded_not_persisted(self):
        payload = report()
        payload["observations"][0]["secret_internal_value"] = "MUST_NOT_STORE"
        record_public_cycle(payload, cycle_id="b"*32)
        for row in AuditLog.objects.filter(action=ACTION):
            self.assertNotIn("MUST_NOT_STORE", str(row.after_state))
            self.assertEqual(row.actor_id, "mojtaba-bot-ai")

    def test_redacted_html_quality_scores_are_durable_without_page_text(self):
        payload = report()
        expected = {
            "status": "review", "score": 75,
            "issues": ["missing_meta_description"],
            "source_content_logged": False, "private_title": "MUST_NOT_STORE"
        }
        payload["observations"][0]["site_html_quality"] = expected
        record_public_cycle(payload, cycle_id="9"*32)
        row = AuditLog.objects.get(action=ACTION, target_id="zomorodmelal")
        self.assertEqual(row.after_state["structural_qa_reported_roles"], 1)
        self.assertEqual(row.after_state["structural_qa_results"][0]["score"], 75)
        self.assertNotIn("MUST_NOT_STORE", str(row.after_state))
        self.assertFalse(row.after_state["legacy_php_dashboard_replaced"])
        self.assertFalse(row.after_state["legacy_sqlite_history_migrated"])

    def test_untrusted_quality_score_cannot_be_recorded(self):
        payload = report()
        payload["observations"][0]["site_html_quality"] = {
            "status": "review", "score": 101, "issues": [],
            "source_content_logged": False,
        }
        with self.assertRaises(SiteFleetError):
            record_public_cycle(payload, cycle_id="8"*32)
        self.assertFalse(AuditLog.objects.filter(action=ACTION).exists())

    def test_quality_raw_page_content_not_accepted_as_log_proof(self):
        payload = report()
        payload["observations"][0]["site_html_quality"] = {
            "status": "review", "score": 100, "issues": [],
            "source_content_logged": True,
        }
        with self.assertRaises(SiteFleetError):
            record_public_cycle(payload, cycle_id="7"*32)

    def test_fabricated_http_success_is_rejected(self):
        payload = report()
        payload["observations"][0]["response_sha256"] = "not-hash"
        with self.assertRaises(SiteFleetError):
            record_public_cycle(payload, cycle_id="a"*32)
        self.assertFalse(AuditLog.objects.filter(action=ACTION).exists())


    def test_per_role_receipts_complete_and_master_aggregates_other_failures(self):
        payload = report()
        commerce = next(x for x in payload["observations"]
                        if x["tenant"] == "zomorodmelal" and x["role"] == "commerce")
        commerce.update(state="unverified", http_status=503, response_sha256=None)
        record_public_cycle(payload, cycle_id="6" * 32)
        row = AuditLog.objects.get(action=ACTION, target_id="zomorodmelal").after_state
        self.assertEqual({x["role"] for x in row["role_health_results"]}, set(ROUTES["zomorodmelal"]))
        self.assertEqual(len(row["role_health_results"]), 11)
        self.assertEqual(row["unhealthy_public_roles"], ["commerce"])
        self.assertEqual(row["site_master_health"], "degraded")
        self.assertFalse(row["all_public_routes_ok"])
        self.assertFalse(row["legacy_agent_retirement_authorized"])
        mpw = AuditLog.objects.get(action=ACTION, target_id="mojplaywin").after_state
        self.assertEqual(len(mpw["role_health_results"]), 3)
        self.assertEqual(mpw["unhealthy_public_roles"], [])
        self.assertIsNone(mpw["site_master_health"])

    def test_master_home_failure_is_unverified_not_healthy(self):
        payload = report()
        master = next(x for x in payload["observations"]
                      if x["tenant"] == "zomorodmelal" and x["role"] == "master")
        master.update(state="unverified", http_status=500, response_sha256=None)
        row = summarize_public_cycle(payload)["zomorodmelal"]
        self.assertEqual(row["site_master_health"], "unverified")
        self.assertEqual(row["unhealthy_public_roles"], ["master"])

    def test_all_routes_healthy_is_public_only_not_private_replacement(self):
        row = summarize_public_cycle(report())["zomorodmelal"]
        self.assertEqual(row["site_master_health"], "healthy_public_routes")
        self.assertEqual(row["master_health_scope"], "public_route_observations_only")
        self.assertEqual(row["unhealthy_public_roles"], [])
        self.assertFalse(row["private_worker_execution_verified"])
        self.assertFalse(row["legacy_sqlite_history_migrated"])
        self.assertFalse(row["payment_verified"])


if __name__ == "__main__":
    unittest.main()
