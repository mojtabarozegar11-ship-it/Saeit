"""Mobile walletless invoice convenience: no funds sent without explicit wallet approval."""
import unittest
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from dataclasses import replace
from services.mpw_trx_walletless_core import InvoiceIntent,PaymentHold
from services.mpw_trx_walletless_one_tap_ui import (
    render_one_tap_invoice,WALLET_ACTION_JS,BUTTONS,
)
from services.mpw_trx_walletless_checkout_ui import SCRIPT,_digest

TS=datetime(2026,10,22,7,0,tzinfo=timezone.utc)
INV=InvoiceIntent(order_id=14,customer_id=22,network="tron-mainnet",
    recipient="T"+"A"*33,amount_sun=1234567,usd_total=Decimal("0.37"),
    issued_at=TS,expires_at=TS+timedelta(minutes=10),
    quote_usd_per_trx=Decimal("0.30"))
PATH="/commerce/trx-easy/status/14/"

class NativeTRXOneTapTests(unittest.TestCase):
    def test_wallet_and_qr_fallback_in_same_invoice(self):
        html,csp=render_one_tap_invoice(INV,status_path=PATH)
        s=html.decode()
        self.assertIn('id="mpw-easy-pay"',s)
        self.assertIn('id="mpw-open-wallet"',s)
        self.assertIn('data-sun="1234567"',s)
        self.assertIn('QR contains the address only',s)
        self.assertIn('<svg',s)
        self.assertIn('1.234567',s)
        self.assertEqual(s.count('<script>'),2)
        self.assertEqual(s.count('</script>'),2)
        self.assertIn(_digest(WALLET_ACTION_JS),csp)
        self.assertIn(_digest(SCRIPT),csp)
        self.assertNotIn("'unsafe-inline'",csp)
        self.assertNotIn("'unsafe-eval'",csp)
        self.assertIn("frame-ancestors 'none'",csp)

    def test_tronlink_launcher_cannot_leave_known_checkout_origin(self):
        self.assertIn('location.hostname==="mojplaywin.com"',WALLET_ACTION_JS)
        self.assertIn("acceptedHost||!approvedInvoice",WALLET_ACTION_JS)
        self.assertIn('tronlinkoutside://pull.activity?param=',WALLET_ACTION_JS)
        self.assertIn('action:"open"',WALLET_ACTION_JS)
        self.assertIn('role="button"',BUTTONS)

    def test_wallet_requires_explicit_click_and_no_client_payment_authority(self):
        self.assertIn('payButton.addEventListener("click"',WALLET_ACTION_JS)
        self.assertIn('app.trx.sendTransaction(recipient,Number(sun))',WALLET_ACTION_JS)
        self.assertIn("server-only payment verification",__import__("services.mpw_trx_walletless_one_tap_ui",fromlist=["__doc__"]).__doc__)
        self.assertNotIn('fetch(',WALLET_ACTION_JS)
        self.assertNotIn('can_download=true',WALLET_ACTION_JS)
        self.assertNotIn('download.href',WALLET_ACTION_JS)
        self.assertNotIn('localStorage',WALLET_ACTION_JS)
        self.assertNotIn('tronWeb.defaultAddress=',WALLET_ACTION_JS)

    def test_invalid_invoice_or_status_must_not_render(self):
        with self.assertRaises(PaymentHold):
            render_one_tap_invoice(replace(INV,network="tron-shasta"),status_path=PATH)
        with self.assertRaises(PaymentHold):
            render_one_tap_invoice(INV,status_path="//fraud.example/charge")
        with self.assertRaises(PaymentHold):
            render_one_tap_invoice(replace(INV,amount_sun=2**53),status_path=PATH)


if __name__=="__main__":unittest.main()
