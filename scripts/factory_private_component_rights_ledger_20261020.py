#!/usr/bin/env python3
"""Write-once PRIVATE component inventory and personal-owner correction evidence.

No rights transfer, clearance, payment, database, store, ZIP or public mutation.
The original byte-bound old legal documents are retained untouched.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import zipfile

SHA = re.compile(r"^[0-9a-f]{64}$")
LEGAL = "مجتبی گلستانی‌نیک"
PROFESSIONAL = "مجتبی روزگار"


def raw_json(data):
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write_once(target, content):
    """No overwrite or symlinks. Mode 0600. Fail on content conflicts."""
    if target.parent.is_symlink() or not target.parent.is_dir():
        raise ValueError("PRIVATE_EVIDENCE_PARENT_UNSAFE")
    if target.exists() or target.is_symlink():
        if (target.is_symlink() or not target.is_file()
                or target.stat().st_mode & 0o077
                or target.read_bytes() != content):
            raise ValueError("PRIVATE_EVIDENCE_CONFLICT")
        return "existing_verified"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(target), flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return "created"


def vps_ledger(root):
    from factory_commercial_evidence_readonly_20261020 import examine_product
    base = Path(root) / "digital-products"
    if base.is_symlink() or not base.is_dir():
        raise ValueError("FACTORY_PRODUCT_ROOT_UNSAFE")
    folders = sorted(base.iterdir())
    if len(folders) > 1000:
        raise ValueError("TOO_MANY_PRODUCTS")
    counts = Counter()
    for folder in folders:
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError("PRODUCT_DIRECTORY_UNSAFE")
        info = examine_product(folder)
        archive = folder / (folder.name + "-internal-qa.zip")
        components = []
        with zipfile.ZipFile(archive) as z:
            for entry in z.infolist():
                sha = hashlib.sha256()
                with z.open(entry) as f:
                    for part in iter(lambda: f.read(65536), b""):
                        sha.update(part)
                components.append({
                    "relative_path": entry.filename.partition("/")[2],
                    "sha256": sha.hexdigest(),
                    "bytes": entry.file_size,
                    "legal_redistribution_permission_verified": False,
                    "attribution_requirements_independently_reviewed": False,
                })
        record = {
            "schema": "saeit.factory.private-component-rights-ledger.v1",
            "product_id": folder.name,
            "artifact_sha256": info["artifact_sha256"],
            "source_sha256_presence_verified": info["source_hash_present"],
            "source_file_index_status": info["source_file_index_status"],
            "components": components,
            "component_count": len(components),
            "declared_economic_rights_owner": PROFESSIONAL,
            "owner_official_name_as_declared": LEGAL,
            "owner_identity_status": "owner_declaration_not_independently_authenticated",
            "company_role": "technology_and_sales_services_platform_not_rights_owner",
            "independent_creator_chain_of_title_verified": False,
            "all_component_commercial_redistribution_rights_verified": False,
            "qualified_legal_release_review_completed": False,
            "commercial_release_allowed": False,
            "old_source_files_rewritten": False,
        }
        if len(components) != info["members_integrity_checked"]:
            raise ValueError("COMPONENT_LEDGER_COUNT_MISMATCH")
        target = folder / ("component_rights." + info["artifact_sha256"] + ".v1.private.json")
        counts[write_once(target, raw_json(record))] += 1
        counts["component_sha256_records"] += len(components)
        counts["source_index_reconstructed"] += int(info["source_file_index_status"].startswith("reconstructed_"))
        counts["source_sha_missing"] += int(not info["source_hash_present"])
    return {
        "private_products": len(folders),
        "new_private_ledgers": counts["created"],
        "existing_verified": counts["existing_verified"],
        "component_sha256_records": counts["component_sha256_records"],
        "source_index_reconstructed": counts["source_index_reconstructed"],
        "source_sha_missing": counts["source_sha_missing"],
        "rights_independently_cleared": 0,
        "commercial_release_enabled": False,
        "source_archives_or_qa_manifests_modified": False,
    }


def cpanel_legal_addenda(home):
    """Supplement historical claimant records without rewriting evidence or DB."""
    base = Path(home) / ".private/zomorod-business/rights-evidence"
    if base.is_symlink() or not base.is_dir():
        raise ValueError("CPANEL_RIGHTS_RECORD_ROOT_UNSAFE")
    inventory = []
    for folder in sorted(base.iterdir()):
        if folder.is_symlink() or not folder.is_dir() or not SHA.fullmatch(folder.name):
            continue
        original = [f for f in folder.iterdir() if f.name.endswith(".rights.json")]
        if len(original) != 1:
            raise ValueError("HISTORICAL_RIGHTS_RECORD_AMBIGUOUS")
        p = original[0]
        if p.is_symlink() or not p.is_file() or not 0 < p.stat().st_size <= 200000:
            raise ValueError("HISTORICAL_RIGHTS_RECORD_UNSAFE")
        source = p.read_bytes()
        d = json.loads(source)
        if (d.get("schema") != "saeit.factory.cpanel-private-rights-register.v1" or
                d.get("original_archive_sha256") != folder.name or
                d.get("commercial_distribution_allowed") is not False or
                d.get("claimant_chain_of_title_verified") is not False or
                d.get("asset_count") != 97):
            raise ValueError("HISTORICAL_RIGHTS_RECORD_MISMATCH")
        inventory.append((folder, p, source, d))
    if len(inventory) != 5:
        raise ValueError("EXPECTED_FIVE_PRIVATE_RIGHTS_RECORDS")
    count = Counter()
    for folder, old_path, old_bytes, old in inventory:
        record = {
            "schema": "saeit.factory.cpanel-owner-claimant-addendum.v2",
            "product_id": old["recipe"],
            "original_archive_sha256": folder.name,
            "historical_rights_dossier_sha256": digest(old_bytes),
            "historical_proposed_claimant_company_not_verified_as_owner": True,
            "owner_personal_rights_declared_professional_name": PROFESSIONAL,
            "owner_legal_name_as_declared": LEGAL,
            "company_services_platform_only": "شرکت کشت و صنعت زمرد ملل",
            "historical_legal_claimant_field_superseded_for_internal_policy": True,
            "original_historical_dossier_preserved_unchanged": True,
            "creator_or_employment_title_evidence_independently_verified": False,
            "all_third_party_component_rights_verified": False,
            "merchant_and_gateway_legal_identity_verified": False,
            "commercial_release_allowed": False,
            "requires_signature_image_to_be_uploaded": False,
        }
        target = folder / ("personal_owner_context." + digest(old_bytes) + ".v2.private.json")
        count[write_once(target, raw_json(record))] += 1
    return {
        "private_cpanel_product_addenda": len(inventory),
        "created": count["created"],
        "existing_verified": count["existing_verified"],
        "historical_rights_documents_modified": False,
        "store_database_modified": False,
        "merchant_contract_verified": False,
        "commercial_release_enabled": False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("vps", "cpanel"))
    p.add_argument("--root")
    args = p.parse_args()
    if args.mode == "vps":
        if not args.root:
            p.error("root required")
        answer = vps_ledger(args.root)
    else:
        answer = cpanel_legal_addenda("/home/zomorod2")
    print("FACTORY_PRIVATE_COMPONENT_RIGHTS_" + args.mode.upper() + "=" + json.dumps(answer, sort_keys=True))


if __name__ == "__main__":
    main()
