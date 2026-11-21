"""Server-rendered, responsive walletless TRX checkout invoice.

QR contains MERCHANT ADDRESS ONLY. User must send exact native TRX amount.
Never claims that a wallet opened or that a transaction settled. Private
receipt or download grants are never decided by JavaScript.
"""
from datetime import timezone
from decimal import Decimal
from html import escape
import base64
import hashlib
import io
import re

from services.mpw_trx_walletless_core import InvoiceIntent, NETWORK, SUN_PER_TRX, PaymentHold

STATUS_ROUTE = re.compile(r"^/commerce/trx-easy/status/[1-9][0-9]*/$")
DOWNLOAD_ROUTE = re.compile(r"^/commerce/trx-easy/download/[1-9][0-9]*/$")
STYLES = """
*,*::before,*::after{box-sizing:border-box}html{color-scheme:dark}
body{font:16px/1.65 system-ui,sans-serif;background:#07182f;color:#eef6ff;margin:0;padding:12px}
main{max-width:650px;margin:16px auto;background:#17263c;border:1px solid #52677f;
border-radius:18px;padding:clamp(14px,4vw,30px);overflow-wrap:anywhere}
h1{font-size:clamp(22px,5vw,32px);line-height:1.3}
dl{display:grid;grid-template-columns:minmax(88px,1fr) 2fr;gap:12px}
dt{color:#b1c6d6}dd{margin:0;font-weight:650;overflow-wrap:anywhere}
button,a.buy{background:#75e7d4;color:#092b2b;font-weight:750;padding:13px 18px;
border-radius:12px;border:0;cursor:pointer;min-height:44px}
button{width:100%;margin:8px 0}a{color:#8ee8df}
.qr{background:white;border-radius:12px;padding:10px;display:inline-block;max-width:100%}
.qr svg{width:min(60vw,240px);height:auto;display:block}
#status{background:#182d3e;padding:12px;border-radius:10px;min-height:52px}
#download[hidden]{display:none} .danger{color:#ffda96}
@media(max-width:380px){dl{grid-template-columns:1fr;gap:4px}dd{margin-bottom:12px}}
"""
SCRIPT = """(() => {
"use strict";
const frame=document.getElementById("checkout");
const status=document.getElementById("status");
const download=document.getElementById("download");
const addr=document.getElementById("recipient").textContent.trim();
const amount=document.getElementById("native-amount").textContent.trim();
async function copy(which){
  try{
    await navigator.clipboard.writeText(which==="recipient"?addr:amount);
    status.textContent="Copied. Double-check the receiving address, exact amount and network.";
  }catch(e){status.textContent="Clipboard unavailable. Copy from the invoice manually.";}
}
document.getElementById("copy-recipient").addEventListener("click",()=>copy("recipient"));
document.getElementById("copy-amount").addEventListener("click",()=>copy("amount"));
let stopped=false,checking=false,failures=0,started=Date.now(),timer=null,lastProofAttempt=0;
function schedule(delay){
  if(stopped)return;
  if(timer!==null)window.clearTimeout(timer);
  timer=window.setTimeout(()=>{timer=null;check();},delay);
}
function nextDelay(){
  const elapsed=Date.now()-started;
  return elapsed<2*60*1000?4000:elapsed<10*60*1000?8000:15000;
}
async function check(){
  if(stopped||checking)return;
  if(Date.now()-started>35*60*1000){stopped=true;status.textContent="Automatic status checks paused. Contact support; do not send a second payment.";return;}
  if(document.hidden){schedule(10000);return;}
  checking=true;
  const controller=new AbortController();
  const timeout=window.setTimeout(()=>controller.abort(),8000);
  let delay=nextDelay();
  try{
    const url=frame.getAttribute("data-status-url");
    if(!/^\\/commerce\\/trx-easy\\/status\\/[1-9][0-9]*\\/$/.test(url))throw new Error("Invalid status endpoint");
    // Optional isolated adapter: ask the merchant server to verify incoming
    // transfers. This POST carries no txID, wallet signature or proof claim.
    const proofUrl=frame.getAttribute("data-reconcile-url")||"";
    const csrf=frame.getAttribute("data-csrf-token")||"";
    if(/^\\/commerce\\/trx-easy\\/reconcile\\/[1-9][0-9]*\\/$/.test(proofUrl)
      && /^[A-Za-z0-9]{32,128}$/.test(csrf)
      && Date.now()-lastProofAttempt>=15000){
      lastProofAttempt=Date.now();
      try{
        await fetch(proofUrl,{method:"POST",credentials:"same-origin",cache:"no-store",
          redirect:"error",signal:controller.signal,headers:{"Accept":"application/json","X-CSRFToken":csrf}});
      }catch(e){/* Await next authenticated status observation; never accept browser proof. */}
    }
    const r=await fetch(url,{credentials:"same-origin",cache:"no-store",redirect:"error",
      signal:controller.signal,headers:{"Accept":"application/json"}});
    if(!r.ok)throw new Error("Payment check temporarily unavailable");
    const data=await r.json();
    if(data.status==="paid" && data.can_download===true
      && typeof data.download_path==="string"
      && /^\\/commerce\\/trx-easy\\/download\\/[1-9][0-9]*\\/$/.test(data.download_path)){
      download.href=data.download_path;download.hidden=false;
      status.textContent="Payment independently confirmed. Your secure download is ready.";
      stopped=true;return;
    }
    status.textContent=data.status==="expired"
      ?"Invoice expired. Do not pay this invoice."
      :data.status==="review"||data.status==="paid"
      ?"Payment needs an additional server check. Do not pay again; contact support if delayed."
      :"Checking TRON automatically. Your download opens after final confirmation; do not pay twice.";
    if(data.status==="expired"){stopped=true;return;}
    failures=0;
  }catch(e){
    failures=Math.min(3,failures+1);
    delay=Math.min(30000,6000*(2**(failures-1)));
    status.textContent="Connection to payment checker is interrupted. It will retry; do not pay twice.";
  }finally{
    window.clearTimeout(timeout);
    checking=false;
    if(!stopped)schedule(delay);
  }
}
document.addEventListener("visibilitychange",()=>{if(!document.hidden && !stopped)check();});
window.addEventListener("online",()=>{if(!stopped)check();});
window.addEventListener("mpw-wallet-submitted",()=>{if(!stopped)check();});
schedule(1500);
})();"""

