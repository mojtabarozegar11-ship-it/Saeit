"""Owner-updated 30 TRX Starter30 source controls after retiring obsolete Plan 1.

This file retains safety guarantees formerly tested for the removed free plan:
no real broker capital, no fund custody, no paid checkout, no sensitive
information in offer URLs, and preservation of consent-based contact.
"""
from html.parser import HTMLParser
from pathlib import Path
import unittest
import re

ROOT=Path(__file__).resolve().parents[1]
LANDING=ROOT/"templates/moj-prop-v4/index.html"
PRODUCT=ROOT/"templates/moj-prop-v4/starter-30-trx/index.html"
LEVELS=("$1,000","$1,500","$2,000","$3,000","$5,000","$7,500",
        "$10,000","$15,000","$20,000","$35,000","$50,000","$70,000",
        "$85,000","$100,000")

class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=set()
        self.urls=[]
        self.h1=0
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if d.get("id"):
            if d["id"] in self.ids:
                raise AssertionError("Duplicate HTML ID")
            self.ids.add(d["id"])
        if tag=="a":
            self.urls.append(d.get("href",""))
        if tag=="h1":
            self.h1+=1

class MainlinePlanOneContactGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page=LANDING.read_text("utf-8")
        cls.product=PRODUCT.read_text("utf-8")
        cls.tags=Tags()
        cls.tags.feed(cls.page)
        cls.product_tags=Tags()
        cls.product_tags.feed(cls.product)

    def test_01_free_challenge_offer_is_retired(self):
        self.assertNotIn("Plan 1",self.page)
        self.assertNotIn("MOJ-PROP-01",self.page)

    def test_02_exact_listed_entry_and_duration(self):
        self.assertIn("30 TRX Starter30 plan",self.page)
        self.assertIn("60-day",self.page)
        self.assertIn("30 TRX",self.product)

    def test_03_only_simulated_balance_offered(self):
        self.assertIn("$1,000 simulated",self.page)
        self.assertIn("$100,000 virtual",self.page)
        self.assertIn("not real funded capital",self.page)

    def test_04_fourteen_progression_levels_are_ordered(self):
        self.assertEqual(self.product.count("<li><strong>Level "),14)
        positions=[self.product.index(f"Level {i}</strong> — {amount}")
                   for i,amount in enumerate(LEVELS,1)]
        self.assertEqual(positions,sorted(positions))

    def test_05_pass_each_level_before_advancement(self):
        self.assertIn("pass each level",self.product.lower())
        self.assertIn("next",self.product.lower())
        self.assertIn("eligibility",self.product.lower())

    def test_06_no_automatic_award_or_guaranteed_return(self):
        self.assertIn("neither profits nor stage promotions are guaranteed",self.product)
        self.assertIn("passing",self.page.lower())

    def test_07_payment_is_closed(self):
        self.assertIn("Payment and new enrollment are currently unavailable",self.page)
        self.assertIn("Payment is currently unavailable",self.product)

    def test_08_no_direct_disabled_checkout_link(self):
        for html in (self.page,self.product):
            self.assertNotIn('href="/mojprop-starter30-checkout/"',html)
            self.assertNotIn("Checkout available · 30 TRX",html)

    def test_09_no_transfer_invocation(self):
        for html in (self.page,self.product):
            self.assertNotIn("tronWeb.trx.sendTransaction(",html)
            self.assertNotIn("eth_sendTransaction",html)

    def test_10_no_sensitive_information_in_offer_urls(self):
        for url in self.tags.urls+self.product_tags.urls:
            self.assertNotRegex(url,r"[?&](?:email|password|token|receipt|wallet_key)=")

    def test_11_opt_in_contact_remains(self):
        self.assertIn("/moj-prop-intake/?format=html",self.page)
        self.assertIn("/moj-prop/contact/",self.tags.urls)

    def test_12_current_tracking_form_is_not_payment(self):
        self.assertIn("const endpoint='/moj-prop-intake/';",self.page)
        self.assertIn("credentials:'same-origin'",self.page)

    def test_13_status_form_hidden(self):
        self.assertRegex(self.page,r'<form id="status-form"[^>]*hidden[^>]*aria-hidden="true"')

    def test_14_not_a_real_funded_account(self):
        self.assertIn("not real funded capital",self.page)
        self.assertIn("not cash payments or real funded broker accounts",self.product)

    def test_15_canonical_urls_preserved(self):
        self.assertIn('href="https://mojplaywin.com/moj-prop/"',self.page)
        self.assertIn('href="https://mojplaywin.com/moj-prop/starter-30-trx/"',self.product)

    def test_16_language_is_english(self):
        self.assertIn('lang="en" dir="ltr"',self.page)
        self.assertFalse(any(0x0600<=ord(char)<=0x06FF for char in self.page))

    def test_17_single_accessible_main_heading(self):
        self.assertEqual(self.tags.h1,1)
        self.assertEqual(self.product_tags.h1,1)

    def test_18_signal_service_and_other_research_untouched(self):
        self.assertIn('href="/moj-prop/signals/"',self.page)
        self.assertIn('id="signals"',self.page)

    def test_19_preserve_canonical_starter_route(self):
        self.assertIn('href="/moj-prop/starter-30-trx/"',self.page)
        self.assertIn('id="scaling-path"',self.product)

    def test_20_full_document_structure(self):
        self.assertIn("<main",self.page)
        self.assertIn("</main>",self.page)
        self.assertGreaterEqual(self.page.count("<section"),4)

if __name__=="__main__":
    unittest.main()
