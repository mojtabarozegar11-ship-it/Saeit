"""Isolated cPanel manifest classification checks: never turn hashes into release."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts import mojprop_starter30_baseline_compare as compare


class MojPropStaticBaselineEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "templates/moj-prop-v4"
        self.root.mkdir(parents=True)
        self.content = {}
        for names in compare.FILES.values():
            for name in names:
                file = self.root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                body = ("reviewed source " + name + "\n").encode()
                file.write_bytes(body)
                self.content[name] = body
        for name in compare.PRODUCT.values():
            file = self.root / name
            file.parent.mkdir(parents=True, exist_ok=True)
            body = ("starter educational " + name + "\n").encode()
            file.write_bytes(body)
            self.content[name] = body
        self.evidence = {
            "schema": compare.SCHEMA,
            "read_only": True,
            "release_permitted": False,
            "revenue_proven": False,
            "owner_account_verified": True,
            "docroot_and_route_ownership_verified": True,
            "public_page_digests": {},
            "assets": {},
        }
        for key, names in compare.FILES.items():
            data = self.content[names[-1]]
            self.evidence["public_page_digests"][key] = {
                "readable": True, "sha256": hashlib.sha256(data).hexdigest()
            }
        for key, name in compare.PRODUCT.items():
            data = self.content[name]
            self.evidence["assets"][key] = {
                "readable": True, "sha256_prefix": hashlib.sha256(data).hexdigest()[:16]
            }

    def result(self):
        return compare.classify(self.evidence, self.root)

    def test_exact_known_source_is_classified_without_release(self):
        report = self.result()
        self.assertTrue(all(x == "reviewed_baseline_or_source" for x in report["public_pages"].values()))
        self.assertFalse(report["release_permitted"])
        self.assertFalse(report["independent_restore_verified"])

    def test_known_legacy_version_is_accepted_for_comparison_only(self):
        old = self.content[compare.FILES["home"][0]]
        self.evidence["public_page_digests"]["home"]["sha256"] = hashlib.sha256(old).hexdigest()
        self.assertTrue(self.result()["existing_home_catalog_signal_match_reviewed_source_or_baseline"])

    def test_page_owner_edit_does_not_pass_known_baseline(self):
        self.evidence["public_page_digests"]["home"]["sha256"] = hashlib.sha256(b"owner edit").hexdigest()
        result = self.result()
        self.assertTrue(result["owner_edit_or_unknown_content_detected"])
        self.assertFalse(result["existing_home_catalog_signal_match_reviewed_source_or_baseline"])

    def test_catalog_owner_edit_detected(self):
        self.evidence["public_page_digests"]["catalog"]["sha256"] = "e" * 64
        self.assertEqual(self.result()["public_pages"]["catalog"], "unknown_or_owner_modified")

    def test_signal_owner_edit_detected(self):
        self.evidence["public_page_digests"]["signal_desk"]["sha256"] = "a" * 64
        self.assertFalse(self.result()["existing_home_catalog_signal_match_reviewed_source_or_baseline"])

    def test_sample_owner_edit_detected(self):
        self.evidence["public_page_digests"]["sample_gold_market_brief"]["sha256"] = "b" * 64
        self.assertTrue(self.result()["owner_edit_or_unknown_content_detected"])

    def test_product_page_owner_edit_detected(self):
        self.evidence["assets"]["index.html"]["sha256_prefix"] = "c" * 16
        self.assertEqual(self.result()["product_assets"]["index.html"], "unknown_or_owner_modified")

    def test_all_product_assets_absent_are_counted(self):
        for data in self.evidence["assets"].values():
            data.update({"readable": False, "sha256_prefix": None})
        self.assertEqual(self.result()["missing_product_asset_count"], 3)

    def test_single_missing_product_not_counted_as_present(self):
        self.evidence["assets"]["journal-guide.txt"] = {"readable": False, "sha256_prefix": None}
        report = self.result()
        self.assertEqual(report["missing_product_asset_count"], 1)
        self.assertEqual(report["product_assets"]["journal-guide.txt"], "absent_or_unreadable")

    def test_missing_home_blocks_baseline(self):
        self.evidence["public_page_digests"]["home"] = {"readable": False, "sha256": None}
        self.assertFalse(self.result()["existing_home_catalog_signal_match_reviewed_source_or_baseline"])

    def test_missing_catalog_blocks_baseline(self):
        self.evidence["public_page_digests"]["catalog"] = {"readable": False, "sha256": None}
        self.assertFalse(self.result()["existing_home_catalog_signal_match_reviewed_source_or_baseline"])

    def test_missing_signal_blocks_baseline(self):
        self.evidence["public_page_digests"]["signal_desk"] = {"readable": False, "sha256": None}
        self.assertFalse(self.result()["existing_home_catalog_signal_match_reviewed_source_or_baseline"])

    def test_missing_sample_not_treated_as_owner_edit(self):
        self.evidence["public_page_digests"]["sample_educational_signal"] = {"readable": False, "sha256": None}
        self.assertEqual(self.result()["public_pages"]["sample_educational_signal"], "absent_or_unreadable")

    def test_no_false_customer_sale(self):
        self.assertFalse(self.result()["customer_consent_or_sale_verified"])

    def test_no_false_effective_http_route(self):
        self.assertFalse(self.result()["http_route_verified"])

    def test_no_false_passenger_tenant_isolation(self):
        self.assertFalse(self.result()["passenger_tenant_isolation_verified"])

    def test_no_false_tron_merchant(self):
        self.assertFalse(self.result()["tron_merchant_or_payment_verified"])

    def test_no_false_backup_restore(self):
        self.assertFalse(self.result()["independent_restore_verified"])

    def test_wrong_evidence_schema_is_rejected(self):
        self.evidence["schema"] = "other"
        with self.assertRaises(ValueError):
            self.result()

    def test_non_read_only_evidence_rejected(self):
        self.evidence["read_only"] = False
        with self.assertRaises(ValueError):
            self.result()

    def test_fake_release_permitted_is_rejected(self):
        self.evidence["release_permitted"] = True
        with self.assertRaises(ValueError):
            self.result()

    def test_fake_received_revenue_is_rejected(self):
        self.evidence["revenue_proven"] = True
        with self.assertRaises(ValueError):
            self.result()

    def test_wrong_owner_account_denied(self):
        self.evidence["owner_account_verified"] = False
        with self.assertRaises(ValueError):
            self.result()

    def test_unverified_docroot_denied(self):
        self.evidence["docroot_and_route_ownership_verified"] = False
        with self.assertRaises(ValueError):
            self.result()

    def test_missing_page_inventory_key_denied(self):
        del self.evidence["public_page_digests"]["home"]
        with self.assertRaises(ValueError):
            self.result()

    def test_forged_extra_page_inventory_key_denied(self):
        self.evidence["public_page_digests"]["unknown"] = {"readable": False, "sha256": None}
        with self.assertRaises(ValueError):
            self.result()

    def test_missing_product_inventory_key_denied(self):
        del self.evidence["assets"]["index.html"]
        with self.assertRaises(ValueError):
            self.result()

    def test_missing_file_with_forged_digest_denied(self):
        self.evidence["public_page_digests"]["home"] = {"readable": False, "sha256": "d" * 64}
        with self.assertRaises(ValueError):
            self.result()

    def test_readable_page_requires_full_64_byte_sha256(self):
        self.evidence["public_page_digests"]["home"]["sha256"] = "a" * 16
        with self.assertRaises(ValueError):
            self.result()

    def test_product_requires_exact_16_hex_prefix(self):
        self.evidence["assets"]["index.html"]["sha256_prefix"] = "verywrong"
        with self.assertRaises(ValueError):
            self.result()

    def test_missing_static_reviewed_source_refuses_classification(self):
        (self.root / "index.html").unlink()
        with self.assertRaises(ValueError):
            self.result()

    def test_symlinked_reviewed_source_refuses(self):
        target = self.root / "index.html"
        target.unlink()
        target.symlink_to(self.root / "catalog/index.html")
        with self.assertRaises(ValueError):
            self.result()

    def test_oversized_source_refuses(self):
        (self.root / "catalog/index.html").write_bytes(b"x" * (512001))
        with self.assertRaises(ValueError):
            self.result()

    def test_source_directory_not_present_refuses(self):
        with self.assertRaises(ValueError):
            compare.classify(self.evidence, self.root / "absent")

    def test_serialized_result_does_not_expose_raw_content(self):
        output = json.dumps(self.result())
        self.assertNotIn("reviewed source", output)
        self.assertNotIn("starter educational", output)
        self.assertNotIn(str(self.root), output)

    def test_classification_makes_no_file_writes(self):
        before = sorted((p.relative_to(self.root).as_posix(), p.stat().st_mtime_ns)
                        for p in self.root.rglob("*") if p.is_file())
        self.result()
        after = sorted((p.relative_to(self.root).as_posix(), p.stat().st_mtime_ns)
                       for p in self.root.rglob("*") if p.is_file())
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
