#!/usr/bin/env python3
"""Strict private QC1000 triage of all agricultural product candidates.

This is an independent *mechanical* inspector, not an invented expert review.
Every rejected artifact is routed to an immutable, version-bound rework ticket.
A scientific or commercial 1000/1000 pass requires separately authenticated
independent domain reviews. No public publishing or approval in this worker.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import zipfile

SCHEMA = "saeit.factory.agri200.strict-qc1000.v1"
REWORK_SCHEMA = "saeit.factory.agri200.qc1000-rework.v1"
NAME = re.compile(r"WO-[0-9]{8}--r[0-9]{3}\.json\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
REQUIRED = frozenset(("README.md", "index.html", "fa-IR.md",
                      "en-US.md", "sources.json", "integrity.json"))
MAX_ZIP = 12_000_000
MAX_FILE = 700_000


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dependency(path, label):
    p = Path(path)
    if not p.is_file() or p.is_symlink():
        raise RuntimeError("STRICT_QC_UNSAFE_DEPENDENCY")
    spec = importlib.util.spec_from_file_location(label, str(p))
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def criteria(path):
    p = Path(path)
    if not p.is_file() or p.is_symlink() or p.stat().st_size > 100_000:
        raise RuntimeError("STRICT_QC_UNSAFE_CRITERIA")
    cat = json.loads(p.read_text(encoding="utf-8"))
    expected = ["Q%03d" % i for i in range(1, 101)]
    groups = cat.get("groups")
    if (cat.get("schema") != "saeit.factory.quality-100-groups.v2"
            or cat.get("total_points") != 1000
            or cat.get("group_count") != 100
            or cat.get("critical_defects_allowed") != 0
            or cat.get("independent_specialist_verification_required") is not True
            or not isinstance(groups, dict) or list(groups) != expected):
        raise RuntimeError("STRICT_QC_CATALOG_NOT_1000")
    for key, value in groups.items():
        if (not isinstance(value, dict) or value.get("maximum_points") != 10
                or not isinstance(value.get("name"), str)
                or not value["name"]):
            raise RuntimeError("STRICT_QC_BAD_CRITERION:" + key)
    return groups


def located(area, relative):
    if not isinstance(relative, str) or len(relative) > 240:
        raise RuntimeError("P0_INVALID_ARCHIVE_PATH")
    part = Path(relative)
    if part.is_absolute() or ".." in part.parts:
        raise RuntimeError("P0_ARCHIVE_TRAVERSAL")
    current = area
    for segment in part.parts:
        current = current / segment
        if current.is_symlink():
            raise RuntimeError("P0_ARCHIVE_SYMLINK")
    if area not in current.parents or not current.is_file():
        raise RuntimeError("P0_ARCHIVE_MISSING")
    if not 0 < current.stat().st_size <= MAX_ZIP:
        raise RuntimeError("P0_ARCHIVE_SIZE_INVALID")
    return current


def inspect_archive(area, name, receipt, manifest, lib):
    problems = []
    signals = {}
    if receipt is None:
        return ["P0_DOWNLOADABLE_CANDIDATE_NOT_BUILT"], signals
    if (receipt.get("order_id") != manifest.get("order_id")
            or receipt.get("stage5_manifest_sha256") != lib.digest(manifest)
            or receipt.get("ready_for_paid_store") is not False
            or receipt.get("scientific_quality_certified") is not False
            or receipt.get("public_distribution_allowed") is not False
            or receipt.get("technical_package_complete") is not True):
        return ["P0_RECEIPT_IDENTITY_OR_RELEASE_GUARD_INVALID"], signals
    try:
        archive = located(area, receipt.get("archive_relative_path"))
        raw = archive.read_bytes()
        digest = sha(raw)
        if not SHA.fullmatch(str(receipt.get("zip_sha256"))) or digest != receipt["zip_sha256"]:
            raise RuntimeError("P0_ARCHIVE_SHA256_MISMATCH")
        if receipt.get("zip_bytes") != len(raw):
            raise RuntimeError("P0_ARCHIVE_SIZE_RECEIPT_MISMATCH")
        root = "agri-" + name[:-5] + "/"
        payloads = {}
        with zipfile.ZipFile(archive) as z:
            members = z.infolist()
            if len(members) != len(REQUIRED) or z.testzip() is not None:
                raise RuntimeError("P0_ARCHIVE_BAD_CRC_OR_CONTENT_COUNT")
            for member in members:
                if (member.filename not in {root + x for x in REQUIRED}
                        or member.filename in payloads
                        or member.file_size <= 0 or member.file_size > MAX_FILE
                        or member.flag_bits & 0x1
                        or (member.external_attr >> 16) & 0o170000 not in (0, 0o100000)):
                    raise RuntimeError("P0_ARCHIVE_UNSAFE_MEMBER")
                payloads[member.filename] = z.read(member)
        file_hashes = {key: sha(payloads[root + key]) for key in REQUIRED}
        if file_hashes != receipt.get("file_hashes"):
            raise RuntimeError("P0_ZIP_CONTENT_RECEIPT_MISMATCH")
        integrity = json.loads(payloads[root + "integrity.json"])
        if (integrity.get("contents_sha256") != {
                key: file_hashes[key] for key in REQUIRED if key != "integrity.json"}
                or integrity.get("stage5_manifest_sha256") != lib.digest(manifest)
                or integrity.get("scientific_quality_certified") is not False
                or integrity.get("ready_for_paid_store") is not False
                or integrity.get("public_distribution_allowed") is not False):
            raise RuntimeError("P0_ZIP_INTERNAL_MANIFEST_INVALID")
        for locale in ("fa-IR", "en-US"):
            manuscript = payloads[root + locale + ".md"]
            if sha(manuscript) != manifest.get("manuscript_sha256", {}).get(locale):
                raise RuntimeError("P0_MANUSCRIPT_NOT_SAME_VERSION")
            text = manuscript.decode("utf-8")
            paragraphs = [re.sub(r"\s+", " ", p).strip().casefold()
                          for p in re.split(r"\n\s*\n", text)
                          if len(p.split()) >= 20]
            duplicate_fraction = ((len(paragraphs) - len(set(paragraphs))) /
                                  len(paragraphs)) if paragraphs else 1.0
            signals[locale] = {
                "words": len(text.split()),
                "substantial_paragraphs": len(paragraphs),
                "duplicate_paragraph_fraction": round(duplicate_fraction, 4),
                "sha256": file_hashes[locale + ".md"],
            }
            if len(text.split()) < 1000:
                problems.append("P0_" + locale + "_MANUSCRIPT_BELOW_MINIMUM")
            if duplicate_fraction > 0.35:
                problems.append("P0_" + locale + "_EXCESSIVE_REPEATED_PARAGRAPHS")
        references = json.loads(payloads[root + "sources.json"])
        if not isinstance(references, list) or len(references) < 4:
            problems.append("P0_INADEQUATE_BIBLIOGRAPHY")
        html = payloads[root + "index.html"].decode("utf-8")
        if "<html" not in html or "function render()" not in html:
            problems.append("P0_OFFLINE_NAVIGATOR_NOT_VERIFIED")
        signals["zip_sha256"] = digest
        signals["zip_entries"] = len(members)
        signals["internal_hashes_match"] = True
    except (RuntimeError, OSError, ValueError, TypeError, UnicodeError,
            KeyError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        problems.append("P0_INTEGRITY:" + str(exc)[:150])
    return problems, signals


def audit_one(area, name, lib, stage5, rubric):
    if NAME.fullmatch(name) is None:
        raise RuntimeError("STRICT_QC_INVALID_ORDER")
    stage5.verified_stage4(area, name, lib)
    manifest_file = area / "stage-05/completed-drafts" / name
    if manifest_file.is_symlink() or not manifest_file.is_file():
        raise RuntimeError("STRICT_QC_MANIFEST_NOT_READY")
    manifest = lib.read(manifest_file)
    lib.deny_approval(manifest)
    if (manifest.get("stage") != 5 or
            manifest.get("order_id") + "--r%03d.json" % manifest.get("revision", -1) != name):
        raise RuntimeError("STRICT_QC_STAGE5_IDENTITY_INVALID")
    receipt_file = area / "stage-05/downloadable-receipts" / name
    receipt = lib.read(receipt_file) if receipt_file.is_file() and not receipt_file.is_symlink() else None
    issues, measured = inspect_archive(area, name, receipt, manifest, lib)
    if manifest.get("draft_kind") == "original_bilingual_evidence_method_workbook":
        issues.append("P0_METHODS_ONLY_NOT_A_SUBJECT_SPECIFIC_SCIENTIFIC_PRODUCT")
    else:
        issues.append("P0_SUBJECT_SPECIFIC_CONTENT_NOT_INDEPENDENTLY_VERIFIED")
    issues += [
        "P0_ORIGINAL_SCIENTIFIC_FULLTEXT_NOT_INDEPENDENTLY_CHECKED",
        "P0_PRACTICAL_REPRODUCIBILITY_AND_LOCAL_SAFETY_NOT_CERTIFIED",
        "P0_INDEPENDENT_DOMAIN_EXPERT_NOT_SIGNED",
        "P0_INDEPENDENT_QC1000_ALL_CRITERIA_NOT_SIGNED",
        "P0_LEGAL_RIGHTS_AND_DISTRIBUTION_NOT_APPROVED",
    ]
    review_file = area / "stage-06/technical-preflight" / name
    if review_file.exists() and not review_file.is_symlink():
        previous = lib.read(review_file)
        if previous.get("stage5_manifest_sha256") != lib.digest(manifest):
            issues.append("P0_STAGE6_REVIEW_FOR_DIFFERENT_BUILD")
        else:
            issues.extend(previous.get("blocking_findings", []))
    issues = sorted(set(issues))
    technical_ok = bool(measured.get("internal_hashes_match")) and not any(
        x.startswith("P0_INTEGRITY:") or "INVALID" in x or
        "MISMATCH" in x for x in issues)
    result = {
        "schema": SCHEMA, "order_file": name,
        "order_id": manifest["order_id"], "revision": manifest["revision"],
        "stage5_manifest_sha256": lib.digest(manifest),
        "receipt_sha256": lib.digest(receipt) if receipt is not None else None,
        "artifact_sha256": measured.get("zip_sha256"),
        "technical_package_integrity_passed": technical_ok,
        "mechanically_measured": measured,
        "criteria_required": 100, "points_per_criterion": 10,
        "required_points": 1000, "p0_allowed": 0,
        "criteria": {key: {
            "name": item["name"], "max_points": 10,
            "independently_verified_points": None,
            "status": "NOT_INDEPENDENTLY_VERIFIED"
        } for key, item in rubric.items()},
        "total_independently_verified_points": None,
        "critical_findings": issues,
        "disposition": "QUARANTINE_INTEGRITY" if not technical_ok
                       else "RETURN_TO_PRODUCTION",
        "independent_specialist_certified": False,
        "quality1000_approved": False, "commercial_release": False,
        "public_distribution_allowed": False
    }
    # Rework refers to the exact quality audit and version, never to a mutable alias.
    actions = []
    if not technical_ok:
        actions.append("Investigate archived bytes, all SHA256 links and ZIP CRC; rebuild as a NEW immutable version.")
    actions += [
        "Replace methods-only drafts with genuinely topic-specific Persian and English manuals; record original full-text pages for every material claim.",
        "Perform independent domain accuracy, Iran/global applicability, safety and legal rights review; preserve authentic reviewer identity.",
        "Re-run all 100 non-compensatory criteria (10 points each) against the NEW artifact SHA; re-submit after corrections.",
    ]
    rework = {
        "schema": REWORK_SCHEMA, "order_file": name,
        "revision_under_review": manifest["revision"],
        "stage5_manifest_sha256": lib.digest(manifest),
        "strict_qc_report_sha256": lib.digest(result),
        "status": "RETURN_TO_STAGE5_OR_PRIOR_SOURCE_STAGE",
        "critical_findings": issues,
        "fixes": actions,
        "must_resubmit_new_artifact_and_repeat_strict_qc": True,
        "quality1000_approved": False, "commercial_release": False,
        "public_distribution_allowed": False,
    }
    audit_path = area / "stage-06/strict-qc1000" / name
    rework_path = area / "stage-05/strict-qc-rework" / name
    created = lib.once(audit_path, result)
    lib.once(rework_path, rework)
    return created, result["disposition"]


def execute(root, lib, stage5, rubric, batch=250):
    root = Path(root).expanduser().resolve()
    area = root / "production-instructions"
    queue = area / "stage-05/completed-drafts"
    if not area.is_dir() or queue.is_symlink() or not queue.is_dir():
        raise RuntimeError("STRICT_QC_PRIVATE_INPUT_MISSING")
    for sub in ("stage-06/strict-qc1000", "stage-05/strict-qc-rework",
                "stage-06/strict-qc-blocked"):
        lib.private_dir(area / sub)
    lock = area / ".strict-qc1000.lock"
    if lock.is_symlink():
        raise RuntimeError("STRICT_QC_LOCK_SYMLINK")
    with lock.open("a+b") as fd:
        os.fchmod(fd.fileno(), 0o600)
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
        names = sorted(x.name for x in queue.iterdir()
                       if x.is_file() and not x.is_symlink() and NAME.fullmatch(x.name))
        cursor_file = area / "stage-06/strict-qc-cursor.json"
        if cursor_file.is_symlink():
            raise RuntimeError("STRICT_QC_CURSOR_SYMLINK")
        cursor = lib.read(cursor_file) if cursor_file.is_file() else {
            "schema": "saeit.factory.agri200.strict-qc-cursor.v1", "next_index": 0}
        if (cursor.get("schema") != "saeit.factory.agri200.strict-qc-cursor.v1"
                or type(cursor.get("next_index")) is not int
                or cursor["next_index"] < 0):
            raise RuntimeError("STRICT_QC_CURSOR_INVALID")
        start = cursor["next_index"] % len(names) if names else 0
        chosen = [names[(start + i) % len(names)] for i in range(min(batch, len(names)))]
        newly_audited = quarantined = blocked = 0
        for name in chosen:
            try:
                created, disposition = audit_one(area, name, lib, stage5, rubric)
                newly_audited += int(created)
                quarantined += int(disposition == "QUARANTINE_INTEGRITY")
            except (RuntimeError, ValueError, TypeError, KeyError, OSError,
                    UnicodeError, zipfile.BadZipFile) as exc:
                blocked += 1
                lib.atomic(area / "stage-06/strict-qc-blocked" / name, {
                    "order_file": name, "error": type(exc).__name__ + ":" + str(exc)[:190],
                    "needs_rework": True, "quality1000_approved": False,
                    "commercial_release": False})
        lib.atomic(cursor_file, {
            "schema": "saeit.factory.agri200.strict-qc-cursor.v1",
            "next_index": (start + len(chosen)) % len(names) if names else 0})
        total = sum(1 for p in (area / "stage-06/strict-qc1000").iterdir()
                    if p.is_file() and NAME.fullmatch(p.name))
        report = {
            "stage5_products_seen": len(names),
            "inspected_this_run": len(chosen),
            "new_strict_qc1000_audits": newly_audited,
            "quarantined_during_this_run": quarantined,
            "audit_execution_blocked": blocked,
            "strict_qc1000_audits_total": total,
            "returned_to_rework_total": sum(
                1 for p in (area / "stage-05/strict-qc-rework").iterdir()
                if p.is_file() and NAME.fullmatch(p.name)),
            "independent_quality1000_approvals_created": 0,
            "public_products_released": 0,
            "sites_modified": False,
        }
        lib.atomic(area / "stage-06/strict-qc-status.json", report)
        return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--factory-private", required=True)
    p.add_argument("--stage34-worker", required=True)
    p.add_argument("--stage5-worker", required=True)
    p.add_argument("--criteria", required=True)
    p.add_argument("--batch", type=int, default=250)
    a = p.parse_args()
    if not 1 <= a.batch <= 1000:
        raise SystemExit("STRICT_QC_BATCH_RANGE")
    lib = dependency(a.stage34_worker, "strict_qc_stage34")
    stage5 = dependency(a.stage5_worker, "strict_qc_stage5")
    print(json.dumps(execute(a.factory_private, lib, stage5, criteria(a.criteria), a.batch),
                     ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("STRICT_QC_ERROR:" + type(exc).__name__ + ":" + str(exc)[:190],
              file=sys.stderr)
        raise SystemExit(1)
