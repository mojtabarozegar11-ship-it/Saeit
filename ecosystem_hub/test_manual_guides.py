"""Manual assistant programs require human source evidence; no fake AI execution."""
from django.test import SimpleTestCase

from .analysis import scan
from .catalog import CATALOG
from .manual_guides import MANUAL_GUIDES


class ManualAssistantGuidanceTests(SimpleTestCase):
    def test_every_unconnected_engine_has_an_individualized_human_workflow(self):
        unsupported = {code for code, item in CATALOG.items() if item["handler"] is None}
        # A connected journal-arithmetic engine still needs a separate manual
        # bank statement checklist; it must not be counted as unconnected.
        self.assertEqual(
            unsupported,
            {code for code in MANUAL_GUIDES if CATALOG[code]["handler"] is None},
        )
        self.assertEqual(
            {code for code in MANUAL_GUIDES if CATALOG[code]["handler"] is not None},
            {"financial-reconciliation"},
        )
        self.assertGreaterEqual(len(unsupported), 12)
        for code in unsupported:
            with self.subTest(code=code):
                steps = MANUAL_GUIDES[code]
                self.assertGreaterEqual(len(steps), 4)
                self.assertEqual(len({title for title, _ in steps}), len(steps))
                self.assertTrue(all(title and detail for title, detail in steps))

    def test_no_research_claim_or_internal_data_access_is_fabricated(self):
        for code in (code for code in MANUAL_GUIDES if CATALOG[code]["handler"] is None):
            with self.subTest(code=code):
                output = scan(None, code)
                self.assertIn("هنوز وصل نشده", output[0]["title"])
                self.assertEqual(output[0]["source"], "اعلام وضعیت فنی")
                self.assertEqual(len(output), 1 + len(MANUAL_GUIDES[code]))
                for item in output[1:]:
                    self.assertIn("اقدام پیشنهادی", item["title"])
                    self.assertIn("مدرک هنوز ارائه نشده", item["source"])
                    self.assertIn("تأیید مسئول", item["detail"])

    def test_production_financial_actions_never_return_automatic_output_from_manual_steps(self):
        for code in ("tax-compliance", "international-trade",
                     "legal-contracts", "online-store", "social-media", "data-security"):
            output = scan(None, code)
            text = " ".join(x["detail"] for x in output)
            self.assertIn("هوش مصنوعی", text)
            self.assertTrue(all(x["severity"] == "info" for x in output))

    def test_connected_journal_control_does_not_replace_bank_reconciliation(self):
        self.assertEqual(CATALOG["financial-reconciliation"]["handler"], "reconciliation")
        steps = MANUAL_GUIDES["financial-reconciliation"]
        self.assertGreaterEqual(len(steps), 4)
        details = " ".join(detail for _, detail in steps)
        self.assertIn("صورتحساب بانک", details)
        self.assertIn("تأیید", details)
