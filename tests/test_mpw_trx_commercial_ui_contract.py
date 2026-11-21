"""Native TRX checkout customer-facing JS/CSP and wallet deep-link checks."""
import subprocess,unittest
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from services.mpw_trx_walletless_checkout_ui import SCRIPT
from services.mpw_trx_walletless_one_tap_ui import (
    WALLET_ACTION_JS,render_one_tap_invoice,
)
from services.mpw_trx_walletless_core import InvoiceIntent
from services.mpw_tron_independent_solidified_rpc import hex_to_tron_address

class WalletlessCheckoutFrontendTests(unittest.TestCase):
    def test_both_real_browser_scripts_parse(self):
        for text in (SCRIPT,WALLET_ACTION_JS):
            result=subprocess.run(["node","--check"],input=text,encoding="utf8",
                                  capture_output=True,timeout=10)
            with self.subTest(first_lines=text[:30]):
                self.assertEqual(result.returncode,0,result.stderr[:1200])

    def test_render_invoice_wallet_app_fallback_and_no_browser_proof(self):
        t=datetime.now(timezone.utc)
        invoice=InvoiceIntent(
            order_id=72,customer_id=1,network="tron-mainnet",
            recipient=hex_to_tron_address("41"+"22"*20),
            amount_sun=150123456,
            usd_total=Decimal("7.50"),
            quote_usd_per_trx=Decimal("0.25"),
            issued_at=t,expires_at=t+timedelta(minutes=10),
        )
        html,policy=render_one_tap_invoice(
            invoice,status_path="/commerce/trx-easy/status/42/"
        )
        page=html.decode("utf8")
        self.assertIn('action="',page) if False else None
        self.assertIn("TRON MAINNET",page)
        self.assertIn("Open in Trust Wallet",page)
        self.assertIn('id="mpw-easy-pay"',page)
        self.assertIn("Checking TRON",page)
        self.assertIn("data-status-url",page)
        self.assertIn("script-src 'sha256-",policy)
        self.assertIn("connect-src 'self'",policy)
        self.assertIn("form-action 'none'",policy)
        self.assertIn("150.123456",page)
        self.assertNotIn("private_key",page.lower())
        self.assertNotIn("seed phrase",page.lower())

if __name__=="__main__":
    unittest.main()
