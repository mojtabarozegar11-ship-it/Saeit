#!/usr/bin/env python3
"""Owner's explicit REJECT_AND_REWORK verdict for every measured private article.
No publication, QC1000 award, file deletion, approval forgery, or cross-tenant I/O.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import zipfile

SCHEMA = "saeit.factory.owner-rework-184.v1"
NAME = re.compile(r"WO-[0-9]{8}--r[0-9]{3}\.json\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")
EXPECTED = 184
REWORK = "stage-05/managerial-content-rework-20261024"
RECEIPTS = "stage-05/downloadable-receipts"
MANIFESTS = "stage-05/completed-drafts"


def require(ok, error):
    if not ok:
        raise RuntimeError(error)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf8")


def regular(path, limit=200000):
    require(not path.is_symlink() and path.is_file(), "UNSAFE_OR_MISSING_INPUT")
    require(0 < path.stat().st_size <= limit, "INPUT_SIZE_INVALID")
    return path.read_bytes()


def within(area, relative):
    require(isinstance(relative, str) and 1 <= len(relative) <= 240,
            "UNSAFE_RELATIVE_PATH")
    item = Path(relative)
    require(not item.is_absolute() and ".." not in item.parts and
            len(item.parts) >= 2, "PATH_TRAVERSAL")
    path = area
    for part in item.parts:
        require(part not in (".", ""), "BAD_PATH_PART")
        path = path / part
        require(not path.is_symlink(), "SYMLINK_IN_ARCHIVE_PATH")
    require(area in path.parents, "OUT_OF_SCOPE")
    return path


def duplicate_rate(raw):
    text = raw.decode("utf-8")
    paragraphs = [re.sub(r"\s+", " ", item).strip().casefold()
                  for item in re.split(r"\n\s*\n", text)
                  if len(item.split()) >= 20]
    require(len(paragraphs) >= 10, "INSUFFICIENT_MANUSCRIPT")
    return round((len(paragraphs) - len(set(paragraphs))) / len(paragraphs), 4)


def validate(area, name):
    require(NAME.fullmatch(name), "INVALID_ARTIFACT_NAME")
    receipt_raw = regular(area / RECEIPTS / name)
    manifest_raw = regular(area / MANIFESTS / name)
    rec, man = json.loads(receipt_raw), json.loads(manifest_raw)
    for item in (rec, man):
        require(isinstance(item, dict), "BAD_DOCUMENT")
        require(item.get("quality1000_approved") is not True and
                item.get("commercial_release") is not True, "EXISTING_RELEASE_CONFLICT")
    require(rec.get("scientific_quality_certified") is False and
            rec.get("ready_for_paid_store") is False and
            rec.get("public_distribution_allowed") is False, "RELEASE_PROHIBITION_MISSING")
    require(man.get("draft_kind") == "original_bilingual_evidence_method_workbook",
            "NOT_THE_MEASURED_METHODS_ONLY_REVISION")
    require(man.get("order_id") == name.split("--r")[0] and
            rec.get("order_id") == man.get("order_id"), "ORDER_IDENTITY_MISMATCH")
    expected_sha = rec.get("zip_sha256")
    require(isinstance(expected_sha, str) and SHA.fullmatch(expected_sha),
            "ZIP_RECEIPT_SHA_MISSING")
    archive_path = within(area, rec.get("archive_relative_path"))
    raw = regular(archive_path, 12000000)
    require(digest(raw) == expected_sha and len(raw) == rec.get("zip_bytes"),
            "ARCHIVE_SHA_OR_SIZE_MISMATCH")
    metrics = {}
    try:
        with zipfile.ZipFile(archive_path) as archive:
            entries = archive.infolist()
            prefix = "agri-" + name[:-5] + "/"
            needed = {prefix + name for name in
                      ("README.md", "index.html", "fa-IR.md", "en-US.md",
                       "sources.json", "integrity.json")}
            require(len(entries) == 6 and {item.filename for item in entries} == needed,
                    "ARCHIVE_MEMBER_SET_CHANGED")
            require(archive.testzip() is None, "ARCHIVE_CRC_ERROR")
            for item in entries:
                require(not item.is_dir() and not (item.flag_bits & 1)
                        and item.file_size <= 700000 and
                        ((item.external_attr >> 16) & 0o170000) != 0o120000,
                        "UNSAFE_ARCHIVE_MEMBER")
            for locale in ("fa-IR", "en-US"):
                chapter = archive.read(prefix + locale + ".md")
                require(digest(chapter) == man.get("manuscript_sha256", {}).get(locale),
                        "MANUSCRIPT_HASH_DRIFT")
                rate = duplicate_rate(chapter)
                require(rate > 0.35, "ARTIFACT_DEFECT_NOT_REPRODUCED")
                metrics[locale] = rate
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as error:
        raise RuntimeError("ARCHIVE_NOT_READABLE") from error
    return {"schema": SCHEMA, "scope": "agri200-private-vps-only",
            "artifact_file": name, "order_id": man["order_id"],
            "revision": man.get("revision"),
            "owner_verdict": "REJECT_AND_RETURN_ALL_MEASURED_ARTIFACTS",
            "disposition": "RETURN_TO_STAGE5_SUBSTANTIVE_REWORK",
            "reason_codes": ["METHODS_ONLY_NOT_A_COMPLETE_PRODUCT",
                             "EXCESSIVE_REPEATED_PARAGRAPHS_IN_BOTH_LANGUAGES"],
            "duplicate_fraction_by_locale": metrics,
            "original_archive_sha256": expected_sha,
            "original_receipt_sha256": digest(receipt_raw),
            "original_manifest_sha256": digest(manifest_raw),
            "must_create_new_version": True,
            "must_repeat_all_real_qc1000_checks": True,
            "independent_specialist_approval_required": True,
            "quality1000_approved": False,
            "commercial_release": False,
            "public_distribution_allowed": False,
            "original_data_preserved": True}


def execute(private_root, expected=EXPECTED, *, write=True):
    root = Path(private_root)
    area = root / "production-instructions"
    require(root.is_dir() and not root.is_symlink() and
            area.is_dir() and not area.is_symlink(), "WRONG_FACTORY_ROOT")
    require(not (area / MANIFESTS).is_symlink() and
            (area / MANIFESTS).is_dir(), "UNSAFE_MANIFEST_DIRECTORY")
    folder = area / RECEIPTS
    require(folder.is_dir() and not folder.is_symlink(), "NO_PRIVATE_CANDIDATES")
    names = sorted(item.name for item in folder.iterdir() if
                   item.is_file() and not item.is_symlink() and NAME.fullmatch(item.name))
    require(len(names) == expected and len(set(names)) == expected,
            "MEASURED_ARTIFACT_COUNT_CHANGED")
    # Validate EVERY source and archive before creating ANY return ticket.
    tickets = [(name, validate(area, name)) for name in names]
    destination = area / REWORK
    if not write:
        return {"validated": len(tickets), "tickets_written": 0, "dry_run": True}
    require(not destination.is_symlink(), "REWORK_DIRECTORY_SYMLINK")
    if not destination.exists():
        destination.mkdir(mode=0o700)
    require(destination.is_dir() and not (destination.stat().st_mode & 0o077),
            "REWORK_DIRECTORY_NOT_PRIVATE")
    unexpected = [p.name for p in destination.iterdir()
                  if p.is_symlink() or not p.is_file() or p.name not in names]
    require(not unexpected, "FOREIGN_REWORK_TICKETS")
    written = 0
    for name, ticket in tickets:
        path = destination / name
        value = canonical(ticket)
        if path.exists():
            require(regular(path) == value, "CONFLICTING_IMMUTABLE_REWORK_TICKET")
            continue
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, "wb") as out:
            out.write(value)
            out.flush()
            os.fsync(out.fileno())
        written += 1
    for name, ticket in tickets:
        require(regular(destination / name) == canonical(ticket),
                "REWORK_READBACK_FAILED")
    return {"schema": SCHEMA, "scope": "agri200-private-vps-only",
            "validated_actual_original_archives": len(tickets),
            "managerial_returns_verified": len(tickets), "new_tickets": written,
            "held_from_publication": len(tickets), "quality1000_approved": 0,
            "original_archive_bytes_modified": 0, "public_sites_modified": False,
            "next_route": "stage5_reauthor_new_revision_then_independent_qc1000"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-private", required=True)
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(execute(args.factory_private, write=not args.audit_only),
                     ensure_ascii=False, sort_keys=True))
