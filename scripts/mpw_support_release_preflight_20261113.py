#!/usr/bin/env python3
"""Read-only, fail-closed MojPlayWin support release source preflight.

No network requests, server access, email, payment operations, or writes.
Pass means source integrity, NOT authorization or readiness to publish.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "quality/mpw_support_release_contract_20261113.json"


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def audit(root: Path = ROOT) -> dict:
    root = Path(root)
    problems = []
    document = json.loads((root / CONTRACT).read_text(encoding="utf-8"))
    expected_paths = {
        "core/templates/brands/mojplaywin/page.html",
        "core/templates/mojplaywin/footer.html",
        "core/templates/mojplaywin/store.html",
        "core/templates/mojplaywin/theme.html",
        "mpw_revenue_20261020/earn/inquiry.php",
        "services/mpw_trx_guest_commerce.py",
        "tests/test_mpw_support_email_contract_20261113.py",
    }
    entries = document.get("files", [])
    actual_paths = [entry.get("path", "") for entry in entries]
    if len(actual_paths) != 7 or set(actual_paths) != expected_paths:
        problems.append("unexpected_file_inventory")
    if document.get("deployment_authorized") is not False:
        problems.append("authorization_must_remain_false")
    if document.get("operational_mode") != "READ_ONLY_SOURCE_PREFLIGHT":
        problems.append("preflight_must_remain_read_only")

    checked = 0
    pending_host_baselines = []
    for entry in entries:
        path = entry.get("path", "")
        if path not in expected_paths or path.startswith("/") or ".." in Path(path).parts:
            problems.append("unsafe_or_unexpected_path:" + path)
            continue
        source = root / path
        if not source.is_file() or source.is_symlink():
            problems.append("missing_or_symlink:" + path)
            continue
        content = source.read_bytes()
        if git_blob_sha(content) != entry.get("source_git_blob_sha"):
            problems.append("source_blob_mismatch:" + path)
        text = content.decode("utf-8")
        for marker in entry.get("markers", []):
            if marker not in text:
                problems.append("missing_source_marker:" + path + ":" + marker)
        checked += 1
        target = entry.get("production_target_hint")
        if entry.get("role") == "source-tests":
            if target is not None:
                problems.append("tests_must_not_be_deployed")
        else:
            if not isinstance(target, str) or not target.startswith("/home/zomorod2/"):
                problems.append("unverified_target_shape:" + path)
            if entry.get("production_target_verified") is not True or not entry.get("expected_live_sha256"):
                pending_host_baselines.append(path)

    workflows = document["workflows"]
    try:
        main_workflow = (root / workflows["main_django"]).read_text(encoding="utf-8")
        guest_workflow = (root / workflows["guest_checkout"]).read_text(encoding="utf-8")
        legacy_workflow = (root / workflows["legacy_content"]).read_text(encoding="utf-8")
        php_workflow = (root / workflows["inquiry_php"]).read_text(encoding="utf-8")
        guide_workflow = (root / workflows["guide_links"]).read_text(encoding="utf-8")
        if "core/templates/mojplaywin/**" not in main_workflow:
            problems.append("main_template_deploy_trigger_missing")
        if "workflow_dispatch:" not in guest_workflow:
            problems.append("guest_release_manual_gate_missing")
        if "if: ${{ false }}" not in legacy_workflow:
            problems.append("legacy_safety_lock_changed")
        if "mpw_revenue_20261020/earn/inquiry.php" not in php_workflow:
            problems.append("inquiry_auto_deploy_trigger_missing")
        if "core/templates/brands/mojplaywin/page.html" not in guide_workflow:
            problems.append("legacy_page_secondary_trigger_missing")
    except (OSError, KeyError) as exc:
        problems.append("release_workflow_unavailable:" + type(exc).__name__)

    return {
        "release_id": document.get("release_id"),
        "source_preflight_passed": not problems,
        "source_files_checked": checked,
        "source_problems": problems,
        "production_deployment_authorized": False,
        "production_ready": False,
        "host_baselines_pending": pending_host_baselines,
        "public_pages_verified": 0,
        "scope": "Source checks only: not a deployment or a live customer test.",
    }


if __name__ == "__main__":
    report = audit()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    raise SystemExit(0 if report["source_preflight_passed"] else 1)
