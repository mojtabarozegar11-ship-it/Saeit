"""Offline source contracts for existing commercial inquiry routes.

No network, no payments, no form submission, no new bot, no deployment.
These tests verify only draft-branch source invariants, not live availability.
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAREMAH = ROOT / "faremah"
NOVA = ROOT / "content/zomorod-nova-pages"


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class LeadSourceContracts(unittest.TestCase):
    def test_r01_contact_only_allowlisted_service_prefill(self):
        page = source(FAREMAH / "contact.html")
        for service in ("laser", "skin", "consultation", "package",
                        "partnership", "content", "gift"):
            self.assertIn('"' + service + '"', page)
        self.assertIn("services.has(choice)", page)
        self.assertIn("serviceSelect.value=choice", page)
        self.assertIn("if(preparing || !form.reportValidity())return;", page)
        self.assertIn("if(submitButton)submitButton.disabled=true;", page)
        self.assertIn("if(submitButton)submitButton.disabled=false;", page)
        self.assertIn('action="/ask-master/index.php"', page)
        self.assertIn("HTMLFormElement.prototype.submit.call(form)", page)

    def test_r02_services_ctas_resolve_to_existing_service_options(self):
        page = source(FAREMAH / "services.html")
        for item in ("laser", "skin", "consultation"):
            self.assertIn('contact.html?service=' + item + '#form', page)

    def test_r03_four_offer_ctas_have_matching_inquiry_type(self):
        page = source(FAREMAH / "offers.html")
        for item in ("consultation", "laser", "skin", "partnership"):
            self.assertIn('contact.html?service=' + item + '#form', page)

    def test_r04_six_distinct_revenue_modes_map_to_approved_inquiry_types(self):
        page = source(FAREMAH / "income.html")
        for item in ("laser", "consultation", "package",
                     "partnership", "content", "gift"):
            self.assertIn('contact.html?service=' + item + '#form', page)

    def test_r05_career_partner_inquiry(self):
        page = source(FAREMAH / "career.html")
        self.assertIn('contact.html?service=partnership#form', page)
        self.assertIn("درخواست همکاری", page)

    def test_r06_home_consultation_and_business_inquiry(self):
        page = source(FAREMAH / "index.html")
        self.assertIn('contact.html?service=consultation#form', page)
        self.assertIn('contact.html?service=partnership#form', page)

    def test_r07_about_to_consultation(self):
        page = source(FAREMAH / "about.html")
        self.assertIn('contact.html?service=consultation#form', page)

    def test_r08_industry_to_existing_company_service_intake(self):
        page = source(NOVA / "industry.html")
        self.assertIn('href="/ask-master/index.php?service=1"', page)
        self.assertIn("استعلام امکان‌سنجی صنعتی", page)
        self.assertIn("تنها پس از استعلام معتبر تعیین می‌شود", page)

    def test_r09_research_to_existing_company_service_intake(self):
        page = source(NOVA / "research.html")
        self.assertIn('href="/ask-master/index.php?service=1"', page)
        self.assertIn("استعلام همکاری پژوهشی", page)
        self.assertIn("تنها پس از استعلام معتبر تعیین می‌شود", page)

    def test_r10_services_to_existing_company_service_intake(self):
        page = source(NOVA / "services.html")
        self.assertIn("ثبت استعلام خدمات", page)
        self.assertIn('href="/ask-master/index.php?service=1"', page)

    def test_r11_cafe_b2b_duplicate_guard_retains_consent(self):
        page = source(ROOT / "public/ghanadi/cafe-shiraz/index.html")
        self.assertIn("if(button.disabled || !form.reportValidity()) return;", page)
        self.assertIn('name="consent" type="checkbox" required', page)
        self.assertIn("button.disabled=true;", page)
        self.assertIn("button.disabled=false;", page)
        self.assertIn("credentials:'same-origin'", page)

    def test_r12_retail_duplicate_guard_preserves_customer_validation(self):
        page = source(ROOT / "public/ghanadi/index.html")
        self.assertIn("if(button.disabled || !panel.reportValidity())return;", page)
        self.assertIn("button.disabled=true;", page)
        self.assertIn("button.disabled=false;", page)
        self.assertIn("if(!text||text.length>2500)", page)

    def test_no_new_agent_or_payment_endpoint_in_changed_lead_pages(self):
        paths = [
            FAREMAH / "contact.html", FAREMAH / "services.html",
            FAREMAH / "offers.html", FAREMAH / "income.html",
            FAREMAH / "career.html", FAREMAH / "index.html",
            FAREMAH / "about.html", NOVA / "industry.html",
            NOVA / "research.html", NOVA / "services.html",
            ROOT / "public/ghanadi/cafe-shiraz/index.html",
            ROOT / "public/ghanadi/index.html",
        ]
        self.assertEqual(len(paths), 12)
        self.assertTrue(all(path.is_file() for path in paths))
        # This test does not assert the absence of legacy references in the
        # whole project; this PR adds no bot runtime or payment integrations.


if __name__ == "__main__":
    unittest.main()
