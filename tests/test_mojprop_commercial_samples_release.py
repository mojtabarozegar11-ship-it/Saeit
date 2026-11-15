"""Source and isolated release integrity tests for Moj Prop sample fulfillment.

No network, cPanel, production database or customer payment is touched.
"""
from __future__ import annotations

import json
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

    def test_signal_desk_releases_public_example_and_separate_opt_in(self):
        source = SITE_SOURCE / "signals/index.html"
        baseline = SITE_SOURCE / "baselines/signals-index-before-free.html"
        self.assertTrue(source.is_file())
        self.assertTrue(baseline.is_file())
        html = source.read_text("utf-8")
        self.assertIn('id="free-preview"', html)
        self.assertIn('id="free-education-membership"', html)
        self.assertIn("/moj-signal-free-subscribe/", html)
        self.assertNotIn("/moj-signal-free-subscribe/", baseline.read_text("utf-8"))

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
        for path in release.FILES + (release.BASELINE_CATALOG, release.BASELINE_HOME, release.BASELINE_SIGNAL, release.BASELINE_SIGNAL_FREE_PREVIEW):
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
        self.assertFalse((self.route / "signals/index.html").exists())

    def test_signal_desk_existing_approved_baseline_is_upgradable_and_reversible(self):
        path = self.route / "signals/index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        prior = (SITE_SOURCE / release.BASELINE_SIGNAL).read_bytes()
        path.write_bytes(prior)
        release.deploy("123", "a" * 40)
        self.assertIn(b'id="free-education-membership"', path.read_bytes())
        backup = self.backups / "moj-prop-catalog-123"
        self.assertTrue((backup / "manifest.json").exists())
        release.restore(backup)
        self.assertEqual(path.read_bytes(), prior)

    def test_reviewed_free_preview_releases_to_double_optin_and_restores_exactly(self):
        page = self.route / "signals/index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        old = (SITE_SOURCE / release.BASELINE_SIGNAL_FREE_PREVIEW).read_bytes()
        self.assertIn(b'id="free-preview"', old)
        self.assertNotIn(b'id="free-education-membership"', old)
        page.write_bytes(old)
        release.deploy("123", "a" * 40)
        self.assertEqual(page.read_bytes(), (SITE_SOURCE / "signals/index.html").read_bytes())
        manifest = self.backups / "moj-prop-catalog-123"
        self.assertTrue((manifest / "manifest.json").is_file())
        release.restore(manifest)
        self.assertEqual(page.read_bytes(), old)

    def test_only_exact_free_preview_version_is_approved(self):
        page = self.route / "signals/index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        old = (SITE_SOURCE / release.BASELINE_SIGNAL_FREE_PREVIEW).read_bytes()
        page.write_bytes(old + b"<!-- unreviewed live addition -->")
        with self.assertRaisesRegex(RuntimeError, "differs from all exact reviewed baselines"):
            release.deploy("123", "a" * 40)
        self.assertEqual(page.read_bytes(), old + b"<!-- unreviewed live addition -->")
        self.assertFalse((self.backups / "moj-prop-catalog-123").exists())

    def test_unknown_live_signal_desk_blocks_deployment_and_preserves_customer_changes(self):
        path = self.route / "signals/index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Operator customised and unpublished content", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            release.deploy("123", "a" * 40)
        self.assertIn("Operator customised", path.read_text("utf-8"))
        self.assertFalse((self.backups / "moj-prop-catalog-123").exists())

    def test_readonly_preflight_proves_no_backup_or_live_write(self):
        before_home = (self.route / "index.html").read_bytes()
        before_catalog = (self.route / "catalog/index.html").read_bytes()
        with patch("builtins.print") as messages:
            release.preflight("123")
        self.assertIn("MOJ_PROP_STATIC_PREFLIGHT=PASS",
                      [call.args[0] for call in messages.call_args_list])
        self.assertEqual((self.route / "index.html").read_bytes(), before_home)
        self.assertEqual((self.route / "catalog/index.html").read_bytes(), before_catalog)
        self.assertFalse((self.backups / "moj-prop-catalog-123").exists())

    def test_readonly_preflight_refuses_unknown_live_content_before_any_write(self):
        target = self.route / "signals/index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("Unknown live Signal Desk content", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "differs from all exact reviewed baselines"):
            release.preflight("123")
        self.assertEqual(target.read_text("utf-8"), "Unknown live Signal Desk content")
        self.assertFalse((self.backups / "moj-prop-catalog-123").exists())

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

    def test_tampered_backup_manifest_never_restores_unapproved_paths(self):
        release.deploy("123", "a" * 40)
        directory = self.backups / "moj-prop-catalog-123"
        path = directory / "manifest.json"
        pristine = json.loads(path.read_text("utf-8"))
        delivered_home = (self.route / "index.html").read_bytes()

        def extra_entry(manifest):
            manifest["files"].append(dict(manifest["files"][0]))

        def forged_path(manifest):
            manifest["files"][0]["path"] = "../../outside.html"

        def mismatched_run(manifest):
            manifest["run_id"] = "124"

        def bad_digest(manifest):
            manifest["files"][0]["after_sha"] = "not-a-sha"

        def unsafe_mode(manifest):
            manifest["files"][0]["mode"] = 0o777

        for mutate in (extra_entry, forged_path, mismatched_run, bad_digest, unsafe_mode):
            with self.subTest(invalid=mutate.__name__):
                bad = json.loads(json.dumps(pristine))
                mutate(bad)
                path.write_text(json.dumps(bad), "utf-8")
                with self.assertRaises(RuntimeError):
                    release.restore(directory)
                self.assertEqual((self.route / "index.html").read_bytes(), delivered_home)
        path.write_text(json.dumps(pristine), "utf-8")
        release.restore(directory)

    def test_symlinked_backup_directory_cannot_be_used_for_rollback(self):
        release.deploy("123", "a" * 40)
        linked = self.backups / "moj-prop-catalog-888"
        linked.symlink_to(self.backups / "moj-prop-catalog-123", target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "Symlinked"):
            release.restore(linked)

    def test_symlinked_sample_target_blocks_installation(self):
        target = self.route / "samples/prop-blueprint/index.html"
        target.parent.mkdir(parents=True)
        target.symlink_to(self.route / "index.html")
        with self.assertRaisesRegex(RuntimeError, "Expected a regular file"):
            release.deploy("123", "a" * 40)
        self.assertFalse((self.backups / "moj-prop-catalog-123").exists())


if __name__ == "__main__":
    unittest.main()
