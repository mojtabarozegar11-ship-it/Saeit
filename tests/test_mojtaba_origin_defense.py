"""Offline regression tests for source-side defense module of one bot."""
import hashlib
import hmac
import json
import unittest
from datetime import datetime, timezone

from core.mojtaba_modules import BOT_ID, MODULE_ID, plan_origin_defense, registered_capabilities
from core.mojtaba_modules.cyber_security import CyberModuleError

KEY = b"fixture-signing-secret-32-bytes-minimum-not-for-production"
NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)


def signed(**changes):
    auth = {
        "schema": "mojtaba.bot.ai.cyber.engagement.v1",
        "bot_id": BOT_ID, "module_id": MODULE_ID,
        "tenant_id": "customer-x", "engagement_id": "job-123",
        "allowed_assets": ["owned.example.com"],
        "mode": "offline_evidence",
        "issued_at": "2026-11-13T10:00:00+00:00",
        "expires_at": "2026-11-14T00:00:00+00:00",
    }
    auth.update(changes)
    payload = json.dumps(auth, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    auth["signature"] = hmac.new(KEY, payload, hashlib.sha256).hexdigest()
    return auth


def signal(**changes):
    row = {
        "asset_hostname": "owned.example.com",
        "source_ip": "8.8.8.8",
        "collector": "verified_edge_export",
        "observed_at": "2026-11-13T11:58:00+00:00",
        "requests_5m": 900, "errors_4xx_5m": 650,
        "errors_5xx_5m": 10, "distinct_paths_5m": 40,
    }
    row.update(changes)
    return row


def traffic(**changes):
    evidence = {
        "schema": "mojtaba.bot.ai.cyber.origin-defense.v1",
        "tenant_id": "customer-x", "engagement_id": "job-123",
        "observations": [signal()],
    }
    evidence.update(changes)
    return evidence


class OriginDefenseTests(unittest.TestCase):
    def run_plan(self, *, auth=None, evidence=None):
        return plan_origin_defense(
            engagement=auth if auth is not None else signed(),
            traffic=evidence if evidence is not None else traffic(),
            verify_key=KEY, now=NOW,
        )

    def test_one_bot_one_module(self):
        registry = registered_capabilities()
        self.assertEqual(list(registry), ["cyber_security"])
        self.assertEqual(registry["cyber_security"]["bot_id"], BOT_ID)
        self.assertIn("origin_defense", registry["cyber_security"]["submodules"])
        self.assertFalse(registry["cyber_security"]["submodules"]["origin_defense"]["network_access"])

    def test_high_pressure_recommends_review_not_block(self):
        plan = self.run_plan()
        self.assertEqual(plan["risk"], "review")
        self.assertEqual(plan["recommendations"][0]["proposed_action"],
                         "review_edge_challenge_or_rate_limit")
        self.assertTrue(plan["recommendations"][0]["approval_required"])
        self.assertFalse(plan["recommendations"][0]["executed"])
        self.assertEqual(plan["network_actions_executed"], 0)
        self.assertTrue(plan["no_hack_back"])
        self.assertEqual(plan["mode"], "offline_recommendations_only")

    def test_sensitive_ip_not_emitted(self):
        self.assertNotIn("8.8.8.8", json.dumps(self.run_plan()))
        self.assertEqual(len(self.run_plan()["recommendations"][0]["source_tag"]), 24)

    def test_unverified_proxy_header_never_triggers_ip_block(self):
        evidence = traffic(observations=[signal(collector="unverified_forwarded_header")])
        plan = self.run_plan(evidence=evidence)
        self.assertEqual(plan["recommendations"][0]["proposed_action"],
                         "validate_proxy_chain_and_source_evidence")
        self.assertEqual(plan["recommendations"][0]["identity_attribution"], "not_established")

    def test_origin_socket_may_be_reverse_proxy(self):
        evidence = traffic(observations=[signal(collector="origin_socket_log")])
        plan = self.run_plan(evidence=evidence)
        self.assertEqual(plan["recommendations"][0]["proposed_action"],
                         "validate_proxy_chain_and_source_evidence")

    def test_very_high_pressure_requests_provider_review(self):
        evidence = traffic(observations=[signal(requests_5m=4500,
                      errors_4xx_5m=500, errors_5xx_5m=150, distinct_paths_5m=50)])
        plan = self.run_plan(evidence=evidence)
        self.assertEqual(plan["risk"], "urgent_review")
        self.assertEqual(plan["recommendations"][0]["proposed_action"],
                         "request_upstream_mitigation_review")

    def test_non_global_source_not_targeted(self):
        evidence = traffic(observations=[signal(source_ip="10.0.0.1")])
        plan = self.run_plan(evidence=evidence)
        self.assertFalse(plan["recommendations"][0]["public_ip_indicator"])
        self.assertEqual(plan["recommendations"][0]["proposed_action"],
                         "validate_proxy_chain_and_source_evidence")

    def test_forged_scope_signature(self):
        auth = signed()
        auth["allowed_assets"] = ["other.example.com"]
        with self.assertRaisesRegex(CyberModuleError, "SIGNATURE_INVALID"):
            self.run_plan(auth=auth)

    def test_wrong_tenant_fail_closed(self):
        with self.assertRaisesRegex(CyberModuleError, "CROSS_TENANT_EVIDENCE_FORBIDDEN"):
            self.run_plan(evidence=traffic(tenant_id="customer-y"))

    def test_outside_asset_scope_fail_closed(self):
        evidence = traffic(observations=[signal(asset_hostname="other.example.com")])
        with self.assertRaisesRegex(CyberModuleError, "ASSET_OUT_OF_SCOPE"):
            self.run_plan(evidence=evidence)

    def test_inconsistent_counts_rejected(self):
        evidence = traffic(observations=[signal(requests_5m=12, errors_4xx_5m=30)])
        with self.assertRaisesRegex(CyberModuleError, "ORIGIN_COUNTERS_INCONSISTENT"):
            self.run_plan(evidence=evidence)

    def test_bad_ip_rejected(self):
        evidence = traffic(observations=[signal(source_ip="not-an-ip")])
        with self.assertRaisesRegex(CyberModuleError, "SOURCE_IP_INVALID"):
            self.run_plan(evidence=evidence)

    def test_future_observation_rejected(self):
        evidence = traffic(observations=[signal(observed_at="2026-11-13T13:00:00+00:00")])
        with self.assertRaisesRegex(CyberModuleError, "OBSERVATION_OUTSIDE_TIME_WINDOW"):
            self.run_plan(evidence=evidence)

    def test_stale_observation_rejected(self):
        evidence = traffic(observations=[signal(observed_at="2026-11-13T10:00:00+00:00")])
        with self.assertRaisesRegex(CyberModuleError, "OBSERVATION_OUTSIDE_TIME_WINDOW"):
            self.run_plan(evidence=evidence)

    def test_empty_evidence_safe(self):
        plan = self.run_plan(evidence=traffic(observations=[]))
        self.assertEqual(plan["recommendations"], [])
        self.assertEqual(plan["risk"], "informational")

    def test_boolean_counters_rejected(self):
        evidence = traffic(observations=[signal(requests_5m=True)])
        with self.assertRaisesRegex(CyberModuleError, "ORIGIN_METRIC_INVALID"):
            self.run_plan(evidence=evidence)

    def test_unrecognized_collector_rejected(self):
        evidence = traffic(observations=[signal(collector="user-supplied-xff")])
        with self.assertRaisesRegex(CyberModuleError, "COLLECTOR_INVALID"):
            self.run_plan(evidence=evidence)

    def test_list_collector_rejected_as_invalid(self):
        bad = traffic(observations=[signal(collector=["verified_edge_export"])])
        with self.assertRaisesRegex(CyberModuleError, "COLLECTOR_INVALID"):
            self.run_plan(evidence=bad)

    def test_dict_collector_rejected_as_invalid(self):
        bad = traffic(observations=[signal(collector={"source": "verified_edge_export"})])
        with self.assertRaisesRegex(CyberModuleError, "COLLECTOR_INVALID"):
            self.run_plan(evidence=bad)



if __name__ == "__main__":
    unittest.main()
