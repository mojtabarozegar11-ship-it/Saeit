"""Offline regression for live-preflight Engine.render(Context(...)) bug."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.mpw_factory_preflight_validation import check_brand_release
from scripts.mpw_branded_store_targeted_patch import EXPECTED

ROOT = Path(__file__).resolve().parents[1]
PARTIAL = ROOT / "core/templates/core/includes/mpw_verified_factory_cards.html"


class PreflightValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.src=self.root/"core_brand_views.py"
        self.src.write_text("from django.shortcuts import render\n\n"+EXPECTED)
        self.part=self.root/"mpw_verified_factory_cards.html"
        self.part.write_bytes(PARTIAL.read_bytes())

    def test_exact_baseline_and_django_template_pass(self):
        result=check_brand_release(self.src,self.part)
        self.assertTrue(result["exactly_one_branded_store_function_modified"])
        self.assertTrue(result["verified_free_template_renders"])
        self.assertTrue(result["empty_release_renders_no_extra_section"])
        self.assertTrue(result["unverified_paid_checkout_hidden"])
        self.assertTrue(result["html_autoescape_checked"])
        self.assertFalse(result["writes_performed"])
        self.assertEqual(len(result["active_brand_view_sha256"]),64)

    def test_no_source_file_modified(self):
        original=self.src.read_bytes()
        old_partial=self.part.read_bytes()
        check_brand_release(self.src,self.part)
        self.assertEqual(self.src.read_bytes(),original)
        self.assertEqual(self.part.read_bytes(),old_partial)

    def test_unexpected_changed_active_function_blocked(self):
        self.src.write_text(self.src.read_text().replace('order_by("-id")','order_by("id")'))
        with self.assertRaisesRegex(ValueError,"DIFFERS_FROM_VERIFIED_BASELINE"):
            check_brand_release(self.src,self.part)

    def test_missing_or_symlinked_inputs_are_blocked(self):
        self.src.unlink()
        with self.assertRaises(ValueError):
            check_brand_release(self.src,self.part)
        self.src.symlink_to(PARTIAL)
        with self.assertRaises(ValueError):
            check_brand_release(self.src,self.part)

    def test_script_never_claims_paid_checkout_for_free_listing(self):
        payload=self.part.read_text()
        self.assertIn("{% if factory_cards %}",payload)
        result=check_brand_release(self.src,self.part)
        self.assertTrue(result["unverified_paid_checkout_hidden"])

    def test_django_template_requires_explicit_context_object(self):
        from django.template import Context, Engine
        rendered=Engine().from_string("{{ field }}").render(Context({"field":"OK"}))
        self.assertEqual(rendered,"OK")
        # No call with dict: the old preflight errored with render_context AttributeError.


if __name__=="__main__":
    unittest.main()
