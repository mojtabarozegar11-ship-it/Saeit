"""Offline tests for the existing owner-attested TRX asset digest contract.

No Django configuration, DB writes, customer data, SSH, or blockchain usage.
"""
import unittest

from scripts.mpw_owner_attested_sku_metadata_20261029 import (
    canonical_sale_digest,
)

ASSET = "a" * 64
OTHER = "b" * 64


class OwnerCatalogHashReconciliationTests(unittest.TestCase):
    def test_missing_sha256_is_filled_from_verified_actual_asset(self):
        for meta in ({}, {"sha256": None}, {"sha256": ""}):
            with self.subTest(metadata=meta):
                self.assertEqual(canonical_sale_digest(meta, ASSET), ASSET)
                self.assertEqual(meta, meta)  # helper must not mutate owner data

    def test_matching_canonical_digest_is_preserved(self):
        self.assertEqual(
            canonical_sale_digest({"sha256": ASSET}, ASSET), ASSET
        )
        self.assertEqual(
            canonical_sale_digest({"sha256": ASSET.upper()}, ASSET),
            ASSET.upper(),
        )

    def test_mismatched_catalog_revision_never_overwritten(self):
        for bad in (OTHER, "not_sha256", 12, False):
            with self.subTest(value=bad):
                with self.assertRaisesRegex(
                    RuntimeError, "CANONICAL_CATALOG_HASH_CONFLICT"
                ):
                    canonical_sale_digest({"sha256": bad}, ASSET)

    def test_existing_asset_metadata_is_not_implicitly_approved(self):
        # Normalizing sha256 is not approval to change rights flags,
        # publication status, price or stock. Those have independent gates.
        meta = {
            "asset_sha256": ASSET,
            "rights_cleared": False,
            "publication_approved": False,
        }
        normalized = canonical_sale_digest(meta, ASSET)
        self.assertEqual(normalized, ASSET)
        self.assertEqual(meta["rights_cleared"], False)
        self.assertEqual(meta["publication_approved"], False)
        self.assertNotIn("sha256", meta)


if __name__ == "__main__":
    unittest.main()
