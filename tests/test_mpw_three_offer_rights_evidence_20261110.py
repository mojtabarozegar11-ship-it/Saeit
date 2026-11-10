"""Offline legal-rights evidence register fail-closed contract tests."""

import copy
import json
import unittest
from scripts import mpw_three_offer_rights_evidence_20261110 as rights


class RightsEvidenceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(rights.REGISTER.read_text("utf-8"))

    def test_known_products_are_all_present_and_uncleared(self):
        result = rights.audit(self.document)
        self.assertEqual(result["records_checked"], 3)
        self.assertEqual(result["documentary_clearances_issued"], 0)
        self.assertEqual(result["current_private_files_examined"], 0)
        self.assertFalse(result["legal_certificate_issued"])
        self.assertEqual(set(result["products"]), {"72", "225", "879"})
        for row in result["products"].values():
            self.assertEqual(row["documentary_status"], "evidence_incomplete")
            self.assertFalse(row["commercial_sale_legally_cleared_by_this_script"])

    def test_all_products_require_independent_signed_review(self):
        for item in self.document["products"]:
            with self.subTest(sku=item["sku"]):
                self.assertIsNone(item["evidence"]["independent_signed_rights_review"])
                self.assertIsNone(item["evidence"]["author_to_seller_distribution_authority"])

    def test_duplicate_product_rejected(self):
        changed = copy.deepcopy(self.document)
        changed["products"][1]["sku"] = 72
        with self.assertRaisesRegex(ValueError, "DUPLICATE_OR_UNKNOWN_SKU"):
            rights.audit(changed)

    def test_missing_product_rejected(self):
        changed = copy.deepcopy(self.document)
        changed["products"].pop()
        with self.assertRaisesRegex(ValueError, "MUST_HAVE_THREE_PRODUCTS"):
            rights.audit(changed)

    def test_unknown_product_rejected(self):
        changed = copy.deepcopy(self.document)
        changed["products"][0]["sku"] = 779
        with self.assertRaisesRegex(ValueError, "DUPLICATE_OR_UNKNOWN_SKU"):
            rights.audit(changed)

    def test_synthetic_rights_approval_is_rejected(self):
        changed = copy.deepcopy(self.document)
        changed["products"][0]["status"] = "approved"
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_LEGAL_STATUS"):
            rights.audit(changed)

    def test_filled_review_reference_is_not_self_certifying(self):
        changed = copy.deepcopy(self.document)
        changed["products"][0]["evidence"]["independent_signed_rights_review"] = "UNVERIFIED CLAIM"
        result = rights.audit(changed)
        self.assertFalse(result["products"]["72"]["commercial_sale_legally_cleared_by_this_script"])
        self.assertIn("independent_signed_rights_review", result["products"]["72"]["unverified_submitted_reference_keys"])

    def test_tampered_historical_hash_is_rejected(self):
        changed = copy.deepcopy(self.document)
        changed["products"][2]["historical_expected_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "HISTORICAL_REFERENCE_DIGEST_CHANGED"):
            rights.audit(changed)

    def test_hash_is_never_a_license(self):
        result = rights.audit(self.document)
        for item in result["products"].values():
            self.assertTrue(item["historical_hash_not_live_integrity_proof"])
            self.assertTrue(item["metadata_flags_not_copyright_proof"])

    def test_atelier_historical_checkout_conflict_is_explicit(self):
        atelier = next(p for p in self.document["products"] if p["sku"] == 879)
        self.assertIn("checkout_enabled=false", atelier["historical_conflict"])
        self.assertIn("paid_delivery_enabled=false", atelier["historical_conflict"])


if __name__ == "__main__":
    unittest.main()
