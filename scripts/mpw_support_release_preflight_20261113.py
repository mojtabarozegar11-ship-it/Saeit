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


# Candidate runtime file locations are not proven production targets.
EXPECTED_RUNTIME_SURFACES = {
    "static_store_fallback": {
        "public_route": "/store/",
        "candidate_active_file": "/home/zomorod2/mojplaywin.com/store/index.html",
        "source_of_hint": ".github/workflows/vps-store-identity-audit.yml",
        "source_anchor": 'cat > "$STORE/index.html" <<\'HTML\'',
        "evidence_level": "SOURCE_CANDIDATE_ONLY",
    },
    "dynamic_support_handler": {
        "public_route": "/support/",
        "candidate_active_file": "/home/zomorod2/Saeit-staging/core/brand_views.py",
        "source_of_hint": "scripts/mpw_purchase_recovery_copy_fix_20261024.py",
        "source_anchor": "core/brand_views.py",
        "evidence_level": "HISTORICAL_PATCH_TARGET_ONLY",
    },
}


def audit_runtime_surfaces(document: dict, root: Path) -> tuple[list[str], list[str]]:
    """Separate unverified runtime candidates from repo-owned release files.

    No host access, mutable secrets, incoming evidence or deployment side effects.
    Promoting a candidate to verified requires a separate authenticated audit.
    """
    problems: list[str] = []
    pending: list[str] = []
    surfaces = document.get("runtime_surfaces")
    if not isinstance(surfaces, list):
        return ["runtime_inventory_missing"], list(EXPECTED_RUNTIME_SURFACES)
    if len(surfaces) != len(EXPECTED_RUNTIME_SURFACES):
        problems.append("runtime_surface_count_mismatch")
    ids = [item.get("id") if isinstance(item, dict) else None for item in surfaces]
    if len(ids) != len(set(ids)) or set(ids) != set(EXPECTED_RUNTIME_SURFACES):
        problems.append("runtime_surface_identity_mismatch")
    for item in surfaces:
        if not isinstance(item, dict):
            problems.append("runtime_surface_not_object")
            continue
        name = item.get("id")
        if name not in EXPECTED_RUNTIME_SURFACES:
            problems.append("unexpected_runtime_surface")
            continue
        ref = EXPECTED_RUNTIME_SURFACES[name]
        for field, required in ref.items():
            if item.get(field) != required:
                problems.append("runtime_candidate_changed:" + name + ":" + field)
        if (item.get("active_file_verified") is not False
                or item.get("verified_live_sha256") is not None
                or item.get("verified_rollback") is not False):
            problems.append("unverified_runtime_claims_ready:" + name)
        else:
            pending.append(name)
        source = root / ref["source_of_hint"]
        if not source.is_file() or source.is_symlink():
            problems.append("runtime_hint_source_missing:" + name)
        elif ref["source_anchor"] not in source.read_text(encoding="utf-8"):
            problems.append("runtime_hint_anchor_missing:" + name)
    return problems, pending



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

    runtime_problems, runtime_pending = audit_runtime_surfaces(document, root)
    problems.extend(runtime_problems)

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

    # Deployment route coverage: main-site publisher does not own every source.
    release_routes = document.get("release_routes", {})
    expected_routes = {
        "core/templates/mojplaywin/footer.html": "main_site_push",
        "core/templates/mojplaywin/store.html": "main_site_push",
        "core/templates/mojplaywin/theme.html": "main_site_push",
        "core/templates/brands/mojplaywin/page.html": "legacy_safe_lock_no_guaranteed_publish",
        "mpw_revenue_20261020/earn/inquiry.php": "separate_php_inquiry_release",
        "services/mpw_trx_guest_commerce.py": "manual_guest_checkout_release",
        "tests/test_mpw_support_email_contract_20261113.py": "test_only_not_deployed",
    }
    if release_routes != expected_routes:
        problems.append("release_route_matrix_mismatch")
    try:
        publisher = (root / "scripts/deploy_mojplaywin_branding.py").read_text(encoding="utf-8")
        owned = publisher.split("OWNED_FILES = (", 1)[1].split("\n)", 1)[0]
        for file in (
            "core/templates/mojplaywin/footer.html",
            "core/templates/mojplaywin/store.html",
            "core/templates/mojplaywin/theme.html",
        ):
            if f'Path("{file}")' not in owned:
                problems.append("owned_release_file_missing:" + file)
        for file in (
            "core/templates/brands/mojplaywin/page.html",
            "services/mpw_trx_guest_commerce.py",
        ):
            if f'Path("{file}")' in owned:
                problems.append("unexpected_main_release_scope:" + file)
    except (OSError, IndexError) as exc:
        problems.append("publisher_scope_unavailable:" + type(exc).__name__)

    # Read-only SSH failed before authenticating; do not promote source checks
    # to proven production access or a live site availability claim.
    access = document.get("last_host_access_evidence") or {}
    expected_access = "RELAY_RETRIES_EXHAUSTED_AND_DIRECT_CPANEL_TIMEOUT"
    if (
        access.get("result") != expected_access
        or access.get("read_only_passenger_run_id") != 43454715777
        or access.get("private_relay_run_id") != 43457001017
        or access.get("pinned_host_keys_verified") is not True
        or access.get("ssh_authenticated") is not False
        or access.get("live_application_files_read") is not False
    ):
        problems.append("host_readback_evidence_unverified")

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
        "runtime_candidate_surfaces": len(EXPECTED_RUNTIME_SURFACES),
        "runtime_surfaces_pending": runtime_pending,
        "runtime_surfaces_verified": 0,
        "public_pages_verified": 0,
        "live_host_access_verified": False,
        "release_route_matrix": release_routes,
        "release_routes_needing_separate_publication": 3,
        "last_host_probe": access.get("result", "UNKNOWN"),
        "scope": "Source checks only: not a deployment or a live customer test.",
    }


if __name__ == "__main__":
    report = audit()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    raise SystemExit(0 if report["source_preflight_passed"] else 1)
