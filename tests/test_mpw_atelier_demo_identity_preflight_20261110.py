"""Dated Sites preview identity evidence must not self-certify product 879."""

import copy
import json
import unittest
from scripts import mpw_atelier_demo_identity_preflight_20261110 as demo


class AtelierDemoIdentityContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads(demo.SNAPSHOT.read_text("utf-8"))

    def test_recognizes_real_sites_project_and_holds_sale_rights(self):
        actual = demo.audit(self.snapshot)
        self.assertEqual(actual["product_id"], 879)
        self.assertEqual(actual["saved_versions_span"], [1, 14])
        self.assertTrue(actual["source_metadata_title_differs_from_offer"])
        self.assertEqual(actual["embedded_asset_rights"], "unverified")
        self.assertFalse(actual["commercial_legal_clearance_issued"])

    def test_wrong_site_project_is_rejected(self):
        changed = copy.deepcopy(self.snapshot)
        changed["preview_site"]["project_id"] = "other-project"
        with self.assertRaisesRegex(ValueError, "DEMO_IDENTITY_PIN_MISMATCH"):
            demo.audit(changed)

    def test_site_title_match_must_be_truthful(self):
        changed = copy.deepcopy(self.snapshot)
        changed["assessment"]["metadata_title_equals_commercial_product_title"] = True
        with self.assertRaisesRegex(ValueError, "DEMO_TITLE_MATCH_ASSERTION_INCONSISTENT"):
            demo.audit(changed)

    def test_undocumented_rights_approval_is_rejected(self):
        changed = copy.deepcopy(self.snapshot)
        changed["assessment"]["commercial_redistribution_rights_independently_verified"] = True
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_UNVERIFIED_CLEARANCE_CLAIM"):
            demo.audit(changed)

    def test_commercial_zip_hash_must_be_historical_reference(self):
        changed = copy.deepcopy(self.snapshot)
        changed["commercial_private_zip_historical_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "PAID_ZIP_HISTORICAL_HASH_CHANGED"):
            demo.audit(changed)

    def test_source_archive_hash_is_not_assumed_to_be_paid_zip(self):
        actual = demo.audit(self.snapshot)
        self.assertEqual(actual["commercial_paid_zip_equivalence"], "unverified")
        self.assertNotEqual(
            self.snapshot["preview_site"]["latest_saved_archive_sha256"],
            self.snapshot["commercial_private_zip_historical_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
