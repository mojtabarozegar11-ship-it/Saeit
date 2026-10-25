#!/usr/bin/env python3
"""Mechanical independent QC of source-grounded v003 revisions (fail closed).

Verifies revision identity, all bytes/cryptographic provenance, source IDs,
language coverage and non-duplicate substantial paragraphs. Cannot impersonate
a scientist, prove full-text accuracy, or grant commercial QC1000.
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

SCHEMA = "saeit.factory.agri200.revised-mechanical-qc.v1"
NAME = re.compile(r"WO-[0-9]{8}--r001\.json\Z")
REQUIRED = {"README.md", "index.html", "fa-IR.md",
            "en-US.md", "sources.json", "integrity.json"}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def module(path, label):
    p = Path(path)
    if not p.is_file() or p.is_symlink():
        raise RuntimeError("REVISED_QC_DEPENDENCY_UNSAFE")
    spec = importlib.util.spec_from_file_location(label, str(p))
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def safe_archive(area, relative):
    if not isinstance(relative, str) or len(relative) > 250:
        raise RuntimeError("REVISED_ARCHIVE_PATH_INVALID")
    item = Path(relative)
    if item.is_absolute() or ".." in item.parts:
        raise RuntimeError("REVISED_ARCHIVE_TRAVERSAL")
    current = area
    for part in item.parts:
        current = current / part
        if current.is_symlink():
            raise RuntimeError("REVISED_ARCHIVE_LINK")
    if area not in current.parents or not current.is_file() or not 0 < current.stat().st_size < 12_000_000:
        raise RuntimeError("REVISED_ARCHIVE_INVALID")
    return current


def check_one(area, name, lib, catalog):
    if not NAME.fullmatch(name):
        raise RuntimeError("REVISED_QC_ORDER_INVALID")
    report = lib.read(area / "stage-05/source-grounded-v003-manifests" / name)
    source = lib.read(area / "stage-05/completed-drafts" / name)
    ticket = lib.read(area / "stage-05/strict-qc-rework" / name)
    if (report.get("schema") != "saeit.factory.agri200.source-grounded-v003.v1"
            or report.get("source_revision") != 1 or report.get("artifact_revision") != 3
            or report.get("order_file") != name
            or report.get("order_id") != source.get("order_id")
            or report.get("original_stage5_sha256") != lib.digest(source)
            or report.get("strict_qc_rework_sha256") != lib.digest(ticket)
            or report.get("quality1000_approved") is not False
            or report.get("commercial_release") is not False
            or report.get("public_distribution_allowed") is not False):
        raise RuntimeError("REVISED_MANIFEST_PROVENANCE_FAILED")
    archive = safe_archive(area, report.get("archive_relative_path"))
    data = archive.read_bytes()
    if sha(data) != report.get("zip_sha256") or len(data) != report.get("zip_bytes"):
        raise RuntimeError("REVISED_ZIP_SHA_MISMATCH")
    base = "agri-" + name[:-5] + "-v003/"
    payloads = {}
    with zipfile.ZipFile(archive, "r") as z:
        if z.testzip() is not None or len(z.infolist()) != len(REQUIRED):
            raise RuntimeError("REVISED_ZIP_CRC")
        for part in z.infolist():
            filename = part.filename
            if (filename not in {base + x for x in REQUIRED}
                    or filename in payloads or part.file_size > 700_000
                    or part.file_size <= 0 or part.flag_bits & 1):
                raise RuntimeError("REVISED_ZIP_UNSAFE_MEMBER")
            payloads[filename] = z.read(part)
    if set(payloads) != {base + x for x in REQUIRED}:
        raise RuntimeError("REVISED_ZIP_MISSING_MEMBER")
    integrity = json.loads(payloads[base + "integrity.json"])
    if (integrity.get("schema") != report["schema"]
            or integrity.get("original_stage5_sha256") != lib.digest(source)
            or integrity.get("strict_qc_rework_sha256") != lib.digest(ticket)
            or integrity.get("revision") != 3
            or integrity.get("independent_qc1000_approved") is not False
            or integrity.get("public_distribution_allowed") is not False
            or integrity.get("file_sha256") != {
                key: sha(payloads[base + key]) for key in REQUIRED if key != "integrity.json"}):
        raise RuntimeError("REVISED_ZIP_MANIFEST_TAMPERED")
    issues = []
    measurements = {}
    for loc in ("fa-IR", "en-US"):
        raw = payloads[base + loc + ".md"]
        text = raw.decode("utf-8")
        if sha(raw) != report["manuscript_sha256"].get(loc):
            raise RuntimeError("REVISED_MANUSCRIPT_IDENTITY_INVALID")
        paragraphs = [re.sub(r"\s+", " ", p).casefold().strip()
                      for p in re.split(r"\n\s*\n", text) if len(p.split()) >= 20]
        repeats = (len(paragraphs) - len(set(paragraphs))) / len(paragraphs) if paragraphs else 1
        measurements[loc] = {"words": len(text.split()),
                              "substantial_paragraphs": len(paragraphs),
                              "duplicate_fraction": round(repeats, 5)}
        if len(text.split()) < 1200:
            issues.append("P0_" + loc + "_SHORT")
        if repeats > 0.1:
            issues.append("P0_" + loc + "_REPETITIVE")
        if text.count("## ") < 6:
            issues.append("P0_" + loc + "_NO_TOPIC_CHAPTERS")
    references = json.loads(payloads[base + "sources.json"])
    source_ids = {src.get("id") for src in references if isinstance(src, dict)}
    if len(source_ids) < 4 or source_ids != set(report.get("source_ids", [])):
        issues.append("P0_SOURCES_INCOMPLETE")
    html = payloads[base + "index.html"].decode("utf-8")
    if "<html" not in html or "manuscripts=" not in html or "textContent=" not in html:
        issues.append("P0_OFFLINE_EDITION_VIEWER_NOT_VERIFIED")
    # Repaired educational edition is not yet independently domain certified.
    issues += [
        "P0_PRIMARY_FULLTEXT_SCIENTIFIC_CHECK_PENDING",
        "P0_INDEPENDENT_SPECIALIST_REVIEW_PENDING",
        "P0_LOCAL_REGULATION_AND_FIELD_SAFETY_PENDING",
        "P0_QC1000_ALL_100_CRITERIA_UNVERIFIED",
    ]
    return {
        "schema": SCHEMA, "order_file": name, "revision": 3,
        "v003_manifest_sha256": lib.digest(report),
        "artifact_sha256": sha(data),
        "mechanical_integrity_pass": not any(x.startswith("P0_") and
            x not in {"P0_PRIMARY_FULLTEXT_SCIENTIFIC_CHECK_PENDING",
                      "P0_INDEPENDENT_SPECIALIST_REVIEW_PENDING",
                      "P0_LOCAL_REGULATION_AND_FIELD_SAFETY_PENDING",
                      "P0_QC1000_ALL_100_CRITERIA_UNVERIFIED"} for x in issues),
        "measurements": measurements, "critical_findings": sorted(issues),
        "rubric_criteria_required": 100, "rubric_points_required": 1000,
        "independent_quality1000_approved": False,
        "commercial_release": False, "public_distribution_allowed": False,
        "disposition": "RETURN_TO_SCIENTIFIC_REVIEW"
    }


def execute(root, lib, batch=250, only_order_id=None):
    if only_order_id is not None and (not isinstance(only_order_id,str)
                                   or re.fullmatch(r"WO-[0-9]{8}",only_order_id) is None):
        raise RuntimeError("REVISED_QC_TARGET_ORDER_INVALID")
    area = Path(root).resolve() / "production-instructions"
    inbox = area / "stage-05/source-grounded-v003-manifests"
    if inbox.is_symlink() or not inbox.is_dir():
        raise RuntimeError("REVISED_QC_INPUT_MISSING")
    for sub in ("stage-06/source-grounded-v003-qc", "stage-06/source-grounded-v003-qc-blocked"):
        lib.private_dir(area / sub)
    lock = area / ".source-grounded-v003-qc.lock"
    if lock.is_symlink():
        raise RuntimeError("REVISED_QC_LOCK_UNSAFE")
    with lock.open("a+b") as fd:
        os.fchmod(fd.fileno(), 0o600)
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
        names = sorted(p.name for p in inbox.iterdir()
                       if p.is_file() and not p.is_symlink() and NAME.fullmatch(p.name))
        if only_order_id is not None:
            names = [name for name in names if name.startswith(only_order_id+"--r")]
        passed_mechanical = errors = new = 0
        for name in names[:batch]:
            try:
                result = check_one(area, name, lib, None)
                passed_mechanical += int(result["mechanical_integrity_pass"])
                new += int(lib.once(area / "stage-06/source-grounded-v003-qc" / name, result))
            except (RuntimeError, OSError, ValueError, TypeError, KeyError, UnicodeError,
                    zipfile.BadZipFile) as exc:
                errors += 1
                lib.atomic(area / "stage-06/source-grounded-v003-qc-blocked" / name, {
                    "order_file": name, "issue": type(exc).__name__ + ":" + str(exc)[:160],
                    "quality1000_approved": False, "commercial_release": False})
        result = {"v003_candidate_editions_seen": len(names),
                  "v003_mechanical_integrity_pass": passed_mechanical,
                  "new_v003_qc_reports": new, "invalid_v003_editions": errors,
                  "independently_approved_1000": 0, "released_products": 0}
        lib.atomic(area / "stage-06/source-grounded-v003-qc-status.json", result)
        return result


if __name__ == "__main__":
    try:
        p = argparse.ArgumentParser()
        p.add_argument("--factory-private", required=True)
        p.add_argument("--stage34-worker", required=True)
        p.add_argument("--batch", type=int, default=250)
        p.add_argument("--only-order-id")
        a = p.parse_args()
        lib = module(a.stage34_worker, "revised_qc_stage34")
        print(json.dumps(execute(a.factory_private, lib, a.batch,
                                 only_order_id=a.only_order_id), sort_keys=True))
    except Exception as exc:
        print("REVISED_QC_ERROR:" + type(exc).__name__ + ":" + str(exc)[:170],
              file=sys.stderr)
        raise SystemExit(1)
