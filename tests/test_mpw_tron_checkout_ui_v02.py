"""Checkout v0.2 regression tests: markup safety and accessibility contracts."""
import json
import re
import unittest
from pathlib import Path
from mpw_tron_pro.webapp import render_checkout

ASSETS = Path(__file__).resolve().parents[1] / 'mpw_tron_pro' / 'static'

class CheckoutUIContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.preview = render_checkout(None, preview=True).decode('utf-8')
        cls.html = (ASSETS / 'checkout.html').read_text('utf-8')
        cls.css = (ASSETS / 'checkout.css').read_text('utf-8')
        cls.js = (ASSETS / 'checkout.js').read_text('utf-8')

    def test_preview_is_explicitly_never_fundable(self):
        self.assertIn('PREVIEW ONLY', self.preview)
        self.assertIn('NO REAL FUNDS', self.preview)
        self.assertIn('No receiving address in preview', self.preview)
        self.assertIn('id="copy-address"', self.preview)
        self.assertRegex(self.preview, r'id="copy-address"[^>]*\bdisabled\b')
        self.assertRegex(self.preview, r'id="verify-button"[^>]*\bdisabled\b')

    def test_all_dynamic_backend_bindings_preserved(self):
        for field in ('TRX_AMOUNT', 'USD_AMOUNT', 'ADDRESS', 'PRODUCT_TITLE', 'QR_MARKUP',
                      'INVOICE_JSON', 'TIME_TEXT', 'INIT_MESSAGE', 'VERIFY_DISABLED', 'COPY_DISABLED'):
            self.assertIn('{{'+field+'}}', self.html)

    def test_expected_api_js_binding_ids(self):
        for ident in ('trx-amount', 'trx-address', 'copy-address', 'copy-amount', 'verify-form',
                      'verify-button', 'txid', 'stage-done', 'timer', 'timer-progress', 'feedback', 'invoice-data'):
            self.assertIn('id="'+ident+'"', self.html)

    def test_public_assets_and_checkout_reference_only(self):
        self.assertIn('href="/assets/checkout.css"', self.html)
        self.assertIn('src="/assets/checkout.js"', self.html)
        self.assertNotIn('seed phrase', self.html.lower())
        self.assertIn('recovery phrase', self.html.lower())
        self.assertIn('native TRX on TRON only', self.html)

    def test_checkout_not_cryptocurrency_network_agnostic(self):
        self.assertIn('TRON MAINNET', self.html)
        self.assertIn('Native TRX', self.html)
        self.assertIn('TRON network', self.html)

    def test_checkout_responsive_and_motion_safe(self):
        self.assertIn('@media(max-width:760px)', self.css)
        self.assertIn('@media(max-width:385px)', self.css)
        self.assertIn('prefers-reduced-motion:reduce', self.css)
        self.assertIn('min-width:0', self.css)
        self.assertIn('role="status" aria-live="polite"', self.html)

    def test_paid_status_visible_without_manual_claim(self):
        self.assertIn("changeStatus('paid')", self.js)
        self.assertIn('Your TRX payment is confirmed', self.js)
        self.assertIn('Waiting for your payment', self.html)
        self.assertIn('config.status', self.js)

    def test_order_title_xss_escaped_in_rendered_html(self):
        safe = render_checkout({
            'product_title': '<script>alert(1)</script>', 'usd':'4.00',
            'amount_sun': 11_000_000,'address':None,
            'expires_ms':1_800_000_000_000,'status':'pending',
        }, token='test').decode('utf-8')
        self.assertNotIn('<script>alert(1)</script>',safe)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;',safe)

if __name__ == '__main__':
    unittest.main()