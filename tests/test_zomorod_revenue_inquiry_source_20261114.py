"""Offline regression: real business-inquiry route without invented orders.

Current templates only, no server writes and no paid checkout activation.
"""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]


def read(p):
    return (ROOT/p).read_text(encoding="utf-8")


class RevenueInquirySource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store=read("content/zomorod-v11/store_index.php")
        cls.shop=read("public/ghanadi/index.html")
        cls.cafe=read("public/ghanadi/cafe-shiraz/index.html")
        cls.django=read("core/templates/core/ghanadi.html")

    def test_paid_store_shows_quote_path_not_fake_payment(self):
        self.assertIn('href="/ask-master/index.php?service=1">درخواست بررسی خرید و پیش‌فاکتور',self.store)
        self.assertIn("ثبت درخواست به معنای خرید یا پرداخت نیست",self.store)
        self.assertIn("پرداخت آنلاین تا اتصال درگاه غیرفعال است",self.store)

    def test_store_official_approval_gate_not_downgraded(self):
        self.assertIn("در این وضعیت خرید آنلاین و برداشت وجه غیرفعال است",self.store)
        self.assertIn("if(!is_file($lib))",self.store)
        self.assertIn("zmStoreDb($private)",self.store)

    def test_store_product_id_and_output_escaping_preserved(self):
        self.assertIn("storeEsc($p['sku'])",self.store)
        self.assertIn("htmlspecialchars($x,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8')",self.store)

    def test_shop_form_requires_valid_customer_contact(self):
        for field in ('name="name"','name="email"','type="email"','required maxlength="120"'):
            self.assertIn(field,self.shop)
        self.assertIn("event.preventDefault()",self.shop)

    def test_shop_fetches_only_official_intake(self):
        self.assertIn("fetch('/ask-master/index.php?service=1'",self.shop)
        self.assertIn("submission.action='/ask-master/index.php'",self.shop)
        self.assertIn("kind:'service_question'",self.shop)

    def test_cafe_form_requires_consent_and_quantity(self):
        self.assertIn('name="consent" type="checkbox" required',self.cafe)
        self.assertIn('name="quantity" type="number" min="1"',self.cafe)
        self.assertIn('name="frequency" required',self.cafe)

    def test_csrf_action_guard_is_scoped_to_same_origin_and_path(self):
        for source in (self.shop,self.cafe):
            self.assertIn("ZM_OFFICIAL_INQUIRY_ACTION_GUARD_20261114",source)
            self.assertIn("destination.origin===location.origin",source)
            self.assertIn("destination.pathname==='/ask-master/index.php'",source)
            self.assertIn('candidate.querySelector(\'input[name="csrf"]\')',source)
            self.assertIn('official?.querySelector(\'input[name="csrf"]\')?.value',source)

    def test_no_automatic_customer_submission(self):
        for source in (self.shop,self.cafe):
            self.assertIn("addEventListener('submit'",source)
            self.assertIn("event.preventDefault()",source)
            self.assertIn("submission.submit()",source)
        self.assertIn("if(!data.has('consent')",self.cafe)

    def test_cafe_revenue_intent_is_expressed_without_guarantees(self):
        self.assertIn("سفارش دوره‌ای",self.cafe)
        self.assertIn("قیمت، ظرفیت تولید و تحویل هنوز قطعی نیستند",self.cafe)
        self.assertIn("فرم پرداخت یا تعهد قطعی تأمین ندارد",self.cafe)

    def test_preserve_templates_and_homepage(self):
        for p in ("public/index.html","core/templates/base.html"):
            s=read(p)
            self.assertNotIn("ZM_OFFICIAL_INQUIRY_ACTION_GUARD_20261114",s)
            self.assertNotIn("درخواست بررسی خرید و پیش‌فاکتور",s)


if __name__=="__main__":
    unittest.main()
