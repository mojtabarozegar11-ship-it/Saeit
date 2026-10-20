#!/usr/bin/env python3
"""Surgical MojPlayWin two-book checkout CSP fix, with no shared Passenger restart.

Patch only the strict CSP hash assembly for two server-rendered style blocks.
Never touches checkout logic, payments, wallets, DB, sibling sites or WSGI.
"""
import ast
import hashlib
import json
import os
import pwd
import re
import stat
import sys
import tempfile
from pathlib import Path

APP = Path("/home/zomorod2/Saeit-staging")
TARGET = APP / "mpw_commerce/product_checkout_page.py"
WSGI = Path("/home/zomorod2/mojplaywin.com/passenger_wsgi.py")
BACKUPS = Path("/home/zomorod2/.private_mojplaywin_main_agents")
OLD1 = """if len(scripts) != 1 or len(styles) != 1 or b'<meta charset="utf-8">' not in body:"""
NEW1 = """if len(scripts) != 1 or len(styles) not in (1, 2) or b'<meta charset="utf-8">' not in body:"""
OLD2 = """"style-src 'self' " + source_hash(styles[0]) + "; """"
NEW2 = """"style-src 'self' " + " ".join(source_hash(style) for style in styles) + "; """"

def sha(blob):
    return hashlib.sha256(blob).hexdigest()

def fail(reason):
    raise RuntimeError(reason)

def guard():
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        fail("Unexpected shell owner")
    for p in (APP, BACKUPS):
        if p.is_symlink() or not p.is_dir():
            fail("Unexpected application or private-backup folder")
    for p in (TARGET, WSGI):
        if p.is_symlink() or not p.is_file() or p.parent.is_symlink():
            fail("Unexpected target or Passenger identity")
    if "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text("utf8", "replace"):
        fail("MojPlayWin application root changed")
    if stat.S_IMODE(BACKUPS.stat().st_mode) & 0o077:
        fail("Backup directory is not private")

def build(original):
    source = original.decode("utf8")
    if source.count(OLD1) != 1 or source.count(OLD2) != 1:
        fail("Expected strict CSP implementation not found exactly once")
    updated = source.replace(OLD1, NEW1, 1).replace(OLD2, NEW2, 1)
    tree = ast.parse(updated, filename=str(TARGET))
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_apply_two_book_strict_csp"]
    if len(functions) != 1:
        fail("Exact checkout CSP function not found")
    source_fn = ast.get_source_segment(updated, functions[0])
    if source_fn is None or "'unsafe-inline'" in source_fn or "'unsafe-eval'" in source_fn:
        fail("CSP security conditions are not preserved")
    compile(updated, str(TARGET), "exec")
    return updated.encode("utf8"), source_fn

def proof(handler):
    import importlib
    import django
    from django.test import RequestFactory
    from types import SimpleNamespace
    from unittest.mock import patch
    os.chdir(APP)
    if str(APP) not in sys.path:
        sys.path.insert(0, str(APP))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
    module = importlib.import_module("mpw_commerce.product_checkout_page")
    from core.models import Product
    for pk in (72, 225):
        req = RequestFactory().get(
            f"/store/product/{pk}/checkout/", secure=True, HTTP_HOST="mojplaywin.com"
        )
        req.user = SimpleNamespace(
            is_authenticated=True, is_active=True, pk=-1000, username="scoped-checkout-audit"
        )
        product = Product.objects.select_related("knowledge_article").get(pk=pk)
        if module.approved_for_checkout(req, product) is not True:
            fail(f"Product {pk} is not approved for live checkout")
        with patch.object(module, "_apply_two_book_strict_csp", handler):
            response = module.product_checkout_page(req, pk)
        body = response.content
        marker = b'<meta http-equiv="Content-Security-Policy" content="'
        if (response.status_code != 200 or body.count(marker) != 1
                or body.count(b"'sha256-") != 3
                or b"unsafe-inline" in body or b"unsafe-eval" in body):
            fail(f"Buyer checkout CSP proof failed for product {pk}")
        print("MPW_CHECKOUT_CSP_PROOF=" + json.dumps({
            "product": pk, "http": 200, "inline_script_hashes": 1,
            "style_hashes": 2, "customer_orders_created": 0,
            "real_payment": False
        }))

def preview():
    guard()
    original = TARGET.read_bytes()
    updated, function_source = build(original)
    namespace = {}
    exec(compile(function_source, str(TARGET), "exec"), namespace)
    proof(namespace["_apply_two_book_strict_csp"])
    print("MPW_CSP_PATCH_PREFLIGHT=" + json.dumps({
        "ready": True, "source_old_sha256": sha(original),
        "source_new_sha256": sha(updated),
        "target": "mpw_commerce.product_checkout_page",
        "passenger_restart": False
    }))

