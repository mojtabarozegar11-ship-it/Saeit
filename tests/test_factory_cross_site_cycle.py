import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import sys

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scripts"))
SPEC = importlib.util.spec_from_file_location("cross_site_cycle", BASE / "scripts/factory_cross_site_cycle.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CrossSitePrivateRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.private = Path(self.temp.name)

    def test_real_repository_source_parity_and_opaque_site_runtime(self):
        result = MODULE.run(BASE, self.private)
        self.assertEqual(result["source_files_hash_verified"], 3)
        self.assertTrue(result["source_copy_integrity"])
        self.assertEqual(result["roles_zomorod"], 11)
        self.assertEqual(result["roles_mojplaywin_robots"], 11)
        self.assertFalse(result["site_monitoring_performed"])
        self.assertEqual(result["mojplaywin_module_slots_not_imported"], 77)
        self.assertEqual(result["factory_agents_added"], 0)
        self.assertFalse(result["quality_or_commercial_release_granted"])

    def test_real_html_preview_review_without_false_product_approval(self):
        preview = self.private / "digital-products" / "product_a" / "preview"
        preview.mkdir(parents=True)
        (preview / "index.html").write_text(
            '<html><head><title>Template</title><meta name="description" '
            'content="Factory product example"></head><body><h1>Preview</h1>'
            '<a href="/details/">Details</a></body></html>', encoding="utf-8")
        actual = MODULE.run(BASE, self.private)
        self.assertEqual(actual["html_previews_scanned"], 1)
        self.assertEqual(actual["html_previews"][0]["score"], 100)
        self.assertFalse(actual["html_previews"][0]["commercial_quality_approved"])
        self.assertFalse(actual["website_files_modified"])

    def test_broken_local_file_score_is_not_customer_ready(self):
        folder = self.private / "digital-products" / "product_a"
        folder.mkdir(parents=True)
        (folder / "index.html").write_text("<html><body><h1>A</h1><h1>B</h1></body></html>" + " " * 80)
        result = MODULE.run(BASE, self.private)
        self.assertEqual(result["html_previews"][0]["status"], "review")
        self.assertEqual(result["html_previews"][0]["score"], 0)
        self.assertFalse(result["html_previews"][0]["commercial_quality_approved"])

    def test_symlinked_html_is_not_read(self):
        folder = self.private / "digital-products" / "product_a"
        folder.mkdir(parents=True)
        (self.private / "elsewhere.html").write_text("x" * 100)
        (folder / "index.html").symlink_to(self.private / "elsewhere.html")
        result = MODULE.run(BASE, self.private)
        self.assertEqual(result["html_previews_scanned"], 0)

    def test_observed_77_remote_modules_are_not_fake_factory_workers(self):
        from datetime import datetime, timezone
        report = self.private / "cross-site-capabilities" / "federation.json"
        report.parent.mkdir(parents=True)
        report.write_text(json.dumps({
            "schema": "saeit.factory.site-federation.v1",
            "received_utc": datetime.now(timezone.utc).isoformat(),
            "module_slots_total": 77,
            "matched_site_source_count": 38,
        }))
        result = MODULE.run(BASE, self.private)
        self.assertEqual(result["federation"]["state"], "fresh_observed_remote_capabilities")
        self.assertEqual(result["federation"]["module_slots"], 77)
        self.assertEqual(result["federation"]["verified_factory_executions"], 0)
        self.assertFalse(result["quality_or_commercial_release_granted"])

    def test_report_atomic_and_private(self):
        path = self.private / "reports" / "last.json"
        data = MODULE.run(BASE, self.private)
        MODULE.write_report(path, data)
        self.assertEqual(json.loads(path.read_text())["schema"], MODULE.SCHEMA)
        self.assertEqual(path.stat().st_mode & 0o077, 0)
        self.assertEqual(path.parent.stat().st_mode & 0o077, 0)


if __name__ == "__main__":
    unittest.main()
