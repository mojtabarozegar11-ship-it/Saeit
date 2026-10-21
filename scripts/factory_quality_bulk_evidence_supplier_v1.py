#!/usr/bin/env python3
"""Supply genuine, immutable technical evidence for every eligible warehouse version."""
import argparse
from collections import Counter
import importlib.util
import json
import os
from pathlib import Path
import re

HEX = re.compile(r"^[a-f0-9]{64}$")
PRODUCT = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


def load_supplier(path):
    spec = importlib.util.spec_from_file_location("factory_quality_evidence_supplier_v1", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("BULK_SUPPLIER_MODULE_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def versions(root):
    base = Path(root) / "production-warehouse" / "finished"
    if base.is_symlink() or not base.is_dir():
        raise RuntimeError("BULK_WAREHOUSE_FINISHED_MISSING_OR_UNSAFE")
    for product_entry in sorted(os.scandir(base), key=lambda x: x.name):
        if not product_entry.is_dir(follow_symlinks=False) or not PRODUCT.fullmatch(product_entry.name):
            continue
        for version_entry in sorted(os.scandir(product_entry.path), key=lambda x: x.name):
            if version_entry.is_dir(follow_symlinks=False) and HEX.fullmatch(version_entry.name):
                yield product_entry.name, version_entry.name


def run(root, catalog_path, supplier_path):
    supplier = load_supplier(supplier_path)
    policy = supplier.catalog(catalog_path)
    counts = Counter()
    records = []
    for product, source_sha in versions(root):
        counts["versions_seen"] += 1
        try:
            folder = Path(root) / "production-warehouse" / "finished" / product / source_sha
            if folder.is_symlink():
                raise RuntimeError("BULK_VERSION_SYMLINK")
            manifest = supplier.read_json(folder / "warehouse_manifest.json")
            artifact_sha = manifest.get("artifact_sha256")
            if manifest.get("product_id") != product or manifest.get("source_sha256") != source_sha:
                raise RuntimeError("BULK_MANIFEST_IDENTITY_MISMATCH")
            dossier = supplier.supplier_dossier(root, policy, product, source_sha, artifact_sha)
            receipt = supplier.persist(root, dossier)
            receipt_path = Path(receipt["receipt"])
            saved = supplier.read_json(receipt_path)
            if (saved.get("product_id") != product or saved.get("source_sha256") != source_sha
                    or saved.get("artifact_sha256") != artifact_sha
                    or saved.get("q068_original_warehouse_zip_measurement", {}).get("zip_crc_verified") is not True
                    or supplier.hash_bytes(receipt_path.read_bytes()) != receipt["receipt_sha256"]):
                raise RuntimeError("BULK_RECEIPT_READBACK_INVALID")
            counts["supplied"] += 1
            records.append({"product_id": product, "source_sha256": source_sha,
                            "artifact_sha256": artifact_sha,
                            "receipt_sha256": receipt["receipt_sha256"],
                            "measured_criteria": saved["automated_criteria_measured"]})
        except Exception as exc:
            code = str(exc) or type(exc).__name__
            counts["rejected_or_unmeasurable"] += 1
            counts["reject:" + code] += 1
    result = {"schema": "saeit.factory.bulk-quality-evidence-supply-run.v1",
              "versions_seen": counts["versions_seen"], "versions_supplied": counts["supplied"],
              "versions_rejected_or_unmeasurable": counts["rejected_or_unmeasurable"],
              "verified_receipts": records,
              "note": "Q068 CRC and Q092 hash binding are technically measured; all professional criteria remain pending independent review."}
    print("FACTORY_BULK_QA1000_EVIDENCE_SUPPLY=" + json.dumps(result, sort_keys=True))
    for key in sorted(k for k in counts if k.startswith("reject:")):
        print("FACTORY_BULK_REJECTION=" + key + ":" + str(counts[key]))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-root", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--supplier", required=True)
    args = parser.parse_args()
    result = run(args.factory_root, args.catalog, args.supplier)
    if result["versions_seen"] == 0 or result["versions_supplied"] == 0:
        raise SystemExit("BULK_NO_ELIGIBLE_VERSIONS_SUPPLIED")


if __name__ == "__main__":
    main()
