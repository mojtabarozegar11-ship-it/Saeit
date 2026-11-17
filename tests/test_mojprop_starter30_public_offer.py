"""Consumer-scope and printable-output tests for the one-product launch branch.

No live site requests, email, wallet, financial account or checkout.
"""
from pathlib import Path
import unittest

from scripts.mojprop_starter30_scorecard import render_private_scorecard
from scripts.mojprop_starter30 import InvalidJournal

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "templates/moj-prop-v4/starter-30-trx/index.html"
RUNBOOK = ROOT / "docs/mojprop/starter30-first-product-release.md"


def journal():
    return [{"session": i, "closing_equity_usd": "100.00",
             "risk_plan_recorded": True, "reflection_recorded": True}
            for i in range(1, 11)]


class Starter30PublicOfferTests(unittest.TestCase):
    def test_self_contained_english_html(self):
        html = PUBLIC.read_text("utf-8")
        self.assertIn("<!doctype html>", html.lower())
        self.assertIn('lang="en" dir="ltr"', html)

    def test_exact_indicative_30_trx(self):
        text = PUBLIC.read_text("utf-8")
        self.assertIn("30 TRX", text)
        self.assertIn("indicative one-time price", text)

    def test_paid_checkout_explicitly_disabled(self):
        page = PUBLIC.read_text("utf-8")
        self.assertIn("Payment not enabled", page)
        self.assertIn("Do not send TRX", page)
        self.assertNotIn('type="submit"', page)

    def test_no_funded_account_claim(self):
        page = PUBLIC.read_text("utf-8")
        for required in ("No funded account is included", "no live brokerage account",
                         "100 USD", "imaginary", "noindex,follow"):
            self.assertIn(required.lower(), page.lower())

    def test_no_wallet_or_external_script(self):
        page = PUBLIC.read_text("utf-8")
        self.assertNotIn("<script", page)
        self.assertNotIn("tronlink", page.lower())
        self.assertNotIn("tronweb", page.lower())
        self.assertNotIn("walletconnect", page.lower())
        self.assertNotIn("window.location=", page)

    def test_manual_inquiry_is_product_specific(self):
        page = PUBLIC.read_text("utf-8")
        self.assertIn("MOJPROP-STARTER30", page)
        self.assertIn("/moj-prop/?service=blueprint&amp;package=starter-30-trx#request", page)
        self.assertNotIn("mailto:", page)
        self.assertIn("not an order", page.lower())

    def test_product_not_misrouted_to_149_usd_blueprint(self):
        page = PUBLIC.read_text("utf-8")
        # The first-party route carries an explicit canonical package marker;
        # the private CRM proposal generator must not quote the generic USD149
        # Blueprint tariff for this buyer-selected training product.
        self.assertIn("?service=blueprint&amp;package=starter-30-trx#request", page)
        self.assertNotIn("?service=blueprint#request", page)
        self.assertNotIn("?service=audit", page)

    def test_release_document_exists_and_covers_receipts(self):
        text = RUNBOOK.read_text("utf-8")
        for term in ("30,000,000 sun", "Karegar #15", "Saeit #2392",
                     "SOLIDIFIED", "refund", "customer-specific invoice"):
            self.assertIn(term, text)

    def test_downloadable_csv_and_guide_really_exist(self):
        page = PUBLIC.read_text("utf-8")
        for filename in ("journal-template.csv", "journal-guide.txt"):
            self.assertIn('href="./' + filename + '"', page)
            self.assertTrue((PUBLIC.parent / filename).is_file())

    def test_customer_csv_has_ten_empty_sessions(self):
        from scripts.mojprop_starter30_journal_csv import empty_journal_csv
        expected = empty_journal_csv()
        actual = (PUBLIC.parent / "journal-template.csv").read_text("utf-8")
        self.assertEqual(actual, expected)

    def test_journal_guide_contains_no_entitlement_to_real_funding(self):
        guide = (PUBLIC.parent / "journal-guide.txt").read_text("utf-8").lower()
        for phrase in ("not funded", "not withdrawable", "no", "payment"):
            self.assertIn(phrase, guide)

    def test_static_release_does_not_ship_account_or_payment_api(self):
        from scripts.mojprop_starter30_static_release import FILES
        self.assertEqual(set(FILES),
                         {"index.html", "journal-template.csv", "journal-guide.txt"})

    def test_starter30_is_in_manual_only_atomic_bundle_not_auto_deployed(self):
        from scripts.update_mojplaywin_moj_prop_catalog import FILES, MANIFEST_SCHEMA
        self.assertIn(Path("starter-30-trx/index.html"), FILES)
        self.assertIn(Path("starter-30-trx/journal-template.csv"), FILES)
        self.assertIn(Path("starter-30-trx/journal-guide.txt"), FILES)
        self.assertEqual(MANIFEST_SCHEMA, "mojprop.static.plan1-c153.v4-contact-rollback")
        self.assertIn(Path("contact/index.html"), FILES)
        from scripts.update_mojplaywin_moj_prop_catalog import PRESERVED_LIVE_FILES
        self.assertEqual(PRESERVED_LIVE_FILES, (Path("signals/index.html"),))
        self.assertNotIn(Path("signals/index.html"), FILES)
        workflow = (ROOT / ".github/workflows/mojplaywin-moj-prop-deploy.yml").read_text("utf-8")
        self.assertIn("github.event_name == 'workflow_dispatch'", workflow)
        self.assertIn("MOJ_PROP_API_PREFLIGHT=PASS", workflow)
        for required in (
            "inputs.owner_approved_static_release == true",
            "MOJPROP_FULL_DB_APP_MEDIA_RESTORE_VERIFIED",
            "MOJPROP_PASSENGER_TENANT_ISOLATION_VERIFIED",
            "MOJPROP_STATIC_ROLLBACK_VERIFIED",
            "MOJPROP_STATIC_APPROVED_MAIN_SHA == github.sha",
        ):
            self.assertIn(required, workflow)
        self.assertIn("MOJ_PROP_STATUS_API_PREFLIGHT=PASS", workflow)


