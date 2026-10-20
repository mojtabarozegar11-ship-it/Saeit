#!/usr/bin/env python3
"""Read-only commercial evidence inspection for actual factory ZIPs and merchant routes.

No signatures, title transfer, PSP credential assertions, customer payments, or
publication can be inferred from this audit. Python 3.8+ / standard library.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sqlite3
import stat
import sys
import zipfile

SHA = re.compile(r"^[0-9a-f]{64}$")
SLUG = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
RIGHTS_NAMES = re.compile(r"(?i)(?:^|[/._-])(license|licence|copyright|permission|attribution|notice|third.party.rights)(?:[/._-]|$)")
DEPENDENCY_NAMES = {"requirements.txt", "package.json", "package-lock.json", "pyproject.toml", "composer.json", "go.mod", "Cargo.lock", "yarn.lock", "Pipfile", "Pipfile.lock"}
MAX_ZIP = 25 * 1024 * 1024
MAX_FILES = 800
MAX_MEMBER_UNCOMPRESSED = 12 * 1024 * 1024


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(131072), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_json(path, limit=200000):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("EVIDENCE_FILE_INVALID")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("EVIDENCE_JSON_NOT_OBJECT")
    return obj


def examine_product(folder):
    """Inspect real bytes. License-like filenames are leads, never permissions."""
    if folder.is_symlink() or not folder.is_dir() or not SLUG.fullmatch(folder.name):
        raise ValueError("UNSAFE_PRODUCT_FOLDER")
    manifest = safe_json(folder / "manufacturing_manifest.json")
    if (manifest.get("recipe") != folder.name or
            manifest.get("qa_status") != "passed" or
            manifest.get("commercial_status") != "private_internal_qa_pass_not_published" or
            manifest.get("public_listing_enabled") is not False or
            manifest.get("owner_publication_approval") is not False or
            manifest.get("price") is not None):
        raise ValueError("NOT_PRIVATE_QA_PRODUCT")
    expected = manifest.get("artifact_sha256")
    if not isinstance(expected, str) or not SHA.fullmatch(expected):
        raise ValueError("EXPECTED_SHA_INVALID")
    zip_path = folder / (folder.name + "-internal-qa.zip")
    if (zip_path.is_symlink() or not zip_path.is_file() or
            not 0 < zip_path.stat().st_size <= MAX_ZIP):
        raise ValueError("ARCHIVE_UNTRUSTED")
    if file_hash(zip_path) != expected:
        raise ValueError("ARCHIVE_SHA_MISMATCH")
    rights_documents = 0
    dependency_manifests = 0
    code_files = 0
    media_files = 0
    other_files = 0
    member_total = 0
    total_uncompressed = 0
    names = set()
    declared_source_names = manifest.get("files")
    # Some historical QA manifests have no source-file-name index. Recover only
    # the verifiable archive member index, not authorship or legal title.
    original_file_index_present = isinstance(declared_source_names, list) and bool(declared_source_names)
    if declared_source_names is not None and not isinstance(declared_source_names, list):
        raise ValueError("SOURCE_FILE_INDEX_MALFORMED")
    if isinstance(declared_source_names, list) and any(
            not isinstance(x, str) or not x for x in declared_source_names):
        raise ValueError("SOURCE_FILE_INDEX_MALFORMED")
    with zipfile.ZipFile(zip_path) as archive:
        info = archive.infolist()
        if not 0 < len(info) <= MAX_FILES:
            raise ValueError("ARCHIVE_FILE_COUNT_INVALID")
        for m in info:
            p = PurePosixPath(m.filename)
            if (m.is_dir() or "\\" in m.filename or "\x00" in m.filename or
                    m.filename.startswith("/") or len(p.parts) < 2 or
                    p.parts[0] != folder.name or
                    any(part in ("", ".", "..") for part in p.parts) or
                    m.filename in names or
                    (m.external_attr >> 16) & 0o170000 == stat.S_IFLNK or
                    m.file_size > MAX_MEMBER_UNCOMPRESSED):
                raise ValueError("ARCHIVE_MEMBER_UNSAFE")
            names.add(m.filename)
            total_uncompressed += m.file_size
            if total_uncompressed > 120 * 1024 * 1024:
                raise ValueError("ARCHIVE_UNCOMPRESSED_TOO_LARGE")
            member_total += 1
            filename = p.name
            if RIGHTS_NAMES.search(filename):
                rights_documents += 1
            if filename in DEPENDENCY_NAMES:
                dependency_manifests += 1
            ext = p.suffix.lower()
            if ext in (".py", ".js", ".ts", ".jsx", ".tsx", ".php", ".html", ".css", ".sh"):
                code_files += 1
            elif ext in (".png", ".jpg", ".jpeg", ".svg", ".webp", ".ttf", ".woff", ".woff2", ".mp3", ".wav", ".mp4", ".pdf"):
                media_files += 1
            else:
                other_files += 1
        if archive.testzip() is not None:
            raise ValueError("ARCHIVE_CRC_FAILED")
    if original_file_index_present and set(declared_source_names) != {
            str(PurePosixPath(x).relative_to(folder.name)) for x in names}:
        raise ValueError("SOURCE_FILE_INDEX_MISMATCH")
    return {
        "artifact_sha256": expected,
        "members_integrity_checked": member_total,
        "source_file_index_status": "original_manifest_index_present" if original_file_index_present else "reconstructed_from_sha_verified_archive_not_source_proof",
        "rights_document_filename_candidates": rights_documents,
        "dependency_manifest_candidates": dependency_manifests,
        "code_files": code_files,
        "media_files": media_files,
        "other_files": other_files,
        "source_hash_present": isinstance(manifest.get("source_sha256"), str) and bool(SHA.fullmatch(manifest["source_sha256"])),
        "owner_claimant": "natural_person_declared_not_company",
        "company_role": "operational_and_sales_services_platform",
        "actual_creator_title_chain_independently_verified": False,
        "each_component_commercial_license_verified": False,
        "sale_allowed_by_this_audit": False,
    }


def audit_factory(root):
    root = Path(root)
    stock = root / "digital-products"
    if (root.is_symlink() or not root.is_dir() or
            stock.is_symlink() or not stock.is_dir()):
        raise ValueError("PRIVATE_FACTORY_ROOT_UNSAFE")
    candidates = sorted(stock.iterdir())
    if len(candidates) > 1000:
        raise ValueError("PRIVATE_STOCK_COUNT_LIMIT")
    counters = Counter()
    failures = Counter()
    for folder in candidates:
        if folder.is_symlink() or not folder.is_dir():
            counters["nonproduct"] += 1
            continue
        try:
            doc = examine_product(folder)
            counters["archive_integrity_verified"] += 1
            counters["components_inspected"] += doc["members_integrity_checked"]
            counters["missing_original_member_index_reconstructed"] += int(
                doc["source_file_index_status"] == "reconstructed_from_sha_verified_archive_not_source_proof")
            counters["rights_document_filename_candidates"] += doc["rights_document_filename_candidates"]
            counters["dependency_manifest_candidates"] += doc["dependency_manifest_candidates"]
            counters["code_files"] += doc["code_files"]
            counters["media_files"] += doc["media_files"]
            counters["missing_original_source_hash"] += int(not doc["source_hash_present"])
        except (OSError, ValueError, TypeError, KeyError, zipfile.BadZipFile) as e:
            counters["blocked"] += 1
            failures[str(e).split(":", 1)[0][:80]] += 1
    return {
        "schema": "saeit.factory.commercial-evidence-readonly.v1",
        "stock_folders_scanned": len(candidates),
        "counts": dict(sorted(counters.items())),
        "failed_reason_counts": dict(sorted(failures.items())),
        "itemized_component_rights_fully_cleared_by_this_audit": 0,
        "owner_signature_uploaded_or_required": False,
        "company_rights_assignee": False,
        "published_items": 0,
        "paid_items_activated": 0,
        "audit_scope": "private_factory_staging_not_all_public_site_products",
    }


def audit_rails(root):
    root = Path(root)
    private = root / "merchant-rails"
    index = safe_json(private / "dashboard.json", 1200000)
    if index.get("site_count") != 2 or index.get("private_site_family_offer_routes") != 80:
        raise ValueError("MERCHANT_ROUTES_NOT_80")
    routes = 0
    unsafe = 0
    missing_provider = 0
    mismatched_site = 0
    for site, host in (("mojplaywin", "mojplaywin.com"), ("zomorodmelal", "zomorodmelal.ir")):
        for n in range(1, 41):
            doc = safe_json(private / "routes" / site / ("F%02d.json" % n))
            routes += 1
            if doc.get("site_host") != host or doc.get("family_id") != "F%02d" % n:
                mismatched_site += 1
            if (doc.get("collect_customer_payment") is not False or
                    doc.get("automatic_paid_entitlement") is not False or
                    doc.get("public_buy_button_enabled") is not False):
                unsafe += 1
            if doc.get("merchant_api_configuration_verified_on_live_site") is not True:
                missing_provider += 1
    if unsafe or mismatched_site:
        raise ValueError("MERCHANT_ROUTE_INTEGRITY_FAILURE")
    return {
        "schema": "saeit.factory.merchant-evidence-readonly.v1",
        "private_routes_checked": routes,
        "provider_identity_or_api_unverified_routes": missing_provider,
        "site_mismatch": mismatched_site,
        "unsafe_payment_route_count": unsafe,
        "bank_shahr_psp_provider_authenticated": index.get("bank_shahr_gateway_psp_verified") is True,
        "mojplaywin_crypto_receipt_verification_authenticated_by_factory": index.get("mojplaywin_crypto_live_receipt_verification_verified_here") is True,
        "legal_seller_gateway_contract_verified_by_this_audit": False,
        "paid_order_created": False,
        "status": "provider_and_merchant_agreement_need_live_independent_verification",
    }


def audit_cpanel():
    """Read only nonsecret site capabilities and public schema, not customer rows."""
    root = Path("/home/zomorod2")
    if not root.is_dir() or root.is_symlink():
        raise ValueError("CPANEL_ROOT_UNAVAILABLE")
    store = root / ".private/zomorod-business/site_store.sqlite3"
    tables = set()
    private_stock = None
    if store.is_file() and not store.is_symlink():
        with sqlite3.connect("file:" + str(store) + "?mode=ro", uri=True) as db:
            tables = {t[0] for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "factory_private_shard_candidates" in tables:
                private_stock = db.execute("SELECT COUNT(*) FROM factory_private_shard_candidates").fetchone()[0]
    django_root = root / "Saeit-staging"
    packages = ("mpw_commerce", "mpw_native_checkout", "mpw_guest_trx_20261020")
    modules = {name: (django_root / name).is_dir() for name in packages}
    # These are process-environment presence tests, NOT an authenticated bank/PSP
    # identity check. Do not read values, connect to PSP, or infer ownership.
    import os
    signal_keys = ("BANK_SHAHR_PSP_MERCHANT_ID", "BANK_SHAHR_PSP_TERMINAL_ID",
                   "BANK_SHAHR_PSP_VERIFY_URL", "BANK_SHAHR_PSP_SECRET",
                   "MPW_MERCHANT_LEGAL_NAME", "MPW_COMMERCE_REAL_RPC_ENABLED")
    return {
        "schema": "saeit.factory.site-merchant-inventory-readonly.v1",
        "native_store_database_present": store.is_file() and not store.is_symlink(),
        "private_shard_candidates": private_stock,
        "merchant_or_gateway_table_names_count": sum(any(word in x.lower() for word in ("gateway", "merchant", "payment")) for x in tables),
        "mojplaywin_app_modules_present": modules,
        "runtime_process_env_key_presence_only": {k: bool(os.environ.get(k)) for k in signal_keys},
        "psp_merchant_contract_or_bank_account_beneficiary_independently_checked": False,
        "crypto_receiving_wallet_ownership_independently_checked": False,
        "production_provider_callback_verified": False,
        "customer_money_moved": False,
        "site_or_database_modified": False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("factory", "rails", "cpanel"))
    p.add_argument("--root", default="")
    args = p.parse_args()
    if args.mode != "cpanel" and not args.root:
        p.error("--root required")
    result = (audit_factory(args.root) if args.mode == "factory" else
              audit_rails(args.root) if args.mode == "rails" else audit_cpanel())
    print("FACTORY_COMMERCE_EVIDENCE_" + args.mode.upper() + "=" + json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
