#!/usr/bin/env python3
"""C130: bounded, read-only cPanel source parity probe for Moj Prop.

The GitHub-hosted workflow sends this vetted script over pinned SSH stdin.
It reads metadata and byte-limited source files for fixed root-relative paths,
never executes/imports the inspected code, and prints only categorical output.
NO database connection, remote writes, backup, migration, secrets, customer
records, payment, or deployment. A match does not prove Passenger loaded it.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import pwd
import stat

ACCOUNT = "zomorod2"
ROOT = Path("/home/zomorod2/Saeit-staging")
PASSENGER = Path("/home/zomorod2/mojplaywin.com/passenger_wsgi.py")
MAX_SOURCE_BYTES = 1_048_576
# Exact source blobs from reviewed default branch; Git blob SHA-1 is ONLY a
# diagnostic byte-parity indicator, never security approval or release proof.
REVIEWED_BLOBS = {
    "config/urls.py": "07c2b6e10a7ec77ed6225f55d30ed655d61a37b3",
    "core/mojprop_views.py": "12ee5e408f2a50e0571d5e6d91a760644ec210a9",
    "core/mojprop_accessible_intake.py": "9642945352357f824cb6ac3b15816b134cb22dec",
    "core/mojprop_receipts.py": "9fe6eb1ad13857143440517b14b3f2ebcfef6db3",
    "core/mojprop_quote_views.py": "fe798dbf938f8a4fe2299616328c8b923d436dca",
    "core/management/commands/mojprop_sales_action_queue.py": "095dcf51e005694f4cb24df1e39ce8a4f6a0cf08",
    "scripts/mojprop_schema_preflight_c83.py": "023f6c58659f9da0c455f6f6a017da27ac4dbf50",
    "core/models.py": "bd4730db7ab924376ea2e77846160a6270dfa660",
    "core/admin.py": "144c568e6bf40fa44ba2095e462a54a4ca920816",
}
REQUIRED_ROUTES = {
    "moj-prop-intake/": "mojprop_intake",
    "moj-prop-status/": "mojprop_receipt_status",
    "moj-prop-quote/<str:token>/": "customer_quote",
}
ALLOWED_RESULTS = frozenset(("match", "drift", "missing", "unsafe", "unreadable", "oversized"))


def _safe_regular(path: Path) -> bool:
    """Reject symbolic links in ALL path components, and nonregular files."""
    if not path.is_absolute():
        return False
    current = Path("/")
    try:
        for part in path.parts[1:]:
            current = current / part
            mode = current.lstat().st_mode
            if stat.S_ISLNK(mode):
                return False
        return stat.S_ISREG(path.lstat().st_mode)
    except OSError:
        return False


def read_bounded(path: Path) -> tuple[str, bytes | None]:
    if not path.exists():
        return "missing", None
    if not _safe_regular(path):
        return "unsafe", None
    try:
        with path.open("rb") as handle:
            body = handle.read(MAX_SOURCE_BYTES + 1)
    except OSError:
        return "unreadable", None
    if len(body) > MAX_SOURCE_BYTES:
        return "oversized", None
    return "ok", body


def git_blob_digest(body: bytes) -> str:
    header = b"blob " + str(len(body)).encode("ascii") + b"\0"
    return hashlib.sha1(header + body).hexdigest()


def compare_source(path: Path, expected_sha: str) -> str:
    status, body = read_bounded(path)
    if status != "ok" or body is None:
        return status
    return "match" if git_blob_digest(body) == expected_sha else "drift"


def declared_routes(body: bytes) -> dict[str, str] | None:
    """AST only: never treat comments, strings or duplicate routes as live."""
    try:
        tree = ast.parse(body.decode("utf-8"))
    except (UnicodeError, SyntaxError):
        return None
    names: dict[str, str] = {}
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            owns_urls = any(
                isinstance(target, ast.Name) and target.id == "urlpatterns"
                for target in statement.targets
            )
        elif isinstance(statement, ast.AugAssign):
            owns_urls = (
                isinstance(statement.target, ast.Name)
                and statement.target.id == "urlpatterns"
            )
        else:
            owns_urls = False
        if not owns_urls:
            continue
        for node in ast.walk(statement.value):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id != "path" or len(node.args) < 2:
                continue
            route, view = node.args[:2]
            if not isinstance(route, ast.Constant) or type(route.value) is not str:
                continue
            if route.value not in REQUIRED_ROUTES:
                continue
            if not isinstance(view, ast.Name) or route.value in names:
                return None
            names[route.value] = view.id
    return names


def source_functions(body: bytes, names: tuple[str, ...]) -> bool:
    try:
        tree = ast.parse(body.decode("utf-8"))
    except (UnicodeError, SyntaxError):
        return False
    found = {
        node.name for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    return all(name in found for name in names)


def audit(root: Path, passenger: Path, *, owner_ok: bool) -> dict:
    reports = {relative: compare_source(root / relative, sha)
               for relative, sha in REVIEWED_BLOBS.items()}
    _, routes_body = read_bounded(root / "config/urls.py")
    routes = declared_routes(routes_body) if routes_body is not None else None
    active = bool(routes is not None and all(
        routes.get(route) == name for route, name in REQUIRED_ROUTES.items()
    ))
    _, view_body = read_bounded(root / "core/mojprop_views.py")
    handlers = bool(view_body is not None and source_functions(
        view_body, ("mojprop_intake", "mojprop_receipt_status")
    ))
    _, wsgi_body = read_bounded(passenger)
    passenger_marker = bool(wsgi_body is not None and b"Saeit-staging" in wsgi_body)
    return {
        "schema": "mojprop.cpanel.source_parity.readonly.v1",
        "read_only": True,
        "owner_shell_verified": owner_ok,
        "expected_sources": len(REVIEWED_BLOBS),
        "source_status": reports,
        "reviewed_source_exact_match_count": sum(x == "match" for x in reports.values()),
        "active_mojprop_routes_present": active,
        "intake_status_handlers_present": handlers,
        "passenger_wsgi_staging_reference_present": passenger_marker,
        "effective_passenger_runtime_verified": False,
        "tenant_quota_verified": False,
        "database_restore_executed": False,
        "media_backup_verified": False,
        "production_deploy_authorized": False,
        "customer_post_or_payment_sent": False,
    }


def main() -> None:
    try:
        user = pwd.getpwuid(os.geteuid()).pw_name
        if user != ACCOUNT:
            report = audit(Path("/nonexistent/mojprop-c130"),
                           Path("/nonexistent/mojprop-passenger"), owner_ok=False)
        else:
            report = audit(ROOT, PASSENGER, owner_ok=True)
    except (OSError, KeyError, ValueError, TypeError):
        report = audit(Path("/nonexistent/mojprop-c130"), Path("/nonexistent/mojprop-passenger"),
                       owner_ok=False)
    # Even if a caller or hosting cage exposes a different account, classify
    # as unsafe instead of inspecting another user's application paths.
    if report["owner_shell_verified"] is not True:
        report["source_status"] = {key: "unsafe" for key in REVIEWED_BLOBS}
        report["reviewed_source_exact_match_count"] = 0
        report["active_mojprop_routes_present"] = False
        report["intake_status_handlers_present"] = False
        report["passenger_wsgi_staging_reference_present"] = False
    print("MOJPROP_C130_SOURCE_PARITY=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
