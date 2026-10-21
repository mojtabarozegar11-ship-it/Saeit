#!/usr/bin/env python3
"""Private checksum-verified cPanel inbox; no Django/database/public listing writes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import zipfile

SLUG = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
MAX_ARCHIVE_BYTES = 25 * 1024 * 1024
MAX_UNPACKED_BYTES = 100 * 1024 * 1024
MAX_FILES = 256  # bounded, manifest-bound private package transfer
F34_EXACT_ICON_FILES = 100  # 48 SVG + 48 PNG + four documented files, private ONLY


def secure_directory(path):
    if path.is_symlink():
        raise ValueError("INBOX_SYMLINK_REJECTED")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or not path.is_dir():
        raise ValueError("INBOX_DIRECTORY_INVALID")
    os.chmod(str(path), 0o700)


def atomic_json(path, value):
    secure_directory(path.parent)
    fd, temp = tempfile.mkstemp(prefix=".pending-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(value, out, ensure_ascii=False, sort_keys=True, indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, str(path))
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_package(zip_file, manifest_file, recipe, expected_digest):
    if not SLUG.fullmatch(recipe) or not DIGEST.fullmatch(expected_digest):
        raise ValueError("INVALID_RECIPE_OR_DIGEST")
    if zip_file.is_symlink() or manifest_file.is_symlink():
        raise ValueError("SYMLINK_IN_UPLOAD")
    if not zip_file.is_file() or not manifest_file.is_file():
        raise ValueError("INCOMPLETE_UPLOAD")
    if zip_file.stat().st_size <= 0 or zip_file.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("INVALID_ARCHIVE_SIZE")
    if manifest_file.stat().st_size > 100000:
        raise ValueError("MANIFEST_TOO_LARGE")
    with manifest_file.open(encoding="utf-8") as f:
        manifest = json.load(f)
    if not isinstance(manifest, dict):
        raise ValueError("BAD_MANIFEST")
    if manifest.get("recipe") != recipe or manifest.get("artifact_sha256") != expected_digest:
        raise ValueError("MANIFEST_IDENTITY_MISMATCH")
    if (manifest.get("qa_status") != "passed"
        or manifest.get("commercial_status") != "private_internal_qa_pass_not_published"
        or manifest.get("public_listing_enabled") is not False
        or manifest.get("owner_publication_approval") is not False
        or manifest.get("price") is not None):
        raise ValueError("UNSAFE_OR_UNREVIEWED_MANIFEST")
    if sha256(zip_file) != expected_digest:
        raise ValueError("SHA256_MISMATCH")
    with zipfile.ZipFile(str(zip_file)) as archive:
        infos = archive.infolist()
        # F34 keeps its exact specialist 100-file contract. Other products
        # may have up to 256 files ONLY when every archived path matches
        # the producer's declared unique file list and SHA-bound ZIP.
        if recipe == "fieldwork_ui_48_icons":
            reviewer = manifest.get("qa_measurements")
            members = manifest.get("files")
            if (manifest.get("family_id") != "F34"
                    or not isinstance(reviewer, dict)
                    or reviewer.get("review_kind") != "separate_automated_technical_verification"
                    or reviewer.get("validated_archive_members") != F34_EXACT_ICON_FILES
                    or reviewer.get("archive_sha256") != expected_digest
                    or reviewer.get("critical_defects") != []
                    or not isinstance(reviewer.get("gates"), dict)
                    or len(reviewer["gates"]) != 10
                    or not all(value is True for value in reviewer["gates"].values())
                    or not isinstance(members, list)
                    or len(members) != F34_EXACT_ICON_FILES
                    or len(set(members)) != F34_EXACT_ICON_FILES):
                raise ValueError("F34_EVIDENCE_CONTRACT_INVALID")
            svg = {name[:-4] for name in members if name.endswith(".svg")}
            png = {name[:-4] for name in members if name.endswith(".png")}
            docs = set(members) - {name for name in members if name.endswith((".svg", ".png"))}
            if (len(svg) != 48 or svg != png
                    or docs != {"README.md", "LICENSE.txt", "catalog.json", "preview.html"}
                    or len(infos) != F34_EXACT_ICON_FILES
                    or {item.filename for item in infos} != {recipe + "/" + name for name in members}):
                raise ValueError("F34_EXACT_ICON_PACKAGE_INVALID")
        elif not infos or len(infos) > MAX_FILES:
            raise ValueError("ARCHIVE_FILE_COUNT_INVALID")
        elif not isinstance(manifest.get("files"), list):
            raise ValueError("ARCHIVE_MANIFEST_MEMBERS_MISSING")
        elif (len(manifest["files"]) != len(infos)
              or len(set(manifest["files"])) != len(infos)
              or not all(isinstance(v,str) and v and len(v)<=240
                         for v in manifest["files"])
              or {recipe + "/" + v for v in manifest["files"]}
                    != {item.filename for item in infos}):
            raise ValueError("ARCHIVE_MANIFEST_MEMBERS_MISMATCH")
        if len({x.filename for x in infos}) != len(infos):
            raise ValueError("ARCHIVE_DUPLICATE_MEMBER")
        if sum(x.file_size for x in infos) > MAX_UNPACKED_BYTES:
            raise ValueError("ARCHIVE_EXPANSION_LIMIT")
        for member in infos:
            name = member.filename
            parts = name.split("/")
            if (name.startswith("/") or "\\" in name or not name.startswith(recipe + "/")
                or any(p in ("", ".", "..") for p in parts)
                or (member.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError("UNSAFE_ARCHIVE_MEMBER")
        if archive.testzip() is not None:
            raise ValueError("CORRUPT_ARCHIVE")
    return manifest


def receipt_path(root, recipe, digest):
    return root / "receipts" / recipe / (digest + ".json")


def status(root, recipe, digest):
    if not SLUG.fullmatch(recipe) or not DIGEST.fullmatch(digest):
        raise ValueError("INVALID_RECIPE_OR_DIGEST")
    receipt = receipt_path(root, recipe, digest)
    if not receipt.is_file() or receipt.is_symlink():
        return False
    try:
        details = json.loads(receipt.read_text(encoding="utf-8"))
        if details.get("status") != "received_private" or details.get("sha256") != digest:
            return False
        archive = root / "packages" / recipe / (digest + ".zip")
        manifest = root / "packages" / recipe / (digest + ".json")
        validate_package(archive, manifest, recipe, digest)
        return True
    except (OSError, ValueError, zipfile.BadZipFile, TypeError):
        return False


def finalize(root, recipe, digest):
    if not SLUG.fullmatch(recipe) or not DIGEST.fullmatch(digest):
        raise ValueError("INVALID_RECIPE_OR_DIGEST")
    incoming = root / "incoming" / recipe
    packages = root / "packages" / recipe
    secure_directory(root)
    secure_directory(incoming)
    secure_directory(packages)
    source_zip = incoming / (digest + ".zip.partial")
    source_json = incoming / (digest + ".json.partial")
    validate_package(source_zip, source_json, recipe, digest)
    target_zip = packages / (digest + ".zip")
    target_json = packages / (digest + ".json")
    os.chmod(str(source_zip), 0o600)
    os.chmod(str(source_json), 0o600)
    os.replace(str(source_zip), str(target_zip))
    os.replace(str(source_json), str(target_json))
    atomic_json(receipt_path(root, recipe, digest), {
        "version": 1, "recipe": recipe, "sha256": digest,
        "status": "received_private", "database_written": False,
        "public_store_listing": False, "owner_approval_required": True,
    })
    return True



def consumer_paths(root, recipe, version):
    if not SLUG.fullmatch(recipe) or not DIGEST.fullmatch(version):
        raise ValueError("CONSUMER_ID_INVALID")
    return (root / "customer-packages" / recipe / version,
            root / "customer-receipts" / recipe / (version + ".json"))


def verify_consumer(root, recipe, version, zipfile_path, manifest_path):
    """Proof of usable PRIVATE buyer package bound to prior technical receipt."""
    if any(p.is_symlink() or not p.is_file() for p in (zipfile_path,manifest_path)):
        raise ValueError("CONSUMER_UPLOAD_INCOMPLETE")
    if not 0 < zipfile_path.stat().st_size <= MAX_ARCHIVE_BYTES:
        raise ValueError("CONSUMER_FILE_TOO_LARGE")
    if not 0 < manifest_path.stat().st_size <= 100000:
        raise ValueError("CONSUMER_MANIFEST_SIZE")
    meta=json.loads(manifest_path.read_text(encoding="utf8"))
    if not isinstance(meta,dict) or meta.get("schema")!="saeit.factory.consumer-package.v1":
        raise ValueError("CONSUMER_SCHEMA_INVALID")
    source=root/"packages"/recipe
    found=False
    if not source.is_dir() or source.is_symlink():
        raise ValueError("CONSUMER_ORIGINAL_MISSING")
    for file in source.glob("*.json"):
        if file.is_symlink() or not file.is_file() or not DIGEST.fullmatch(file.stem):
            raise ValueError("CONSUMER_SOURCE_UNSAFE")
        entry=json.loads(file.read_text("utf8"))
        if (entry.get("recipe")==recipe and entry.get("source_sha256")==version
                and entry.get("artifact_sha256")==meta.get("factory_internal_zip_sha256")
                and status(root,recipe,file.stem)):
            found=True
            break
    if not found:
        raise ValueError("CONSUMER_FACTORY_VERSION_NOT_VERIFIED")
    if (meta.get("product_id")!=recipe or meta.get("factory_source_sha256")!=version
            or meta.get("technical_buyer_package_verified") is not True
            or meta.get("consumer_cli_smoke_examples_passed")!=2
            or meta.get("commercial_release") is not False
            or meta.get("public_download_allowed") is not False
            or meta.get("eligible_for_commercial_listing") is not False
            or meta.get("rights_and_license_review_completed") is not False
            or meta.get("independent_domain_review_completed") is not False
            or meta.get("price") is not None
            or meta.get("package_bytes")!=zipfile_path.stat().st_size
            or meta.get("package_sha256")!=sha256(zipfile_path)):
        raise ValueError("CONSUMER_SHA_OR_COMMERCE_HOLD_INVALID")
    with zipfile.ZipFile(str(zipfile_path)) as z:
        infos=z.infolist()
        if not infos or len(infos)>MAX_FILES or sum(t.file_size for t in infos)>MAX_UNPACKED_BYTES:
            raise ValueError("CONSUMER_EXPANSION_LIMIT")
        needed={"product/calculator.py","product/example_inputs.json",
                "guide/START_HERE.md","qa/SHA256SUMS.txt","license/REVIEW_REQUIRED.txt"}
        names={t.filename for t in infos}
        if not needed.issubset(names) or z.testzip() is not None:
            raise ValueError("CONSUMER_ZIP_FILE_CONTRACT_INVALID")
        for info in infos:
            name=info.filename
            if (name.startswith("/") or "\\" in name or ".." in name.split("/")
                    or (info.external_attr >> 16) & 0o170000==0o120000):
                raise ValueError("CONSUMER_ZIP_UNSAFE")
        if b"NOT LICENSED FOR PUBLIC RESALE" not in z.read("license/REVIEW_REQUIRED.txt"):
            raise ValueError("CONSUMER_LICENSE_HOLD_INVALID")
        for line in z.read("qa/SHA256SUMS.txt").decode("utf8").splitlines():
            sha,sep,filename=line.partition("  ")
            if not sep or not DIGEST.fullmatch(sha) or filename not in names:
                raise ValueError("CONSUMER_MEMBER_HASH_RECORD_INVALID")
            if hashlib.sha256(z.read(filename)).hexdigest()!=sha:
                raise ValueError("CONSUMER_MEMBER_HASH_MISMATCH")
    return meta


def consumer_status(root,recipe,version):
    dest,receipt=consumer_paths(root,recipe,version)
    if dest.is_symlink() or receipt.is_symlink() or not receipt.is_file():
        return False
    try:
        state=json.loads(receipt.read_text("utf8"))
        info=verify_consumer(root,recipe,version,dest/"customer-package.zip",
                             dest/"candidate_manifest.json")
        return (state.get("schema")=="saeit.store.consumer-private-receipt.v1"
                and state.get("status")=="received_private_customer"
                and state.get("product_id")==recipe
                and state.get("version")==version
                and state.get("package_sha256")==info["package_sha256"])
    except (OSError,ValueError,TypeError,zipfile.BadZipFile):
        return False


def consumer_finalize(root,recipe,version):
    target,receipt=consumer_paths(root,recipe,version)
    incoming=root/"incoming"/"consumer"/recipe/version
    bundle=incoming/"customer-package.zip.partial"
    meta=incoming/"candidate_manifest.json.partial"
    doc=verify_consumer(root,recipe,version,bundle,meta)
    if consumer_status(root,recipe,version):
        return True
    secure_directory(target)
    dest_zip=target/"customer-package.zip"
    dest_manifest=target/"candidate_manifest.json"
    if dest_zip.exists() or dest_manifest.exists() or receipt.exists():
        raise ValueError("CONSUMER_EXISTING_VERSION_CONFLICT")
    for src,dest in ((bundle,dest_zip),(meta,dest_manifest)):
        os.chmod(str(src),0o600)
        os.replace(str(src),str(dest))
    if sha256(dest_zip)!=doc["package_sha256"]:
        raise ValueError("CONSUMER_COPY_SHA_FAILED")
    atomic_json(receipt,{"schema":"saeit.store.consumer-private-receipt.v1",
        "product_id":recipe,"version":version,"package_sha256":doc["package_sha256"],
        "status":"received_private_customer","public_listing":False,
        "order_fulfillment_enabled":False,"independent_approval_pending":True})
    return True


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "status", "finalize",
                                                    "consumer-prepare","consumer-status","consumer-finalize"))
    parser.add_argument("recipe")
    parser.add_argument("digest")
    parser.add_argument("--root", required=True)
    args = parser.parse_args(argv)
    if not SLUG.fullmatch(args.recipe) or not DIGEST.fullmatch(args.digest):
        raise ValueError("INVALID_RECIPE_OR_DIGEST")
    root = Path(args.root).expanduser().resolve()
    if args.mode == "consumer-prepare":
        secure_directory(root)
        secure_directory(root/"incoming"/"consumer"/args.recipe/args.digest)
        print("STORE_CONSUMER_PRIVATE_INBOX_READY")
    elif args.mode == "consumer-finalize":
        consumer_finalize(root,args.recipe,args.digest)
        print("STORE_CONSUMER_PRIVATE_RECEIPT_CREATED")
    elif args.mode == "consumer-status":
        if not consumer_status(root,args.recipe,args.digest):
            print("STORE_CONSUMER_NOT_RECEIVED")
            return 1
        print("STORE_CONSUMER_PRIVATE_RECEIPT_VERIFIED")
    elif args.mode == "prepare":
        secure_directory(root)
        secure_directory(root / "incoming" / args.recipe)
        print("STORE_PRIVATE_INBOX_READY")
    elif args.mode == "finalize":
        finalize(root, args.recipe, args.digest)
        print("STORE_PRIVATE_RECEIPT_CREATED")
    elif args.mode == "status":
        if not status(root, args.recipe, args.digest):
            print("STORE_NOT_RECEIVED")
            return 1
        print("STORE_PRIVATE_RECEIPT_VERIFIED")
    print("STORE_PUBLICATION_ENABLED=false")
    return 0


# Fixed, nonsecret policy codes only: no exception message, path, account or
# manifest text may be printed to GitHub Actions diagnostics.
SAFE_FINALIZE_REASONS = frozenset({
    "INBOX_SYMLINK_REJECTED", "INBOX_DIRECTORY_INVALID",
    "INVALID_RECIPE_OR_DIGEST", "SYMLINK_IN_UPLOAD", "INCOMPLETE_UPLOAD",
    "INVALID_ARCHIVE_SIZE", "MANIFEST_TOO_LARGE", "BAD_MANIFEST",
    "MANIFEST_IDENTITY_MISMATCH", "UNSAFE_OR_UNREVIEWED_MANIFEST",
    "SHA256_MISMATCH", "F34_EVIDENCE_CONTRACT_INVALID",
    "F34_EXACT_ICON_PACKAGE_INVALID", "ARCHIVE_FILE_COUNT_INVALID",
    "ARCHIVE_EXPANSION_LIMIT", "UNSAFE_ARCHIVE_MEMBER", "CORRUPT_ARCHIVE",
})


def safe_finalize_reason(error):
    reason = str(error)
    return reason if type(error) is ValueError and reason in SAFE_FINALIZE_REASONS else None


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as err:
        print("STORE_RECEIVER_ERROR=" + type(err).__name__, file=sys.stderr)
        code = safe_finalize_reason(err)
        if code:
            print("STORE_RECEIVER_SAFE_REASON=" + code, file=sys.stderr)
        sys.exit(1)
