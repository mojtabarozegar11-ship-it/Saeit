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
from html.parser import HTMLParser


APP = Path("/home/zomorod2/Saeit-staging")
PUBLIC = Path("/home/zomorod2/mojplaywin.com")
GUEST = APP / "services/mpw_trx_guest_commerce.py"
TEMPLATE = APP / "mpw_commerce/templates/mpw_commerce/product_checkout.html"
BACKUPS = Path("/home/zomorod2/.local/share/mpw-guest-no-email")
RESTART = PUBLIC / "tmp/restart.txt"

# The reviewed no-email guest module, not an arbitrary uploaded Python file.
APPROVED_GUEST_SHA256 = "41d86a1985288c3db1097b66aae5a17f8fe0faaaa5d9dfa25b1d0cdfc154eaf0"
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
        # Exact recorder module found by read-only pinned cPanel SSH evidence:
        # services.mpw_trx_guest_delivery.record_invoice
        "services/mpw_trx_guest_delivery.py",
    )
    inspected = []
    invoice_handlers = 0
    invoice_recorders = 0
    inspected_functions = 0
    # Every permitted imported recorder must match exactly one scanned definition.
    permitted_recorders = {
        "services.mpw_trx_commercial_web": "services/mpw_trx_commercial_web.py",
        "services.mpw_trx_commercial_context": "services/mpw_trx_commercial_context.py",
        "mpw_commerce.buyer_orders": "mpw_commerce/buyer_orders.py",
        "services.mpw_trx_guest_delivery": "services/mpw_trx_guest_delivery.py",
    }
    recorder_definitions = {}
    invoked_recorders = set()

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
        recorder_imports = {}
        for stmt in tree.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.setdefault(stmt.name, []).append(stmt)
            elif isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                value = folded_string(stmt.value) if stmt.value is not None else None
                if stmt.value is None:
                    continue
                # A module-level dictionary/tuple/list may hide the required
                # email field from the existing direct-string alias check:
                #     INVOICE_FIELDS = {"buyer": "customer_email"}
                #     request.POST.get(INVOICE_FIELDS["buyer"])
                # It is safe to mark the entire *referenced* container as
                # email-dependent; do not execute arbitrary source expressions.
                if value is None:
                    parts = [
                        folded_string(child)
                        for child in ast.walk(stmt.value)
                        if isinstance(child, (ast.Constant, ast.BinOp, ast.JoinedStr))
                    ]
                    if any(part is not None and "email" in part.lower()
                           for part in parts):
                        value = "email-container"
                if value is not None:
                    targets = stmt.targets if isinstance(stmt, ast.Assign) else (stmt.target,)
                    for symbol in targets:
                        if isinstance(symbol, ast.Name):
                            constant_aliases[symbol.id] = value
            elif isinstance(stmt, ast.ImportFrom):
                for alias in stmt.names:
                    if alias.name == "record_invoice":
                        recorder_imports[alias.asname or alias.name] = (
                            stmt.module if stmt.level == 0 else ""
                        )

        if rel.endswith("mpw_trx_commercial_web.py"):
            invoice_handlers = len(functions.get("_start_order", []))
        invoice_recorders += len(functions.get("record_invoice", []))
        module_name = rel[:-3].replace("/", ".")
        recorder_definitions[module_name] = len(functions.get("record_invoice", []))

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

            # A handler-local recorder import is permitted only when it comes
            # from the identical, separately scanned module path.
            local_recorders = dict(recorder_imports)
            for child in ast.walk(fn):
                if isinstance(child, ast.ImportFrom):
                    for alias in child.names:
                        if alias.name == "record_invoice":
                            name = alias.asname or alias.name
                            origin = child.module if child.level == 0 else ""
                            if name in local_recorders and local_recorders[name] != origin:
                                abort("INVOICE_RECORDER_AMBIGUOUS_IMPORT:" + path.name)
                            local_recorders[name] = origin
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
                    if callee in local_recorders:
                        origin = local_recorders[callee]
                        if origin not in permitted_recorders:
                            abort("INVOICE_RECORDER_OUTSIDE_AUDIT_SCOPE:" + path.name)
                        invoked_recorders.add(origin)
                    if callee in functions and callee not in reached:
                        queue.append(callee)
        inspected.append(rel)

    if invoice_handlers != 1:
        abort("INVOICE_HANDLER_MISSING_OR_DUPLICATED")
    # Do not certify an invoice path merely because the HTTP handler exists.
    # Every recorder definition is analyzed above; zero or multiple are unknown.
    if invoice_recorders != 1:
        abort("INVOICE_RECORDER_MISSING_OR_DUPLICATED")
    if any(recorder_definitions.get(module, 0) != 1
           for module in invoked_recorders):
        abort("INVOICE_RECORDER_IMPLEMENTATION_MISSING")
    return {"invoice_sources_examined": len(inspected),
            "invoice_recorder_found": True,
            "audited_imported_recorders": len(invoked_recorders),
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


class CheckoutEmailControlParser(HTMLParser):
    """Fail closed on non-submitting invoice CTAs or unusable CSRF controls.

    The buyer-visible words must belong to an enabled submit control inside
    the precise TRX invoice POST form.  A generic text label, a GET endpoint,
    an unrelated form or a disabled input cannot prove checkout readiness.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.has_email_control = False
        self.forms = []
        self.current_form = None
        self.current_button = None
        self.malformed_forms = False

    def handle_starttag(self, tag, attrs):
        attributes = {name.lower(): (value or "").strip()
                      for name, value in attrs}
        if tag == "form":
            # Duplicate browser attributes and nested forms are ambiguous.
            field_names = [name.lower() for name, _ in attrs]
            if (self.current_form is not None or
                    field_names.count("method") != 1 or
                    field_names.count("action") != 1):
                self.malformed_forms = True
            self.current_form = {
                "method": attributes.get("method", "").lower(),
                "action": attributes.get("action", ""),
                "csrf": False,
                "csrf_hidden": False,
                "csrf_strong": False,
                "cta": False,
            }
        if self.current_form is not None:
            if tag == "button":
                if self.current_button is not None:
                    self.malformed_forms = True
                self.current_button = {
                    "submit": (attributes.get("type", "submit").lower() == "submit"
                               and "disabled" not in attributes),
                }
            if tag == "input":
                if (attributes.get("name", "").lower() == "csrfmiddlewaretoken"
                        and attributes.get("type", "hidden").lower() == "hidden"
                        and "disabled" not in attributes
                        and bool(attributes.get("value", ""))):
                    # Template-level verification accepts a nonempty rendered
                    # fixture; public verification independently insists on
                    # a full-length alphanumeric Django CSRF token.
                    token = attributes["value"]
                    self.current_form["csrf"] = True
                    self.current_form["csrf_hidden"] = True
                    self.current_form["csrf_strong"] = (
                        32 <= len(token) <= 128 and token.isascii()
                        and token.isalnum()
                    )
                if (attributes.get("type", "").lower() == "submit"
                        and attributes.get("value", "") == CTA.decode("utf-8")
                        and "disabled" not in attributes):
                    self.current_form["cta"] = True
        if tag not in ("input", "textarea", "select", "button"):
            return
        for name, value in attrs:
            name = name.lower()
            value = (value or "").strip().lower()
            if ((name in ("name", "id") and "email" in value) or
                    (name in ("type", "autocomplete") and value == "email")):
                self.has_email_control = True

    def handle_data(self, data):
        if self.current_form is None:
            return
        if re.search(r"{%\s*csrf_token\s*%}", data):
            self.current_form["csrf"] = True
        if (self.current_button is not None and
                self.current_button["submit"] and
                CTA.decode("utf-8") in data):
            self.current_form["cta"] = True

    def handle_endtag(self, tag):
        if tag == "button":
            self.current_button = None
        if tag == "form":
            if self.current_form is None or self.current_button is not None:
                self.malformed_forms = True
            if self.current_form is not None:
                self.forms.append(self.current_form)
                self.current_form = None
            self.current_button = None


def verify_template(raw: bytes):
    disallowed = (b'mpw-buy-email', b'name="email"', b"Email address for your order", EMAIL_COPY)
    if any(term in raw for term in disallowed):
        abort("EMAIL_FIELD_REMAINS")
    try:
        inspector = CheckoutEmailControlParser()
        inspector.feed(raw.decode("utf-8"))
        inspector.close()
    except (UnicodeError, ValueError) as exc:
        abort("UNREADABLE_CHECKOUT_TEMPLATE")
    if inspector.has_email_control:
        abort("EMAIL_FIELD_REMAINS")
    if inspector.malformed_forms or inspector.current_form is not None or raw.count(CTA) != 1:
        abort("FORM_CONTRACT_LOST")
    invoice_forms = [form for form in inspector.forms if form["cta"]]
    if len(invoice_forms) != 1:
        abort("FORM_CONTRACT_LOST")
    form = invoice_forms[0]
    action = form["action"].strip()
    # No loose prefix matching: /start/72/elsewhere, query strings, traversal,
    # nonpositive IDs and unreviewed template URL helpers are not accepted.
    allowed_action = re.fullmatch(
        r"/commerce/trx-easy/start/(?:[1-9][0-9]*|{{\s*product\.(?:id|pk)\s*}})/",
        action,
    ) is not None
    if form["method"] != "post" or not allowed_action or not form["csrf"]:
        abort("FORM_CONTRACT_LOST")



# Only actual public anonymous HTML proves every released SKU is usable.
# These checks never POST, authenticate, read buyer records, or log CSRF values.
PUBLIC_CHECKOUT_PRODUCTS = (72, 225, 879)


def verify_live_checkout_markup(raw: bytes, product_id: int) -> dict:
    """Strict, read-only acceptance for one *rendered* public checkout page."""
    if product_id not in PUBLIC_CHECKOUT_PRODUCTS:
        abort("LIVE_PRODUCT_NOT_ALLOWLISTED")
    if not raw or len(raw) > 500_000:
        abort("LIVE_CHECKOUT_UNSAFE_SIZE:" + str(product_id))
    try:
        inspector = CheckoutEmailControlParser()
        inspector.feed(raw.decode("utf-8"))
        inspector.close()
    except (UnicodeError, ValueError) as exc:
        abort("LIVE_CHECKOUT_UNREADABLE:" + str(product_id))
    if inspector.has_email_control:
        abort("LIVE_EMAIL_FIELD_PRESENT:" + str(product_id))
    if inspector.malformed_forms or inspector.current_form is not None:
        abort("LIVE_FORM_MALFORMED:" + str(product_id))
    exact = "/commerce/trx-easy/start/" + str(product_id) + "/"
    forms = [form for form in inspector.forms if form["action"] == exact]
    if len(forms) != 1:
        abort("LIVE_INVOICE_ACTION_MISSING:" + str(product_id))
    form = forms[0]
    # {% csrf_token %} in unrendered source is NOT a rendered CSRF control.
    if (form["method"] != "post" or not form["cta"]
            or not form["csrf_hidden"] or not form["csrf_strong"]):
        abort("LIVE_INVOICE_CONTRACT_INVALID:" + str(product_id))
    return {"product_id": product_id, "http_method": "POST",
            "email_field": False, "rendered_csrf": True,
            "invoice_action": "exact", "probe": "GET_ONLY"}


def audit_live_public_checkout_forms() -> list:
    """Three bounded anonymous GETs; no order creation or sensitive output."""
    import urllib.request
    from urllib.parse import urlsplit
    passed = []
    for product_id in PUBLIC_CHECKOUT_PRODUCTS:
        url = ("https://mojplaywin.com/store/product/" + str(product_id)
               + "/checkout/")
        req = urllib.request.Request(
            url, method="GET", headers={
                "Cache-Control": "no-cache, no-store", "Pragma": "no-cache",
                "Cookie": "", "User-Agent": "MPWReadOnlyBuyerContract/1.0",
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=16) as response:
                final = urlsplit(response.geturl())
                if (response.status != 200 or final.scheme != "https"
                        or final.netloc != "mojplaywin.com"
                        or final.path != "/store/product/" + str(product_id) + "/checkout/"
                        or final.query or final.fragment):
                    abort("LIVE_CHECKOUT_REDIRECT_OR_HTTP:" + str(product_id))
                content = response.read(500_001)
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError("MPW_EMAIL_FREE_ABORT:LIVE_CHECKOUT_UNREACHABLE:"
                               + str(product_id)) from exc
        passed.append(verify_live_checkout_markup(content, product_id))
    return passed


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
        buyer_contracts = audit_live_public_checkout_forms()
        print(json.dumps({"MPW_EMAIL_FREE": "PUBLIC_BUYER_FORMS_VERIFIED",
                          "products": buyer_contracts,
                          "email_field": False, "invoices_created": 0,
                          "payments_created": 0, "emails_sent": 0},
                         sort_keys=True))
    elif len(argv) == 2 and argv[1] == "public-audit":
        print(json.dumps({"MPW_LIVE_CHECKOUT_AUDIT": audit_live_public_checkout_forms(),
                          "invoices_created": 0, "payments_created": 0},
                         sort_keys=True))
    elif len(argv) == 3 and argv[1] == "rollback":
        rollback(argv[2])
    else:
        raise SystemExit("preflight GUEST_SOURCE | publish RUN_ID GUEST_SOURCE | verify | public-audit | rollback RUN_ID")


if __name__ == "__main__":
    main(sys.argv)
