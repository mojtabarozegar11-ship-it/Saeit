"""Local synthetic fixtures for source-only cPanel production provenance."""
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

FILE = (Path(__file__).resolve().parents[1] /
        "scripts/mpw_onepass_cpanel_source_provenance_readonly_20261113.py")
spec = importlib.util.spec_from_file_location("mpw_src_probe", FILE)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class ReadOnlySourceProvenanceTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.base = Path(t.name)
        self.app = self.base / "Saeit-staging"
        self.public = self.base / "mojplaywin.com"
        self.app.mkdir()
        self.public.mkdir()
        self.guest = self.app / "services/mpw_trx_guest_commerce.py"
        self.template = (self.app /
                         "mpw_commerce/templates/mpw_commerce/product_checkout.html")
        self.ht = self.public / ".htaccess"
        self.wsgi = self.public / "passenger_wsgi.py"
        self.store = self.public / "store/index.html"
        for file in (self.guest, self.template, self.ht, self.wsgi, self.store):
            file.parent.mkdir(parents=True, exist_ok=True)
        self.guest.write_bytes(b"synthetic source only\n")
        self.template.write_bytes(
            b'<form method="post" action="/commerce/trx-easy/start/72/">'
            b'<input id="mpw-buy-email" name="email" type="email"></form>')
        self.ht.write_bytes(probe.FALLBACK_BLOCK + b"Owner original directives\n")
        self.wsgi.write_bytes(b"APP='/home/zomorod2/Saeit-staging'\n")
        self.store.write_bytes(b"<html>MPW_STATIC_STORE_FALLBACK_V1</html>\n")

    def inspect(self):
        return probe.inspect(self.app, self.public)

    def test_zero_real_sales_not_inferred_from_source(self):
        r = self.inspect()
        self.assertIsNone(r["confirmed_revenue"])
        self.assertFalse(r["production_invoice_post_verified"])
        self.assertFalse(r["authenticated_delivery_verified"])
        self.assertFalse(r["independent_chain_finality_verified"])
        self.assertFalse(r["production_release_permitted_by_this_report"])

    def test_private_email_field_and_fallback_both_visible(self):
        r = self.inspect()
        self.assertEqual(r["template_disk_source"], "email_field_present")
        self.assertEqual(r["public_fallback"], "owned_static_fallback_rule_on_disk")
        self.assertTrue(r["passenger_stage_source_marker"])
        self.assertFalse(r["effective_django_template_origin_verified"])

    def test_approved_guest_digest_is_exact(self):
        expected = hashlib.sha256(self.guest.read_bytes()).hexdigest()
        with patch.object(probe, "APPROVED_GUEST_SHA256", expected):
            self.assertEqual(self.inspect()["guest_source"], "approved_email_free_source")

    def test_reviewed_legacy_guest_digest_is_separate(self):
        expected = hashlib.sha256(self.guest.read_bytes()).hexdigest()
        with patch.object(probe, "REVIEWED_LEGACY_SHA256", frozenset({expected})):
            self.assertEqual(self.inspect()["guest_source"], "reviewed_legacy_source")

    def test_unknown_guest_source_never_claims_release(self):
        report = self.inspect()
        self.assertEqual(report["guest_source"], "source_unknown")
        self.assertFalse(report["production_release_permitted_by_this_report"])

    def test_missing_guest_refuses_source_proof(self):
        self.guest.unlink()
        self.assertEqual(self.inspect()["guest_source"], "source_missing_or_unsafe")

    def test_no_email_static_template_is_not_django_origin_evidence(self):
        self.template.write_bytes(b'<form method="post" action="/safe/">'
                                  b'<input name="csrfmiddlewaretoken"></form>')
        r = self.inspect()
        self.assertEqual(r["template_disk_source"], "email_not_found_static_source")
        self.assertFalse(r["effective_django_template_origin_verified"])

    def test_other_email_control_aliases_are_detected(self):
        for field in (
            b"<input name='buyer_email'>",
            b'<input id="alternate-email">',
            b'<input type="email">',
            b'<input autocomplete="email">',
        ):
            with self.subTest(field=field):
                self.template.write_bytes(b"<form>" + field + b"</form>")
                self.assertEqual(self.inspect()["template_disk_source"], "email_field_present")

    def test_symlinked_guest_file_refuses_read(self):
        self.guest.unlink()
        external = self.base / "external.py"
        external.write_bytes(b"do not read anything private\n")
        self.guest.symlink_to(external)
        self.assertEqual(self.inspect()["guest_source"], "source_missing_or_unsafe")

    def test_symlinked_checkout_directory_refuses_read(self):
        root = self.template.parent
        saved = self.base / "outside-template"
        root.rename(saved)
        root.symlink_to(saved, target_is_directory=True)
        self.assertEqual(self.inspect()["template_disk_source"], "missing_or_unsafe")

    def test_oversize_template_refuses_source_proof(self):
        self.template.write_bytes(b"X" * 240001)
        self.assertEqual(self.inspect()["template_disk_source"], "missing_or_unsafe")

    def test_duplicate_fallback_is_not_cleared(self):
        self.ht.write_bytes(probe.FALLBACK_BLOCK * 2)
        self.assertEqual(self.inspect()["public_fallback"], "fallback_not_exactly_proven")

    def test_owned_fallback_rule_not_at_start_is_not_sufficient(self):
        self.ht.write_bytes(b"RewriteRule ^ /another/ [END]\n" +
                            probe.FALLBACK_BLOCK)
        self.assertEqual(self.inspect()["public_fallback"],
                         "fallback_not_exactly_proven")

    def test_missing_fallback_marker_in_index_refuses_exact_source_claim(self):
        self.store.write_bytes(b"<html>Ordinary static page</html>")
        self.assertEqual(self.inspect()["public_fallback"],
                         "fallback_not_exactly_proven")

    def test_fallback_source_claim_does_not_prove_effective_routing(self):
        report = self.inspect()
        self.assertEqual(report["public_fallback"],
                         "owned_static_fallback_rule_on_disk")
        self.assertFalse(report["production_release_permitted_by_this_report"])
        self.assertFalse(report["effective_django_template_origin_verified"])

    def test_missing_fallback_index_stays_unknown(self):
        self.store.unlink()
        self.assertEqual(self.inspect()["public_fallback"], "unknown")

    def test_passenger_root_drift_is_not_assumed_equivalent(self):
        self.wsgi.write_bytes(b"APP='/unexpected/runtime'\n")
        self.assertFalse(self.inspect()["passenger_stage_source_marker"])

    def test_readonly_probe_never_changes_any_fixture_bytes(self):
        files = (self.guest, self.template, self.ht, self.wsgi, self.store)
        before = {str(file): file.read_bytes() for file in files}
        report = self.inspect()
        after = {str(file): file.read_bytes() for file in files}
        self.assertEqual(before, after)
        self.assertFalse(report["customer_data_read"])
        self.assertFalse(report["database_accessed"])
        self.assertFalse(report["external_network_requests"])
        self.assertFalse(report["files_modified"])

    def test_report_has_no_private_template_or_source_content(self):
        report = self.inspect()
        out = str(report)
        self.assertNotIn("synthetic source only", out)
        self.assertNotIn("mpw-buy-email", out)
        self.assertNotIn("APP='/home", out)
        self.assertLess(len(out), 1500)


if __name__ == "__main__":
    unittest.main()
