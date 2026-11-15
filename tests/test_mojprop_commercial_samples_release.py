"""Source and isolated release integrity tests for Moj Prop sample fulfillment.

No network, cPanel, production database or customer payment is touched.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import update_mojplaywin_moj_prop_catalog as release

ROOT = Path(__file__).resolve().parents[1]
SITE_SOURCE = ROOT / "templates/moj-prop-v4"


class MojPropCatalogSamplesContractTests(unittest.TestCase):
    def test_four_client_samples_are_valid_standalone_pages(self):
        for path in (
            "samples/prop-blueprint/index.html",
            "samples/gold-market-brief/index.html",
            "samples/educational-signal/index.html",
            "samples/commercial-gate-audit/index.html",
        ):
            with self.subTest(path=path):
                page = (SITE_SOURCE / path).read_text("utf-8")
                self.assertIn("<!doctype html>", page.lower())
                self.assertIn("<title>", page)
                self.assertIn('lang="en" dir="ltr"', page)
                self.assertIn('href="/moj-prop/#request"', page)
                self.assertNotIn('type="submit"', page)
                self.assertNotIn("wallet address", page.lower())

    def test_market_brief_uses_named_sources_and_no_unverified_quote(self):
        page = (SITE_SOURCE / "samples/gold-market-brief/index.html").read_text("utf-8")
        for expected in ("cmegroup.com", "gold.org", "elibrary.imf.org",
                         "Scenario A", "Scenario B", "Scenario C",
                         "No independently verified"):
            self.assertIn(expected, page)
        for unsafe in ("guaranteed profit", "BUY NOW", "SELL NOW", "live quote"):
            self.assertNotIn(unsafe, page)

    def test_blueprint_contains_risk_controls_and_contractual_non_sale_boundary(self):
        page = (SITE_SOURCE / "samples/prop-blueprint/index.html").read_text("utf-8")
        for required in ("Daily loss boundary", "Overall loss boundary",
                         "Separation of duties", "Deliverable acceptance",
                         "No purchase is performed"):
            self.assertIn(required, page)

    def test_catalog_links_to_both_real_sample_files(self):
        catalog = (SITE_SOURCE / "catalog/index.html").read_text("utf-8")
        for slug in ("prop-blueprint", "gold-market-brief",
                     "educational-signal", "commercial-gate-audit"):
            path = SITE_SOURCE / ("samples/" + slug + "/index.html")
            self.assertTrue(path.is_file(), slug)
            self.assertIn('href="/moj-prop/samples/' + slug + '/"', catalog)


    def test_every_catalog_offer_has_matching_sample_not_checkout(self):
        catalog = (SITE_SOURCE / "catalog/index.html").read_text("utf-8")
        for slug in ("prop-blueprint", "gold-market-brief", "educational-signal", "commercial-gate-audit"):
            page = SITE_SOURCE / ("samples/" + slug + "/index.html")
            self.assertTrue(page.is_file())
            self.assertIn("/moj-prop/samples/" + slug + "/", catalog)
            self.assertIn("/moj-prop/#request", page.read_text("utf-8"))
            self.assertNotIn("onchain_checkout(", page.read_text("utf-8"))

    def test_production_release_requires_private_receipt_endpoint_before_static_form(self):
        workflow = (ROOT / ".github/workflows/mojplaywin-moj-prop-deploy.yml").read_text("utf-8")
        self.assertIn("MOJ_PROP_STATUS_API_PREFLIGHT=PASS", workflow)
        self.assertIn("MOJ_PROP_API_PREFLIGHT=PASS", workflow)
        self.assertIn("inputs.owner_approved_static_release == true", workflow)
        self.assertLess(
            workflow.index("Verify live Django intake is ready BEFORE publishing form"),
            workflow.index("Verify private status receipt API exists"),
        )
        self.assertLess(
            workflow.index("Verify private status receipt API exists"),
            workflow.index("Update only /moj-prop/ commercial catalog"),
        )
        self.assertNotIn("scripts/deploy_mojplaywin_moj_prop_backend.py templates/moj-prop-v4", workflow)

    def test_source_control_keeps_both_old_baselines_immutable(self):
        for name in ("index-v4.html", "catalog-index-v4.html"):
            self.assertTrue((SITE_SOURCE / "baselines" / name).is_file())
        self.assertNotEqual(
            (SITE_SOURCE / "baselines/catalog-index-v4.html").read_bytes(),
            (SITE_SOURCE / "catalog/index.html").read_bytes(),
        )
        self.assertNotEqual(
            (SITE_SOURCE / "baselines/index-v4.html").read_bytes(),
            (SITE_SOURCE / "index.html").read_bytes(),
        )


class MojPropReleaseIsolatedBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.docroot = self.home / "mojplaywin.com"
        self.route = self.docroot / "moj-prop"
        self.route.mkdir(parents=True)
        stage = self.home / ".mojplaywin-moj-prop-catalog-123" / "templates/moj-prop-v4"
        for path in release.FILES + (release.BASELINE_CATALOG, release.BASELINE_HOME):
            source = SITE_SOURCE / path
            target = stage / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        for before, current in (("baselines/index-v4.html", "index.html"),
                                ("baselines/catalog-index-v4.html", "catalog/index.html")):
            source = SITE_SOURCE / before
            target = self.route / current
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        self.backups = self.home / ".mojplaywin-backups"
        for key, value in (
            ("HOME", self.home),
            ("DOCROOT", self.docroot),
            ("ROUTE", self.route),
            ("BACKUPS", self.backups),
            ("validate_host", lambda: None),
        ):
            p = patch.object(release, key, value)
            p.start()
            self.addCleanup(p.stop)
        self.stage = stage

    def test_updater_delivers_both_samples_and_retains_reversible_catalog(self):
        old_index = (self.route / "index.html").read_bytes()
        old_catalog = (self.route / "catalog/index.html").read_bytes()
        release.deploy("123", "a" * 40)
        for path in release.FILES:
            self.assertEqual((self.route / path).read_bytes(), (self.stage / path).read_bytes())
        backup = self.backups / "moj-prop-catalog-123"
        self.assertTrue((backup / "manifest.json").is_file())
        release.restore(backup)
        self.assertEqual((self.route / "index.html").read_bytes(), old_index)
        self.assertEqual((self.route / "catalog/index.html").read_bytes(), old_catalog)
        self.assertFalse((self.route / "samples/prop-blueprint/index.html").exists())
        self.assertFalse((self.route / "samples/gold-market-brief/index.html").exists())
        self.assertFalse((self.route / "samples/educational-signal/index.html").exists())
        self.assertFalse((self.route / "samples/commercial-gate-audit/index.html").exists())

    def test_idempotent_deploy_never_makes_second_backup(self):
        release.deploy("123", "a" * 40)
        release.deploy("123", "a" * 40)
        self.assertEqual(len(list(self.backups.glob("moj-prop-catalog-*"))), 1)

    def test_unauthorized_catalog_modification_blocks_all_writes(self):
        (self.route / "catalog/index.html").write_text("<title>Unapproved change</title>", "utf-8")
        with self.assertRaisesRegex(RuntimeError, "differs from both approved baseline"):
            release.deploy("123", "a" * 40)
        self.assertFalse((self.route / "samples/prop-blueprint/index.html").exists())
        self.assertFalse((self.backups / "moj-prop-catalog-123").exists())

    def test_unauthorized_home_modification_blocks_all_writes(self):
        (self.route / "index.html").write_text("<title>Changed without approval</title>", "utf-8")
        with self.assertRaisesRegex(RuntimeError, "Live home differs from approved baseline"):
            release.deploy("123", "a" * 40)
        self.assertFalse((self.route / "samples/prop-blueprint/index.html").exists())

    def test_mutated_live_content_fails_closed_during_rollback(self):
        release.deploy("123", "a" * 40)
        page = self.route / "index.html"
        page.write_bytes(page.read_bytes() + b"<!-- external edit -->")
        with self.assertRaisesRegex(RuntimeError, "subsequently modified"):
            release.restore(self.backups / "moj-prop-catalog-123")
        self.assertTrue((self.route / "samples/prop-blueprint/index.html").exists())

    def test_symlinked_sample_target_blocks_installation(self):
        target = self.route / "samples/prop-blueprint/index.html"
        target.parent.mkdir(parents=True)
        target.symlink_to(self.route / "index.html")
        with self.assertRaisesRegex(RuntimeError, "Expected a regular file"):
            release.deploy("123", "a" * 40)
        self.assertFalse((self.backups / "moj-prop-catalog-123").exists())


if __name__ == "__main__":
    unittest.main()
