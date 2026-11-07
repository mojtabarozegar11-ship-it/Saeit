"""Offline-only redaction and manifest checks. No production connections."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.mpw_store_dynamic_readonly_diag_20261107 import (
    classify_frame,
    manifest_summary,
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
            self.assertEqual(result, {
                "state": "readable",
                "css_recorded": True,
                "header_image_recorded": False,
                "css_collected": True,
                "header_image_collected": False,
            })
            self.assertNotIn("must-not-be-printed", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
