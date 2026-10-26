#!/usr/bin/env python3
"""Owner-authorized MojPlayWin TRX invoice responsive mobile wallet layout repair.

One guarded CSS-only edit to the existing invoice renderer. No checkout
logic, amounts, QR payload, wallet URLs, orders, data, or sibling sites change.
"""
import hashlib
import inspect
import json
import os
from pathlib import Path
import stat
import sys
import time

APP=Path("/home/zomorod2/Saeit-staging")
LIVE=Path("/home/zomorod2/mojplaywin.com")
OLD_CSS=".qr svg{width:min(60vw,240px);height:auto;display:block}"
MARKER="/* MPW_TRX_MOBILE_ACTIONS_20261026 */"
NEW_CSS=OLD_CSS+"""
/* MPW_TRX_MOBILE_ACTIONS_20261026 */
section[aria-label="Easy TRX payment"]{
  display:grid;grid-template-columns:minmax(0,1fr);gap:12px;
  width:100%;min-width:0;margin:18px 0
}
section[aria-label="Easy TRX payment"]>button,
section[aria-label="Easy TRX payment"]>a.buy{
  display:flex;align-items:center;justify-content:center;
  width:100%;max-width:100%;min-width:0;
  box-sizing:border-box;margin:0;padding:13px 16px;
  line-height:1.5;white-space:normal;overflow-wrap:anywhere;
  word-break:normal;text-align:center;text-decoration:none;
}
section[aria-label="Easy TRX payment"]>p{
  min-width:0;margin:0;overflow-wrap:anywhere
}
#recipient{direction:ltr;unicode-bidi:isolate;overflow-wrap:anywhere;word-break:break-all}
@media(max-width:600px){
  main{max-width:100%}
  dl{grid-template-columns:1fr;gap:4px}
  dt{margin-top:8px}
  dd{margin:0 0 10px}
  .qr{display:block;width:max-content;max-width:100%;margin:0 auto 12px}
  .qr svg{width:min(64vw,240px);max-width:100%}
}
"""


def identify_renderer():
    os.chdir(APP)
    sys.path.insert(0,str(APP))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    import django
    django.setup()
    import services.mpw_trx_walletless_one_tap_ui as one
    target=Path(inspect.getfile(one.render_invoice_page))
    if not target.is_file() or target.is_symlink() or APP not in target.resolve().parents:
        raise RuntimeError("Invoice renderer outside protected app")
    source=target.read_text(encoding="utf-8")
    if MARKER in source:
        if NEW_CSS not in source:raise RuntimeError("Unexpected existing responsive marker")
        print("MPW_TRX_MOBILE_ALREADY_APPLIED")
        return target,source,source,one
    if source.count(OLD_CSS)!=1:
        raise RuntimeError("Invoice CSS anchor not unique")
    if 'STYLES' not in source or 'render_invoice_page' not in source:
        raise RuntimeError("Invoice renderer baseline missing")
    candidate=source.replace(OLD_CSS,NEW_CSS,1)
    compile(candidate,str(target),"exec")
    return target,source,candidate,one


def validate():
    import importlib
    import services.mpw_trx_walletless_one_tap_ui as one
    importlib.reload(one)
    css=one.render_invoice_page.__globals__["STYLES"]
    for rule in (MARKER,'section[aria-label="Easy TRX payment"]',
                 'grid-template-columns:minmax(0,1fr)','white-space:normal',
                 '#recipient{direction:ltr','@media(max-width:600px)'):
        if rule not in css:raise RuntimeError("Missing rule "+rule)
    from core.models import PaymentIntent
    import services.mpw_trx_commercial_web as web
    invoice_row=PaymentIntent.objects.select_related("order").filter(pk=14).first()
    if invoice_row and invoice_row.provider==web.PROVIDER:
        decoded=web._decode(invoice_row)
        page,csp=one.render_one_tap_invoice(decoded,status_path="/commerce/trx-easy/status/14/")
        html=page.decode("utf-8")
        ids=("mpw-open-wallet","mpw-open-trustwallet","recipient","copy-recipient","native-amount")
        for element_id in ids:
            if html.count('id="'+element_id+'"')!=1:raise RuntimeError("Missing or duplicate UI ID: "+element_id)
        if html.count(MARKER)!=1:raise RuntimeError("New responsive CSS missing from invoice HTML")
        if html.count("<script>")!=2 or html.count("</script>")!=2:
            raise RuntimeError("Invoice CSP script count changed")
        if "script-src" not in csp or "style-src" not in csp:
            raise RuntimeError("Invoice CSP weakened or removed")
        if decoded.recipient not in html or str(decoded.amount_sun) not in html:
            raise RuntimeError("Payment payload rendering changed")
        print("MPW_TRX_RENDERED_INVOICE_VERIFIED="+json.dumps({
            "status":"PASS","action_links":2,"qr_and_amount_preserved":True,
            "csp_preserved":True,"html_bytes":len(page)
        }))
    else:
        print("MPW_TRX_RENDERED_INVOICE_SKIP=No owner-controlled preserved reference invoice")
    from django.test import Client
    c=Client(raise_request_exception=False)
    for route in ("/store/product/779/","/store/product/72/","/store/product/225/",
                  "/store/product/879/","/accounts/login/"):
        code=c.get(route,secure=True,HTTP_HOST="mojplaywin.com").status_code
        if code!=200:raise RuntimeError("Protected product route changed: "+route)
        print("MPW_TRX_PRESERVED_ROUTE="+json.dumps({"route":route,"code":code}))


def restart():
    for p in (APP/"tmp/restart.txt",LIVE/"tmp/restart.txt"):
        if not p.parent.is_dir() or p.is_symlink():
            raise RuntimeError("Unexpected Passenger restart path")
        p.touch()


def main():
    if sys.argv[1:] not in (["check"],["apply"]):raise SystemExit("check|apply")
    target,before,after,one=identify_renderer()
    print("MPW_TRX_MOBILE_PREFLIGHT="+json.dumps({
        "file":target.name,"changed":before!=after,"source_sha":hashlib.sha256(before.encode()).hexdigest()[:18]
    }))
    if sys.argv[1]=="check":return
    if before==after:
        validate()
        print("MPW_TRX_MOBILE_RELEASE=ALREADY_APPLIED")
        return
    backupdir=APP/".release-backups"
    backupdir.mkdir(mode=0o700,exist_ok=True)
    backup=backupdir/("invoice-mobile-"+str(int(time.time()))+".py")
    backup.write_text(before,encoding="utf-8")
    backup.chmod(0o600)
    temp=target.with_name(target.name+".mobile-atomic")
    if temp.exists() or temp.is_symlink():raise RuntimeError("Unexpected preexisting temp")
    current_mode=stat.S_IMODE(target.stat().st_mode)
    try:
        temp.write_text(after,encoding="utf-8")
        temp.chmod(current_mode)
        os.replace(temp,target)
        validate()
        restart()
        print("MPW_TRX_MOBILE_RELEASE=PASS")
    except Exception:
        rollback=target.with_name(target.name+".mobile-rollback")
        rollback.write_text(before,encoding="utf-8")
        rollback.chmod(current_mode)
        os.replace(rollback,target)
        restart()
        print("MPW_TRX_MOBILE_RELEASE=ROLLED_BACK")
        raise


if __name__=="__main__":main()
