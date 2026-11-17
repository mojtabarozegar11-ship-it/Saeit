#!/usr/bin/env python3
"""Compare deployed cPanel Moj Prop intake source/URL mapping with audited main.

Owner-only stdin stream. Does not POST, connect to wallet, read buyer records,
create app files, issue an invoice, log Django settings/secrets or change host.
Git SHA-1 is for precise source identity, not a cryptographic trust signature.
"""
from __future__ import annotations

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
EXPECTED = {
    # Candidate source hash reviewed on the Plan1 prelaunch PR head;
    # different live source must report DRIFT until a verified release.
    # 2026-11-18 reviewed additive /world/ routes: no intake view was removed.
    # This is source identity only, not a live Passenger release.
    "core/mojprop_views.py": "12ee5e408f2a50e0571d5e6d91a760644ec210a9",
    "core/mojprop_receipts.py": "9fe6eb1ad13857143440517b14b3f2ebcfef6db3",
    "core/mojprop_accessible_intake.py": "505a1d237e3deb156e7e394e94b1c34ddf1e0071",
    "config/urls.py": "b924051fc75df43a8dfc7822fede041495230491",
    "core/management/commands/mojprop_sales_action_queue.py":
        "095dcf51e005694f4cb24df1e39ce8a4f6a0cf08",
}
MAX_SOURCE = 128 * 1024

def exact_git_blob(data):
    if type(data) is not bytes or len(data) > MAX_SOURCE:
        raise ValueError("unexpected source")
    return hashlib.sha1(b"blob " + str(len(data)).encode() + bytes([0]) + data).hexdigest()

def safe_source_state(root, rel, reference):
    """Only path identity/boolean returned; no byte content or arbitrary path."""
    target = root / rel
    if not root.is_dir() or root.is_symlink():
        return "unavailable"
    cursor = target
    while cursor != root:
        if cursor.is_symlink() or root not in cursor.parents:
            return "unavailable"
        cursor = cursor.parent
    try:
        meta = target.lstat()
        if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid()
                or meta.st_size > MAX_SOURCE or meta.st_mode & 0o002):
            return "unsafe"
        with target.open("rb") as handle:
            body = handle.read(MAX_SOURCE + 1)
        return "matches" if exact_git_blob(body) == reference else "drifted"
    except FileNotFoundError:
        # Distinguish a genuinely absent reviewed module from unreadable
        # content; never disclose arbitrary paths or exception messages.
        return "missing"
    except (OSError, ValueError):
        return "unavailable"

def read_only_route_snapshot():
    from django.urls import resolve
    result = {}
    for label, route in (
        ("canonical", "/moj-prop-intake/"),
        ("legacy", "/moj-prop/intake/"),
    ):
        try:
            match = resolve(route)
            view = inspect.unwrap(match.func)
            result[label] = (getattr(view, "__module__", "") == "core.mojprop_views"
                             and getattr(view, "__name__", "") == "mojprop_intake")
        except Exception:
            result[label] = False
    return result

def main():
    out = {
        "schema": "mojprop.intake.live_source_drift.readonly.v1",
        "read_only": True,
        "owner_identity_verified": False,
        "staging_root_verified": False,
        "source_identity": {},
        "django_route_map_available": False,
        "canonical_intake_route_maps_to_mojprop_view": False,
        "legacy_intake_route_maps_to_mojprop_view": False,
        "public_wsgi_mentions_expected_staging": False,
        "browser_public_endpoint_post_verified": False,
        "production_mysql_schema_upgrade_proven": False,
        "public_runtime_equals_cli_runtime_proven": False,
        "customer_data_accessed": False,
        "customer_lead_created": False,
        "production_release_permitted": False,
    }
    try:
        if pwd.getpwuid(os.geteuid()).pw_name != APP_USER:
            raise PermissionError("wrong app identity")
        out["owner_identity_verified"] = True
        if any(p.is_symlink() or not p.is_dir() for p in (ROOT, WEBROOT)):
            raise ValueError("app path not trusted")
        out["staging_root_verified"] = True
        out["source_identity"] = {
            p: safe_source_state(ROOT, p, v) for p, v in EXPECTED.items()
        }
        wsgi = WEBROOT / "passenger_wsgi.py"
        if wsgi.is_file() and not wsgi.is_symlink():
            data = wsgi.read_bytes()[:4096]
            out["public_wsgi_mentions_expected_staging"] = b"Saeit-staging" in data
        os.chdir(ROOT)
        sys.path.insert(0, str(ROOT))
        os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
        import django
        django.setup()
        routes = read_only_route_snapshot()
        out["django_route_map_available"] = True
        out["canonical_intake_route_maps_to_mojprop_view"] = routes["canonical"]
        out["legacy_intake_route_maps_to_mojprop_view"] = routes["legacy"]
    except Exception as exc:
        out["probe_error_type"] = type(exc).__name__
    print("MOJPROP_C95_LIVE_INTAKE_SOURCE_READONLY=" + json.dumps(out, sort_keys=True))

if __name__ == "__main__":
    main()
