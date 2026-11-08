"""Offline-only redaction and manifest checks. No production connections."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.mpw_store_dynamic_readonly_diag_20261107 import (
    classify_frame,
    manifest_target_collected,
    manifest_summary,
    static_root_matches_expected,
    safe_error,
)


class SafeDiagnosticTests(unittest.TestCase):
    def test_no_exception_message_or_buyer_data_in_output(self):
        result = safe_error("django_setup", ValueError("secret buyer address"))
        payload = json.dumps(result)
        self.assertEqual(result["exception_class"], "ValueError")
        self.assertEqual(result["exception_origin"], "unknown")
        self.assertNotIn("secret buyer address", payload)
        self.assertFalse(result["payments_created"])
        self.assertFalse(result["mail_sent"])
        self.assertFalse(result["source_mutated"])

    def test_only_fixed_origin_labels_are_emitted(self):
        self.assertEqual(classify_frame("/venv/whitenoise/storage.py"), "staticfiles_storage")
        self.assertEqual(classify_frame("/venv/django/template/base.py"), "django_template_engine")
        self.assertEqual(classify_frame("/app/command_center/mpw_public.py"), "managed_public_context")
        self.assertEqual(classify_frame("/app/private/buyer@example.com"), "unknown")

    def test_manifest_missing_is_reported_without_side_effects(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(manifest_summary(root), {"state": "missing"})

    def test_manifest_presence_reports_only_fixed_boolean_keys(self):
        with tempfile.TemporaryDirectory() as root:
            static = Path(root) / "staticfiles"
            (static / "site").mkdir(parents=True)
            (static / "site/mojplaywin.css").write_text("body{}", encoding="utf-8")
            (static / "staticfiles.json").write_text(json.dumps({
                "paths": {"site/mojplaywin.css": "site/mojplaywin.abc123.css"},
                "private_secret": "must-not-be-printed",
            }), encoding="utf-8")
            result = manifest_summary(root)
            self.assertIsInstance(result.pop("free_space_above_512mib"), bool)
            self.assertEqual(result, {
                "state": "readable",
                "header_image_source_present": False,
                "css_recorded": True,
                "header_image_recorded": False,
                "css_collected": True,
                "header_image_collected": False,
                "css_manifest_target_collected": False,
                "header_image_manifest_target_collected": False,
            })
            self.assertNotIn("must-not-be-printed", json.dumps(result))

    def test_source_asset_detected_without_following_symlink(self):
        with tempfile.TemporaryDirectory() as root:
            static = Path(root) / "staticfiles"
            static.mkdir()
            (static / "staticfiles.json").write_text('{"paths":{}}', encoding="utf-8")
            source = Path(root) / "core/static/site/mojplaywin-header-emblem.jpg"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"original-image")
            self.assertTrue(manifest_summary(root)["header_image_source_present"])
            source.unlink()
            external = Path(root) / "outside.jpg"
            external.write_bytes(b"another-image")
            source.symlink_to(external)
            self.assertFalse(manifest_summary(root)["header_image_source_present"])

    def test_effective_static_root_guard(self):
        with tempfile.TemporaryDirectory() as root:
            expected = Path(root) / "staticfiles"
            expected.mkdir()
            self.assertTrue(static_root_matches_expected(expected, root))
            self.assertFalse(static_root_matches_expected(None, root))
            self.assertFalse(static_root_matches_expected(Path(root) / "other", root))
            link = Path(root) / "linked"
            link.symlink_to(expected, target_is_directory=True)
            self.assertFalse(static_root_matches_expected(link, root))

    def test_manifest_targets_distinguish_collected_hashes_from_originals(self):
        with tempfile.TemporaryDirectory() as root:
            static = Path(root) / "staticfiles"
            (static / "site").mkdir(parents=True)
            (static / "site/mojplaywin.abc123.css").write_text("body{}", encoding="utf-8")
            (static / "site/mojplaywin-header-emblem.a1b2c3.jpg").write_bytes(b"jpeg")
            (static / "staticfiles.json").write_text(json.dumps({"paths": {
                "site/mojplaywin.css": "site/mojplaywin.abc123.css",
                "site/mojplaywin-header-emblem.jpg": "site/mojplaywin-header-emblem.a1b2c3.jpg",
            }}), encoding="utf-8")
            result = manifest_summary(root)
            self.assertTrue(result["css_manifest_target_collected"])
            self.assertTrue(result["header_image_manifest_target_collected"])
            self.assertFalse(result["css_collected"])
            self.assertFalse(result["header_image_collected"])

    def test_manifest_targets_refuse_unsafe_or_symlinked_paths(self):
        with tempfile.TemporaryDirectory() as root:
            static = Path(root) / "staticfiles"
            (static / "site").mkdir(parents=True)
            (static / "site/mojplaywin.actual.css").write_text("ok", encoding="utf-8")
            key = "site/mojplaywin.css"
            for invalid in ("../secret", "/etc/passwd", "site/../../secret", "site/other.css",
                            "site/mojplaywin\\bad.css", "site/mojplaywin.png"):
                self.assertFalse(manifest_target_collected(static, {key: invalid}, key))
            (static / "site/mojplaywin.link.css").symlink_to(static / "site/mojplaywin.actual.css")
            self.assertFalse(manifest_target_collected(static, {key: "site/mojplaywin.link.css"}, key))


    def test_guarded_store_source_requires_post_repair_code(self):
        from scripts.mpw_store_dynamic_readonly_diag_20261107 import (
            REQUIRED_BYTES, GUARDED_STORE_ANCHOR, known_guarded_store_source,
        )
        fixture = (GUARDED_STORE_ANCHOR + b"\n try:\n  from .commerce_funnel import record_funnel_event\n"
                   b" except Exception as exc:\n  pass\n")
        self.assertLess(len(fixture), REQUIRED_BYTES)
        fixture += b"#" * (REQUIRED_BYTES - len(fixture))
        self.assertTrue(known_guarded_store_source(fixture))
        self.assertFalse(known_guarded_store_source(fixture.replace(b"except Exception as exc:", b"except ValueError as exc:")))
        self.assertFalse(known_guarded_store_source(fixture + b"changed"))
        self.assertFalse(known_guarded_store_source(fixture.replace(GUARDED_STORE_ANCHOR, b"def store(request):\n from .commerce_funnel import record_funnel_event")))

    def test_diagnostic_never_stubs_analytics_and_checks_real_route(self):
        source = (Path(__file__).resolve().parents[1] /
                  "scripts/mpw_store_dynamic_readonly_diag_20261107.py").read_text()
        self.assertNotIn("patch.dict", source)
        self.assertNotIn("types.ModuleType", source)
        self.assertIn("resolve(\"/store/\")", source)
        self.assertIn("Client(raise_request_exception=False)", source)
        self.assertIn('"routed_django_get": route_check', source)


if __name__ == "__main__":
    unittest.main()
