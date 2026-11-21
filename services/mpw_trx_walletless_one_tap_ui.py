"""One-tap TRX wallet action for the walletless checkout invoice UI.

TronLink DApp injected provider can prefill amount and receiving address
from trusted, *server-issued* invoice. The wallet itself ALWAYS requires user
confirmation. If no provider exists, display a wallet-launch action or a
non-custodial QR/manual payment fallback. Wallet transaction return never
confers an entitlement: independent server-only reconciliation does.
"""
from __future__ import annotations

import base64
import hashlib
from html import escape
from decimal import Decimal
from urllib.parse import urlencode
from services.mpw_trx_walletless_checkout_ui import (
    render_invoice_page, _digest, STATUS_ROUTE,
)
from services.mpw_trx_walletless_core import (
    InvoiceIntent, PaymentHold, NETWORK, ADDRESS, SUN_PER_TRX,
)

WALLET_ACTION_JS = r"""(()=>{
"use strict";
const root=document.getElementById("checkout");
const payButton=document.getElementById("mpw-easy-pay");
const appButton=document.getElementById("mpw-open-wallet");
const note=document.getElementById("mpw-wallet-note");
const amount=document.getElementById("native-amount").textContent.trim();
const recipient=document.getElementById("recipient").textContent.trim();
const sun=BigInt(root.dataset.sun);
const app=window.tron && window.tron.tronWeb || window.tronWeb;
const acceptedHost=(location.hostname==="mojplaywin.com"||location.hostname==="www.mojplaywin.com");
const approvedInvoice=/^\/commerce\/trx-easy\/invoice\/[1-9][0-9]*\/$/.test(location.pathname);
const guestClaim=root.dataset.guest==="true";
const oneTime=root.dataset.walletHandoff||"";
const ticketOk=/^\/commerce\/trx-easy\/claim\/[a-f0-9]{64}\/$/.test(oneTime);
const launchTarget=guestClaim?(ticketOk?location.origin+oneTime:""):location.href.split("#")[0];
if (!acceptedHost||!approvedInvoice||!launchTarget) {
  appButton.hidden=true;
} else {
  const p={url:launchTarget,action:"open",protocol:"TronLink",version:"1.0"};
  appButton.href="tronlinkoutside://pull.activity?param="+encodeURIComponent(JSON.stringify(p));
}
if(!/^\d+\.\d{6}$/.test(amount)||!/^T[1-9A-HJ-NP-Za-km-z]{33}$/.test(recipient)||
   sun<=0n||sun>BigInt(Number.MAX_SAFE_INTEGER)||BigInt(amount.replace(".",""))!==sun){
  payButton.hidden=true;note.textContent="Wallet transfer is unavailable. Contact support before paying.";
  return;
}
const canSend=Boolean(app && app.trx && typeof app.trx.sendTransaction==="function");
if (!canSend) {
  payButton.hidden=true;
  note.textContent="On a phone, choose Open in Trust Wallet or TronLink; or use the QR and exact amount in any TRX wallet.";
} else {
  appButton.hidden=true;
}
// A wallet call can time out after a broadcast; never offer a rapid second
// payment on the same invoice based solely on a client-side error or reply.
let attempted=false;
payButton.addEventListener("click",async()=>{
  if(!canSend||attempted)return;
  attempted=true;
  payButton.disabled=true;
  note.textContent="Review recipient, amount and TRON network in your wallet. Approve only if correct.";
  try {
    const result=await app.trx.sendTransaction(recipient,Number(sun));
    // Browser wallet results are UNTRUSTED and are NEVER used to grant a download.
    if(result===false||result?.result===false) {
      note.textContent="Wallet did not confirm. Check wallet activity before any retry; do not pay twice.";
    } else {
      note.textContent="Wallet request completed. The site checks TRON automatically. Do not pay twice.";
    }
  }catch(err){
    note.textContent="Wallet response is uncertain. Check activity before retrying; the site keeps verifying.";
  }finally{
    payButton.hidden=true;
    window.dispatchEvent(new Event("mpw-wallet-submitted"));
  }
});
})();"""

