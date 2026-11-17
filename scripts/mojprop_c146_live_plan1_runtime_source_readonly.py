#!/usr/bin/env python3
"""C146 owner-only Plan1 staging-vs-Passenger diagnostic (no writes).

Run by vetted GitHub factory runner as the fixed cPanel user via Python -B -.
Only bounded, owner-owned, non-symlink, FIXED source files are inspected.
No API passwords, DB credentials, customer IDs, HTTP POST, archive contents,
DB connection, migration, deployment or broker action. The optional Django
route resolver only loads config URLConf; it NEVER calls customer views.
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import json
import os
from pathlib import Path
import pwd
import stat
import sys

ROOT = Path("/home/zomorod2/Saeit-staging")
WEBROOT = Path("/home/zomorod2/mojplaywin.com")
APP_USER = "zomorod2"
SOURCE = {
    "config/urls.py": "54ae76cea9c1708efbae2f63742d80aa772d36b9",
    "core/moj_prop_views.py": "1a2c07faf0c3880fcec9dc5373e3bfad9e84c0a3",
    "core/templates/mojplaywin/moj_prop_interest_form_d.html":
        "a8c8d791035c53f9120eccfcac32d99733a794d1",
    "prop_firm/lead_models.py": "45b113c9d6ffdb08f50209a5cedee7b0c418d468",
}
ROUTES = {
    "browser_get": ("moj-prop-interest/form/", "moj_prop_interest_form"),
    "consent_post": ("moj-prop-interest/", "moj_prop_interest"),
}
MAX_FILE_BYTES = 96 * 1024


def exact_git_blob(data: bytes) -> str:
    if type(data) is not bytes or len(data) > MAX_FILE_BYTES:
        raise ValueError("invalid bounded Git blob")
    return hashlib.sha1(b"blob " + str(len(data)).encode() +
                        b"\0" + data).hexdigest()


def safe_directory(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    return (stat.S_ISDIR(info.st_mode) and
            info.st_uid == os.geteuid() and
            not (info.st_mode & 0o022))


def source_state(root: Path, name: str, expected: str) -> str:
    """No content or filename from user input: caller supplies only constants."""
    if name not in SOURCE or root != ROOT:
        return "unsafe"
    if not safe_directory(root):
        return "unsafe"
    path = root / name
    current = path.parent
    while current != root:
        if root not in current.parents or not safe_directory(current):
            return "unsafe"
        current = current.parent
    try:
        entry = path.lstat()
        if (not stat.S_ISREG(entry.st_mode) or
                entry.st_uid != os.geteuid() or
                entry.st_mode & 0o022 or
                entry.st_nlink != 1 or
                entry.st_size > MAX_FILE_BYTES):
            return "unsafe"
        data = path.read_bytes()
        return "matches" if exact_git_blob(data) == expected else "drifted"
    except FileNotFoundError:
        return "missing"
    except (OSError, ValueError):
        return "unavailable"


def declared_routes(blob: bytes) -> dict:
    """Static AST proof, not comments, strings, import side effects or view calls."""
    out = {label: False for label in ROUTES}
    if type(blob) is not bytes or not 1 <= len(blob) <= MAX_FILE_BYTES:
        return out
    try:
        tree = ast.parse(blob.decode("utf-8"), mode="exec")
    except (UnicodeError, SyntaxError, ValueError, RecursionError,
            MemoryError):
        return out
    for node in ast.walk(tree):
        if (not isinstance(node, ast.Call) or
                not isinstance(node.func, (ast.Name, ast.Attribute)) or
                getattr(node.func, "id", getattr(node.func, "attr", None)) != "path" or
                len(node.args) < 2 or
                not isinstance(node.args[0], ast.Constant) or
                type(node.args[0].value) is not str or
                not isinstance(node.args[1], ast.Name)):
            continue
        for label, (route, handler) in ROUTES.items():
            if node.args[0].value == route and node.args[1].id == handler:
                out[label] = True
    return out


def inspect_staging_routes() -> dict:
    out = {label: False for label in ROUTES}
    try:
        # Cannot read customer records: only import URLConf and resolver metadata.
        os.chdir(ROOT)
        sys.path.insert(0, str(ROOT))
        os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
        import django
        django.setup()
        from django.urls import resolve
        for label, (route, handler) in ROUTES.items():
            try:
                match = resolve("/" + route)
                view = inspect.unwrap(match.func)
                out[label] = (
                    getattr(view, "__module__", "") == "core.moj_prop_views"
                    and getattr(view, "__name__", "") == handler
                )
            except Exception:
                out[label] = False
    except Exception as exc:
        out["startup_error_type"] = type(exc).__name__
    return out


def report() -> dict:
    out = {
        "schema": "mojprop.plan1.live_source.readonly.c146.v1",
        "read_only": True,
        "owner_identity_verified": False,
        "staging_root_safe": False,
        "webroot_safe": False,
        "source_identity": {key: "unavailable" for key in SOURCE},
        "static_urlconf_declares": {key: False for key in ROUTES},
        "django_cli_route_resolves": {key: False for key in ROUTES},
        "passenger_entry_present": False,
        "passenger_declares_staging_literal": False,
        "htaccess_present": False,
        "htaccess_explicit_plan1_rewrite": False,
        "actual_passenger_worker_source_proven": False,
        "public_plan1_get_verified": False,
        "full_app_db_media_restore_proven": False,
        "payment_or_enrollment_proven": False,
        "customer_data_accessed": False,
        "database_accessed": False,
        "external_network_called": False,
        "production_change_or_cost_authorized": False,
    }
    try:
        if pwd.getpwuid(os.geteuid()).pw_name != APP_USER:
            return out
        out["owner_identity_verified"] = True
        if not (safe_directory(ROOT) and safe_directory(WEBROOT)):
            return out
        out["staging_root_safe"] = True
        out["webroot_safe"] = True
        out["source_identity"] = {
            name: source_state(ROOT, name, expected)
            for name, expected in SOURCE.items()
        }
        urls = ROOT / "config/urls.py"
        if out["source_identity"]["config/urls.py"] in ("matches", "drifted"):
            data = urls.read_bytes()
            out["static_urlconf_declares"] = declared_routes(data)
        # The public WSGI entrypoint is only SOURCE, never the active worker.
        entry = WEBROOT / "passenger_wsgi.py"
        try:
            info = entry.lstat()
            if (stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
                    and not info.st_mode & 0o022
                    and info.st_nlink == 1 and info.st_size <= 32768):
                data = entry.read_bytes()
                tree = ast.parse(data.decode("utf-8"))
                strings = [n.value for n in ast.walk(tree)
                           if isinstance(n, ast.Constant)
                           and type(n.value) is str]
                out["passenger_entry_present"] = True
                out["passenger_declares_staging_literal"] = (
                    "/home/zomorod2/Saeit-staging" in strings
                )
        except (OSError, UnicodeError, SyntaxError, RecursionError,
                ValueError, MemoryError):
            pass
        # .htaccess is not executed, and its body is never logged.
        htaccess = WEBROOT / ".htaccess"
        try:
            info = htaccess.lstat()
            if (stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
                    and not info.st_mode & 0o022 and info.st_nlink == 1
                    and 0 < info.st_size <= 32768):
                content = htaccess.read_bytes().lower()
                out["htaccess_present"] = True
                out["htaccess_explicit_plan1_rewrite"] = (
                    b"moj-prop-interest" in content
                )
        except OSError:
            pass
        out["django_cli_route_resolves"] = inspect_staging_routes()
    except Exception as exc:
        out["probe_error_type"] = type(exc).__name__
    return out


if __name__ == "__main__":
    print("MOJPROP_C146_PLAN1_LIVE_SOURCE_READONLY=" +
          json.dumps(report(), sort_keys=True, separators=(",", ":")))
