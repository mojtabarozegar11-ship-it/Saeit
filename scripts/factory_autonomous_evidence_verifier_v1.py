#!/usr/bin/env python3
"""Autonomous, fail-closed re-verification of private factory evidence.

Rechecks original ZIP bytes, supplier measurements and AI workpapers. It creates
immutable *machine* receipts and a rework queue, never an owner's signature,
human expert verdict, independent third-party attestation or sale permission.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re

SCHEMA = "saeit.factory.autonomous-evidence-verification.v1"
HEX = re.compile(r"^[a-f0-9]{64}$")
PRODUCT = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


def load(path, name):
    candidate = Path(path)
    if not candidate.is_file() or candidate.is_symlink():
        raise ValueError("VERIFIER_MODULE_UNSAFE:" + name)
    spec = importlib.util.spec_from_file_location(name, str(candidate))
    if spec is None or spec.loader is None:
        raise ValueError("VERIFIER_MODULE_UNAVAILABLE:" + name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(value):
    return hashlib.sha256(value).hexdigest()


def require(ok, code):
    if not ok:
        raise ValueError(code)


def private_path(root, *parts):
    path = Path(root)
    require(not path.is_symlink(), "VERIFIER_ROOT_SYMLINK")
    for part in parts:
        path = path / part
        require(not path.is_symlink(), "VERIFIER_PATH_SYMLINK")
    return path


def read_latest(root, family, product, source, prefix, supplier):
    folder = private_path(root, "quality-excellence", family, product, source)
    require(folder.is_dir(), "VERIFIER_" + family.upper().replace("-", "_") + "_MISSING")
    candidates = []
    for candidate in sorted(folder.glob(prefix + "-*.json")):
        require(candidate.is_file() and not candidate.is_symlink(), "VERIFIER_RECEIPT_UNSAFE")
        raw = candidate.read_bytes()
        require(len(raw) <= 10_000_000
                and candidate.name == prefix + "-" + sha(raw) + ".json",
                "VERIFIER_RECEIPT_DIGEST_MISMATCH")
        record = supplier.read_json(candidate, size=10_000_000)
        require(record.get("product_id") == product
                and record.get("source_sha256") == source,
                "VERIFIER_RECEIPT_WRONG_VERSION")
        candidates.append((record, sha(raw)))
    require(candidates, "VERIFIER_NO_HASH_BOUND_RECEIPTS")
    return candidates


def verify_version(root, product, source, catalog, supplier, agent, evaluator):
    require(PRODUCT.fullmatch(product) and HEX.fullmatch(source), "VERIFIER_ID_UNSAFE")
    version = private_path(root, "production-warehouse", "finished", product, source)
    require(version.is_dir(), "VERIFIER_VERSION_MISSING")
    manifest_path = private_path(version, "warehouse_manifest.json")
    manifest = supplier.read_json(manifest_path)
    artifact = manifest.get("artifact_sha256")
    require(isinstance(artifact, str) and HEX.fullmatch(artifact),
            "VERIFIER_MANIFEST_ARTIFACT_ID")
    archive = private_path(version, "product.zip")
    require(archive.is_file() and 0 < archive.stat().st_size <= supplier.MAX_PACKAGE,
            "VERIFIER_ARCHIVE_MISSING_OR_UNSAFE")
    require(manifest.get("schema") == "saeit.factory.production-warehouse.v1"
            and manifest.get("product_id") == product
            and manifest.get("source_sha256") == source
            and manifest.get("manufacturing_qc") == "passed"
            and manifest.get("commercial_release") is False
            and manifest.get("site_transfer_state") == "not_transferred"
            and manifest.get("bytes") == archive.stat().st_size
            and sha(archive.read_bytes()) == artifact,
            "VERIFIER_ORIGINAL_WAREHOUSE_BINDING_FAILED")

    supplies = read_latest(root, "evidence-suppliers", product, source, "supply", supplier)
    supplies = [(item, h) for item, h in supplies
                if item.get("schema") == supplier.SCHEMA
                and item.get("artifact_sha256") == artifact
                and item.get("professional_quality_1000_certified") is False
                and item.get("sale_or_publication_allowed") is False]
    require(supplies, "VERIFIER_NO_ELIGIBLE_SUPPLIER")
    supplies.sort(key=lambda pair: len(pair[0].get("automated_criteria_measured", [])),
                  reverse=True)
    dossier, supplier_sha = supplies[0]
    report = evaluator.evaluate(dossier, archive, catalog,
                                supplier_script=Path(supplier.__file__),
                                manifest_path=manifest_path)
    require(not report["rejected_claims"] and report["machine_evidence_rechecked_count"] > 0,
            "VERIFIER_TECHNICAL_MEASUREMENT_REJECTED")
    # An AI workpaper is allowed to provide leads, not independent professional points.
    workpapers = read_latest(root, "ai-evidence-workpapers", product, source,
                             "workpaper", supplier)
    expected = agent.build_dossier(root, catalog, product, source, artifact, supplier)
    matching = [(item, h) for item, h in workpapers if item == expected]
    require(matching, "VERIFIER_AI_WORKPAPERS_NOT_REPRODUCIBLE")
    workpaper, workpaper_sha = matching[0]
    require(workpaper.get("criteria_total") == 100
            and len(workpaper.get("ai_workpapers", {})) == 100
            and workpaper.get("sale_or_publication_allowed") is False
            and workpaper.get("professional_quality_1000_certified") is False,
            "VERIFIER_AI_WORKPAPER_AUTHORITY_MISSTATED")

    accepted = report["machine_evidence_rechecked_criteria"]
    missing = [key for key in catalog if key not in accepted]
    receipt = {
        "schema": SCHEMA,
        "product_id": product,
        "source_sha256": source,
        "artifact_sha256": artifact,
        "manifest_sha256": sha(manifest_path.read_bytes()),
        "supplier_receipt_sha256": supplier_sha,
        "ai_workpaper_receipt_sha256": workpaper_sha,
        "evaluator_report": report,
        "ai_workpapers_reproduced": 100,
        "machine_measured_criteria_rechecked": accepted,
        "criteria_missing_independent_quality_decisions": list(catalog),
        "technical_evidence_gaps_for_rework": missing,
        "machine_status": "BOUNDED_TECHNICAL_EVIDENCE_REVERIFIED",
        "signature_status": "UNSIGNED_MACHINE_RECEIPT_NOT_OWNER_SIGNATURE",
        "external_independence_claimed": False,
        "licensed_specialist_review_claimed": False,
        "professional_quality_1000_certified": False,
        "commercial_release_allowed": False,
        "original_product_modified": False,
    }
    return receipt


def persist(root, receipt):
    folder = private_path(root, "quality-excellence", "autonomous-verification",
                          receipt["product_id"], receipt["source_sha256"])
    folder.mkdir(parents=True, mode=0o700, exist_ok=True)
    raw = (json.dumps(receipt, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()
    target = private_path(folder, "verification-" + sha(raw) + ".json")
    if target.exists():
        require(target.is_file() and target.read_bytes() == raw,
                "VERIFIER_IMMUTABLE_RECEIPT_CONFLICT")
    else:
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(str(target), flags, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    require(target.read_bytes() == raw, "VERIFIER_READBACK_FAILED")
    return sha(raw)


def run(root, catalog_path, supplier_path, agent_path, evaluator_path):
    supplier = load(supplier_path, "autoverifier_supplier")
    agent = load(agent_path, "autoverifier_agent")
    evaluator = load(evaluator_path, "autoverifier_evaluator")
    catalog = supplier.catalog(catalog_path)
    base = private_path(root, "production-warehouse", "finished")
    require(base.is_dir(), "VERIFIER_WAREHOUSE_UNAVAILABLE")
    total = verified = 0
    rejected = []
    measured = 0
    for product in sorted(os.scandir(base), key=lambda e: e.name):
        if not product.is_dir(follow_symlinks=False) or not PRODUCT.fullmatch(product.name):
            continue
        for version in sorted(os.scandir(product.path), key=lambda e: e.name):
            if not version.is_dir(follow_symlinks=False) or not HEX.fullmatch(version.name):
                continue
            total += 1
            try:
                result = verify_version(root, product.name, version.name,
                                        catalog, supplier, agent, evaluator)
                persist(root, result)
                verified += 1
                measured += len(result["machine_measured_criteria_rechecked"])
            except (OSError, ValueError, RuntimeError, KeyError, TypeError,
                    json.JSONDecodeError) as exc:
                rejected.append({"version_sha256": version.name,
                                 "reason": str(exc)[:160] or type(exc).__name__})
    summary = {
        "schema": "saeit.factory.autonomous-evidence-verification-run.v1",
        "versions_seen": total,
        "versions_machine_reverified": verified,
        "versions_rejected": len(rejected),
        "technical_criterion_checks": measured,
        "ai_workpapers_reproduced": 100 * verified,
        "independent_professional_certifications": 0,
        "owner_digital_signatures": 0,
        "commercial_releases": 0,
        "rejected": rejected,
    }
    print("FACTORY_AUTONOMOUS_EVIDENCE_VERIFICATION=" +
          json.dumps(summary, sort_keys=True))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("factory-root", "catalog", "supplier", "agent", "evaluator"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    outcome = run(args.factory_root, args.catalog, args.supplier,
                  args.agent, args.evaluator)
    if outcome["versions_seen"] == 0 or outcome["versions_rejected"]:
        raise SystemExit("VERIFIER_FAIL_CLOSED")


if __name__ == "__main__":
    main()
