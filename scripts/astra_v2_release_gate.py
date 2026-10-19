#!/usr/bin/env python3
"""Read-only, fail-closed evidence gate for the three private Astra V2 prototypes.

Never sets retail prices, grades unknown domain quality, triggers payment or
publishes a product.  All reads are scoped to the private QA product directory,
its read-only SQLite queue and exact allowlisted source files. No network calls.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import zipfile

MAX_SOURCE_BYTES = 2_000_000
MAX_ARCHIVE_BYTES = 25_000_000
MAX_MANIFEST_BYTES = 128_000
SOURCE_FAMILIES = {
    "orchard_decision_audit_v2": (
        "orchard_decision_audit",
        ("decision_audit.py", "serve_local.py", "app.js", "index.html",
         "style.css", "example_synthetic.json", "README.md", "self_test.py")),
    "farm_procurement_audit_v1": (
        "farm_procurement_audit",
        ("procurement_audit.py", "render_report.py", "example_synthetic.json",
         "self_test.py", "README.md")),
    "farm_water_land_margin_audit_v1": (
        "farm_water_land_margin_audit",
        ("water_margin_audit.py", "render_report.py", "example_synthetic.json",
         "self_test.py", "README.md")),
}
MANDATORY_FALSE = (
    "sale_ready", "commercial_product", "owner_publication_approval",
    "public_deployment_allowed", "real_payment_allowed",
    "qualified_market_opportunity", "evidence_of_willingness_to_pay",
    "independent_domain_review", "ux_user_study", "rights_and_support_review",
)
RESEARCH_WORK = (
    "VERIFY_BUYER_PROBLEM_AND_WILLINGNESS_WITH_REAL_PEOPLE",
    "COMPARE_USEFULNESS_AGAINST_FREE_COMPETITORS",
    "OBTAIN_INDEPENDENT_DOMAIN_AND_ACCESSIBILITY_REVIEW",
    "CHECK_ORIGINAL_RIGHTS_LICENSE_SUPPORT_AND_MAINTENANCE",
    "DOCUMENT_REPRODUCIBLE_QUALITY_SCORE_AND_FAIR_PRICE_EVIDENCE",
    "REQUIRE_SEPARATE_STORE_AND_PAYMENT_RELEASE_CONTROLS",
)


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def directory(path):
    item = Path(path).expanduser()
    if item.is_symlink() or not item.is_dir():
        raise ValueError("missing or symlinked private directory")
    return item.resolve(strict=True)


def ordinary_file(path, limit):
    if path.is_symlink() or not path.is_file():
        raise ValueError("missing or symlinked file")
    if not (0 < path.stat().st_size <= limit):
        raise ValueError("file size outside safe bounds")
    return path.read_bytes()


def source_revision(source, builder, slug, filenames):
    folder = source / "product_prototypes" / slug
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("unavailable specialist source folder")
    parts = []
    raw = {}
    for name in filenames:
        data = ordinary_file(folder / name, MAX_SOURCE_BYTES)
        raw[name] = data
        parts.append(name.encode() + b"\x00" + sha(data).encode())
    return sha(builder.encode() + b"".join(parts)), raw


def verify_family(private, source, conn, builder, slug, filenames):
    row = {
        "builder": builder,
        "technical_artifact_integrity": "BLOCKED",
        "commercial_quality_score": None,
        "commercial_release_authorized": False,
        "evidence_of_customer_demand": False,
        "blocking_reason": None,
        "next_evidence_work": list(RESEARCH_WORK),
    }
    try:
        revision, source_bytes = source_revision(source, builder, slug, filenames)
        report_path = private / ("qa-" + revision + ".json")
        package_path = private / ("artifact-" + revision + ".zip")
        data = json.loads(ordinary_file(report_path, MAX_MANIFEST_BYTES))
        if not isinstance(data, dict):
            raise ValueError("invalid QA object")
        if (data.get("source_builder") != builder or
                data.get("product_slug") != slug or
                data.get("source_digest") != revision or
                data.get("included_files") != sorted(filenames)):
            raise ValueError("QA source identity mismatch")
        if (data.get("technical_regression") != "PASSED" or
                data.get("integrity_check") != "PASSED" or
                data.get("quality_score") is not None or
                any(data.get(key) is not False for key in MANDATORY_FALSE)):
            raise ValueError("untrusted or promoted commercial QA assertions")
        package = ordinary_file(package_path, MAX_ARCHIVE_BYTES)
        if data.get("artifact_sha256") != sha(package):
            raise ValueError("artifact hash does not match QA report")
        with zipfile.ZipFile(package_path, "r") as archive:
            members = archive.namelist()
            expected = [slug + "/" + name for name in filenames]
            if (len(members) != len(expected) or
                    set(members) != set(expected) or
                    archive.testzip() is not None):
                raise ValueError("archive membership or CRC invalid")
            for name, raw in source_bytes.items():
                member = archive.getinfo(slug + "/" + name)
                if member.file_size != len(raw) or archive.read(member) != raw:
                    raise ValueError("packaged content does not match source")
        records = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE builder=? AND stage=? AND artifact_sha=?",
            (builder, "PRIVATE_QA_PASSED", sha(package))).fetchone()[0]
        if records < 1:
            raise ValueError("no matching accepted private queue record")
        row["technical_artifact_integrity"] = "VERIFIED"
        row["blocking_reason"] = "COMMERCIAL_ATTESTATIONS_NOT_PRESENT"
    except (OSError, ValueError, TypeError, KeyError, zipfile.BadZipFile,
            zipfile.LargeZipFile, sqlite3.Error):
        row["blocking_reason"] = "TECHNICAL_SOURCE_MANIFEST_ARCHIVE_OR_QUEUE_CHECK_FAILED"
    return row


def evaluate(private_path, source_path):
    private = directory(private_path)
    source = directory(source_path)
    db = private / "queue.sqlite3"
    if db.is_symlink() or not db.is_file():
        raise ValueError("missing or symlinked private queue database")
    with sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True, timeout=10) as conn:
        conn.execute("PRAGMA query_only=ON")
        results = [
            verify_family(private, source, conn, builder, slug, files)
            for builder, (slug, files) in SOURCE_FAMILIES.items()
        ]
    count = sum(p["technical_artifact_integrity"] == "VERIFIED" for p in results)
    return {
        "schema_version": 1,
        "audit_type": "read_only_private_release_gap",
        "network_requests": 0,
        "factory_mutations": 0,
        "public_site_mutations": 0,
        "payment_attempts": 0,
        "verified_private_technical_families": count,
        "expected_private_families": len(SOURCE_FAMILIES),
        "commercially_qualified_products": 0,
        "release_readiness": "BLOCKED_INDEPENDENT_EVIDENCE_REQUIRED",
        "technical_integrity_gate": "PASS" if count == len(SOURCE_FAMILIES) else "FAIL",
        "families": results,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--private-root", required=True)
    ap.add_argument("--active-source", required=True)
    ap.add_argument("--strict-technical", action="store_true")
    args = ap.parse_args(argv)
    report = evaluate(args.private_root, args.active_source)
    print(json.dumps(report, sort_keys=True, indent=2))
    print("ASTRA_PRIVATE_TECHNICAL_FAMILIES=" +
          str(report["verified_private_technical_families"]), file=sys.stderr)
    print("ASTRA_COMMERCIAL_PRODUCTS_VERIFIED=0", file=sys.stderr)
    if args.strict_technical and report["technical_integrity_gate"] != "PASS":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
