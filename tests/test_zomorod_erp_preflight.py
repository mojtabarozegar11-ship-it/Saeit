"""No-network checks for fail-closed ERP deployment preparation."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "zomorod_erp_preflight", ROOT / "scripts/zomorod_erp_preflight.py"
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class FakeResponse:
    def __init__(self, status, url):
        self.status = status
        self.url = url

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeOpener:
    def __init__(self, status=200, base="https://zomorodmelal.ir"):
        self.status = status
        self.base = base
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request.method, request.full_url, timeout))
        if self.status >= 400:
            raise urllib.error.HTTPError(request.full_url, self.status, "error", {}, None)
        return FakeResponse(self.status, request.full_url)


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.doc = self.root / "checklist.json"
        self.doc.write_text(json.dumps({
            "checks": {
                k: {"status": "pending", "evidence": ""}
                for k in module.MANDATORY_CHECKS
            }
        }))
        for name in module.SCHEMA_FILES:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# fake schema\n")

    def tearDown(self):
        self.temp.cleanup()

    def test_real_checklist_starts_blocked_without_fabricated_success(self):
        real = module.load_checklist()
        self.assertFalse(real["all_verified"])
        self.assertEqual(real["check_count"], 9)

    def test_repository_migrations_are_present(self):
        self.assertTrue(module.schema_check(ROOT)["ready"])

    def test_offline_mode_cannot_claim_public_site_healthy(self):
        report = module.build_report(online=False, root=self.root, checklist=self.doc)
        self.assertTrue(report["release_blocked"])
        self.assertFalse(report["production_ready"])
        self.assertFalse(report["automatic_deploy_permitted"])
        self.assertEqual(report["live_probes"], [])
        self.assertIn("live endpoints not inspected", report["outstanding"])

    def test_all_public_http_200_still_blocked_without_restorable_backup(self):
        opener = FakeOpener(status=200)
        report = module.build_report(
            online=True, root=self.root, checklist=self.doc, opener=opener
        )
        self.assertTrue(all(x["healthy"] for x in report["live_probes"]))
        self.assertTrue(report["release_blocked"])
        self.assertTrue(all(method == "GET" for method, _, _ in opener.requests))
        self.assertTrue(all("/company/office/" not in url or "login/" in url for _, url, _ in opener.requests))

    def test_http_503_is_blocking_and_reported_only_as_status(self):
        result = module.probe_one("/admin/login/", opener=FakeOpener(status=503))
        self.assertFalse(result["healthy"])
        self.assertEqual(result["http_status"], 503)
        self.assertNotIn("SECRET_KEY", json.dumps(result))

    def test_offsite_redirect_not_accepted(self):
        opener = FakeOpener(status=200)
        class Offsite(FakeOpener):
            def open(self, request, timeout):
                return FakeResponse(200, "https://malicious.invalid/")
        self.assertFalse(module.probe_one("/api/health/", opener=Offsite())["healthy"])
        self.assertTrue(module.probe_one("/api/health/", opener=opener)["healthy"])

    def test_bad_non_https_origin_and_nonrelative_url_refused(self):
        with self.assertRaises(ValueError):
            module.probe_one("/", origin="http://zomorodmelal.ir", opener=FakeOpener())
        with self.assertRaises(ValueError):
            module.probe_one("//malicious.invalid", opener=FakeOpener())

    def test_unverified_or_evidence_less_manual_check_blocks_release(self):
        data = json.loads(self.doc.read_text())
        for item in data["checks"].values():
            item["status"] = "verified"
        self.doc.write_text(json.dumps(data))
        result = module.load_checklist(self.doc)
        self.assertFalse(result["all_verified"])
        self.assertEqual(len(result["outstanding"]), 9)

    def test_valid_manual_evidence_and_all_200_may_request_human_review(self):
        data = json.loads(self.doc.read_text())
        for key, item in data["checks"].items():
            item.update(status="verified", evidence=f"signed evidence for {key}")
        self.doc.write_text(json.dumps(data))
        result = module.build_report(
            online=True, root=self.root, checklist=self.doc,
            opener=FakeOpener(status=200),
        )
        self.assertEqual(result["status"], "READY_FOR_HUMAN_RELEASE_REVIEW")
        self.assertFalse(result["automatic_deploy_permitted"])
        self.assertTrue(result["production_ready"])

    def test_missing_schema_blocks_even_if_all_other_checks_pass(self):
        (self.root / module.SCHEMA_FILES[0]).unlink()
        self.assertFalse(module.schema_check(self.root)["ready"])
        report = module.build_report(online=False, root=self.root, checklist=self.doc)
        self.assertIn("database schema migration files absent", report["outstanding"])

    def test_probe_url_encoding_is_not_used_for_login_or_secret_submission(self):
        fake = FakeOpener()
        module.probe_one("/company/office/login/", opener=fake)
        self.assertEqual(len(fake.requests), 1)
        method, url, timeout = fake.requests[0]
        self.assertEqual(method, "GET")
        self.assertNotIn("password", url.lower())
        self.assertEqual(timeout, 13)


if __name__ == "__main__":
    unittest.main()
