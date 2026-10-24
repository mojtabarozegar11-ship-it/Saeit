#!/usr/bin/env python3
"""Record the owner's rejection of 184 real private Stage-5 archives, without rewriting them.

This is an immutable, content-hash-bound RETURN FOR REWORK decision, not a
scientific specialist attestation or a claim that rewritten goods now exist.
The existing VPS-local Stage-5/6 workers consume their own QC rework tickets.
"""
import argparse
from collections import Counter
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import zipfile

SCHEMA = "saeit.factory.owner-reject184.v1"
NAME = re.compile(r"WO-[0-9]{8}--r[0-9]{3}\.json\Z")
EXPECTED = 184
REASONS = ["METHODS_ONLY_NOT_SUBJECT_SPECIFIC", "FA_SUBSTANTIAL_PARAGRAPHS_REPEATED",
           "EN_SUBSTANTIAL_PARAGRAPHS_REPEATED"]


def require(condition, code):
    if not condition:
        raise ValueError(code)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def read_json(path):
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size < 2_000_000,
            "UNSAFE_OR_MISSING_JSON")
    return json.loads(path.read_text(encoding="utf-8"))


def safe_archive(area, value):
    require(isinstance(value, str) and 0 < len(value) < 240, "BAD_ARCHIVE_RELATIVE_PATH")
    relative = Path(value)
    require(not relative.is_absolute() and ".." not in relative.parts, "TRAVERSAL")
    target = area
    for part in relative.parts:
        target = target / part
        require(not target.is_symlink(), "ARCHIVE_SYMLINK")
    require(target.is_file() and 0 < target.stat().st_size <= 12_000_000,
            "ARCHIVE_NOT_A_SAFE_FILE")
    return target


def duplication(text):
    paragraphs = [re.sub(r"\s+", " ", p).strip().casefold()
                  for p in re.split(r"\n\s*\n", text) if len(p.split()) >= 20]
    return round((len(paragraphs) - len(set(paragraphs))) / len(paragraphs), 5) if paragraphs else 1.0


def inspect_one(area, name):
    require(NAME.fullmatch(name) is not None, "INVALID_ORDER_FILENAME")
    receipt_path = area / "stage-05/downloadable-receipts" / name
    manifest_path = area / "stage-05/completed-drafts" / name
    rec, man = read_json(receipt_path), read_json(manifest_path)
    require(rec.get("order_id") == man.get("order_id")
            and rec.get("stage5_manifest_sha256") == sha(canonical(man).rstrip(b"\n")),
            "ORIGINAL_MANIFEST_MISMATCH")
    require(man.get("draft_kind") == "original_bilingual_evidence_method_workbook",
            "REJECTED_COHORT_CHANGED_KIND")
    require(rec.get("scientific_quality_certified") is False
            and rec.get("ready_for_paid_store") is False
            and rec.get("public_distribution_allowed") is False,
            "RELEASE_FLAGS_NOT_FAIL_CLOSED")
    archive_path = safe_archive(area, rec.get("archive_relative_path"))
    raw = archive_path.read_bytes()
    require(sha(raw) == rec.get("zip_sha256") and len(raw) == rec.get("zip_bytes"),
            "ORIGINAL_ARCHIVE_INTEGRITY")
    root = "agri-" + name[:-5] + "/"
    expected = {root + x for x in
                ("README.md", "index.html", "fa-IR.md", "en-US.md", "sources.json", "integrity.json")}
    with zipfile.ZipFile(archive_path) as z:
        members = z.infolist()
        require(len(members) == 6 and {x.filename for x in members} == expected,
                "ORIGINAL_ZIP_MEMBERS_CHANGED")
        require(z.testzip() is None and all(x.file_size <= 700000 and
                not (x.flag_bits & 1) for x in members), "ORIGINAL_ZIP_UNSAFE")
        fa, en = [z.read(root + loc + ".md").decode("utf8") for loc in ("fa-IR", "en-US")]
    fractions = {"fa-IR": duplication(fa), "en-US": duplication(en)}
    require(all(v > 0.35 for v in fractions.values()), "REJECTED_COHORT_REQUIRES_REAUDIT")
    strict = area / "stage-05/strict-qc-rework" / name
    substantive = area / "stage-05/substantive-rework-inbox" / name
    strict_ready = strict.is_file() and not strict.is_symlink() and (
        read_json(strict).get("must_resubmit_new_artifact_and_repeat_strict_qc") is True)
    substantive_ready = substantive.is_file() and not substantive.is_symlink()
    return {
        "schema": SCHEMA, "order_file": name, "order_id": rec["order_id"],
        "owner_decision": "REJECT_RETURN_TO_STAGE5_REWORK",
        "scope": "CURRENT_PRIVATE_R001_ARCHIVE_ONLY",
        "original_archive_sha256": sha(raw),
        "original_receipt_sha256": sha(receipt_path.read_bytes()),
        "original_stage5_manifest_sha256": sha(manifest_path.read_bytes()),
        "observed_duplicate_fraction": fractions,
        "critical_findings": REASONS,
        "existing_strict_qc_rework_route": strict_ready,
        "existing_substantive_rework_route": substantive_ready,
        "rework_required": True,
        "source_verified_new_content_and_new_archive_hash_required": True,
        "must_resubmit_new_revision_and_repeat_measured_qc": True,
        "old_artifact_preserved": True,
        "owner_policy_approval_is_not_independent_expert_review": True,
        "expert_review_completed": False,
        "quality1000_approved": False,
        "public_distribution_allowed": False,
        "commercial_release": False,
    }


