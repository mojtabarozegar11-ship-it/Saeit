#!/usr/bin/env python3
"""Fail-closed, reversible cPanel release of *email-free* guest TRX checkout.

The existing branded Django template is surgically preserved.  Only the
checkout email label/input and obsolete email-recovery copy are removed.
The existing signed-cookie guest adapter replaces the previous adapter.

Usage on the authorised cPanel account (not via GitHub Actions):
    preflight GUEST_SOURCE
    publish RUN_ID GUEST_SOURCE
    verify
    rollback RUN_ID

Never creates an invoice, sends email, moves money or edits customer data.
Publication requires separate owner approval. No command executes on import.
"""
from __future__ import annotations

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
PUBLIC = Path("/home/zomorod2/mojplaywin.com")
GUEST = APP / "services/mpw_trx_guest_commerce.py"
TEMPLATE = APP / "mpw_commerce/templates/mpw_commerce/product_checkout.html"
BACKUPS = Path("/home/zomorod2/.local/share/mpw-guest-no-email")
RESTART = PUBLIC / "tmp/restart.txt"

# The reviewed no-email guest module, not an arbitrary uploaded Python file.
APPROVED_GUEST_SHA256 = "11b0aa037c31fbcd1198331444d88426d9b4722d13606a7fda846c8f7601d949"
# Both are previously reviewed cPanel upgrade candidates; unknown versions stop.
PREVIOUS_GUEST_SHA256 = {
    "ef74a3ed84686e0c171f628932c2015338328ef93213e106834c2add7cdb1b2e",
    "6258de790fa95c774d847a6f3bf0cb170e69ebeccf1130a4b0b88be0bf55adc4",
    APPROVED_GUEST_SHA256,
}
EMAIL_LABEL = b'<label for="mpw-buy-email"><strong>Email address for your order (no account required)</strong></label>'
EMAIL_INPUT = re.compile(
    rb'<input\b(?=[^>]*\bid="mpw-buy-email")(?=[^>]*\bname="email")'
    rb'(?=[^>]*\btype="email")[^>]*>', re.I,
)
EMAIL_COPY = b"Email recovery on another device is not yet available."
CTA = b"Create my TRX payment invoice"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def abort(reason: str):
    raise RuntimeError("MPW_EMAIL_FREE_ABORT:" + reason)


def _file(path: Path) -> bytes:
    if (path.is_symlink() or path.parent.is_symlink() or not path.is_file()
            or not 0 < path.stat().st_size < 200_000):
        abort("UNSAFE_OR_MISSING:" + path.name)
    return path.read_bytes()


def guard():
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        abort("WRONG_ACCOUNT")
    for root in (APP, PUBLIC):
        if root.is_symlink() or not root.is_dir() or root.resolve() != root:
            abort("ROOT_DRIFT")
    wsgi = _file(PUBLIC / "passenger_wsgi.py")
    if b"APP='/home/zomorod2/Saeit-staging'" not in wsgi:
        abort("PASSENGER_APP_DRIFT")
    htaccess = _file(PUBLIC / ".htaccess").decode("utf-8", "replace")
    roots = re.findall(r"(?im)^\s*PassengerAppRoot\s+([^\r\n#]+)", htaccess)
    if (len(roots) != 1 or roots[0].strip().strip('"').strip("'").rstrip("/")
            not in (str(PUBLIC), "mojplaywin.com")):
        abort("PASSENGER_ROOT_DRIFT")
    if RESTART.is_symlink() or RESTART.parent.is_symlink() or not RESTART.parent.is_dir():
        abort("RESTART_TARGET_DRIFT")
    for target in (GUEST, TEMPLATE):
        _file(target)


