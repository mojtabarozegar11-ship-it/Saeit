#!/usr/bin/env python3
"""Actual evidence supplier for 100x10 quality obligations.

The automated supplier currently performs one real, scope-limited measurement:
Q068, integrity and CRC verification of a finished, hash-locked warehouse ZIP.
It assigns concrete *supplier roles* for all 100 criteria, but does not invent
connected third parties, empirical user tests, expert opinions or 1000 points.
No store, payments, approvals, or warehouse versions are modified.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import zipfile

SCHEMA = "saeit.factory.quality-evidence-supply.v1"
HEX = re.compile(r"^[a-f0-9]{64}$")
PRODUCT = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
ROLES = (
    ("market_benchmark_supplier", "current real competitor and market measurement", "independent market research required"),
    ("innovation_provenance_supplier", "original build history, novelty research, independently checked ownership", "prior-art and originality confirmation required"),
    ("engineering_test_supplier", "reproducible engineering, profiling and integration tests", "automated builds plus independent reproducibility"),
    ("domain_specialist_supplier", "scientific field observations and qualified discipline review", "externally authenticated domain expert and real data"),
    ("customer_research_supplier", "consenting genuine user tasks, outcomes and blind feedback", "real users and privacy-respecting recordings"),
    ("ux_accessibility_supplier", "multi-device sessions, accessibility findings and regressions", "real hardware and independent accessibility testing"),
    ("adversarial_qa_supplier", "fault, recovery, reproducibility and actual ZIP validation", "tool evidence plus independent adversarial review"),
    ("security_rights_supplier", "security assessment, chain of title and licence permission", "independent security/legal specialist"),
    ("commerce_operations_supplier", "actual permitted order, entitlement, support and delivery tests", "sandbox commerce plus owner-only release approval"),
    ("independent_review_supplier", "authenticated unbiased reviewers, repeatability and signed final verdict", "owner-pinned reviewer trust and external signatures"),
)
EXTERNAL_REQUIRED = {
    "market_benchmark_supplier", "domain_specialist_supplier",
    "customer_research_supplier", "security_rights_supplier",
    "independent_review_supplier",
}
MAX_PACKAGE = 25 * 1024 * 1024
MAX_MEMBERS = 100
MAX_UNPACKED = 40 * 1024 * 1024


def require(ok, code):
    if not ok:
        raise RuntimeError(code)


def hash_bytes(value):
    return hashlib.sha256(value).hexdigest()


def read_json(path, size=200000):
    p = Path(path)
    require(p.is_file() and not p.is_symlink() and 0 < p.stat().st_size <= size,
            "SUPPLIER_JSON_UNSAFE")
    doc = json.loads(p.read_text(encoding="utf8"))
    require(isinstance(doc, dict), "SUPPLIER_JSON_INVALID")
    return doc


def catalog(path):
    data = read_json(path)
    groups = data.get("groups")
    require(data.get("schema") == "saeit.factory.quality-100-groups.v2"
            and data.get("group_count") == 100
            and data.get("points_per_group") == 10
            and data.get("total_points") == 1000
            and isinstance(groups, dict)
            and list(groups) == ["Q%03d" % i for i in range(1, 101)],
            "SUPPLIER_CATALOG_CONTRACT_INVALID")
    require(all(isinstance(x.get("name"), str) and x.get("maximum_points") == 10
                and isinstance(x.get("quality_dimensions"), list)
                for x in groups.values()), "SUPPLIER_CATALOG_CRITERION_INVALID")
    return groups


def supplier_route(criterion, policy):
    n = int(criterion[1:])
    role, output, review = ROLES[(n - 1) // 10]
    return {
        "criterion_id": criterion,
        "criterion_name": policy["name"],
        "possible_supplier_role": role,
        "required_output": output,
        "independent_review_dependency": review,
        "person_or_company_contractually_connected": False,
        "supplier_identity_authenticated": False,
        "supplier_authorized_to_sign": False,
        "automated_evidence_executable_now": criterion == "Q068",
        "engine": ("scripts/factory_quality_evidence_supplier_v1.py"
                   if criterion == "Q068" else None),
        "required_evidence_state": "MEASURED_TECHNICAL_ONLY" if criterion == "Q068"
                                  else "AWAITING_REAL_SUPPLIER_WORK",
        "professional_points_awarded": None,
    }


def zip_proof(file, recipe):
    require(file.is_file() and not file.is_symlink() and
            0 < file.stat().st_size <= MAX_PACKAGE, "SUPPLIER_PACKAGE_UNSAFE")
    members = []
    total = 0
    with zipfile.ZipFile(str(file)) as archive:
        items = archive.infolist()
        require(0 < len(items) <= MAX_MEMBERS and archive.testzip() is None,
                "SUPPLIER_ZIP_CRC_FAILED")
        seen = set()
        for item in items:
            name = item.filename
            parts = name.split("/")
            require(name not in seen and not item.is_dir()
                    and not (item.flag_bits & 0x1)
                    and len(parts) >= 2 and parts[0] == recipe
                    and all(re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", p)
                            and p not in (".", "..") for p in parts)
                    and item.file_size <= MAX_UNPACKED
                    and (item.external_attr >> 16) & 0o170000 != 0o120000,
                    "SUPPLIER_ZIP_UNSAFE_MEMBER")
            seen.add(name)
            total += item.file_size
            require(total <= MAX_UNPACKED, "SUPPLIER_ZIP_EXPANSION_LIMIT")
            payload = archive.read(item)
            require(len(payload) == item.file_size, "SUPPLIER_ZIP_MEMBER_MISMATCH")
            members.append({
                "path": name, "sha256": hash_bytes(payload), "bytes": item.file_size
            })
    return {"members": sorted(members, key=lambda x: x["path"]),
            "member_count": len(members), "unpacked_bytes": total,
            "zip_crc_verified": True}


def supplier_dossier(root, policy, recipe, source_sha, artifact_sha):
    require(PRODUCT.fullmatch(recipe) and HEX.fullmatch(source_sha)
            and HEX.fullmatch(artifact_sha), "SUPPLIER_VERSION_ID_INVALID")
    root = Path(root)
    warehouse = root / "production-warehouse"
    version = warehouse / "finished" / recipe / source_sha
    require(version.is_dir() and not version.is_symlink()
            and not warehouse.is_symlink(), "SUPPLIER_VERSION_NOT_PRESENT")
    saved = read_json(version / "warehouse_manifest.json")
    archive = version / "product.zip"
    require(saved.get("schema") == "saeit.factory.production-warehouse.v1"
            and saved.get("product_id") == recipe
            and saved.get("source_sha256") == source_sha
            and saved.get("artifact_sha256") == artifact_sha
            and saved.get("manufacturing_qc") == "passed"
            and saved.get("commercial_release") is False
            and saved.get("site_transfer_state") == "not_transferred"
            and saved.get("bytes") == archive.stat().st_size
            and hash_bytes(archive.read_bytes()) == artifact_sha,
            "SUPPLIER_WAREHOUSE_VERSION_HASH_OR_POLICY_MISMATCH")
    measured = zip_proof(archive, recipe)
    routes = {
        key: supplier_route(key, value) for key, value in policy.items()
    }
    return {
        "schema": SCHEMA,
        "product_id": recipe,
        "source_sha256": source_sha,
        "artifact_sha256": artifact_sha,
        "warehouse_manifest_sha256": hash_bytes(
            (version / "warehouse_manifest.json").read_bytes()),
        "criteria_total": len(routes),
        "possible_supplier_roles": sorted(set(x["possible_supplier_role"]
                                              for x in routes.values())),
        "genuinely_connected_external_supplier_count": 0,
        "automated_technical_suppliers_executed": 1,
        "automated_criteria_measured": ["Q068"],
        "q068_original_warehouse_zip_measurement": measured,
        "supplier_assignments": routes,
        "unmet_criterion_count": 99,
        "independent_external_assessments_completed": 0,
        "professional_quality_1000_points": None,
        "professional_quality_1000_certified": False,
        "sale_or_publication_allowed": False,
        "original_warehouse_modified": False,
    }


def persist(root, dossier):
    root = Path(root)
    folder = (root / "quality-excellence" / "evidence-suppliers"
              / dossier["product_id"] / dossier["source_sha256"])
    require(not folder.is_symlink() and
            not (folder.parent.exists() and folder.parent.is_symlink()),
            "SUPPLIER_OUTPUT_SYMLINK")
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    raw = (json.dumps(dossier, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()
    receipt = folder / ("supply-" + hash_bytes(raw) + ".json")
    require(not receipt.is_symlink(), "SUPPLIER_RECEIPT_SYMLINK")
    if receipt.exists():
        require(receipt.is_file() and receipt.read_bytes() == raw,
                "SUPPLIER_IMMUTABLE_RECEIPT_CONFLICT")
    else:
        flags = os.O_CREAT | os.O_WRONLY | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(str(receipt), flags, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
    require(hash_bytes(receipt.read_bytes()) == hash_bytes(raw),
            "SUPPLIER_RECEIPT_READBACK_FAILED")
    return {
        "product_id": dossier["product_id"],
        "artifact_sha256": dossier["artifact_sha256"],
        "receipt": str(receipt),
        "receipt_sha256": hash_bytes(raw),
        "criteria_assigned": len(dossier["supplier_assignments"]),
        "genuine_technical_evidence_supplied": 1,
        "external_independent_evidence_pending": True,
        "quality_1000_certified": False,
        "public_release_allowed": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-root", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--recipe", required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--artifact-sha256", required=True)
    args = parser.parse_args()
    proof = supplier_dossier(
        args.factory_root, catalog(args.catalog), args.recipe,
        args.source_sha256, args.artifact_sha256)
    print("FACTORY_QA1000_EVIDENCE_SUPPLIER=" + json.dumps(
        persist(args.factory_root, proof), sort_keys=True))


if __name__ == "__main__":
    main()
