#!/usr/bin/env python3
"""Surgical MojPlayWin 779 legacy checkout routing repair; never alters money or DB."""
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
SITE = Path("/home/zomorod2/mojplaywin.com")
TARGET = APP / "core/cryptopay_checkout.py"
BACKUPS = Path("/home/zomorod2/.private_mojplaywin_main_agents")
OLD = re.compile(r"pk\s+in\s*\(\s*72\s*,\s*225\s*,\s*879\s*\)")
NEW = "pk in (72, 225, 779, 879)"

def digest(data):
    return hashlib.sha256(data).hexdigest()

def guard():
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("Unexpected tenant identity")
    for folder in (APP, SITE, BACKUPS, TARGET.parent):
        if folder.is_symlink() or not folder.is_dir():
            raise RuntimeError("Unexpected deployment directory")
    if stat.S_IMODE(BACKUPS.stat().st_mode) & 0o077:
        raise RuntimeError("Backup area must be private")
    if TARGET.is_symlink() or not TARGET.is_file():
        raise RuntimeError("Unsafe checkout module")
    wsgi = SITE / "passenger_wsgi.py"
    if not wsgi.is_file() or wsgi.is_symlink():
        raise RuntimeError("Unverified Passenger entry")
    if "APP='/home/zomorod2/Saeit-staging'" not in wsgi.read_text("utf8", "replace"):
        raise RuntimeError("Wrong deployed app")

def transform(original):
    source = original.decode("utf8")
    updated, n = OLD.subn(NEW, source)
    if n != 1 or "pk in (72, 225, 779, 879)" in source:
        raise RuntimeError("Unexpected checkout route revision; no overwrite")
    old_ast, new_ast = ast.parse(source), ast.parse(updated)
    def get_checkout(tree):
        found = [f for f in tree.body if isinstance(f, ast.FunctionDef) and f.name == "checkout"]
        if len(found) != 1:
            raise RuntimeError("Checkout handler cannot be uniquely found")
        return found[0]
    before, after = get_checkout(old_ast), get_checkout(new_ast)
    changed_elsewhere = lambda root: [ast.dump(n, include_attributes=False) for n in root.body if n is not (before if root is old_ast else after)]
    if changed_elsewhere(old_ast) != changed_elsewhere(new_ast):
        raise RuntimeError("Unexpected change outside checkout")
    if ast.dump(before, include_attributes=False) == ast.dump(after, include_attributes=False):
        raise RuntimeError("Route was not changed")
    compile(updated, str(TARGET), "exec")
    return updated.encode("utf8")

def checkout_contract(blob):
    os.chdir(APP)
    sys.path.insert(0, str(APP))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.test import RequestFactory
    from types import SimpleNamespace
    import core.cryptopay_checkout as checkout_module
    namespace = dict(vars(checkout_module))
    tree = ast.parse(blob.decode("utf8"))
    fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "checkout")
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<779-checkout-test>", "exec"), namespace)
    result = []
    for pk in (72, 225, 779):
        request = RequestFactory().get("/store/product/%d/checkout/" % pk, secure=True, HTTP_HOST="mojplaywin.com")
        request.user = SimpleNamespace(is_authenticated=True, is_active=True, pk=-779221)
        response = namespace["checkout"](request, pk)
        result.append({"product": pk, "http": response.status_code})
        if response.status_code != 200:
            raise RuntimeError("Authenticated checkout must render HTTP 200 for %s" % pk)
    print("MPW_779_PATCH_SYNTHETIC_AUTHENTICATED=" + json.dumps(result))

def file_paths(run_id):
    if not re.fullmatch(r"[0-9]{8,20}", run_id):
        raise RuntimeError("Invalid release ID")
    return BACKUPS / ("mpw-native-779-checkout-" + run_id + ".bak"), BACKUPS / ("mpw-native-779-checkout-" + run_id + ".json")