def audit_invoice_email_dependencies() -> dict:
    """Read-only indicator check for invoice code and reachable local helpers.

    Checks source only: it cannot prove that a live invoice or paid download
    succeeds. Rejects hidden email references in helper functions called by
    the invoice handlers, including email aliases in module-level constants.
    External recorder implementations remain unverified, never assumed safe.
    """
    required = (
        "services/mpw_trx_commercial_web.py",
        "services/mpw_trx_commercial_context.py",
        "mpw_commerce/buyer_orders.py",
    )
    inspected = []
    invoice_handlers = 0
    invoice_recorders = 0
    inspected_functions = 0

    def folded_string(node):
        """Resolve only bounded, literal concatenations; never execute source."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value if len(node.value) <= 256 else None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = folded_string(node.left)
            right = folded_string(node.right)
            if left is not None and right is not None and len(left) + len(right) <= 256:
                return left + right
        if isinstance(node, ast.JoinedStr):
            parts = [folded_string(item) for item in node.values]
            if all(part is not None for part in parts) and sum(map(len, parts)) <= 256:
                return "".join(parts)
        return None

    def email_tokens(node, constant_aliases):
        matches = []
        for child in ast.walk(node):
            if isinstance(child, (ast.BinOp, ast.JoinedStr)):
                folded = folded_string(child)
                if folded is not None and "email" in folded.lower():
                    matches.append("constructed-string")
            if isinstance(child, ast.Name):
                if "email" in child.id.lower():
                    matches.append(child.id)
                if "email" in constant_aliases.get(child.id, "").lower():
                    matches.append(child.id)
            elif isinstance(child, ast.Attribute) and "email" in child.attr.lower():
                matches.append(child.attr)
            elif isinstance(child, ast.Constant) and isinstance(child.value, str):
                if "email" in child.value.lower():
                    matches.append("string")
            elif isinstance(child, ast.arg) and "email" in child.arg.lower():
                matches.append(child.arg)
            elif isinstance(child, ast.ImportFrom):
                if "email" in (child.module or "").lower():
                    matches.append("import")
                if any("email" in alias.name.lower() for alias in child.names):
                    matches.append("import")
            elif isinstance(child, ast.Import):
                if any("email" in alias.name.lower() for alias in child.names):
                    matches.append("import")
        return matches

    for rel in required:
        path = APP / rel
        raw = _file(path)
        try:
            tree = ast.parse(raw.decode("utf-8"))
        except (SyntaxError, UnicodeError):
            abort("INVOICE_SOURCE_UNREADABLE:" + path.name)

        functions = {}
        constant_aliases = {}
        recorder_imports = set()
        for stmt in tree.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.setdefault(stmt.name, []).append(stmt)
            elif isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                value = folded_string(stmt.value) if stmt.value is not None else None
                if value is not None:
                    targets = stmt.targets if isinstance(stmt, ast.Assign) else (stmt.target,)
                    for symbol in targets:
                        if isinstance(symbol, ast.Name):
                            constant_aliases[symbol.id] = value
            elif isinstance(stmt, ast.ImportFrom):
                for alias in stmt.names:
                    if alias.name == "record_invoice":
                        recorder_imports.add(alias.asname or alias.name)

        if rel.endswith("mpw_trx_commercial_web.py"):
            invoice_handlers = len(functions.get("_start_order", []))
        invoice_recorders += len(functions.get("record_invoice", []))

        roots = {"_start_order", "record_invoice"}
        queue = list(roots.intersection(functions))
        reached = set()
        while queue:
            name = queue.pop()
            if name in reached:
                continue
            reached.add(name)
            candidates = functions.get(name, [])
            if len(candidates) != 1:
                abort("DUPLICATE_INVOICE_HELPER:" + path.name + ":" + name)
            fn = candidates[0]
            inspected_functions += 1
            if email_tokens(fn, constant_aliases):
                abort("INVOICE_EMAIL_DEPENDENCY:" + path.name + ":" + name)

            for child in ast.walk(fn):
                # A recorder imported inside a handler bypasses the module-level
                # import index; its implementation has not been inspected.
                if isinstance(child, ast.ImportFrom):
                    if any(alias.name == "record_invoice" for alias in child.names):
                        abort("INVOICE_RECORDER_OUTSIDE_AUDIT_SCOPE:" + path.name)
            for call in ast.walk(fn):
                if not isinstance(call, ast.Call):
                    continue
                # Namespace-qualified recording (e.g., ledger.record_invoice)
                # is also external to the audited local call graph.
                if (isinstance(call.func, ast.Attribute) and
                        call.func.attr == "record_invoice"):
                    abort("INVOICE_RECORDER_OUTSIDE_AUDIT_SCOPE:" + path.name)
                if isinstance(call.func, ast.Name):
                    callee = call.func.id
                    if callee in recorder_imports:
                        abort("INVOICE_RECORDER_OUTSIDE_AUDIT_SCOPE:" + path.name)
                    if callee in functions and callee not in reached:
                        queue.append(callee)
        inspected.append(rel)

    if invoice_handlers != 1:
        abort("INVOICE_HANDLER_MISSING_OR_DUPLICATED")
    # Do not certify an invoice path merely because the HTTP handler exists.
    # Every recorder definition is analyzed above; zero or multiple are unknown.
    if invoice_recorders != 1:
        abort("INVOICE_RECORDER_MISSING_OR_DUPLICATED")
    return {"invoice_sources_examined": len(inspected),
            "invoice_recorder_found": True,
            "invoice_functions_examined": inspected_functions,
            "invoice_handler_found": True,
            "email_dependency_in_examined_handlers": False,
            "scope": "reachable_source_indicators_only_not_live_transaction"}


def patch_template(original: bytes) -> bytes:
    """Change exactly one known field; refuse unfamiliar templates."""
    if original.count(EMAIL_LABEL) != 1:
        abort("EMAIL_LABEL_DRIFT")
    matches = EMAIL_INPUT.findall(original)
    if len(matches) != 1 or not re.search(rb"\brequired\b", matches[0]):
        abort("EMAIL_INPUT_DRIFT")
    label_start = original.index(EMAIL_LABEL)
    input_start = original.index(matches[0])
    if not 0 < input_start - label_start - len(EMAIL_LABEL) < 256:
        abort("EMAIL_FIELD_STRUCTURE_DRIFT")
    if original.count(CTA) != 1 or b"csrf_token" not in original and b"csrfmiddlewaretoken" not in original:
        abort("FORM_CONTRACT_DRIFT")
    result = original.replace(EMAIL_LABEL, b"", 1).replace(matches[0], b"", 1)
    if result.count(EMAIL_COPY) == 1:
        result = result.replace(EMAIL_COPY, b"", 1)
    elif result.count(EMAIL_COPY) > 1:
        abort("EMAIL_COPY_DRIFT")
    verify_template(result)
    return result


def verify_template(raw: bytes):
    disallowed = (b'mpw-buy-email', b'name="email"', b"Email address for your order", EMAIL_COPY)
    if any(term in raw for term in disallowed):
        abort("EMAIL_FIELD_REMAINS")
    # Named controls and type=email must be absent even when legacy aliases,
    # single quotes or optional/hidden fields bypass the original exact bytes.
    # This is a fail-closed source gate, not a replacement for runtime POST QA.
    for tag in re.finditer(rb"<(?:input|textarea|select)\b[^>]*>", raw, re.I | re.S):
        opening = tag.group(0)
        for attribute in (b"name", b"id", b"type", b"autocomplete"):
            match = re.search(
                rb"(?<![\w:-])" + attribute +
                rb"""\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s/>]+))""",
                opening, re.I | re.S,
            )
            if match is None:
                continue
            value = next(group for group in match.groups() if group is not None)
            if ((attribute in (b"name", b"id") and b"email" in value.lower()) or
                    (attribute in (b"type", b"autocomplete") and value.lower() == b"email")):
                abort("EMAIL_FIELD_REMAINS")
    if raw.count(CTA) != 1 or (b"csrf_token" not in raw and b"csrfmiddlewaretoken" not in raw):
        abort("FORM_CONTRACT_LOST")


def _source(path: Path) -> bytes:
    code = _file(path)
    if sha(code) != APPROVED_GUEST_SHA256:
        abort("UNREVIEWED_GUEST_SOURCE")
    compile(code.decode("utf-8"), str(path), "exec")
    if b"def _new_user(request):" not in code or b"def patch_commercial(namespace):" not in code:
        abort("GUEST_CONTRACT_DRIFT")
    return code


def plan(source: Path):
    original_guest = _file(GUEST)
    original_template = _file(TEMPLATE)
    desired_guest = _source(source)
    current_guest = sha(original_guest)
    if current_guest not in PREVIOUS_GUEST_SHA256:
        abort("UNKNOWN_GUEST_BASE:" + current_guest)
    if original_guest == desired_guest and b"mpw-buy-email" not in original_template:
        verify_template(original_template)
        return {"guest": original_guest, "template": original_template}, None
    if b"mpw-buy-email" not in original_template:
        abort("PARTIAL_EMAIL_REMOVAL")
    desired_template = patch_template(original_template)
    return ({"guest": original_guest, "template": original_template},
            {"guest": desired_guest, "template": desired_template})


def _write_atomic(target: Path, raw: bytes, expected_hash: str):
    if sha(_file(target)) != expected_hash:
        abort("CONCURRENT_CHANGE:" + target.name)
    mode = stat.S_IMODE(target.stat().st_mode)
    fd, tmp = tempfile.mkstemp(prefix=".mpw-no-email-", dir=target.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as fh:
            fh.write(raw)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
        dirfd = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _safe_backup_location():
    # A symlink in ~/.local/share would redirect backups outside the private
    # account, even when BACKUPS itself is not a symlink.
    for ancestor in (BACKUPS, *BACKUPS.parents):
        if ancestor.is_symlink():
            abort("BACKUP_ANCESTOR_SYMLINK:" + ancestor.name)
    if BACKUPS.exists():
        st = BACKUPS.stat()
        if (not BACKUPS.is_dir() or st.st_uid != os.geteuid()
                or stat.S_IMODE(st.st_mode) & 0o077):
            abort("BACKUP_ROOT_UNSAFE")


def _backup_dir(run: str) -> Path:
    if not re.fullmatch(r"[0-9]{8,20}", run):
        abort("INVALID_RUN_ID")
    _safe_backup_location()
    BACKUPS.mkdir(mode=0o700, parents=True, exist_ok=True)
    _safe_backup_location()
    folder = BACKUPS / run
    if folder.exists() or folder.is_symlink():
        abort("RUN_ALREADY_EXISTS")
    folder.mkdir(mode=0o700)
    return folder


def _private_write(path: Path, data: bytes):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())


def _restart():
    if RESTART.is_symlink() or RESTART.parent.is_symlink():
        abort("RESTART_DRIFT")
    RESTART.touch()


def publish(run: str, source: Path):
    guard()
    audit_invoice_email_dependencies()
    old, new = plan(source)
    if new is None:
        print("MPW_EMAIL_FREE=ALREADY_INSTALLED")
        return
    folder = _backup_dir(run)
    before = {k: sha(v) for k, v in old.items()}
    after = {k: sha(v) for k, v in new.items()}
    for name in old:
        _private_write(folder / (name + ".bak"), old[name])
    manifest = {"run": run, "before": before, "after": after}
    _private_write(folder / "manifest.json", json.dumps(manifest, sort_keys=True).encode())
    targets = {"guest": GUEST, "template": TEMPLATE}
    changed = []
    try:
        for name, target in targets.items():
            if old[name] != new[name]:
                _write_atomic(target, new[name], before[name])
                changed.append(name)
        _restart()
    except BaseException:
        for name in reversed(changed):
            if sha(_file(targets[name])) == after[name]:
                _write_atomic(targets[name], old[name], after[name])
        _restart()
        raise
    print("MPW_EMAIL_FREE=PUBLISHED;CHANGED=" + ",".join(changed) +
          ";INVOICES_CREATED=0;EMAILS_SENT=0")


def rollback(run: str):
    guard()
    if not re.fullmatch(r"[0-9]{8,20}", run):
        abort("INVALID_RUN_ID")
    _safe_backup_location()
    folder = BACKUPS / run
    if folder.is_symlink() or not folder.is_dir() or stat.S_IMODE(folder.stat().st_mode) & 0o077:
        abort("INVALID_BACKUP")
    manifest = json.loads(_file(folder / "manifest.json"))
    if manifest.get("run") != run:
        abort("BACKUP_RUN_MISMATCH")
    for name, path in (("guest", GUEST), ("template", TEMPLATE)):
        if sha(_file(path)) != manifest["after"][name]:
            abort("ROLLBACK_TARGET_DRIFT:" + name)
        backup = _file(folder / (name + ".bak"))
        if sha(backup) != manifest["before"][name]:
            abort("ROLLBACK_BACKUP_DRIFT:" + name)
    for name, path in (("template", TEMPLATE), ("guest", GUEST)):
        _write_atomic(path, _file(folder / (name + ".bak")), manifest["after"][name])
    _restart()
    print("MPW_EMAIL_FREE=ROLLED_BACK")


def main(argv):
    if len(argv) == 3 and argv[1] == "preflight":
        guard()
        invoice_audit = audit_invoice_email_dependencies()
        old, new = plan(Path(argv[2]))
        print(json.dumps({"invoice_source_audit": invoice_audit, "publish_needed": new is not None,
                          "before": {k: sha(v) for k, v in old.items()},
                          "after": {k: sha(v) for k, v in (new or old).items()},
                          "invoices_created": 0, "emails_sent": 0}, sort_keys=True))
    elif len(argv) == 4 and argv[1] == "publish":
        publish(argv[2], Path(argv[3]))
    elif len(argv) == 2 and argv[1] == "verify":
        guard()
        audit_invoice_email_dependencies()
        if sha(_file(GUEST)) != APPROVED_GUEST_SHA256:
            abort("GUEST_NOT_INSTALLED")
        verify_template(_file(TEMPLATE))
        print("MPW_EMAIL_FREE=SOURCE_VERIFIED;NO_PAYMENT_ATTEMPTED=TRUE")
    elif len(argv) == 3 and argv[1] == "rollback":
        rollback(argv[2])
    else:
        raise SystemExit("preflight GUEST_SOURCE | publish RUN_ID GUEST_SOURCE | verify | rollback RUN_ID")


if __name__ == "__main__":
    main(sys.argv)
