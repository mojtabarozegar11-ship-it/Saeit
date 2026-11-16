"""Offline safety regressions for the canonical site-native capabilities."""
import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "core" / "mojtaba_site_fleet.py"
spec = importlib.util.spec_from_file_location("site_fleet", PATH)
fleet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fleet)


class SiteFleetTests(unittest.TestCase):
    def test_single_owner_identity_and_known_roles(self):
        i = fleet.inventory()
        self.assertEqual(i["canonical_bot"], "mojtaba.bot.ai")
        self.assertEqual(i["zomorodmelal"]["role_count"], 11)
        self.assertEqual(len(i["mojplaywin"]["legacy_named_robot_slots"]), 11)
        self.assertEqual(i["mojplaywin"]["legacy_module_slots_not_functionally_verified"], 77)
        self.assertIsNone(i["mojplaywin"]["actual_active_worker_count"])
        self.assertFalse(i["legacy_cleanup_authorized"])

    def test_allowlisted_https_probe(self):
        calls = []
        def transport(url):
            calls.append(url)
            return 200, "text/html; charset=utf-8", b"<html><title>Test</title>" + b"x" * 80 + b"</html>"
        a = fleet.probe("zomorodmelal", "content", transport=transport)
        b = fleet.probe("mojplaywin", "public_store", transport=transport)
        self.assertEqual(calls, [
            "https://zomorodmelal.ir/knowledge/",
            "https://mojplaywin.com/store/",
        ])
        self.assertEqual(a["state"], "http_probe_ok")
        self.assertEqual(b["state"], "http_probe_ok")
        self.assertFalse(a["payment_verified"])
        self.assertFalse(b["publication_verified"])

    def test_reject_arbitrary_ssrf_targets(self):
        for tenant, role in (
            ("evil", "content"), ("zomorodmelal", "https://evil"),
            ("mojplaywin", "/../../private"), ("mojplaywin", "master_gen64")
        ):
            with self.subTest(tenant=tenant, role=role):
                with self.assertRaises(fleet.SiteFleetError):
                    fleet.probe(tenant, role, transport=lambda _: (200, "text/html", b"x"*80))

    def test_short_and_redirect_and_oversized_are_not_healthy(self):
        for status, data in ((200, b"x"*30), (302, b"x"*90), (200, b"x"*262145)):
            with self.subTest(status=status, size=len(data)):
                r = fleet.probe("zomorodmelal", "seo",
                                transport=lambda _: (status, "text/html", data))
                self.assertEqual(r["state"], "unverified")

    def test_json_and_content_type_strict(self):
        bad = fleet.probe("mojplaywin", "public_home",
                          transport=lambda _: (200, "application/octet-stream", b"x"*90))
        self.assertEqual(bad["state"], "unverified")
        with self.assertRaises(fleet.SiteFleetError):
            fleet.probe("mojplaywin", "public_home", transport=lambda _: ("200", "text/html", b"x"*90))

    def test_two_tenant_evidence_required(self):
        with self.assertRaises(fleet.SiteFleetError):
            fleet.retirement_decision({"zomorodmelal": {}})
        with self.assertRaises(fleet.SiteFleetError):
            fleet.retirement_decision({"zomorodmelal": {"tenant":"wrong"}, "mojplaywin": {"tenant":"mojplaywin"}})

    def test_missing_proofs_fail_closed(self):
        now = datetime.now(timezone.utc)
        raw = {k: {"tenant": k, "observed_at_utc": now.isoformat()} for k in fleet.TENANTS}
        r = fleet.retirement_decision(raw, now=now)
        self.assertFalse(r["all_sites_ready"])
        self.assertEqual(r["files_deleted"], 0)
        self.assertEqual(r["crons_removed"], 0)
        for v in r["site_decisions"].values():
            self.assertFalse(v["root_or_parent_directory_deletion_allowed"])
            self.assertIn("independent_functional_receipt_ids_missing", v["blockers"])

    def test_fake_truthy_flags_fail_closed(self):
        now = datetime.now(timezone.utc)
        raw = {k: {"tenant": k, "observed_at_utc": now.isoformat(),
                   "functional_receipt_ids": ["a"*64],
                   **{gate: "true" for gate in fleet.GATES}} for k in fleet.TENANTS}
        self.assertFalse(fleet.retirement_decision(raw, now=now)["all_sites_ready"])

    def test_complete_attestation_only_allows_review_not_deletion(self):
        now = datetime.now(timezone.utc)
        raw = {k: {"tenant": k, "observed_at_utc": now.isoformat(),
                   "functional_receipt_ids": ["a"*64, "b"*64],
                   **{gate: True for gate in fleet.GATES}} for k in fleet.TENANTS}
        d = fleet.retirement_decision(raw, now=now)
        self.assertTrue(d["all_sites_ready"])
        self.assertEqual(d["files_deleted"], 0)
        for v in d["site_decisions"].values():
            self.assertFalse(v["root_or_parent_directory_deletion_allowed"])

    def test_duplicate_receipts_rejected(self):
        now = datetime.now(timezone.utc)
        raw = {k: {"tenant": k, "observed_at_utc": now.isoformat(),
                   "functional_receipt_ids": ["a"*64, "a"*64],
                   **{gate: True for gate in fleet.GATES}} for k in fleet.TENANTS}
        self.assertFalse(fleet.retirement_decision(raw, now=now)["all_sites_ready"])


if __name__ == "__main__":
    unittest.main()
