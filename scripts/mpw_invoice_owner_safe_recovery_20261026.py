#!/usr/bin/env python3
"""Owner-authorized narrow MojPlayWin login-return and invoice-expiry recovery.

Only two guarded cPanel files are modified. No wallet, order, invoice,
payment intent, customer, product, or sibling website data are written.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import time

APP = Path("/home/zomorod2/Saeit-staging")
LIVE = Path("/home/zomorod2/mojplaywin.com")
TARGETS = {
    "login": APP / "mpw_commerce/customer_auth.py",
    "invoice": APP / "services/mpw_trx_commercial_web.py",
}
LOGIN_OLD = '''    def get_success_url(self):
        return "/commerce/my-purchases/"
'''
LOGIN_NEW = '''    def get_success_url(self):
        # Honor Django's same-host validated return target after sign-in.
        # This is essential for checkout links with tracking query parameters.
        return self.get_redirect_url() or "/commerce/my-purchases/"
'''
INVOICE_OLD = '''    if intent.status!=WAITING or invoice.expires_at<=timezone.now():
        raise Http404("This invoice is no longer payable")
'''
INVOICE_NEW = '''    if intent.status!=WAITING or invoice.expires_at<=timezone.now():
        # Closed invoices are still accessible to their verified owner, but
        # must never display a payable amount or invite a second transfer.
        closed_page = """<!doctype html><html lang="en"><head>
        <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
        <meta name="robots" content="noindex,nofollow">
        <title>Invoice closed | MojPlayWin</title>
        <style>body{margin:0;background:#09192c;color:#f2f7ff;font:17px system-ui,sans-serif}
        main{max-width:650px;margin:7vh auto;padding:32px;border:1px solid #385674;
        border-radius:18px;background:#172b45}h1{font-size:clamp(25px,5vw,35px)}
        p{line-height:1.65}a{display:inline-block;margin:10px 12px 0 0;padding:13px 16px;
        border-radius:10px;background:#75e1d2;color:#082039;font-weight:700;text-decoration:none}
        a.secondary{background:#e8f0ff}</style></head><body>
        <main role="status"><h1>This invoice is no longer payable.</h1>
        <p>It has expired or its payment state has changed. Do not send TRX to
        this invoice or pay it a second time.</p>
        <p>If you already transferred TRX, check your purchase history and
        wait for verified blockchain settlement; contact support if necessary.</p>
        <a href="/commerce/trx-easy/purchases/">My TRX purchases</a>
        <a class="secondary" href="/store/">Return to store</a>
        <a class="secondary" href="/support/">Purchase support</a>
        </main></body></html>"""
        response=HttpResponse(closed_page,content_type="text/html; charset=utf-8")
        response["Content-Security-Policy"]="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
        response["X-Robots-Tag"]="noindex, nofollow"
        return _nocache(response)
'''
EXPECTED = {
    "login": (LOGIN_OLD, LOGIN_NEW),
    "invoice": (INVOICE_OLD, INVOICE_NEW),
}
MARKERS = {
    "login": "Honor Django's same-host validated return target",
    "invoice": "Closed invoices are still accessible to their verified owner",
}


def safe_target(path):
    if not path.is_file() or path.is_symlink():
        raise RuntimeError("Missing or symlinked target: " + str(path))
    if APP not in path.parents:
        raise RuntimeError("Unexpected target root")
    return path


def digest(data):
    return hashlib.sha256(data).hexdigest()[:20]


def prepare():
    updates = {}
    for key, path in TARGETS.items():
        safe_target(path)
        oldbytes = path.read_bytes()
        original = oldbytes.decode("utf-8")
        old, new = EXPECTED[key]
        if MARKERS[key] in original:
            if new not in original or old in original:
                raise RuntimeError("Ambiguous previously patched state: " + key)
            print("MPW_REPAIR_ALREADY_APPLIED=" + key)
            continue
        if original.count(old) != 1:
            raise RuntimeError("Expected unique source block absent: " + key)
        candidate = original.replace(old, new, 1)
        compile(candidate, str(path), "exec")
        updates[key] = (path, oldbytes, candidate.encode("utf-8"))
    return updates


def reload_passenger():
    for p in (APP / "tmp/restart.txt", LIVE / "tmp/restart.txt"):
        if not p.parent.is_dir() or p.is_symlink():
            raise RuntimeError("Passenger restart target invalid: " + str(p))
        p.touch()


def validate():
    os.chdir(APP)
    sys.path.insert(0, str(APP))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.test import Client, RequestFactory
    from django.contrib.auth import get_user_model
    from django.http import Http404
    from django.utils import timezone
    from core.models import PaymentIntent
    from mpw_commerce.customer_auth import CustomerLogin
    from services.mpw_trx_commercial_web import _show_invoice, _decode, WAITING, PROVIDER

    rf = RequestFactory()
    cases = [
        ("/commerce/book/779/", "/commerce/book/779/"),
        ("/commerce/trx-easy/invoice/14/?utm_source=chatgpt.com",
         "/commerce/trx-easy/invoice/14/?utm_source=chatgpt.com"),
        ("https://other.example/phish", "/commerce/my-purchases/"),
    ]
    for target, expected in cases:
        req = rf.get("/accounts/login/", {"next": target}, secure=True,
                     HTTP_HOST="mojplaywin.com")
        obj = CustomerLogin()
        obj.setup(req)
        got = obj.get_success_url()
        if got != expected:
            raise RuntimeError("Login redirect mismatch for case: " + repr(target) +
                               " actual=" + repr(got))
        print("MPW_LOGIN_SAFE_NEXT=" + json.dumps({"target": target, "passed": True}))

    c = Client(raise_request_exception=False)
    for path in ("/store/product/779/", "/store/product/72/",
                 "/store/product/225/", "/store/product/879/",
                 "/accounts/login/"):
        response = c.get(path, secure=True, HTTP_HOST="mojplaywin.com")
        if response.status_code != 200:
            raise RuntimeError("Protected MojPlayWin GET failed: " + path + " " +
                               str(response.status_code))
        print("MPW_PRESERVED_ROUTE=" + json.dumps({"route": path, "status": response.status_code}))

    for path in ("/commerce/book/779/", "/commerce/trx-easy/invoice/14/"):
        response = c.get(path, secure=True, HTTP_HOST="mojplaywin.com")
        if response.status_code not in (302, 303) or "/accounts/login/" not in response.get("Location", ""):
            raise RuntimeError("Anonymous invoice confidentiality regression: " + path)
        print("MPW_ANON_REDIRECT=" + json.dumps({"route": path, "status": response.status_code}))

    row = PaymentIntent.objects.select_related("order").filter(pk=14).first()
    if row:
        user = get_user_model().objects.filter(pk=row.order.customer_id).first()
        if user and user.is_active and row.provider == PROVIDER:
            inv = _decode(row)
            if row.status != WAITING or inv.expires_at <= timezone.now():
                req = rf.get("/commerce/trx-easy/invoice/14/", secure=True,
                             HTTP_HOST="mojplaywin.com")
                req.user = user
                response = _show_invoice(req, 14)
                body = response.content.decode("utf-8", "replace")
                if response.status_code != 200 or "no longer payable" not in body:
                    raise RuntimeError("Expired owner invoice not recoverable")
                if "0.103721" in body or "THFNU" in body:
                    raise RuntimeError("Closed page unexpectedly leaked payment instructions")
                print("MPW_EXPIRED_OWNER_VIEW=" + json.dumps({"status": response.status_code, "private": True}))
        else:
            print("MPW_OWNER_EXPIRED_TEST_SKIP=Provider or user ineligible")
    else:
        print("MPW_OWNER_EXPIRED_TEST_SKIP=Invoice 14 unavailable")


def main():
    if sys.argv[1:] not in (["apply"], ["check"]):
        raise SystemExit("Usage: script apply|check")
    changes = prepare()
    if sys.argv[1] == "check":
        print("MPW_FIX_PREFLIGHT=" + json.dumps({"keys": list(changes), "safe": True}))
        return
    if not changes:
        # A previous verified release must not create redundant backups or
        # restart the shared Passenger application and its protected subsites.
        validate()
        print("MPW_INVOICE_OWNER_SAFE_RELEASE=ALREADY_APPLIED_VERIFIED")
        return
    backup_root = APP / ".release-backups"
    backup_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    backup_dir = backup_root / ("owner-safe-invoice-" + str(int(time.time())))
    backup_dir.mkdir(mode=0o700)
    touched = []
    try:
        for key, (path, before, after) in changes.items():
            (backup_dir / (key + ".py")).write_bytes(before)
            temp = path.with_name(path.name + ".owner-safe-tmp")
            if temp.exists() or temp.is_symlink():
                raise RuntimeError("Existing unexpected temporary file")
            temp.write_bytes(after)
            temp.chmod(stat.S_IMODE(path.stat().st_mode))
            os.replace(temp, path)
            touched.append((path, before))
            print("MPW_PATCH_APPLIED=" + json.dumps({"file": key, "old": digest(before), "new": digest(after)}))
        validate()
        reload_passenger()
        print("MPW_INVOICE_OWNER_SAFE_RELEASE=PASS")
    except Exception:
        for path, oldbytes in reversed(touched):
            tmp = path.with_name(path.name + ".owner-safe-rollback")
            tmp.write_bytes(oldbytes)
            tmp.chmod(stat.S_IMODE(path.stat().st_mode))
            os.replace(tmp, path)
        if touched:
            reload_passenger()
        print("MPW_INVOICE_OWNER_SAFE_RELEASE=ROLLED_BACK")
        raise


if __name__ == "__main__":
    main()
