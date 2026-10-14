"""Offline tests for candidate-only MojPlayWin storefront release bundle."""
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from scripts.mpw_storefront_release_package import build_package
from scripts.mpw_branded_store_targeted_patch import EXPECTED


class ReleasePackageSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.site=self.root/"Saeit-staging"
        self.core=self.site/"core"
        self.core.mkdir(parents=True)
        self.active=self.core/"brand_views.py"
        self.active.write_text("from django.shortcuts import render\n\n"+EXPECTED)
        self.private=self.root/"private-staging"
        self.private.mkdir()
        self.destination=self.private/"candidate-v1"

    def test_generates_digested_candidate_and_rollback_with_no_live_edits(self):
        original=self.active.read_bytes()
        summary=build_package(self.active,self.destination)
        self.assertTrue(summary["candidate_only_not_deployed"])
        self.assertFalse(summary["paid_checkout_enabled"])
        self.assertFalse(summary["product_activation_performed"])
        self.assertEqual(self.active.read_bytes(),original)
        backup=(self.destination/"rollback/brand_views.py").read_bytes()
        patch=(self.destination/"core/brand_views.py").read_bytes()
        self.assertEqual(backup,original)
        self.assertNotEqual(patch,original)
        self.assertEqual(summary["baseline_sha256"],hashlib.sha256(original).hexdigest())
        self.assertEqual(summary["candidate_sha256"],hashlib.sha256(patch).hexdigest())
        self.assertIn("core/factory_storefront.py",summary["payload_sha256"])
        self.assertIn("core/templates/core/includes/mpw_verified_factory_cards.html",summary["payload_sha256"])
        self.assertIn("controlled atomic file promotion with rollback",summary["preflight_required"])
        self.assertEqual(json.loads((self.destination/"manifest.json").read_text())["live_destination"],"core/brand_views.py")

    def test_repeat_run_fails_without_overwriting_existing_output(self):
        build_package(self.active,self.destination)
        original=(self.destination/"core/brand_views.py").read_bytes()
        with self.assertRaisesRegex(ValueError,"RELEASE_OUTPUT_ALREADY_EXISTS"):
            build_package(self.active,self.destination)
        self.assertEqual((self.destination/"core/brand_views.py").read_bytes(),original)

    def test_edited_real_function_refuses_staging(self):
        self.active.write_text(self.active.read_text().replace('order_by("-id")','order_by("id")'))
        with self.assertRaisesRegex(ValueError,"DIFFERS_FROM_VERIFIED_BASELINE"):
            build_package(self.active,self.destination)
        self.assertFalse(self.destination.exists())

    def test_missing_source_or_symlink_refused(self):
        self.active.unlink()
        with self.assertRaises(ValueError):
            build_package(self.active,self.destination)
        self.active.symlink_to(Path(__file__).resolve())
        with self.assertRaises(ValueError):
            build_package(self.active,self.destination)

    def test_output_inside_active_django_project_refused(self):
        with self.assertRaisesRegex(ValueError,"UNSAFE_OUTPUT_LOCATION"):
            build_package(self.active,self.site/"private-artifact")
        self.assertFalse((self.site/"private-artifact").exists())

    def test_staging_must_have_existing_safe_parent(self):
        with self.assertRaises((FileNotFoundError,OSError)):
            build_package(self.active,self.root/"missing-parent/new")