BUTTONS = """<section aria-label="Easy TRX payment">
<button id="mpw-easy-pay" type="button">Pay TRX in my wallet</button>
<a id="mpw-open-wallet" class="buy" rel="noopener noreferrer" href="#" role="button">Open in TronLink</a>
{trust_wallet_link}
<p id="mpw-wallet-note" role="status" aria-live="polite">The wallet will ask you to approve payment; download unlocks only after blockchain confirmation.</p>
</section>"""


def render_one_tap_invoice(invoice: InvoiceIntent, *, status_path: str, guest_checkout:bool=False, wallet_handoff_path:str|None=None) -> tuple[bytes,str]:
    if not isinstance(invoice,InvoiceIntent) or invoice.network != NETWORK:
        raise PaymentHold("Invalid merchant TRX invoice")
    if not isinstance(status_path,str) or not STATUS_ROUTE.fullmatch(status_path):
        raise PaymentHold("Invalid owner-only status route")
    old,csp=render_invoice_page(invoice,status_path=status_path)
    if invoice.amount_sun>2**53-1:
        raise PaymentHold("Amount exceeds wallet's safe atomic-number limit")
    if not ADDRESS.fullmatch(invoice.recipient):
        raise PaymentHold("Invalid Trust Wallet TRON payment recipient")
    # Trust Wallet's official Send Payment deep link; TRON uses SLIP-44 195.
    # Parameters are generated exclusively from the immutable server invoice.
    # A wallet confirmation is still required; this URL grants no entitlement.
    amount=f"{Decimal(invoice.amount_sun)/Decimal(SUN_PER_TRX):.6f}"
    trust_wallet_url="https://link.trustwallet.com/send?"+urlencode({
        "asset":"c195", "address":invoice.recipient, "amount":amount,
    })
    trust_wallet_link=(
        '<a id="mpw-open-trustwallet" class="buy" role="button" '
        'rel="noopener noreferrer" href="'+escape(trust_wallet_url,quote=True)
        +'">Open in Trust Wallet (TRX)</a>'
    )
    html=old.decode("utf8")
    if html.count('<p>QR contains the address only.') != 1:
        raise PaymentHold("Invoice template unexpectedly changed")
    html=html.replace('<p>QR contains the address only.',
                      BUTTONS.format(trust_wallet_link=trust_wallet_link)
                      +'\n<p>QR contains the address only.',1)
    if html.count('<main id="checkout"')!=1:
        raise PaymentHold("Unexpected invoice frame")
    if guest_checkout is True:
        if wallet_handoff_path is not None and not __import__("re").fullmatch(
            r"/commerce/trx-easy/claim/[a-f0-9]{64}/",wallet_handoff_path
        ):
            raise PaymentHold("Untrusted one-time guest wallet handoff link")
        extra=' data-guest="true"'
        if wallet_handoff_path is not None:
            extra+=' data-wallet-handoff="'+escape(wallet_handoff_path,quote=True)+'"'
    elif wallet_handoff_path is not None:
        raise PaymentHold("Only validated guest invoices may have a wallet handoff")
    else:
        extra=""
    html=html.replace('<main id="checkout"',
                      '<main data-sun="'+str(invoice.amount_sun)+'"'+extra+' id="checkout"',1)
    if html.count("</body>")!=1:
        raise PaymentHold("Unsafe HTML script boundary")
    html=html.replace("</body>","<script>"+WALLET_ACTION_JS+"</script></body>",1)
    if html.count("<script>")!=2 or html.count("</script>")!=2:
        raise PaymentHold("Two invoice scripts required")
    # Add a second hash to the same CSP script-src directive.
    digest=_digest(WALLET_ACTION_JS)
    before="; frame-ancestors 'none'"
    if csp.count(before)!=1:
        raise PaymentHold("Unexpected strict CSP layout")
    csp=csp.replace(before," "+digest+before,1)
    return html.encode("utf8"),csp