class Starter30ScorecardTests(unittest.TestCase):
    def test_private_report_is_actual_complete_document(self):
        html = render_private_scorecard(journal(), "MPS30-ABCD1234")
        self.assertIn("<!doctype html>", html.lower())
        self.assertIn("Educational scorecard", html)
        self.assertIn("MPS30-ABCD1234", html)
        self.assertIn("Individual learning recommendations", html)
        self.assertIn("100.00", html)

    def test_scoring_does_not_claim_funds(self):
        html = render_private_scorecard(journal(), "MPS30-ABCD1234")
        self.assertIn("not owned, funded or withdrawable", html)
        self.assertIn("does not", html)

    def test_specific_loss_recommendation(self):
        rows = journal()
        rows[0]["closing_equity_usd"] = "95.00"
        for r in rows[1:]:
            r["closing_equity_usd"] = "95.00"
        html = render_private_scorecard(rows, "MPS30-ABCD1234")
        self.assertIn("Reduce simulated exposure", html)
        self.assertIn("Session 1: daily loss", html)

    def test_missing_reflection_recommendation(self):
        rows = journal()
        rows[0]["reflection_recorded"] = False
        html = render_private_scorecard(rows, "MPS30-ABCD1234")
        self.assertIn("end-of-session reflection", html)

    def test_case_reference_must_not_accept_html_or_pii(self):
        for value in ("<script>alert(1)</script>", "MPS30-X", "buyer@example.com",
                      "MPS30-ABCD1234?token=secret", "MPS30-abcdefgh"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                render_private_scorecard(journal(), value)

    def test_report_never_turns_bad_journal_into_success(self):
        with self.assertRaises(InvalidJournal):
            render_private_scorecard(journal() + journal(), "MPS30-ABCD1234")

    def test_report_has_no_external_tracking(self):
        html = render_private_scorecard(journal(), "MPS30-ABCD1234")
        self.assertNotIn("<script", html)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)

    def test_incomplete_training_is_not_funding_eligibility(self):
        html = render_private_scorecard(journal()[:2], "MPS30-ABCD1234")
        self.assertIn("incomplete_training", html)
        self.assertIn("does not", html)


if __name__ == "__main__":
    unittest.main()