def build_recipient_qr(recipient: str) -> str:
    try:
        import segno
    except ImportError as exc:
        raise PaymentHold("Offline QR generator not installed") from exc
    if not isinstance(recipient,str) or not re.fullmatch(r"T[1-9A-HJ-NP-Za-km-z]{33}",recipient):
        raise PaymentHold("Unsafe receiving address")
    qr=segno.make_qr(recipient, error="m")
    out=io.BytesIO()
    qr.save(out,kind="svg",scale=5,xmldecl=False)
    svg=out.getvalue().decode("utf8")
    if "<svg" not in svg or "<script" in svg.lower():
        raise PaymentHold("Unexpected QR SVG")
    return svg


def _digest(content: str) -> str:
    return "'sha256-"+base64.b64encode(hashlib.sha256(content.encode()).digest()).decode()+"'"


def render_invoice_page(invoice: InvoiceIntent, *, status_path: str) -> tuple[bytes,str]:
    if not isinstance(invoice,InvoiceIntent) or invoice.network!=NETWORK:
        raise PaymentHold("Untrusted invoice")
    if not isinstance(status_path,str) or not STATUS_ROUTE.fullmatch(status_path):
        raise PaymentHold("Invalid server status endpoint")
    if invoice.expires_at<=invoice.issued_at or invoice.amount_sun<=0:
        raise PaymentHold("Unusable invoice")
    if invoice.amount_sun>=10**18:
        raise PaymentHold("Unrepresentable TRX value")
    amount=f"{(Decimal(invoice.amount_sun)/Decimal(SUN_PER_TRX)):.6f}"
    issued=invoice.issued_at.astimezone(timezone.utc).isoformat()
    expiry=invoice.expires_at.astimezone(timezone.utc).isoformat()
    qr=build_recipient_qr(invoice.recipient)
    content=f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><meta name="referrer" content="no-referrer">
<title>Secure TRX payment - MojPlayWin</title><style>{STYLES}</style></head><body>
<main id="checkout" data-status-url="{escape(status_path,quote=True)}">
<h1>Pay securely with TRX</h1><p>No website wallet connection or signing is required.</p>
<p class="danger"><strong>TRON MAINNET only.</strong> Do not pay before confirming network, amount and address. Sending crypto is irreversible.</p>
<div class="qr" aria-label="QR code containing the merchant wallet address ONLY">{qr}</div>
<p>QR contains the address only. You must enter the exact TRX amount below in your wallet.</p>
<dl><dt>To address</dt><dd id="recipient">{escape(invoice.recipient)}</dd>
<dt>Exact amount</dt><dd><span id="native-amount">{amount}</span> TRX</dd>
<dt>Original price</dt><dd>USD {escape(str(invoice.usd_total))}</dd>
<dt>Expires UTC</dt><dd><time datetime="{escape(expiry,quote=True)}">{escape(expiry)}</time></dd></dl>
<button id="copy-recipient" type="button">Copy receiving address</button>
<button id="copy-amount" type="button">Copy exact TRX amount</button>
<p id="status" role="status" aria-live="polite">Waiting for independent TRON confirmation. Do not send twice.</p>
<a id="download" hidden rel="nofollow" href="#">Download purchased file</a>
<p>If the invoice expires or there is a network error, do not pay again. Contact support.</p>
</main><script>{SCRIPT}</script></body></html>"""
    policy=("default-src 'none'; base-uri 'none'; form-action 'none'; object-src 'none';"
      " connect-src 'self'; img-src 'self' data:; font-src 'self'; "
      "style-src "+_digest(STYLES)+"; script-src "+_digest(SCRIPT)+"; "
      "frame-ancestors 'none'; upgrade-insecure-requests")
    return content.encode("utf8"),policy
