"""Mobile walletless invoice convenience: no funds sent without explicit wallet approval."""
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs,urlparse
from html.parser import HTMLParser
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

class WalletLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            self.links.append(dict(attrs))

class NativeTRXOneTapTests(unittest.TestCase):
    def setUp(self):
        # Render tests verify the checkout HTML/CSP, not QR generation. QR's
        # encoder has separate tests and requires the optional segno wheel.
        qr=patch("services.mpw_trx_walletless_checkout_ui.build_recipient_qr",
                 return_value='<svg xmlns="http://www.w3.org/2000/svg"></svg>')
        qr.start()
        self.addCleanup(qr.stop)

    def test_wallet_and_qr_fallback_in_same_invoice(self):
        html,csp=render_one_tap_invoice(INV,status_path=PATH)
        s=html.decode()
        self.assertIn('id="mpw-easy-pay"',s)
        self.assertIn('id="mpw-open-wallet"',s)
        self.assertIn('id="mpw-open-trustwallet"',s)
        self.assertIn('id="mpw-easy-pay" type="button" hidden',s)
        self.assertIn('id="mpw-open-wallet" class="buy" rel="noopener noreferrer" href="#" role="button" hidden',s)
        self.assertIn("Never pay an expired invoice.",s)
        self.assertIn("Open installed Trust Wallet (TRX)",s)
        self.assertIn("appButton.hidden=true;note.textContent",WALLET_ACTION_JS)
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

    def test_trust_wallet_prefills_only_server_issued_tron_invoice(self):
        html,_=render_one_tap_invoice(INV,status_path=PATH)
        p=WalletLinkParser()
        p.feed(html.decode())
        item=next(x for x in p.links if x.get("id")=="mpw-open-trustwallet")
        target=urlparse(item["href"])
        self.assertEqual((target.scheme,target.netloc,target.path),
            ("trust","","send"))
        self.assertEqual(parse_qs(target.query),{
            "asset":["c195"],"address":[INV.recipient],"amount":["1.234567"],
        })
        self.assertIn("noopener",item["rel"])
        self.assertNotIn("tx_hash",item["href"])
        self.assertNotIn("private",item["href"])

    def test_tronlink_launcher_cannot_leave_known_checkout_origin(self):
        self.assertIn('location.hostname==="mojplaywin.com"',WALLET_ACTION_JS)
        self.assertIn("acceptedHost||!approvedInvoice",WALLET_ACTION_JS)
        self.assertIn('tronlinkoutside://pull.activity?param=',WALLET_ACTION_JS)
        self.assertIn('action:"open"',WALLET_ACTION_JS)
        self.assertIn('role="button"',BUTTONS)

    def test_wallet_requires_explicit_click_and_no_client_payment_authority(self):
        self.assertIn('payButton.addEventListener("click"',WALLET_ACTION_JS)
        self.assertIn('app.trx.sendTransaction(recipient,Number(sun))',WALLET_ACTION_JS)
        self.assertIn("server-only reconciliation",__import__("services.mpw_trx_walletless_one_tap_ui",fromlist=["__doc__"]).__doc__)
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
