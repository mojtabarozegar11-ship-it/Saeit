"""C141 exact source review for fail-closed dynamic-store fallback cutover.

Does not execute production cutover, inspect customer records or create orders.
"""
from __future__ import annotations
import ast
from pathlib import Path
import unittest

from scripts.mpw_dynamic_store_cutover_20261108 import (
    REVIEWED_STAGING_BLOBS, DEAD_CHECKOUT_ROUTES, git_blob_sha,
)
ROOT = Path(__file__).resolve().parents[1]

class SafeStoreCutoverC141Tests(unittest.TestCase):
    def test_five_exact_reviewed_sources_match_combined_branch(self):
        self.assertEqual(len(REVIEWED_STAGING_BLOBS), 5)
        for name, expected in REVIEWED_STAGING_BLOBS.items():
            with self.subTest(file=name):
                source = ROOT / name
                self.assertTrue(source.is_file() and not source.is_symlink())
                self.assertEqual(git_blob_sha(source.read_bytes()), expected)

    def test_new_funnel_source_is_privacy_bounded_and_never_claims_invoice(self):
        file = ROOT / "core/commerce_funnel.py"
        source = file.read_text("utf-8")
        ast.parse(source)
        self.assertIn("A-Za-z0-9", source)
        self.assertIn("utm_source", source)
        self.assertIn('utm_campaign", 80', source)
        self.assertIn("except DatabaseError:", source)
        for unsafe in ("request.POST", "request.body", "request.META", "request.user.email",
                       "wallet", "reconcile_invoice(", "payment_verified = True"):
            self.assertNotIn(unsafe, source)

    def test_no_dead_checkout_links_marketed_on_public_store(self):
        source = (ROOT / "core/templates/mojplaywin/store.html").read_bytes()
        for forbidden in DEAD_CHECKOUT_ROUTES:
            with self.subTest(link=forbidden):
                self.assertNotIn(forbidden, source)
        for product in (72, 225, 879):
            self.assertIn(f'href="/store/product/{product}/"'.encode(), source)

    def test_cutover_still_requires_exact_source_and_owned_safe_backup(self):
        code = (ROOT / "scripts/mpw_dynamic_store_cutover_20261108.py").read_text("utf-8")
        self.assertIn("STAGING_SOURCE_VERSION_MISMATCH", code)
        self.assertIn("STAGING_REQUIRED_SOURCE_MISSING_OR_UNSAFE", code)
        self.assertIn("assert_reviewed_staging_sources(APP)", code)
        self.assertIn("BACKUP_READBACK_FAILED", code)
        self.assertIn("LIVE_DYNAMIC_PUBLIC_SMOKE_FAILED", code)
        self.assertIn("HTACCESS_REPLACEMENT_NOT_VERIFIED", code)

if __name__ == "__main__":
    unittest.main()
