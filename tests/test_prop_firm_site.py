"""Guarantee the informational site cannot turn into an accidental checkout."""
import unittest
from prop_firm.site import render_site
from prop_firm.rules import POLICY

class PropFirmSiteTests(unittest.TestCase):
    def test_policy_values_and_fourteen_levels(self):
        page=render_site()
        self.assertEqual(page.count('<li><span>ماه '),14)
        for expected in ('30 TRX','9.6%','6%','4%','8%','32%',
                         '0.8%','1.6%','3.6%','$50,000','$100,000',
                         POLICY.canonical_bot,'noindex,nofollow'):
            with self.subTest(value=expected):
                self.assertIn(expected,page)

    def test_payments_trades_and_visitor_forms_absent(self):
        page=render_site().lower()
        for forbidden in ('<form','checkout/', 'connect-wallet',
                          'sendtransaction','<iframe'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,page)
        self.assertIn('این صفحه اطلاع‌رسانی قابلیت ثبت سفارش، دریافت وجه',page)
        self.assertIn('فعال و تأمین سرمایه‌شده طبق اعلام مالک',page)
        self.assertIn('موقتاً غیرفعال',page)
        self.assertIn('aria-labelledby',page)
