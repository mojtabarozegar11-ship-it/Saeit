"""Owner-safe MojPlayWin dynamic-store preflight and no-false-checkout regression.

All tests use checked-in sources and private temporary files. These tests
never connect to cPanel, create an invoice, send mail, or modify a live store.
"""
from __future__ import annotations

import contextlib
import io
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.mpw_dynamic_store_cutover_20261108 import (
    DEAD_CHECKOUT_ROUTES,
    FALLBACK_BLOCK,
    PRODUCT_ROUTES,
    REVIEWED_STAGING_BLOBS,
    assert_reviewed_staging_sources,
    git_blob_sha,
    inspect_owned_fallback,
    verify_dynamic_public,
)

ROOT = Path(__file__).resolve().parents[1]


class ReviewedStagingCatalogTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.app = Path(self.directory.name) / "Saeit-staging"
        self.app.mkdir()
        for relative in REVIEWED_STAGING_BLOBS:
            dest = self.app / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, dest)
        dest = self.app / "core/models.py"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "core/models.py", dest)

    def test_checked_in_catalog_is_reviewed_exact_file_versions(self):
        self.assertEqual(len(REVIEWED_STAGING_BLOBS), 5)
        self.assertEqual(len(PRODUCT_ROUTES), 3)
        self.assertEqual(PRODUCT_ROUTES, (
            b'href="/store/product/72/"',
            b'href="/store/product/225/"',
            b'href="/store/product/879/"',
        ))
        for path, sha in REVIEWED_STAGING_BLOBS.items():
            self.assertEqual(git_blob_sha((ROOT / path).read_bytes()), sha, path)
        assert_reviewed_staging_sources(self.app)

    def test_missing_or_stale_catalog_component_refuses_cutover(self):
        for relative in REVIEWED_STAGING_BLOBS:
            path = self.app / relative
            original = path.read_bytes()
            with self.subTest(relative=relative):
                path.write_bytes(original + b"\n# stale staged bytes")
                with self.assertRaisesRegex(RuntimeError, "STAGING_SOURCE_VERSION_MISMATCH"):
                    assert_reviewed_staging_sources(self.app)
                path.write_bytes(original)
                path.unlink()
                with self.assertRaisesRegex(RuntimeError, "STAGING_REQUIRED_SOURCE_MISSING_OR_UNSAFE"):
                    assert_reviewed_staging_sources(self.app)
                path.write_bytes(original)
        assert_reviewed_staging_sources(self.app)

    def test_symlinked_product_detail_refused(self):
        path = self.app / "core/mojplaywin_product_detail.py"
        original = path.read_bytes()
        path.unlink()
        path.symlink_to(ROOT / "core/mojplaywin_product_detail.py")
        with self.assertRaisesRegex(RuntimeError, "STAGING_REQUIRED_SOURCE_MISSING_OR_UNSAFE"):
            assert_reviewed_staging_sources(self.app)
        path.unlink()
        path.write_bytes(original)
        assert_reviewed_staging_sources(self.app)

    def test_funnel_schema_missing_refused_without_database_connection(self):
        path = self.app / "core/models.py"
        original = path.read_bytes()
        path.write_bytes(original.replace(b"class CommerceFunnelEvent(", b"class OldFunnelEvent("))
        with self.assertRaisesRegex(RuntimeError, "STAGING_FUNNEL_MODEL_MISSING"):
            assert_reviewed_staging_sources(self.app)
        path.write_bytes(original)
        assert_reviewed_staging_sources(self.app)

    def test_unreviewed_store_html_checkout_cta_does_not_pass_staging(self):
        path = self.app / "core/templates/mojplaywin/store.html"
        old = path.read_bytes()
        path.write_bytes(old.replace(b'href="/store/product/72/"', b'href="/store/product/72/checkout/"'))
        with self.assertRaisesRegex(RuntimeError, "STAGING_SOURCE_VERSION_MISMATCH"):
            assert_reviewed_staging_sources(self.app)
        path.write_bytes(old)
        assert_reviewed_staging_sources(self.app)

    def test_public_probe_rejects_legacy_pay_links_even_with_valid_marker(self):
        source = b"mpw-shop-kicker mpw-store-catalog-20261026 " + b" ".join(PRODUCT_ROUTES)
        for poisoned in DEAD_CHECKOUT_ROUTES:
            with self.subTest(payload=poisoned):
                response = source + b" " + poisoned
                output = io.StringIO()
                with patch("scripts.mpw_dynamic_store_cutover_20261108.public_response", return_value=response):
                    with patch("scripts.mpw_dynamic_store_cutover_20261108.time.sleep", return_value=None):
                        with contextlib.redirect_stdout(output):
                            self.assertFalse(verify_dynamic_public("42425162108"))
                self.assertIn('"dynamic_confirmed": false', output.getvalue())

    def test_positive_catalog_probe_requires_all_three_real_details(self):
        valid = b"mpw-shop-kicker mpw-store-catalog-20261026 " + b" ".join(PRODUCT_ROUTES)
        with patch("scripts.mpw_dynamic_store_cutover_20261108.public_response", return_value=valid):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertTrue(verify_dynamic_public("42425162108"))
        self.assertIn('"dynamic_confirmed": true', output.getvalue())
        for route in PRODUCT_ROUTES:
            with patch("scripts.mpw_dynamic_store_cutover_20261108.public_response", return_value=valid.replace(route, b"")):
                with patch("scripts.mpw_dynamic_store_cutover_20261108.time.sleep", return_value=None):
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertFalse(verify_dynamic_public("42425162108"))

    def test_no_cutover_preflight_store_request_or_invoice_side_effect(self):
        from scripts import mpw_dynamic_store_cutover_20261108 as target
        import inspect
        source = inspect.getsource(target.check_actual_staging_store)
        for forbidden in ("store(RequestFactory", "Client(", "record_funnel_event(", "invoice", "send_mail", "pay_trx"):
            self.assertNotIn(forbidden, source)
        self.assertIn("assert_reviewed_staging_sources(APP)", source)
        self.assertIn("resolve(\"/store/\")", source)
        self.assertIn('route.func is not brand_product_detail', source)


if __name__ == "__main__":
    unittest.main()
