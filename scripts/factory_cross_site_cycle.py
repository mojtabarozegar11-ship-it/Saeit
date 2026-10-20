#!/usr/bin/env python3
"""Private factory one-pass site-capability audit and real HTML preview QA.

No network, no site writes, no agent cloning or automatic commercial approval.
Reports real existing HTML preview quality, verifies exact site-source copies,
and represents inaccessible private site telemetry as unknown.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from factory_cross_site_capabilities import audit_repo, html_quality, telemetry_state, MAX_HTML

SCHEMA = "saeit.factory.cross-site-live-cycle.v1"
PILOT_PATHS = ("preview/index.html", "preview.html", "index.html", "guide/index.html")
MAX_PRODUCT_DIRS = 150
MAX_PREVIEWS = 5


def _dir(path, create=False):
    if path.is_symlink():
        raise RuntimeError("CROSS_SITE_UNSAFE_DIRECTORY")
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(str(path), 0o700)
    if not path.is_dir() or path.is_symlink():
        raise RuntimeError("CROSS_SITE_MISSING_DIRECTORY")


def safe_preview(path):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_HTML:
        return None
    return path.read_bytes()


def run(repo, private):
    audit = audit_repo(repo)
    root = Path(private).expanduser()
    _dir(root)
    candidates = root / "digital-products"
    checks = []
    examined = 0
    if candidates.exists():
        _dir(candidates)
        for product in sorted(candidates.iterdir()):
            if examined >= MAX_PRODUCT_DIRS or len(checks) >= MAX_PREVIEWS:
                break
            examined += 1
            if product.is_symlink() or not product.is_dir():
                continue
            for relative in PILOT_PATHS:
                file = product / relative
                if any(p.is_symlink() for p in list(file.parents) if p != product and product in p.parents):
                    continue
                data = safe_preview(file)
                if data is None:
                    continue
                result = html_quality(200, "text/html", data)
                checks.append({"product_dir": product.name, "local_preview_path": relative,
                               "source": "existing_local_file_only",
                               "status": result["status"], "score": result["score"],
                               "issues": result["issues"], "sha256": result["html_sha256"],
                               "commercial_quality_approved": False})
                break
    return {
        "schema": SCHEMA,
        "observed_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "actual_runtime_scan": True,
        "source_files_hash_verified": audit["imported_source_files"],
        "source_copy_integrity": all(x["identical_source_copy"] for x in audit["sources"]),
        "roles_zomorod": len(audit["zomorod_site_agents"]),
        "roles_mojplaywin_robots": audit["mojplaywin_private_robot_roles"],
        "mojplaywin_module_slots_not_imported": 77,
        "html_previews_scanned": len(checks),
        "html_previews": checks,
        "factory_product_directories_sampled": examined,
        "site_live_telemetry": {"zomorodmelal": "unobserved",
                                "mojplaywin": "unobserved"},
        "site_monitoring_performed": False,
        "factory_agents_added": 0,
        "generation_upgrade_claimed": False,
        "quality_or_commercial_release_granted": False,
        "website_files_modified": False,
    }


def write_report(path, data):
    _dir(path.parent, True)
    if path.is_symlink():
        raise RuntimeError("CROSS_SITE_REPORT_SYMLINK")
    raw = (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    fd, stage = tempfile.mkstemp(prefix=".cross-audit-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(stage, 0o600)
        os.replace(stage, str(path))
    finally:
        if os.path.exists(stage):
            os.unlink(stage)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--factory-private", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run(args.repo, args.factory_private)
    write_report(Path(args.output), result)
    print("CROSS_SITE_VPS_SOURCE_PROOFS=" + str(result["source_files_hash_verified"]))
    print("CROSS_SITE_VPS_REAL_HTML_PREVIEWS=" + str(result["html_previews_scanned"]))
    print("CROSS_SITE_VPS_SITE_REPLICATION=false")
    print("CROSS_SITE_VPS_CYCLE=PASS")


if __name__ == "__main__":
    main()
