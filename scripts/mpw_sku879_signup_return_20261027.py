#!/usr/bin/env python3
"""Guarded SKU 879 signup return-path repair. No database, wallet or payment writes."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
SITE = HOME / "mojplaywin.com"
TARGET = APP / "core/templates/brands/mojplaywin/product.html"
OLD = '<a href="/accounts/register/">New customer? Create an account</a>'
NEW = '<a href="/accounts/register/?next=/store/product/{{ product.pk }}/checkout/">New customer? Create an account</a>'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def transform(data):
    source = data.decode("utf-8")
    # Existing book links are already checkout-aware. Only the remaining
    # single generic signup link is eligible for replacement.
    if source.count(OLD) == 0 and source.count(NEW) >= 2:
        return data, False
    if source.count(OLD) != 1 or source.count(NEW) < 1:
        raise RuntimeError("Unexpected live product signup anchors")
    if "product.pk == 72 or product.pk == 225" not in source:
        raise RuntimeError("Expected book checkout branch missing")
    updated = source.replace(OLD, NEW, 1).encode("utf-8")
    return updated, True


def selftest():
    fixture = ('{% elif product.pk == 72 or product.pk == 225 %}' + NEW +
               '{% else %}' + OLD + '{% endif %}').encode()
    patched, changed = transform(fixture)
    assert changed and patched.count(NEW.encode()) == 2
    assert transform(patched) == (patched, False)
    for bad in (fixture + OLD.encode(), fixture.replace(NEW.encode(), b"")):
        try:
            transform(bad)
        except RuntimeError:
            pass
        else:
            raise AssertionError("Fail-closed anchor guard failed")
    print("MPW_879_SIGNUP_SELFTEST=PASS")


def guard():
    wsgi = SITE / "passenger_wsgi.py"
    for p in (APP, SITE):
        if not p.is_dir() or p.is_symlink():
            raise RuntimeError("Unverified app/site root")
    for p in (wsgi, TARGET):
        if not p.is_file() or p.is_symlink() or p.parent.is_symlink():
            raise RuntimeError("Unverified main-tenant target")
    if "APP='/home/zomorod2/Saeit-staging'" not in wsgi.read_text("utf-8", "replace"):
        raise RuntimeError("Passenger app identity mismatch")


def state_dir(run):
    if not re.fullmatch(r"[0-9]{8,20}", run):
        raise RuntimeError("Invalid run identifier")
    return HOME / (".mpw-879-signup-" + run)


def atomic(data):
    mode = stat.S_IMODE(TARGET.stat().st_mode)
    fd, name = tempfile.mkstemp(prefix=".mpw-879-signup-", dir=str(TARGET.parent))
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        if TARGET.is_symlink():
            raise RuntimeError("Target changed to symlink")
        os.replace(name, TARGET)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def validate():
    os.chdir(APP)
    sys.path.insert(0, str(APP))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.template import Template
    Template(TARGET.read_text("utf-8"))
    from django.test import Client
    client = Client(raise_request_exception=True)
    for product in (72, 225, 879):
        route = "/store/product/%d/" % product
        response = client.get(route, secure=True, HTTP_HOST="mojplaywin.com")
        if response.status_code != 200:
            raise RuntimeError("Product route unhealthy: " + route)
        body = response.content.decode("utf-8", "replace")
        expected = "/accounts/register/?next=/store/product/%d/checkout/" % product
        if expected not in body:
            raise RuntimeError("Checkout-aware signup missing: " + route)
    checkout = client.get("/store/product/879/checkout/", secure=True,
                          HTTP_HOST="mojplaywin.com")
    if checkout.status_code not in (302, 303) or "login" not in checkout.get("Location", "").lower():
        raise RuntimeError("Anonymous checkout protection changed")
    print("MPW_879_SIGNUP_DJANGO_ROUTES=PASS;DB_WRITES=0;PAYMENTS=0")


def reload_site():
    for p in (SITE / "tmp/restart.txt", APP / "tmp/restart.txt"):
        if not p.parent.is_dir() or p.parent.is_symlink() or p.is_symlink():
            raise RuntimeError("Unsafe Passenger restart marker")
        p.touch(exist_ok=True)


def preview():
    guard()
    before = TARGET.read_bytes()
    after, changed = transform(before)
    print("MPW_879_SIGNUP_PREVIEW=" + json.dumps({
        "changed": changed, "before": sha(before), "after": sha(after)}))


def apply(run):
    guard()
    before = TARGET.read_bytes()
    after, changed = transform(before)
    if not changed:
        validate()
        print("MPW_879_SIGNUP_ALREADY_APPLIED=PASS")
        return
    state = state_dir(run)
    if state.exists() or state.is_symlink():
        raise RuntimeError("Backup state already exists")
    state.mkdir(mode=0o700)
    backup = state / "product.html"
    with backup.open("xb") as out:
        os.fchmod(out.fileno(), 0o600)
        out.write(before)
        out.flush()
        os.fsync(out.fileno())
    manifest = {"run": run, "before": sha(before), "after": sha(after)}
    with (state / "manifest.json").open("x") as out:
        os.fchmod(out.fileno(), 0o600)
        json.dump(manifest, out)
        out.flush()
        os.fsync(out.fileno())
    if sha(TARGET.read_bytes()) != manifest["before"]:
        raise RuntimeError("Concurrent source change")
    atomic(after)
    try:
        if sha(TARGET.read_bytes()) != manifest["after"]:
            raise RuntimeError("Write verification failed")
        validate()
        reload_site()
    except BaseException:
        if sha(TARGET.read_bytes()) == manifest["after"]:
            atomic(before)
            reload_site()
        print("MPW_879_SIGNUP=ROLLED_BACK")
        raise
    print("MPW_879_SIGNUP=APPLIED;DB_WRITES=0;PAYMENTS=0")


def rollback(run):
    guard()
    state = state_dir(run)
    if not state.is_dir() or state.is_symlink():
        raise RuntimeError("Backup state missing")
    manifest = json.loads((state / "manifest.json").read_text("utf-8"))
    backup = state / "product.html"
    if backup.is_symlink() or not backup.is_file():
        raise RuntimeError("Backup unsafe")
    before = backup.read_bytes()
    if manifest.get("run") != run or sha(before) != manifest.get("before"):
        raise RuntimeError("Backup checksum mismatch")
    if sha(TARGET.read_bytes()) != manifest.get("after"):
        raise RuntimeError("Refuse rollback over a newer edit")
    atomic(before)
    reload_site()
    print("MPW_879_SIGNUP=ROLLBACK_VERIFIED")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["selftest"]:
        selftest()
    elif args == ["preview"]:
        preview()
    elif len(args) == 2 and args[0] in ("apply", "rollback"):
        (apply if args[0] == "apply" else rollback)(args[1])
    else:
        raise SystemExit("Usage: selftest | preview | apply RUN_ID | rollback RUN_ID")
