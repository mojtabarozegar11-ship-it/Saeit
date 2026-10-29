#!/usr/bin/env python3
"""S-01 surgical CSP repair for checkout templates with zero inline scripts.

The current authenticated buyer template has 0 inline scripts and 2 styles.
Keep script-src self only (no unsafe-inline) when there is no script.
Preview is read-only; publish requires explicit separate release gate.
Never touches orders, payments, wallets, DB, sibling sites or WSGI.
"""
import ast
import fcntl
from contextlib import contextmanager
import hashlib
import json
import os
import pwd
import re
import stat
import sys
import tempfile
from pathlib import Path

EXPECTED_SOURCE_SHA256 = "f33d80b7e843a66c9a55d8a8da46d5fb6049fb4c487f8f559c3471cfd42cdf74"
MIN_RELEASE_HEADROOM = 20 * 1024 * 1024
APP = Path("/home/zomorod2/Saeit-staging")
TARGET = APP / "mpw_commerce/product_checkout_page.py"
WSGI = Path("/home/zomorod2/mojplaywin.com/passenger_wsgi.py")
BACKUPS = Path("/home/zomorod2/.private_mojplaywin_main_agents")
OLD1 = """if len(scripts) != 1 or len(styles) not in (1, 2) or b'<meta charset="utf-8">' not in body:"""
NEW1 = """if len(scripts) not in (0, 1) or len(styles) not in (1, 2) or b'<meta charset="utf-8">' not in body:"""
OLD2 = '"script-src \'self\' " + source_hash(scripts[0]) + "; "'
NEW2 = '"script-src \'self\'" + (" " + source_hash(scripts[0]) if scripts else "") + "; "'

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

def _read_only_checkout_sql(execute, sql, params, many, context):
    """Reject every non-SELECT statement during the synthetic buyer GET proof.

    This is a safety guard, not an invoice-idempotency or live-payment test.
    In particular, no UPDATE, INSERT, DELETE, PRAGMA or transaction control is
    authorized by this probe. Fail closed if the view starts writing.
    """
    if not isinstance(sql, str) or not re.match(r"^\s*SELECT\b", sql, re.IGNORECASE):
        fail("Checkout proof refused non-SELECT database operation")
    return execute(sql, params, many, context)


