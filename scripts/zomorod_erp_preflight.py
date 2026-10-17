#!/usr/bin/env python3
"""Non-invasive ERP deployment preflight for Zomorod Melal.

This script is an *inspector*, never an installer:
- no DB writes, migrations, login attempts, SSH or secret reads
- read-only HTTPS GET against public health/login pages only
- no protected subsite write, filesystem rewrite or service restart
- emits JSON evidence and returns exit status 2 while deployment is blocked

Usage:
  python scripts/zomorod_erp_preflight.py --offline
  python scripts/zomorod_erp_preflight.py --live --output /tmp/zomorod-readiness.json

Passing this inspector is NOT authorization to deploy: root server repair,
tested recovery, a release owner and accountant approval remain separate.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = ROOT / "docs" / "zomorod-erp-release-checklist.json"
ORIGIN = "https://zomorodmelal.ir"
HEALTH_PATHS = (
    ("/", "homepage", 200),
    ("/admin/login/", "django_admin", 200),
    ("/api/health/", "django_health", 200),
    ("/company/office/login/", "private_office_login", 200),
)
SCHEMA_FILES = (
    "enterprise_portal/migrations/0001_initial.py",
    "enterprise_portal/migrations/0002_officeloginfailure.py",
    "ecosystem_hub/migrations/0001_initial.py",
    "ecosystem_hub/migrations/0002_materialpricereference_productioncostscenario.py",
)
MANDATORY_CHECKS = (
    "server_selector_wsgi_fixed",
    "verified_restorable_backup",
    "staging_migrations_and_rollback",
    "tls_and_secure_session_cookies",
    "enforced_mfa_and_ingress_throttle",
    "independent_subsites_baseline",
    "intercompany_data_permissions",
    "finance_and_tax_policy_review",
    "designated_release_approval",
)


class SameOriginHTTPS(urllib.request.HTTPRedirectHandler):
    """Refuse an untrusted redirect destination instead of sending probes away."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        source = urllib.parse.urlsplit(req.full_url)
        if target.scheme != "https" or target.netloc.lower() != source.netloc.lower():
            raise urllib.error.URLError("cross-origin-or-non-HTTPS redirect rejected")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def probe_one(path: str, *, origin: str = ORIGIN, opener=None) -> dict:
    """Observe only status, destination and errors; never retain response content."""
    origin_parts = urllib.parse.urlsplit(origin)
    if origin_parts.scheme != "https" or not origin_parts.hostname:
        raise ValueError("Public probes require an HTTPS origin")
    if not path.startswith("/") or path.startswith("//"):
        raise ValueError("Only relative site paths can be checked")
    if opener is None:
        opener = urllib.request.build_opener(SameOriginHTTPS())
    request = urllib.request.Request(
        origin.rstrip("/") + path,
        headers={"User-Agent": "ZomorodMelalERPReleaseReadiness/1.0",
                 "Accept": "text/html,application/json",
                 "Cache-Control": "no-cache"},
        method="GET",
    )
    result = {"path": path, "checked": True, "http_status": None, "healthy": False}
    try:
        with opener.open(request, timeout=13) as response:
            status = response.status
            result["http_status"] = status
            target = urllib.parse.urlsplit(response.geturl())
            result["healthy"] = (
                status == 200 and target.scheme == "https"
                and target.netloc.lower() == origin_parts.netloc.lower()
            )
    except urllib.error.HTTPError as exc:
        result["http_status"] = exc.code
        result["error"] = f"HTTP {exc.code}"
        exc.close()
    except (urllib.error.URLError, TimeoutError, ssl.SSLError, OSError) as exc:
        # Do not return user data, auth headers or raw private exception bodies.
        result["error"] = type(exc).__name__
    return result


def schema_check(root: Path = ROOT) -> dict:
    missing = [name for name in SCHEMA_FILES if not (root / name).is_file()]
    return {"present": len(SCHEMA_FILES) - len(missing),
            "expected": len(SCHEMA_FILES), "missing": missing,
            "ready": not missing}


def load_checklist(path: Path = CHECKLIST) -> dict:
    """An unaudited claim is never evidence of a completed release check."""
    document = json.loads(path.read_text(encoding="utf-8"))
    checks = document.get("checks", {})
    problems = []
    for key in MANDATORY_CHECKS:
        item = checks.get(key, {})
        if item.get("status") != "verified":
            problems.append(f"{key}: not verified")
        elif not str(item.get("evidence", "")).strip():
            problems.append(f"{key}: evidence missing")
    return {"check_count": len(MANDATORY_CHECKS),
            "verified_count": len(MANDATORY_CHECKS) - len(problems),
            "outstanding": problems, "all_verified": not problems}


def build_report(*, online: bool, root: Path = ROOT,
                 checklist: Path = CHECKLIST, opener=None) -> dict:
    schema = schema_check(root)
    evidence = load_checklist(checklist)
    endpoint_results = []
    if online:
        for path, label, expected in HEALTH_PATHS:
            result = probe_one(path, opener=opener)
            result["name"] = label
            result["expected_http_status"] = expected
            endpoint_results.append(result)
    production_health = (
        bool(endpoint_results) and
        all(item["healthy"] for item in endpoint_results)
    )
    outstanding = list(evidence["outstanding"])
    if not schema["ready"]:
        outstanding.append("database schema migration files absent")
    if not online:
        outstanding.append("live endpoints not inspected")
    elif not production_health:
        outstanding.append("one or more production endpoints unhealthy")
    # Advisory only; never substitute for actual signed deployment approval.
    is_ready = not outstanding and production_health and schema["ready"]
    return {
        "project": "Zomorod Melal private ERP & ecosystem hub",
        "operation": "READ_ONLY_DEPLOYMENT_PREPARATION",
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "production_ready": is_ready,
        "release_blocked": not is_ready,
        "status": "READY_FOR_HUMAN_RELEASE_REVIEW" if is_ready else "BLOCKED",
        "automatic_deploy_permitted": False,
        "schema": schema,
        "manual_evidence": evidence,
        "live_probes": endpoint_results,
        "outstanding": outstanding,
        "notes": [
            "No production database access or writes were performed.",
            "No payment, stock movement, admin login or subsite modification performed.",
            "MFA, trusted proxy configuration and backup RESTORE must be verified outside CI.",
            "A successful source test does not prove production Passenger/WSGI is healthy.",
            "A readiness report does not merge, deploy or authorize financial posting.",
        ],
    }


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    group = cli.add_mutually_exclusive_group(required=True)
    group.add_argument("--live", action="store_true", help="Read-only public HTTPS probes")
    group.add_argument("--offline", action="store_true", help="Source and human-evidence checks only")
    cli.add_argument("--output", type=Path, help="Where to write a JSON report (optional)")
    args = cli.parse_args(argv)
    report = build_report(online=args.live)
    data = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data, encoding="utf-8")
    print(data)
    return 0 if report["production_ready"] else 2


if __name__ == "__main__":
    sys.exit(main())
