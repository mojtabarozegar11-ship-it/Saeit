#!/usr/bin/env python3
"""Read-only, redacted cPanel runtime identity probe for the factory storefront.

Run as cPanel account through the pinned VPS SSH relay. Does not open database
connections, inspect credentials, print server paths, publish, or write files.
"""
import json
from pathlib import Path
import subprocess
import sys


CPANEL_HOME = Path("/home/zomorod2")
PUBLIC_ROOT = CPANEL_HOME / "mojplaywin.com"
SHARED_STAGE = CPANEL_HOME / "Saeit-staging"
RECIPE = "farm_enterprise_economics"


def app_records(value):
    if isinstance(value, dict):
        if "domain" in value and any(
            key in value for key in ("app_root", "app_path", "application_root")
        ):
            yield value
        for child in value.values():
            yield from app_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from app_records(child)


def classify_root(raw):
    if not isinstance(raw, str) or not raw.strip():
        return "absent", None
    candidate = Path(raw.strip())
    if not candidate.is_absolute():
        candidate = CPANEL_HOME / candidate
    if candidate.is_symlink():
        return "symlink", None
    normalized = candidate.resolve()
    if normalized == PUBLIC_ROOT:
        return "mojplaywin_public_root", normalized
    if normalized == SHARED_STAGE:
        return "saeit_staging", normalized
    return "other_root", None


def summarize(uapi):
    if not isinstance(uapi, dict) or not isinstance(uapi.get("result"), dict):
        raise RuntimeError("INVALID_UAPI_RESULT")
    result = uapi["result"]
    if result.get("status") not in (1, True):
        raise RuntimeError("UAPI_PASSENGER_FAILED")
    matches = []
    for entry in app_records(result.get("data")):
        if str(entry.get("domain") or "").lower().strip() != "mojplaywin.com":
            continue
        uri = str(entry.get("base_uri") or entry.get("app_uri")
                  or entry.get("application_uri") or "/").strip()
        if uri.rstrip("/") != "":
            continue
        kind, path = classify_root(
            entry.get("app_root") or entry.get("app_path")
            or entry.get("application_root")
        )
        matches.append((kind, path))
    matched = matches[0] if len(matches) == 1 else ("missing_or_ambiguous", None)
    kind, root = matched
    private = CPANEL_HOME / ".saeit-factory-inbox" / "receipts" / RECIPE
    count = 0
    if private.is_dir() and not private.is_symlink():
        count = sum(1 for receipt in private.iterdir() if receipt.is_file()
                    and not receipt.is_symlink() and receipt.suffix == ".json"
                    and len(receipt.stem) == 64
                    and all(ch in "0123456789abcdef" for ch in receipt.stem))
    return {
        "schema": "saeit.factory.live-storefront-runtime-readonly.v1",
        "read_only": True,
        "passenger_main_domain_root_mappings": len(matches),
        "passenger_root_kind": kind,
        "mapped_app_has_manage_py": bool(root and (root / "manage.py").is_file()),
        "mapped_app_has_django_settings": bool(root and (root / "config/settings.py").is_file()),
        "mapped_app_has_passenger_wsgi": bool(root and (root / "passenger_wsgi.py").is_file()),
        "mapped_app_has_php_index": bool(root and (root / "index.php").is_file()),
        "mapped_app_has_php_app": bool(root and (root / "app.php").is_file()),
        "staging_django_source_exists": (SHARED_STAGE / "manage.py").is_file(),
        "public_docroot_passenger_wsgi_exists": (PUBLIC_ROOT / "passenger_wsgi.py").is_file(),
        "private_flagship_receipt_files": count,
        "runtime_database_mapping_proven": False,
        "recoverable_production_backup_proven": False,
        "public_release_permitted": False,
        "customer_or_secret_data_read": False,
        "files_written": 0,
    }


def main():
    try:
        response = subprocess.run(
            ["uapi", "--output=json", "PassengerApps", "list_applications"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=30, check=False,
        )
        if response.returncode != 0 or not 0 < len(response.stdout) <= 2_000_000:
            raise RuntimeError("UAPI_NOT_AVAILABLE")
        summary = summarize(json.loads(response.stdout))
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print("FACTORY_STORE_RUNTIME_PROBE_FAILED=" + type(exc).__name__, file=sys.stderr)
        return 1
    print("FACTORY_STORE_RUNTIME_READONLY=" + json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
