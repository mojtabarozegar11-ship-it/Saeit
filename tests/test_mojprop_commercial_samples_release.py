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

    def test_starter30_all_three_public_assets_are_atomic_release_members(self):
        expected = (
            Path("starter-30-trx/index.html"),
            Path("starter-30-trx/journal-template.csv"),
            Path("starter-30-trx/journal-guide.txt"),
        )
        for item in expected:
            with self.subTest(item=str(item)):
                self.assertIn(item, release.FILES)
                self.assertTrue((SITE_SOURCE / item).is_file())
        self.assertEqual(len(release.FILES), len(set(release.FILES)))
        home = (SITE_SOURCE / "index.html").read_text("utf-8")
        catalog = (SITE_SOURCE / "catalog/index.html").read_text("utf-8")
        self.assertNotIn('href="/moj-prop/starter-30-trx/"', home)
        self.assertIn("SOLE CURRENT PRODUCT", home)
        self.assertIn("MOJ-PROP-01", home)
        self.assertIn('href="/moj-prop/starter-30-trx/"', catalog)
        starter = (SITE_SOURCE / expected[0]).read_text("utf-8")
        self.assertIn("./journal-template.csv", starter)
        self.assertIn("./journal-guide.txt", starter)
        self.assertIn("Payment not enabled", starter)
        self.assertIn("not a funded account", starter)

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
        for name in ("index-v4.html", "catalog-index-v4.html", "contact-index-pre-plan1.html"):
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
        for path in release.FILES + release.PRESERVED_LIVE_FILES + (release.BASELINE_CATALOG, release.BASELINE_HOME, release.BASELINE_CONTACT, release.BASELINE_SIGNAL, release.BASELINE_SIGNAL_FREE_PREVIEW):
            source = SITE_SOURCE / path
            target = stage / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        for before, current in (("baselines/index-v4.html", "index.html"),
                                ("baselines/catalog-index-v4.html", "catalog/index.html"),
                                ("baselines/contact-index-pre-plan1.html", "contact/index.html")):
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

    def test_plan1_contact_is_an_atomic_member_and_legacy_manifest_is_rejected(self):
        self.assertIn(Path("contact/index.html"), release.FILES)
        self.assertIn("v4-contact-rollback", release.MANIFEST_SCHEMA)
        self.assertNotIn(Path("signals/index.html"), release.FILES)
        old = (self.route / "contact/index.html").read_bytes()
        release.deploy("123", "a" * 40)
        self.assertEqual(
            (self.route / "contact/index.html").read_bytes(),
            (self.stage / "contact/index.html").read_bytes(),
        )
        backup = self.backups / "moj-prop-catalog-123"
        manifest = json.loads((backup / "manifest.json").read_text("utf-8"))
        self.assertEqual(manifest["schema"], release.MANIFEST_SCHEMA)
        self.assertIn("contact/index.html", [item["path"] for item in manifest["files"]])
        release.restore(backup)
        self.assertEqual((self.route / "contact/index.html").read_bytes(), old)

    def test_owner_modified_live_contact_is_never_overwritten(self):
        contact = self.route / "contact/index.html"
        contact.write_text("Owner-managed contact page", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "Live Plan1 contact differs"):
            release.deploy("123", "a" * 40)
        self.assertEqual(contact.read_text("utf-8"), "Owner-managed contact page")
        self.assertFalse((self.backups / "moj-prop-catalog-123").exists())

    def test_unreviewed_staged_contact_or_direct_404_link_denies_release(self):
        staged = self.stage / "contact/index.html"
        original = staged.read_bytes()
        for altered in (
            b"<html><body>Unreviewed inquiry</body></html>",
            original.replace(b"Dedicated Plan 1 form not live",
                             b'<a href="/moj-prop-interest/form/">Submit private data</a>'),
        ):
            with self.subTest(bad_size=len(altered)):
                staged.write_bytes(altered)
                with self.assertRaisesRegex(RuntimeError, "Prelaunch contact is not"):
                    release.deploy("123", "a" * 40)
                self.assertFalse((self.backups / "moj-prop-catalog-123").exists())
        staged.write_bytes(original)

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

    def test_missing_starter30_artifact_rejects_all_release_before_backup(self):
        missing = self.stage / "starter-30-trx/journal-guide.txt"
        missing.unlink()
        with self.assertRaisesRegex(RuntimeError, "Expected a regular file"):
            release.deploy("123", "a" * 40)
        self.assertFalse((self.backups / "moj-prop-catalog-123").exists())
        self.assertFalse((self.route / "starter-30-trx/index.html").exists())

    def test_starter30_csv_cannot_carry_trading_positions_or_formulas(self):
        page = self.stage / "starter-30-trx/journal-template.csv"
        page.write_text(
            "session,closing_equity_usd,risk_plan_recorded,reflection_recorded\n"
            + "1,=WEBSERVICE(\"https://invalid.example\"),yes,yes\n"
            + "".join(f"{i},,,\n" for i in range(2, 11)),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(RuntimeError, "exactly 10 EMPTY simulated sessions"):
            release.deploy("123", "a" * 40)
        self.assertFalse((self.backups / "moj-prop-catalog-123").exists())

    def test_live_starter30_owner_edit_blocks_release_and_preserves_source(self):
        file = self.route / "starter-30-trx/journal-guide.txt"
        file.parent.mkdir(parents=True)
        file.write_text("Operator-authored private teaching notes; do not overwrite", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "unexpected content"):
            release.deploy("123", "a" * 40)
        self.assertIn("Operator-authored", file.read_text("utf-8"))
        self.assertFalse((self.backups / "moj-prop-catalog-123").exists())

    def test_starter30_assets_are_removed_on_clean_rollback(self):
        release.deploy("123", "a" * 40)
        backup = self.backups / "moj-prop-catalog-123"
        entries = json.loads((backup / "manifest.json").read_text("utf-8"))["files"]
        indexed = {entry["path"] for entry in entries}
        for path in release.STARTER30_FILES + (Path("starter-30-trx/index.html"),):
            self.assertIn(str(path), indexed)
            self.assertEqual((self.route / path).read_bytes(), (self.stage / path).read_bytes())
        release.restore(backup)
        for path in release.STARTER30_FILES + (Path("starter-30-trx/index.html"),):
            self.assertFalse((self.route / path).exists(), str(path))

    def test_corrupted_last_backup_refuses_any_partial_live_restore(self):
        # Reverse-order rollback would restore catalog BEFORE discovering that
        # its final saved home/index.html is corrupt. Verify zero live writes.
        release.deploy("123", "a" * 40)
        backup = self.backups / "moj-prop-catalog-123"
        live_home = (self.route / "index.html").read_bytes()
        live_catalog = (self.route / "catalog/index.html").read_bytes()
        live_starter = (self.route / "starter-30-trx/index.html").read_bytes()
        saved_home = backup / "files/index.html"
        original = saved_home.read_bytes()
        saved_home.write_bytes(b"tampered old home")
        with self.assertRaisesRegex(RuntimeError, "Backup checksum mismatch before any live change"):
            release.restore(backup)
        self.assertEqual((self.route / "index.html").read_bytes(), live_home)
        self.assertEqual((self.route / "catalog/index.html").read_bytes(), live_catalog)
        self.assertEqual((self.route / "starter-30-trx/index.html").read_bytes(), live_starter)
        saved_home.write_bytes(original)
        release.restore(backup)
        self.assertNotEqual((self.route / "index.html").read_bytes(), live_home)

    def test_symlinked_saved_home_is_denied_before_rollback_modifies_site(self):
        release.deploy("123", "a" * 40)
        backup = self.backups / "moj-prop-catalog-123"
        live_catalog = (self.route / "catalog/index.html").read_bytes()
        saved_home = backup / "files/index.html"
        saved_home.unlink()
        foreign = self.home / "external-owner-content"
        foreign.write_bytes(b"unrelated tenant content")
        saved_home.symlink_to(foreign)
        with self.assertRaisesRegex(RuntimeError, "Expected a regular file"):
            release.restore(backup)
        self.assertEqual((self.route / "catalog/index.html").read_bytes(), live_catalog)
        self.assertEqual(foreign.read_bytes(), b"unrelated tenant content")

    def test_insecure_saved_backup_mode_is_denied_before_rollback(self):
        release.deploy("123", "a" * 40)
        backup = self.backups / "moj-prop-catalog-123"
        saved = backup / "files/index.html"
        saved.chmod(0o644)
        original_live = (self.route / "index.html").read_bytes()
        with self.assertRaisesRegex(RuntimeError, "Unsafe saved backup owner or permissions"):
            release.restore(backup)
        self.assertEqual((self.route / "index.html").read_bytes(), original_live)

    def test_deploy_denies_unverified_saved_bytes_before_publication(self):
        # Even if the backup was corrupted immediately after copying it, the
        # static publisher must refuse before changing any public sales page.
        old_home = (self.route / "index.html").read_bytes()
        old_catalog = (self.route / "catalog/index.html").read_bytes()
        with patch.object(release, "verified_saved_bytes",
                          side_effect=RuntimeError("all-file backup failed")):
            with self.assertRaisesRegex(RuntimeError, "all-file backup failed"):
                release.deploy("123", "a" * 40)
        self.assertEqual((self.route / "index.html").read_bytes(), old_home)
        self.assertEqual((self.route / "catalog/index.html").read_bytes(), old_catalog)
        self.assertFalse((self.route / "starter-30-trx/index.html").exists())

    def test_mismatched_live_starter30_digest_prevents_incorrect_rollback(self):
        release.deploy("123", "a" * 40)
        buyer_access = self.route / "starter-30-trx/journal-guide.txt"
        buyer_access.write_bytes(buyer_access.read_bytes() + b"\noperator revision\n")
        with self.assertRaisesRegex(RuntimeError, "subsequently modified"):
            release.restore(self.backups / "moj-prop-catalog-123")
        self.assertTrue((self.route / "starter-30-trx/index.html").is_file())

    def test_new_manifest_cannot_be_downgraded_to_legacy_seven_file_rollback(self):
        release.deploy("123", "a" * 40)
        path = self.backups / "moj-prop-catalog-123/manifest.json"
        full = json.loads(path.read_text("utf-8"))
        self.assertEqual(full["schema"], release.MANIFEST_SCHEMA)
        self.assertEqual(len(full["files"]), len(release.FILES))
        # An untrusted manifest edited to look like the 7-file legacy version
        # may otherwise leave the newly deployed Starter30 assets untouched.
        forged = dict(full)
        forged.pop("schema")
        forged["files"] = full["files"][:7]
        path.write_text(json.dumps(forged), "utf-8")
        with self.assertRaisesRegex(RuntimeError, "Legacy or unrecognized"):
            release.restore(path.parent)
        self.assertTrue((self.route / "starter-30-trx/index.html").is_file())
        path.write_text(json.dumps(full), "utf-8")
        release.restore(path.parent)

    def test_signal_desk_baseline_is_preserved_without_any_replacement(self):
        path = self.route / "signals/index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        prior = (SITE_SOURCE / release.BASELINE_SIGNAL).read_bytes()
        path.write_bytes(prior)
        release.deploy("123", "a" * 40)
        self.assertEqual(path.read_bytes(), prior)
        backup = self.backups / "moj-prop-catalog-123"
        manifest = json.loads((backup / "manifest.json").read_text("utf-8"))
        self.assertNotIn("signals/index.html", [entry["path"] for entry in manifest["files"]])
        release.restore(backup)
        self.assertEqual(path.read_bytes(), prior)


    def test_existing_free_preview_is_preserved_on_static_starter30_release(self):
        page = self.route / "signals/index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        old = (SITE_SOURCE / release.BASELINE_SIGNAL_FREE_PREVIEW).read_bytes()
        page.write_bytes(old)
        release.deploy("123", "a" * 40)
        self.assertEqual(page.read_bytes(), old)
        self.assertTrue((self.route / "starter-30-trx/journal-guide.txt").is_file())
        release.restore(self.backups / "moj-prop-catalog-123")
        self.assertEqual(page.read_bytes(), old)


    def test_unreviewed_signal_edit_is_never_replaced_by_product_release(self):
        page = self.route / "signals/index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        original = (SITE_SOURCE / release.BASELINE_SIGNAL_FREE_PREVIEW).read_bytes()
        modified = original + b"<!-- independently reviewed only by the owner -->"
        page.write_bytes(modified)
        release.deploy("123", "a" * 40)
        self.assertEqual(page.read_bytes(), modified)
        release.restore(self.backups / "moj-prop-catalog-123")
        self.assertEqual(page.read_bytes(), modified)


    def test_unknown_live_signal_is_preserved_while_starter30_assets_publish(self):
        path = self.route / "signals/index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        unchanged = b"Operator customised and unpublished content"
        path.write_bytes(unchanged)
        release.deploy("123", "a" * 40)
        self.assertEqual(path.read_bytes(), unchanged)
        self.assertTrue((self.route / "starter-30-trx/index.html").exists())
        manifest = json.loads((self.backups / "moj-prop-catalog-123/manifest.json").read_text("utf-8"))
        self.assertEqual(len(manifest["files"]), len(release.FILES))
        self.assertNotIn("signals/index.html", [entry["path"] for entry in manifest["files"]])
        release.restore(self.backups / "moj-prop-catalog-123")
        self.assertEqual(path.read_bytes(), unchanged)
        self.assertFalse((self.route / "starter-30-trx/index.html").exists())


    def test_symlinked_live_signal_desk_still_blocks_publish_for_tenant_safety(self):
        path = self.route / "signals/index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        outside = self.home / "other-private-tenant.html"
        outside.write_text("PRIVATE CONTENT", encoding="utf-8")
        path.symlink_to(outside)
        with self.assertRaisesRegex(RuntimeError, "Unsafe Signal Desk path"):
            release.deploy("123", "a" * 40)
        self.assertEqual(outside.read_text("utf-8"), "PRIVATE CONTENT")
        self.assertFalse((self.route / "starter-30-trx/index.html").exists())
        self.assertFalse((self.backups / "moj-prop-catalog-123").exists())

    def test_legacy_ten_file_manifest_can_never_rewrite_owner_signal(self):
        live = self.route / "signals/index.html"
        live.parent.mkdir(parents=True, exist_ok=True)
        live.write_bytes(b"customer signal changes are protected")
        release.deploy("123", "a" * 40)
        path = self.backups / "moj-prop-catalog-123/manifest.json"
        original = json.loads(path.read_text("utf-8"))
        forged = dict(original)
        forged["schema"] = "mojprop.static.starter30.v2"
        path.write_text(json.dumps(forged), "utf-8")
        with self.assertRaisesRegex(RuntimeError, "Legacy or unrecognized"):
            release.restore(path.parent)
        self.assertEqual(live.read_bytes(), b"customer signal changes are protected")
        path.write_text(json.dumps(original), "utf-8")
        release.restore(path.parent)
        self.assertEqual(live.read_bytes(), b"customer signal changes are protected")

    def test_symlinked_backup_root_cannot_redirect_starter30_publication(self):
        foreign = self.home / "unrelated-tenant-private"
        foreign.mkdir()
        self.backups.symlink_to(foreign, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "Symlinked Moj Prop backup root"):
            release.deploy("123", "a" * 40)
        self.assertEqual(list(foreign.iterdir()), [])
        self.assertFalse((self.route / "starter-30-trx/index.html").exists())

    def test_preexisting_untrusted_backup_root_is_not_chmod_repaired(self):
        self.backups.mkdir()
        self.backups.chmod(0o755)
        with self.assertRaisesRegex(RuntimeError, "Untrusted Moj Prop backup root owner or mode"):
            release.deploy("123", "a" * 40)
        self.assertEqual(self.backups.stat().st_mode & 0o777, 0o755)
        self.assertFalse((self.route / "starter-30-trx/index.html").exists())

    def test_world_writable_backup_parent_blocks_release_without_public_writes(self):
        self.home.chmod(0o777)
        with self.assertRaisesRegex(RuntimeError, "Untrusted Moj Prop backup parent owner or mode"):
            release.deploy("123", "a" * 40)
        self.assertFalse(self.backups.exists())
        self.assertFalse((self.route / "starter-30-trx/index.html").exists())

    def test_backup_root_replacement_cannot_redirect_rollback(self):
        release.deploy("123", "a" * 40)
        moved = self.home / "unrelated-existing-vault"
        self.backups.rename(moved)
        self.backups.symlink_to(moved, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "Symlinked Moj Prop backup root"):
            release.restore(self.backups / "moj-prop-catalog-123")
        self.assertTrue((self.route / "starter-30-trx/index.html").exists())
        self.assertTrue((moved / "moj-prop-catalog-123/manifest.json").is_file())

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

    def test_readonly_preflight_accepts_unknown_signal_but_never_writes(self):
        target = self.route / "signals/index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("Unknown live Signal Desk content", encoding="utf-8")
        with patch("builtins.print") as messages:
            release.preflight("123")
        self.assertIn("MOJ_PROP_STATIC_PREFLIGHT=PASS",
                      [call.args[0] for call in messages.call_args_list])
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
