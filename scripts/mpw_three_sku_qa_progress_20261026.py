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
    if audit_dir.is_symlink() or len(audit_files) != 1:
        raise RuntimeError("PRIVATE_QA_AUDIT_REPORT_INVALID")
    audit_bytes = read_private(audit_files[0], 5000000)
    audit = json.loads(audit_bytes)
    if (audit.get("schema") != AUDIT_SCHEMA or audit.get("sku") != ident
            or audit.get("source_sha256") != digest
            or audit.get("professional_quality_score") is not None
            or audit.get("quality1000_verified") is not False
            or not isinstance(audit.get("measured_artifact"), dict)
            or audit["measured_artifact"].get("sha256") != digest):
        raise RuntimeError("PRIVATE_QA_AUDIT_IDENTITY_INVALID")
    measured = audit.get("measured_artifact")
    checks = measured.get("checks") if isinstance(measured, dict) else None
    if not isinstance(checks, dict) or not checks or not all(value is True for value in checks.values()):
        raise RuntimeError("PRIVATE_QA_MECHANICAL_CHECKS_NOT_PASSED")

    if ident in (72, 225):
        visual = measured.get("visual_render")
        expected_pages = 415 if ident == 72 else 40
        if (not isinstance(visual, dict) or visual.get("rendered_page_count") != expected_pages
                or visual.get("page_count_matches") is not True or visual.get("render_failure") is not None
                or visual.get("near_blank_page_numbers") or visual.get("pages_with_color_signal", 0) <= 0):
            raise RuntimeError("PRIVATE_QA_FULL_PAGE_RENDER_NOT_VERIFIED")
        mechanical_action = "FULL_PDF_RENDER_AND_MECHANICAL_CHECKS_PASSED"
        visual_metrics = {
            "pages_rendered": expected_pages,
            "pages_with_color_signal": visual["pages_with_color_signal"],
            "near_blank_page_count": len(visual.get("near_blank_page_numbers", [])),
        }
    else:
        mechanical_action = "ZIP_INTEGRITY_AND_STATIC_ACCESSIBILITY_CHECKS_PASSED"
        visual_metrics = {"zip_checks_passed": len(checks)}

    evidence = {
        "schema": SCHEMA,
        "product_id": ident,
        "source_sha256": digest,
        "base_rework_ticket_sha256": ticket_hashes[0],
        "base_rework_ticket_sha256s": ticket_hashes,
        "technical_audit_sha256": sha(audit_bytes),
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
            879: "isolated browser gameplay and security review, then create a version-bound improved candidate",
        }[ident],
    }
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
