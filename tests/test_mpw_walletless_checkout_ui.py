"""Offline tests for walletless invoice UI, QR and fail-closed status contract."""
import re
import unittest
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from services.mpw_trx_walletless_core import InvoiceIntent,PaymentHold
from services.mpw_trx_walletless_checkout_ui import render_invoice_page,SCRIPT,STYLES

NOW=datetime(2026,10,22,10,0,tzinfo=timezone.utc)
ADDRESS='T'+'A'*33
INV=InvoiceIntent(order_id=12,customer_id=50,network='tron-mainnet',recipient=ADDRESS,
                  amount_sun=1234567,usd_total=Decimal('0.37'),
                  issued_at=NOW,expires_at=NOW+timedelta(minutes=10),
                  quote_usd_per_trx=Decimal('0.30'))

class InvoicePageTests(unittest.TestCase):
    def test_qr_invoice_safely_renders_exact_sun(self):
        page,csp=render_invoice_page(INV,status_path='/commerce/trx-easy/status/12/')
        html=page.decode()
        self.assertIn('1.234567',html)
        self.assertIn('id="recipient">'+ADDRESS,html)
        self.assertIn('<svg',html)
        self.assertIn('QR contains the address only',html)
        self.assertIn('Copy exact TRX amount',html)
        self.assertIn("data-status-url=\"/commerce/trx-easy/status/12/\"",html)
        self.assertIn("script-src 'sha256-",csp)
        self.assertIn("style-src 'sha256-",csp)
        self.assertIn("frame-ancestors 'none'",csp)
        self.assertNotIn("unsafe-inline",csp)
        self.assertNotIn("unsafe-eval",csp)
        self.assertNotIn("private key",html.lower())
        self.assertNotIn("mnemonic",html.lower())

    def test_untrusted_status_urls_fail_closed(self):
        for u in ('https://evil.example/a','//evil.example',
                  '/commerce/trx-easy/status/../','/commerce/trx-easy/status/0/',
                  '/commerce/trx-easy/status/12/?redirect=http://evil.example',
                  '<script>alert(1)</script>'):
            with self.subTest(url=u),self.assertRaises(PaymentHold):
                render_invoice_page(INV,status_path=u)

    def test_wrong_network_amount_expiry_rejected(self):
        for x in (replace(INV,network='tron-shasta'),replace(INV,amount_sun=0),
                  replace(INV,expires_at=INV.issued_at)):
            with self.assertRaises(PaymentHold):
                render_invoice_page(x,status_path='/commerce/trx-easy/status/12/')

    def test_browser_never_local_grants(self):
        self.assertIn('data.can_download===true',SCRIPT)
        self.assertIn('data.status==="paid"',SCRIPT)
        self.assertIn("credentials:\"same-origin\"",SCRIPT)
        self.assertIn('redirect:"error"',SCRIPT)
        self.assertIn('35*60*1000',SCRIPT)
        self.assertNotIn('window.ethereum',SCRIPT)
        self.assertNotIn('window.tronWeb',SCRIPT)
        self.assertNotIn('tronLink',SCRIPT)
        self.assertNotIn('https://',SCRIPT)
        self.assertNotIn('@import',STYLES)

if __name__=='__main__':unittest.main()