def atomic(blob):
    fd, path = tempfile.mkstemp(dir=TARGET.parent, prefix=".mpw-native-779-")
    try:
        os.fchmod(fd, stat.S_IMODE(TARGET.stat().st_mode))
        with os.fdopen(fd, "wb") as f:
            f.write(blob)
            f.flush()
            os.fsync(f.fileno())
        os.replace(path, TARGET)
    finally:
        if os.path.exists(path):
            os.unlink(path)

def preview():
    guard()
    old = TARGET.read_bytes()
    updated = transform(old)
    checkout_contract(updated)
    print("MPW_779_ROUTE_PREVIEW=" + json.dumps({"old_sha256": digest(old), "new_sha256": digest(updated), "file": "core/cryptopay_checkout.py", "db_writes": 0, "money_moved": 0}))

def publish(run_id):
    guard()
    before = TARGET.read_bytes()
    after = transform(before)
    checkout_contract(after)
    backup, manifest = file_paths(run_id)
    if backup.exists() or manifest.exists() or backup.is_symlink() or manifest.is_symlink():
        raise RuntimeError("Existing release backup")
    with backup.open("xb") as f:
        os.fchmod(f.fileno(), 0o600)
        f.write(before)
        f.flush()
        os.fsync(f.fileno())
    doc = {"id": run_id, "old": digest(before), "new": digest(after), "path": "core/cryptopay_checkout.py"}
    with manifest.open("x", encoding="utf8") as f:
        os.fchmod(f.fileno(), 0o600)
        json.dump(doc, f)
        f.flush()
        os.fsync(f.fileno())
    if digest(TARGET.read_bytes()) != doc["old"]:
        raise RuntimeError("Concurrent change; deployment prevented")
    atomic(after)
    if digest(TARGET.read_bytes()) != doc["new"]:
        raise RuntimeError("Write mismatch")
    print("MPW_779_ROUTE_PUBLISHED=PASS; SINGLE_FILE=core/cryptopay_checkout.py")

def verify(run_id):
    guard()
    backup, manifest = file_paths(run_id)
    if backup.is_symlink() or manifest.is_symlink() or not backup.is_file() or not manifest.is_file():
        raise RuntimeError("Backup missing")
    data = json.loads(manifest.read_text("utf8"))
    if data["id"] != run_id or digest(backup.read_bytes()) != data["old"] or digest(TARGET.read_bytes()) != data["new"]:
        raise RuntimeError("Unexpected live revision")
    if digest(transform(backup.read_bytes())) != data["new"]:
        raise RuntimeError("Patch outside approved diff")
    checkout_contract(TARGET.read_bytes())
    print("MPW_779_ROUTE_VERIFIED=PASS")

def rollback(run_id):
    guard()
    backup, manifest = file_paths(run_id)
    if backup.is_symlink() or manifest.is_symlink() or not backup.is_file() or not manifest.is_file():
        raise RuntimeError("Rollback backup missing")
    data = json.loads(manifest.read_text("utf8"))
    old = backup.read_bytes()
    if data["id"] != run_id or digest(old) != data["old"] or digest(TARGET.read_bytes()) != data["new"]:
        raise RuntimeError("Concurrent edit; rollback held")
    atomic(old)
    assert digest(TARGET.read_bytes()) == data["old"]
    print("MPW_779_ROUTE_ROLLBACK=PASS")

def selftest():
    assert NEW == "pk in (72, 225, 779, 879)"
    try:
        transform(b"def checkout(request,pk): return None")
    except RuntimeError:
        pass
    else:
        raise RuntimeError("Drift guard absent")
    print("MPW_779_ROUTE_SELFTEST=PASS")

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] in ("preview", "selftest"):
        globals()[sys.argv[1]]()
    elif len(sys.argv) == 3 and sys.argv[1] in ("publish", "verify", "rollback"):
        globals()[sys.argv[1]](sys.argv[2])
    else:
        raise SystemExit("selftest|preview|publish RUN_ID|verify RUN_ID|rollback RUN_ID")