def ident(run):
    if not re.fullmatch(r"[0-9]{8,20}", run):
        fail("Invalid release identifier")
    return BACKUPS / ("mpw-checkout-csp-" + run + ".bak"), BACKUPS / ("mpw-checkout-csp-" + run + ".json")

def atomic(data):
    fd, name = tempfile.mkstemp(dir=TARGET.parent, prefix=".mpw-csp-")
    try:
        os.fchmod(fd, stat.S_IMODE(TARGET.stat().st_mode))
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, TARGET)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def publish(run):
    guard()
    original = TARGET.read_bytes()
    updated, function_source = build(original)
    namespace = {}
    exec(compile(function_source, str(TARGET), "exec"), namespace)
    proof(namespace["_apply_two_book_strict_csp"])
    backup, manifest = ident(run)
    if backup.exists() or manifest.exists() or backup.is_symlink() or manifest.is_symlink():
        fail("CSP backup already exists")
    with backup.open("xb") as out:
        os.fchmod(out.fileno(), 0o600)
        out.write(original)
        out.flush()
        os.fsync(out.fileno())
    payload = {"run": run, "old": sha(original), "new": sha(updated), "scope": "mpw_commerce/product_checkout_page.py"}
    with manifest.open("x", encoding="utf8") as out:
        os.fchmod(out.fileno(), 0o600)
        json.dump(payload, out)
        out.flush()
        os.fsync(out.fileno())
    if sha(TARGET.read_bytes()) != payload["old"]:
        fail("Concurrent checkout source change; backup kept; no edit")
    atomic(updated)
    if sha(TARGET.read_bytes()) != payload["new"]:
        if sha(TARGET.read_bytes()) == payload["old"]:
            fail("Checkout source unchanged after write")
        fail("Checkout source mismatch; investigate before using payments")
    print("MPW_CSP_PATCH=" + json.dumps({
        "status": "source_installed", "run": run,
        "only_file": payload["scope"], "passenger_restart": False,
        "wallet_or_payment_changes": False
    }))

def verify(run):
    guard()
    backup, manifest = ident(run)
    if backup.is_symlink() or manifest.is_symlink() or not backup.is_file() or not manifest.is_file():
        fail("CSP release backup missing")
    info = json.loads(manifest.read_text("utf8"))
    if info.get("run") != run or sha(backup.read_bytes()) != info.get("old"):
        fail("CSP rollback backup invalid")
    if sha(TARGET.read_bytes()) != info.get("new"):
        fail("Live CSP patch does not match expected digest")
    import importlib
    os.chdir(APP)
    sys.path.insert(0, str(APP))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    handler = importlib.import_module("mpw_commerce.product_checkout_page")._apply_two_book_strict_csp
    proof(handler)
    print("MPW_CSP_PATCH_VERIFIED=" + json.dumps({
        "on_disk": True, "new_python_process_render": True,
        "passenger_restart": False, "live_customer_payment": "not_tested"
    }))

def rollback(run):
    guard()
    backup, manifest = ident(run)
    if backup.is_symlink() or manifest.is_symlink() or not backup.is_file() or not manifest.is_file():
        fail("No rollback files")
    info = json.loads(manifest.read_text("utf8"))
    if info.get("run") != run or sha(backup.read_bytes()) != info.get("old"):
        fail("Invalid rollback")
    if sha(TARGET.read_bytes()) != info.get("new"):
        fail("Concurrent production change: rollback refused")
    atomic(backup.read_bytes())
    if sha(TARGET.read_bytes()) != info["old"]:
        fail("Rollback verification failed")
    print("MPW_CSP_PATCH_ROLLBACK=PASS")

def selftest():
    source = (
        "def _apply_two_book_strict_csp(response):\n"
        "    scripts=[b'abc']\n"
        "    styles=[b'one',b'two']\n"
        "    body=response\n"
        "    if len(scripts) != 1 or len(styles) != 1 or b'<meta charset=\"utf-8\">' not in body:\n"
        "        raise RuntimeError()\n"
        "    source_hash=lambda s: repr(s)\n"
        "    policy=(\"style-src 'self' \" + source_hash(styles[0]) + \"; \")\n"
        "    return policy\n"
    )
    result, fn = build(source.encode("utf8"))
    assert NEW1 in result.decode("utf8") and NEW2 in result.decode("utf8")
    assert len(result) > len(source) and "unsafe-inline" not in fn
    print("MPW_CSP_TWO_STYLES_SELFTEST=PASS")

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "selftest":
        selftest()
    elif len(sys.argv) == 2 and sys.argv[1] == "preview":
        preview()
    elif len(sys.argv) == 3 and sys.argv[1] in ("publish", "verify", "rollback"):
        {"publish": publish, "verify": verify, "rollback": rollback}[sys.argv[1]](sys.argv[2])
    else:
        raise SystemExit("Usage: selftest | preview | publish|verify|rollback RUN_ID")
