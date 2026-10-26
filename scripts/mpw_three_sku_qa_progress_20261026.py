#!/usr/bin/env python3
"""Advance private three-SKU QA stages from hash-bound mechanical evidence only.

Writes immutable private progress receipts. It never inspects or emits product text,
changes rights, touches the store, or certifies professional quality1000.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

ROOT = Path("/home/githubops/factory-runtime/private/autonomous-product-cycle/design-intake/mpw-live-three-sku-qa")
IDS = (72, 225, 879)
HEX = re.compile(r"^[0-9a-f]{64}$")
SCHEMA = "saeit.mpw.private-quality1000-progress.v1"
TICKET_SCHEMA = "saeit.mpw.three-retail-artifact-qa1000-rework.v1"
AUDIT_SCHEMA = "saeit.mpw.private-content-audit.v1"
CANDIDATE_12VIEW_SCHEMA = "saeit.mpw.sku879.private-candidate-multiview-qa.v1"
SKU879_PRIVATE_CANDIDATE_SHA = "b6f171affcafcafc777279e70649dbebda87a0f7fd45389252423ffb0d1066f3"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_private(path, limit):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size <= 0 or path.stat().st_size > limit:
        raise RuntimeError("PRIVATE_QA_EVIDENCE_UNSAFE")
    return path.read_bytes()


def write_once(path, raw):
    path = Path(path)
    parent = path.parent
    if parent.is_symlink():
        raise RuntimeError("PRIVATE_QA_PROGRESS_DIRECTORY_UNSAFE")
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(parent, 0o700)
    if path.is_symlink():
        raise RuntimeError("PRIVATE_QA_PROGRESS_LINK")
    if path.exists():
        if read_private(path, 1000000) != raw:
            raise RuntimeError("PRIVATE_QA_PROGRESS_CONFLICT")
        return False
    fd, temp = tempfile.mkstemp(prefix=".qa-progress-", dir=str(parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, 0o600)
        try:
            os.link(temp, path)
            return True
        except FileExistsError:
            if path.is_symlink() or read_private(path, 1000000) != raw:
                raise RuntimeError("PRIVATE_QA_PROGRESS_CONFLICT")
            return False
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def candidate_browser_evidence(root, source_sha, candidate_sha=SKU879_PRIVATE_CANDIDATE_SHA):
    if not HEX.fullmatch(candidate_sha):
        raise RuntimeError("PRIVATE_QA_CANDIDATE_SHA_INVALID")
    folder = root / "quality1000-rework" / "879" / source_sha / "mobile-candidates"
    candidate = folder / (candidate_sha + ".zip")
    if not candidate.exists():
        return None
    if candidate.is_symlink() or not candidate.is_file() or candidate.stat().st_size <= 0:
        raise RuntimeError("PRIVATE_QA_CANDIDATE_FILE_UNSAFE")
    digest = hashlib.sha256()
    with candidate.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != candidate_sha:
        raise RuntimeError("PRIVATE_QA_CANDIDATE_HASH_MISMATCH")
    audits = folder / "browser-audits" / candidate_sha
    if audits.is_symlink() or not audits.is_dir():
        return None
    passing = []
    for path in sorted(audits.glob("*.json")):
        raw = read_private(path, 60000)
        report = json.loads(raw)
        checks = report.get("checks")
        if (path.stem != sha(raw) or
                report.get("schema") != CANDIDATE_12VIEW_SCHEMA or
                report.get("source_sha256") != source_sha or
                report.get("candidate_sha256") != candidate_sha or
                report.get("quality1000_verified") is not False or
                report.get("commercial_release_allowed") is not False or
                report.get("live_product_modified") is not False):
            raise RuntimeError("PRIVATE_QA_CANDIDATE_RECEIPT_IDENTITY_INVALID")
        if (report.get("browser_and_accessibility_smoke_passed") is True and
                isinstance(checks, dict) and len(checks) >= 10 and
                all(v is True for v in checks.values()) and
                len(report.get("viewports", [])) == 12):
            passing.append(sha(raw))
    if not passing:
        return None
    return {
        "candidate_sha256": candidate_sha,
        "browser_a11y_receipt_sha256": sorted(passing)[0],
        "real_browser_viewports_passed": 12,
        "browser_a11y_checks_passed": len(checks),
        "quality1000_verified": False,
        "commercial_release_allowed": False,
    }


def verified_progress(root, ident):
    receipt_dir = root / "review-requests" / str(ident)
    receipt_files = sorted(receipt_dir.glob("*.json"))
    if receipt_dir.is_symlink() or len(receipt_files) != 1:
        raise RuntimeError("PRIVATE_QA_RECEIPT_COUNT_INVALID")
    receipt_path = receipt_files[0]
    receipt = json.loads(read_private(receipt_path, 20000))
    digest = receipt.get("copy_sha256")
    if (not isinstance(digest, str) or not HEX.fullmatch(digest) or receipt_path.stem != digest
            or receipt.get("product_id") != ident or receipt.get("original_sha256") != digest):
        raise RuntimeError("PRIVATE_QA_RECEIPT_HASH_INVALID")
    copy_path = root / "copies" / str(ident) / (digest + ".bin")
    copied_bytes = read_private(copy_path, 1000000000)
    if sha(copied_bytes) != digest:
        raise RuntimeError("PRIVATE_QA_COPY_BYTES_HASH_MISMATCH")
    ticket_dir = root / "quality1000-rework" / str(ident) / digest
    ticket_files = sorted(ticket_dir.glob("*.json"))
    if ticket_dir.is_symlink() or not ticket_files:
        raise RuntimeError("PRIVATE_QA_BASE_TICKET_INVALID")
    ticket_hashes = []
    for ticket_path in ticket_files:
        ticket_bytes = read_private(ticket_path, 1000000)
        ticket = json.loads(ticket_bytes)
        if (ticket.get("schema") != TICKET_SCHEMA or ticket.get("product_id") != ident
                or ticket.get("source_file_sha256") != digest):
            raise RuntimeError("PRIVATE_QA_BASE_TICKET_IDENTITY_INVALID")
        if (ticket.get("legal_dossier_status") != "owner_confirmed_complete"
                or ticket.get("legal_execution_status") != "active"
                or ticket.get("legal_dossier_reopened") is not False):
            continue
        ticket_hashes.append(sha(ticket_bytes))
    if not ticket_hashes:
        raise RuntimeError("PRIVATE_QA_CURRENT_ACTIVE_LEGAL_TICKET_MISSING")
    ticket_hashes.sort()
    audit_dir = ticket_dir / "content-audits"
    audit_files = sorted(audit_dir.glob("*.json"))
    if audit_dir.is_symlink() or not audit_files:
        raise RuntimeError("PRIVATE_QA_AUDIT_REPORT_INVALID")
    passing_audits = []
    for audit_path in audit_files:
        audit_bytes_candidate = read_private(audit_path, 5000000)
        audit_candidate = json.loads(audit_bytes_candidate)
        if (audit_candidate.get("schema") != AUDIT_SCHEMA or audit_candidate.get("sku") != ident
                or audit_candidate.get("source_sha256") != digest
                or audit_candidate.get("professional_quality_score") is not None
                or audit_candidate.get("quality1000_verified") is not False
                or not isinstance(audit_candidate.get("measured_artifact"), dict)
                or audit_candidate["measured_artifact"].get("sha256") != digest):
            raise RuntimeError("PRIVATE_QA_AUDIT_IDENTITY_INVALID")
        measured_candidate = audit_candidate["measured_artifact"]
        checks_candidate = measured_candidate.get("checks")
        if (not isinstance(checks_candidate, dict) or not checks_candidate
                or not all(value is True for value in checks_candidate.values())):
            continue
        if ident in (72, 225):
            visual_candidate = measured_candidate.get("visual_render")
            expected_pages = 415 if ident == 72 else 40
            if (not isinstance(visual_candidate, dict)
                    or visual_candidate.get("rendered_page_count") != expected_pages
                    or visual_candidate.get("page_count_matches") is not True
                    or visual_candidate.get("render_failure") is not None
                    or visual_candidate.get("near_blank_page_numbers")
                    or visual_candidate.get("pages_with_color_signal", 0) <= 0):
                continue
            action_candidate = "FULL_PDF_RENDER_AND_MECHANICAL_CHECKS_PASSED"
            metrics_candidate = {
                "pages_rendered": expected_pages,
                "pages_with_color_signal": visual_candidate["pages_with_color_signal"],
                "near_blank_page_count": len(visual_candidate.get("near_blank_page_numbers", [])),
            }
        else:
            action_candidate = "ZIP_INTEGRITY_AND_STATIC_ACCESSIBILITY_CHECKS_PASSED"
            metrics_candidate = {"zip_checks_passed": len(checks_candidate)}
        passing_audits.append((audit_bytes_candidate, audit_candidate, action_candidate, metrics_candidate))
    if not passing_audits:
        raise RuntimeError("PRIVATE_QA_NO_PASSING_AUDIT_FOR_SOURCE_HASH")
    passing_audits.sort(key=lambda item: sha(item[0]))
    audit_bytes, audit, mechanical_action, visual_metrics = passing_audits[0]
    audit_hashes = sorted({sha(item[0]) for item in passing_audits})
    evidence = {
        "schema": SCHEMA,
        "product_id": ident,
        "source_sha256": digest,
        "base_rework_ticket_sha256": ticket_hashes[0],
        "base_rework_ticket_sha256s": ticket_hashes,
        "technical_audit_sha256": audit_hashes[0],
        "technical_audit_sha256s": audit_hashes,
        "mechanical_stage": mechanical_action,
        "mechanical_evidence": visual_metrics,
        "legal_dossier_status": "owner_confirmed_complete",
        "legal_execution_status": "active",
        "legal_dossier_reopened": False,
        "professional_quality_score": None,
        "quality1000_verified": False,
        "commercial_release_allowed": False,
        "live_product_modified": False,
        "completed_next_operation": "private mechanical QA evidence reconciled to exact source hash",
        "next_private_operation": {
            72: "source-specific factual and citation review, then create a version-bound improved candidate",
            225: "story, child-appropriateness and illustration review, then create a version-bound improved candidate",
            879: "isolated responsive-browser, navigation, accessibility and security review, then create a version-bound improved website-kit candidate",
        }[ident],
    }
    if ident == 879:
        candidate = candidate_browser_evidence(root, digest)
        if candidate is not None:
            evidence["verified_private_responsive_candidate"] = candidate
            evidence["completed_next_operation"] = "independent 12-viewport browser and accessibility smoke QA passed for private candidate"
            evidence["next_private_operation"] = "professional visual/content review, real navigation and security review before any commercial release"
    raw = (json.dumps(evidence, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    evidence_hash = sha(raw)
    output = ticket_dir / "progress" / (evidence_hash + ".json")
    created = write_once(output, raw)
    return {"sku": ident, "source_sha256": digest, "progress_sha256": evidence_hash,
            "mechanical_stage": mechanical_action, "progress_receipt_created": created,
            "quality1000_verified": False}


def run(root=ROOT):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("PRIVATE_QA_ROOT_MISSING")
    rows = [verified_progress(root, ident) for ident in IDS]
    print("MPW_PRIVATE_QA_PROGRESS_ADVANCED=" + json.dumps(rows, sort_keys=True))
    print("MPW_LEGAL_DOSSIER_REOPENED=0;MPW_LIVE_PRODUCT_MUTATIONS=0;MPW_QUALITY1000_CERTIFIED=0")
    return rows


if __name__ == "__main__":
    run()