def inspect(root, expected=EXPECTED):
    area = Path(root).resolve() / "production-instructions"
    require(area.is_dir() and not area.is_symlink(), "FACTORY_ROOT_UNSAFE")
    receipts = area / "stage-05/downloadable-receipts"
    require(receipts.is_dir() and not receipts.is_symlink(), "RECEIPT_DIRECTORY_UNSAFE")
    names = sorted(p.name for p in receipts.iterdir()
                   if p.is_file() and not p.is_symlink() and NAME.fullmatch(p.name))
    require(len(names) == expected and len(set(names)) == expected,
            "COHORT_COUNT_CHANGED_REAUDIT_BEFORE_WRITE")
    packets = [inspect_one(area, name) for name in names]
    return area, packets


def execute(root, *, expected=EXPECTED, dry_run=False):
    area = Path(root).resolve() / "production-instructions"
    lock = area / ".owner-rework-184.lock"
    require(not lock.is_symlink(), "UNSAFE_OWNER_LOCK")
    if dry_run:
        _, packets = inspect(root, expected)
        return summarize(packets, False)
    with lock.open("a+b") as fd:
        os.fchmod(fd.fileno(), 0o600)
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
        _, packets = inspect(root, expected)
        parent = area / "stage-05"
        dest = parent / "owner-rework-20261024"
        require(not parent.is_symlink() and not dest.is_symlink(), "UNSAFE_OWNER_DIR")
        if dest.exists():
            require(dest.is_dir(), "OWNER_DIR_IS_NOT_DIRECTORY")
            names = sorted(p.name for p in dest.iterdir() if p.is_file()
                           and not p.is_symlink() and NAME.fullmatch(p.name))
            require(len(names) == expected, "OWNER_REJECTION_PARTIAL_OR_UNKNOWN")
            for item in packets:
                require(read_json(dest / item["order_file"]) == item, "OWNER_REJECTION_CONFLICT")
            return summarize(packets, True)
        staging = Path(tempfile.mkdtemp(prefix=".owner-rework-stage-", dir=parent))
        os.chmod(staging, 0o700)
        try:
            for item in packets:
                path = staging / item["order_file"]
                with path.open("xb") as stream:
                    os.fchmod(stream.fileno(), 0o600)
                    stream.write(canonical(item))
                    stream.flush()
                    os.fsync(stream.fileno())
            os.replace(staging, dest)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        return summarize(packets, True)


def summarize(packets, persisted):
    found = Counter(("strict" if p["existing_strict_qc_rework_route"] else "missing_strict",
                     "substantive" if p["existing_substantive_rework_route"] else "missing_substantive")
                    for p in packets)
    return {"schema": SCHEMA, "owner_rejected_and_returned": len(packets) if persisted else 0,
            "preflight_checked": len(packets), "ledger_persisted": persisted,
            "routing_existing_strict": sum(p["existing_strict_qc_rework_route"] for p in packets),
            "routing_existing_substantive": sum(p["existing_substantive_rework_route"] for p in packets),
            "missing_routes_require_worker_repair": dict((str(k), v) for k, v in found.items()),
            "original_archives_modified": 0, "public_sites_modified": False,
            "quality1000_certifications": 0, "independent_specialist_reviews": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-private", required=True)
    parser.add_argument("--expected-count", type=int, default=EXPECTED)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(execute(args.factory_private, expected=args.expected_count,
                             dry_run=args.dry_run), sort_keys=True), flush=True)
