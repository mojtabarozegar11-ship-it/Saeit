"""C136 source-only adversarial regression for merging main + canonical Moj Prop.

No third-party network, production writes, live wallet, email or customer data.
CI sets the *already fetched* Git SHAs, not this test.
"""
import ast
import os
from pathlib import Path
import subprocess
import unittest

from scripts.mojprop_c136_preserve_main_merge_resolver import (
    CONFLICT_PATHS, MAIN_ROUTES, CANONICAL_ROUTES, require, resolve_source
)


def source_at(sha, path):
    if len(sha) != 40 or path not in CONFLICT_PATHS:
        raise ValueError("not a pinned branch/file")
    proc = subprocess.run(["git", "show", sha + ":" + path],
                          capture_output=True, text=True, check=False, timeout=12)
    if proc.returncode:
        raise RuntimeError("required reviewed input unavailable")
    return proc.stdout


class MojPropC136MergeResolver(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The approved C136 merge has two independently proven real parents.
        # Full-repository CI does not inject the special C136 runner variables.
        # Verify Git ancestry rather than treating absent variables as 18 errors
        # or substituting synthetic source files.
        reviewed_merge = "2ee98ecfab950903e9cb550908f8242255c39e9d"
        reviewed_main = "0af1a0415bb75354cb119a8653230486f95e1a96"
        reviewed_prop = "70c6607142d8ad90efe5e98bdcda04504b58c59b"
        ancestry = subprocess.run(
            ["git", "show", "-s", "--format=%P", reviewed_merge],
            capture_output=True, text=True, check=False, timeout=12,
        )
        if ancestry.returncode or ancestry.stdout.strip().split() != [reviewed_main, reviewed_prop]:
            raise RuntimeError("C136 reviewed merge parent identity unavailable or changed")
        env_main = os.environ.get("C136_MAIN_SHA")
        env_prop = os.environ.get("C136_PROP_SHA")
        if bool(env_main) != bool(env_prop):
            raise RuntimeError("C136 both source SHAs required together")
        cls.main_sha = env_main or reviewed_main
        cls.prop_sha = env_prop or reviewed_prop
        if len(cls.main_sha) != 40 or len(cls.prop_sha) != 40:
            raise RuntimeError("C136 real ref SHAs mandatory; cannot silently fake input")
        cls.main = {p: source_at(cls.main_sha, p) for p in CONFLICT_PATHS}
        cls.prop = {p: source_at(cls.prop_sha, p) for p in CONFLICT_PATHS}
        cls.integrated = {p: resolve_source(p, cls.main[p], cls.prop[p])
                          for p in CONFLICT_PATHS}

    def test_exactly_reviewed_eight_conflicts(self):
        self.assertEqual(len(CONFLICT_PATHS), 8)
        self.assertEqual(len(set(CONFLICT_PATHS)), 8)

    def test_no_untracked_file_can_be_reconciled(self):
        with self.assertRaises(ValueError):
            resolve_source("secrets/.env", "x", "y")

    def test_missing_or_oversized_source_fails(self):
        p = "config/urls.py"
        for a, b in (("", self.prop[p]), (self.main[p], ""),
                     ("x" * 160001, self.prop[p])):
            with self.subTest(size=len(a)):
                with self.assertRaises(ValueError):
                    resolve_source(p, a, b)

    def test_routes_compose_old_intake_and_new_optin_without_duplicates(self):
        code = self.integrated["config/urls.py"]
        ast.parse(code)
        for token in MAIN_ROUTES + CANONICAL_ROUTES:
            self.assertEqual(code.count(token), 1, token)
        self.assertIn("from core.mojprop_views import mojprop_intake", code)
        self.assertIn("from core.moj_prop_views import moj_prop_landing", code)
        self.assertIn("path(\"moj-prop/<str:lang>/dashboard/\"", code)
        self.assertIn("path(\"moj-prop/<str:lang>/\", moj_prop_landing", code)

    def test_legacy_paths_cannot_be_removed(self):
        bad = self.main["config/urls.py"].replace(
            'path("moj-prop-intake/", mojprop_intake',
            'path("moj-prop-intake-old/", mojprop_intake')
        with self.assertRaises(ValueError):
            resolve_source("config/urls.py", bad, self.prop["config/urls.py"])

    def test_consent_get_cannot_be_pointed_to_generic_service(self):
        bad = self.prop["config/urls.py"].replace(
            'path("moj-prop-interest/form/", moj_prop_interest_form',
            'path("moj-prop-interest/form/", mojprop_intake')
        with self.assertRaises(ValueError):
            resolve_source("config/urls.py", self.main["config/urls.py"], bad)

    def test_host_locale_matches_main_secure_get_host(self):
        code = self.integrated["core/financial_brand_pages.py"]
        ast.parse(code)
        self.assertIn('request.get_host().split(":", 1)[0]', code)
        self.assertNotIn('request.META.get("HTTP_X_FORWARDED_HOST")', code)
        self.assertIn("signal_offer = offer(slug, locale)", code)
        self.assertIn('"destination_url": destination_url', code)
        self.assertIn('"free_destination_url": free_destination_url', code)

    def test_brand_pages_preserve_educational_cta_and_no_payable_signals(self):
        code = self.integrated["core/templates/core/financial_brand_page.html"]
        self.assertIn("{{ destination_url }}", code)
        self.assertIn("{{ free_destination_url }}", code)
        self.assertIn('data-signal-subscription="not-released"', code)
        self.assertIn("No live subscription, checkout or guaranteed return", code)
        self.assertNotIn('action="/commerce/', code)

    def test_main_route_verified_guest_checkout_stronger_than_canonical(self):
        code = self.integrated["core/mojplaywin_product_detail.py"]
        ast.parse(code)
        self.assertIn("verified_guest_checkout_url(product.pk)", code)
        self.assertNotIn('return reverse("mpw_commerce:book"', code)
        self.assertEqual(code, self.main["core/mojplaywin_product_detail.py"])

    def test_payment_canary_is_exact_true_and_precedes_db_writes(self):
        code = self.integrated["services/mpw_trx_guest_commerce.py"]
        ast.parse(code)
        self.assertIn('MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED", False) is True', code)
        before = code.index('if not _new_trx_merchant_canary_is_true(settings):',
                            code.index('def _checkout_page('))
        after = code.index("from django.db import connection", before)
        self.assertLess(before, after)
        self.assertIn('raise Http404("New TRX invoices unavailable")', code)

    def test_analytics_event_requires_exact_committed_invoice_redirect(self):
        code = self.integrated["services/mpw_trx_guest_commerce.py"]
        self.assertIn('getattr(response, "status_code", None) not in (302, 303)', code)
        self.assertIn('r"/commerce/trx-easy/invoice/[1-9][0-9]{0,18}/"', code)
        self.assertIn("_record_funnel_event_best_effort", code)
        self.assertNotIn("if 200 <= status_code < 300:", code)
        self.assertIn('return response', code)

    def test_cannot_merge_payment_without_merchant_canary(self):
        code = self.main["services/mpw_trx_guest_commerce.py"].replace(
            'MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED', "UNVERIFIED_FLAG")
        with self.assertRaises(ValueError):
            resolve_source("services/mpw_trx_guest_commerce.py", code,
                           self.prop["services/mpw_trx_guest_commerce.py"])

    def test_cannot_merge_payment_with_weak_analytics_guard(self):
        code = self.prop["services/mpw_trx_guest_commerce.py"].replace(
            'getattr(response, "status_code", None) not in (302, 303)',
            'getattr(response, "status_code", None) == 200')
        with self.assertRaises(ValueError):
            resolve_source("services/mpw_trx_guest_commerce.py",
                           self.main["services/mpw_trx_guest_commerce.py"], code)

    def test_main_store_negative_checkout_checks_are_retained(self):
        code = self.integrated["core/tests/test_mpw_store_real_template_render.py"]
        ast.parse(code)
        self.assertIn('self.assertNotIn(b\'href="/store/product/72/checkout/"\'', code)
        self.assertIn('href="/store/product/72/"', code)
        self.assertIn('href="/store/product/225/"', code)

    def test_plan1_bilingual_form_and_independent_service_desk_retained(self):
        landing = self.integrated["templates/moj-prop-v4/index.html"]
        contact = self.integrated["templates/moj-prop/contact/index.html"]
        for source in (landing, contact):
            self.assertIn('href="/moj-prop-interest/form/"', source)
            self.assertIn('href="/moj-prop-interest/form/?lang=fa"', source)
            self.assertIn("MOJ-PROP-01", source)
            self.assertNotIn("MOJPROP-STARTER30", source)
        self.assertIn("Other service requests — not Plan 1", landing)
        self.assertIn("no payment", contact.lower())

    def test_wrong_plan1_cta_would_block_reconciliation(self):
        code = self.prop["templates/moj-prop-v4/index.html"].replace(
            'href="/moj-prop-interest/form/?lang=fa"',
            'href="/moj-prop-intake/?service=blueprint"')
        with self.assertRaises(ValueError):
            resolve_source("templates/moj-prop-v4/index.html",
                           self.main["templates/moj-prop-v4/index.html"], code)

    def test_hardcoded_invoice_wallet_or_live_payment_not_introduced(self):
        landing = self.integrated["templates/moj-prop-v4/index.html"]
        self.assertIn("No wallet or payment collection now.", landing)
        self.assertIn("30,000,000 SUN", landing)
        self.assertIn("NOT an educational product", landing)

    def test_no_merge_write_in_resolver_code(self):
        source = (Path(__file__).resolve().parents[1] /
                  "scripts/mojprop_c136_preserve_main_merge_resolver.py").read_text("utf-8")
        for banned in ('"push"', '"merge"', '"commit"', "requests.post(",
                       "send_mail(", "objects.create(", "paramiko", "rsync"):
            self.assertNotIn(banned, source)
        self.assertIn('"add"', source)


if __name__ == "__main__":
    unittest.main()
