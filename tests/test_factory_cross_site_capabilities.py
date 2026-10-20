import importlib.util
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import unittest

P = Path(__file__).resolve().parents[1] / "scripts" / "factory_cross_site_capabilities.py"
spec = importlib.util.spec_from_file_location("factory_cross_site_capabilities", P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class CrossSiteFactoryCapabilityTests(unittest.TestCase):
    def test_real_source_copies_are_byte_identical_and_registry_is_grounded(self):
        report = m.audit_repo(P.parents[1])
        self.assertEqual(report["imported_source_files"], 3)
        self.assertTrue(all(x["identical_source_copy"] for x in report["sources"]))
        self.assertEqual(len(report["zomorod_site_agents"]), 11)
        self.assertEqual(len(report["mojplaywin_health_roles"]), 11)
        self.assertEqual(report["mojplaywin_private_robot_roles"], 11)
        self.assertEqual(report["mojplaywin_module_slots"], 77)
        self.assertFalse(report["module_names_retrieved_from_private_runtime"])
        self.assertEqual(report["newly_activated_factory_agents"], 0)
        self.assertFalse(report["site_generations_directly_comparable_to_factory"])

    def test_factory_web_preview_uses_site_review_logic_no_public_approval(self):
        body = (b'<html><head><title>Page</title>'
                b'<meta name="description" content="Clear summary"></head>'
                b'<body><h1>Title</h1><a href="/about/">About</a>'
                b'<p>Example local preview for a factory product</p></body></html>')
        result = m.html_quality(200, "text/html;charset=utf-8", body)
        self.assertEqual(result["status"], "review")
        self.assertEqual(result["score"], 100)
        self.assertFalse(result["publish_approved"])
        self.assertEqual(result["issues"], [])

    def test_failed_page_never_passes(self):
        self.assertEqual(m.html_quality(503, "text/html", b"unavailable")["status"], "blocked")
        self.assertEqual(m.html_quality(200, "text/plain", b"x" * 100)["score"], 0)
        with self.assertRaises(ValueError):
            m.html_quality(200, "text/html", b"x" * (m.MAX_HTML + 1))

    def test_reuse_site_issue_detection_in_factory(self):
        s = b"<html><head></head><body><h1>A</h1><h1>B</h1></body></html>" + b" " * 64
        x = m.html_quality(200, "text/html", s)
        self.assertEqual(x["status"], "review")
        self.assertIn("missing_title", x["issues"])
        self.assertIn("h1_count_not_one", x["issues"])
        self.assertIn("missing_meta_description", x["issues"])
        self.assertIn("no_anchor_links", x["issues"])
        self.assertEqual(x["score"], 0)

    def test_stale_missing_and_load_only_not_marked_healthy(self):
        now = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
        self.assertEqual(m.telemetry_state("healthy", None, now), "unknown")
        self.assertEqual(m.telemetry_state("healthy", "2026-10-19T00:00:00Z", now), "stale")
        self.assertEqual(m.telemetry_state("loaded_only", "2026-10-20T11:00:00Z", now), "loaded_only")
        self.assertEqual(m.telemetry_state("failed", "2026-10-20T11:00:00Z", now), "failed")
        self.assertEqual(m.telemetry_state("gen65_operational_private",
                                            "2026-10-20T11:59:00Z", now, 300), "healthy")
        self.assertEqual(m.telemetry_state("ok", "2026-10-20T12:02:00Z", now), "stale")

    def test_private_copy_mismatch_fails_without_overwriting(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for _, origin, imported in m.SOURCES:
                original = root / origin
                clone = root / imported
                original.parent.mkdir(parents=True, exist_ok=True)
                clone.parent.mkdir(parents=True, exist_ok=True)
                original.write_bytes(b"legitimate source")
                clone.write_bytes(b"legitimate source")
            (root / m.SOURCES[1][2]).write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "CROSS_SITE_COPY_MISMATCH"):
                m.audit_repo(root)


if __name__ == "__main__":
    unittest.main()