def proof(handler):
    import importlib
    import django
    from django.db import connection
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
    with connection.execute_wrapper(_read_only_checkout_sql):
        for pk in (72, 225, 879):
            req = RequestFactory().get(
                f"/store/product/{pk}/checkout/", secure=True, HTTP_HOST="mojplaywin.com"
            )
            req.user = SimpleNamespace(
                is_authenticated=True, is_active=True, pk=-1000, username="scoped-checkout-audit"
            )
            product = Product.objects.select_related("knowledge_article").get(pk=pk)
            approved = module.approved_for_checkout(req, product) is True
            if not approved:
                if pk in (72, 225):
                    fail(f"Product {pk} is not approved for live checkout")
                print("MPW_CHECKOUT_RIGHTS_STATUS=" + json.dumps({
                    "product": pk, "approved": False, "no_sale_attempted": True
                }))
                continue
            with patch.object(module, "_apply_two_book_strict_csp", handler):
                response = module.product_checkout_page(req, pk)
            # SKU879 has a separate product/rights lifecycle: verify its
            # authenticated GET shape without imposing the two-book CSP hash
            # contract on a potentially different template.
            if pk == 879:
                if response.status_code != 200:
                    fail("SKU879 authenticated checkout GET did not return 200")
                print("MPW_CHECKOUT_SKU879_READONLY=" + json.dumps({
                    "product": 879, "http": 200, "payment": "not_tested",
                    "invoice": "not_created", "entitlement": "not_verified"
                }))
                continue
            body = response.content
            marker = b'<meta http-equiv="Content-Security-Policy" content="'
            if (response.status_code != 200 or body.count(marker) != 1
                    or body.count(b"'sha256-") != 2
                    or b"unsafe-inline" in body or b"unsafe-eval" in body):
                fail(f"Buyer checkout CSP proof failed for product {pk}")
            print("MPW_CHECKOUT_CSP_PROOF=" + json.dumps({
                "product": pk, "http": 200, "inline_script_hashes": 0,
                "style_hashes": 2, "sql_write_attempts_allowed": 0,
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

def release_preconditions(original):
    if sha(original) != EXPECTED_SOURCE_SHA256:
        fail("Production checkout source SHA drift; release refused")
    for folder in (TARGET.parent, BACKUPS):
        fs = os.statvfs(folder)
        if fs.f_bavail * fs.f_frsize < MIN_RELEASE_HEADROOM:
            fail("Insufficient local release/rollback headroom")

@contextmanager
def release_lock():
    # Linux advisory lock on the existing private directory: no lockfile write.
    fd = os.open(BACKUPS, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fail("Concurrent MojPlayWin checkout release lock held")
        yield
    finally:
        os.close(fd)

def publish(run):
    if os.environ.get("MPW_CSP_RELEASE_APPROVED") != "YES":
        fail("Production source write blocked without explicit release gate")
    # A local backup alone cannot authorize a production release. Both
    # independently checked recovery and effective Passenger DB identity must
    # be explicitly attested by the release operator; never infer them from
    # the SSH shell's SQLite configuration or an old workflow run.
    if os.environ.get("MPW_CSP_OFFHOST_RESTORE_VERIFIED") != "YES":
        fail("Production source write blocked: independent off-host restore not verified")
    if os.environ.get("MPW_CSP_PASSENGER_DB_AUTHORITY_VERIFIED") != "YES":
        fail("Production source write blocked: Passenger database authority not verified")
    guard()
    with release_lock():
        return _publish_locked(run)

def _publish_locked(run):
    original = TARGET.read_bytes()
    release_preconditions(original)
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
    if sha(backup.read_bytes()) != sha(original):
        fail("Immutable rollback preimage readback mismatch")
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
    import django
    django.setup()
    handler = importlib.import_module("mpw_commerce.product_checkout_page")._apply_two_book_strict_csp
    proof(handler)
    print("MPW_CSP_PATCH_VERIFIED=" + json.dumps({
        "on_disk": True, "new_python_process_render": True,
        "passenger_restart": False, "live_customer_payment": "not_tested"
    }))

def rollback(run):
    # A rollback is a production write too: serialize it with publish and
    # require the same explicit owner-controlled release authorization.
    if os.environ.get("MPW_CSP_RELEASE_APPROVED") != "YES":
        fail("Production rollback blocked without explicit release gate")
    guard()
    with release_lock():
        return _rollback_locked(run)


def _rollback_locked(run):
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
    source = '''def _apply_two_book_strict_csp(response):
    scripts=[b'abc'] if response else []
    styles=[b'one',b'two']
    body=b'<meta charset="utf-8">'
    if len(scripts) != 1 or len(styles) not in (1, 2) or b'<meta charset="utf-8">' not in body:
        raise RuntimeError()
    source_hash=lambda s: "\'sha256-synthetic\'"
    policy=("script-src 'self' " + source_hash(scripts[0]) + "; ")
    return policy
'''
    result, fn = build(source.encode("utf8"))
    assert NEW1 in result.decode("utf8") and NEW2 in result.decode("utf8")
    namespace = {}
    exec(compile(fn, "<csp-selftest>", "exec"), namespace)
    handler = namespace["_apply_two_book_strict_csp"]
    assert handler(False) == "script-src 'self'; "
    assert handler(True) == "script-src 'self' 'sha256-synthetic'; "
    assert "unsafe-inline" not in fn and "unsafe-eval" not in fn
    print("MPW_CSP_ZERO_SCRIPT_SELFTEST=PASS")

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "selftest":
        selftest()
    elif len(sys.argv) == 2 and sys.argv[1] == "preview":
        preview()
    elif len(sys.argv) == 3 and sys.argv[1] in ("publish", "verify", "rollback"):
        {"publish": publish, "verify": verify, "rollback": rollback}[sys.argv[1]](sys.argv[2])
    else:
        raise SystemExit("Usage: selftest | preview | publish|verify|rollback RUN_ID")
