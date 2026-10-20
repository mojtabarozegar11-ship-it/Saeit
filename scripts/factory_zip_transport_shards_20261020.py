#!/usr/bin/env python3
"""Lossless private transport shards for QA-only collections.

NEVER edits manufactured goods, claims rights, creates a sale, or changes sites.
Every <=80-file ZIP is independently checked against the original source bytes.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile

RECIPES = (
    "fieldwork_arithmetic_assessment_packs",
    "fieldwork_arithmetic_mini_courses",
    "fieldwork_arithmetic_teacher_kits",
    "fieldwork_offline_operations_guides",
    "fieldwork_vector_illustration_suite",
)
NAME = re.compile(r"^[a-z][a-z0-9_]{1,80}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
MAX_ZIP = 25 * 1024 * 1024
MAX_UNPACKED = 100 * 1024 * 1024
MAX_FILES = 80
MAX_ORIGINAL_FILES = 600
SCHEMA = "saeit.factory.private-lossless-shards.v1"

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def filehash(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for data in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()

def load(path):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 200000:
        raise ValueError("SHARD_SOURCE_METADATA_UNSAFE")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("SHARD_SOURCE_METADATA_INVALID")
    return data

def good_file(name, recipe):
    if not isinstance(name, str) or not name.startswith(recipe + "/"):
        return False
    suffix = name[len(recipe) + 1:]
    return bool(suffix and len(name) <= 255 and "\\" not in name and
                all(x not in ("", ".", "..") for x in name.split("/")))

def source(root, recipe):
    if not NAME.fullmatch(recipe):
        raise ValueError("SHARD_RECIPE_ID_INVALID")
    folder = root / "digital-products" / recipe
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("SHARD_SOURCE_FOLDER_MISSING")
    manifest_file = folder / "manufacturing_manifest.json"
    archive_file = folder / (recipe + "-internal-qa.zip")
    meta = load(manifest_file)
    if archive_file.is_symlink() or not archive_file.is_file() or not 100 <= archive_file.stat().st_size <= MAX_ZIP:
        raise ValueError("SHARD_SOURCE_ARCHIVE_INVALID")
    original_digest = filehash(archive_file)
    if (meta.get("recipe") != recipe or meta.get("qa_status") != "passed" or
        meta.get("artifact_sha256") != original_digest or
        not isinstance(meta.get("source_sha256"), str) or
        not SHA.fullmatch(meta["source_sha256"]) or
        meta.get("owner_publication_approval") is True or
        meta.get("public_listing_enabled") is True):
        raise ValueError("SHARD_SOURCE_MANIFEST_MISMATCH")
    members = []
    with zipfile.ZipFile(archive_file) as archive:
        infos = archive.infolist()
        if (len(infos) <= MAX_FILES or len(infos) > MAX_ORIGINAL_FILES or
            sum(x.file_size for x in infos) > MAX_UNPACKED or
            archive.testzip() is not None):
            raise ValueError("SHARD_ORIGINAL_COLLECTION_INVALID")
        if len({x.filename for x in infos}) != len(infos):
            raise ValueError("SHARD_DUPLICATE_FILE")
        for info in infos:
            if (info.is_dir() or info.flag_bits & 1 or info.file_size > MAX_ZIP or
                not good_file(info.filename, recipe) or
                (info.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError("SHARD_UNSAFE_ORIGINAL_MEMBER")
            raw = archive.read(info)
            members.append({"name": info.filename, "sha256": digest(raw), "bytes": len(raw)})
    return archive_file, original_digest, filehash(manifest_file), members

def inspect_parts(directory, receipt, original):
    shards = receipt.get("parts")
    files = receipt.get("files")
    if not isinstance(shards, list) or not shards or not isinstance(files, list):
        raise ValueError("SHARD_RECEIPT_INVALID")
    original_by_name = {x["name"]: x for x in original}
    if files != original:
        raise ValueError("SHARD_SOURCE_CHANGED")
    recovered = {}
    for part in shards:
        name = part.get("file")
        if not isinstance(name, str) or not re.fullmatch(r"part-[0-9]{3}\.zip", name):
            raise ValueError("SHARD_PART_NAME_INVALID")
        path = directory / name
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_ZIP:
            raise ValueError("SHARD_PART_MISSING")
        if filehash(path) != part.get("sha256"):
            raise ValueError("SHARD_PART_SHA_MISMATCH")
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if (not infos or len(infos) > MAX_FILES or
                sum(x.file_size for x in infos) > MAX_UNPACKED or
                archive.testzip() is not None):
                raise ValueError("SHARD_PART_LIMIT")
            for info in infos:
                if info.filename not in original_by_name or info.filename in recovered:
                    raise ValueError("SHARD_EXTRA_OR_DUPLICATE_MEMBER")
                raw = archive.read(info)
                if digest(raw) != original_by_name[info.filename]["sha256"]:
                    raise ValueError("SHARD_CONTENT_MISMATCH")
                recovered[info.filename] = original_by_name[info.filename]
    if len(recovered) != len(original):
        raise ValueError("SHARD_LOSSY_REASSEMBLY")
    return len(recovered)

def build_one(root, recipe):
    archive, archive_hash, manifest_hash, members = source(root, recipe)
    output = root / "product-lifecycle" / "private-transport-shards"
    if output.is_symlink():
        raise ValueError("SHARD_OUTPUT_SYMLINK")
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(output, 0o700)
    folder = output / recipe
    if folder.is_symlink():
        raise ValueError("SHARD_RECIPE_SYMLINK")
    folder.mkdir(mode=0o700, exist_ok=True)
    version = folder / archive_hash
    if version.is_symlink():
        raise ValueError("SHARD_VERSION_SYMLINK")
    if version.exists():
        receipt = load(version / "receipt.json")
        if (receipt.get("schema") != SCHEMA or receipt.get("recipe") != recipe or
            receipt.get("original_zip_sha256") != archive_hash or
            receipt.get("manufacturing_manifest_sha256") != manifest_hash or
            receipt.get("public_distribution_allowed") is not False or
            receipt.get("commercial_review_complete") is not False):
            raise ValueError("SHARD_IMMUTABLE_RECEIPT_CONFLICT")
        restored = inspect_parts(version, receipt, members)
        return {"recipe": recipe, "created": False, "parts": len(receipt["parts"]), "verified_members": restored}
    with tempfile.TemporaryDirectory(prefix=".transport-", dir=str(folder)) as temp:
        pending = Path(temp)
        parts = []
        with zipfile.ZipFile(archive) as src:
            for idx in range(0, len(members), MAX_FILES):
                chunk = members[idx:idx + MAX_FILES]
                name = "part-%03d.zip" % (idx // MAX_FILES + 1)
                partfile = pending / name
                with zipfile.ZipFile(partfile, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=8) as out:
                    for file in chunk:
                        entry = zipfile.ZipInfo(file["name"], (2020, 1, 1, 0, 0, 0))
                        entry.compress_type = zipfile.ZIP_DEFLATED
                        entry.external_attr = 0o100644 << 16
                        out.writestr(entry, src.read(file["name"]))
                if not 0 < partfile.stat().st_size <= MAX_ZIP:
                    raise ValueError("SHARD_PART_TOO_LARGE")
                os.chmod(partfile, 0o600)
                parts.append({"file": name, "sha256": filehash(partfile), "members": len(chunk)})
        receipt = {"schema": SCHEMA, "recipe": recipe,
                   "original_zip_sha256": archive_hash, "manufacturing_manifest_sha256": manifest_hash,
                   "original_files": len(members), "files": members, "parts": parts,
                   "reconstruction_verified": False, "technical_transfer_only": True,
                   "commercial_review_complete": False, "owner_publication_approval": False,
                   "public_distribution_allowed": False, "sale_enabled": False}
        # The source-to-shard byte comparison is mandatory before publishing this private receipt.
        restored = inspect_parts(pending, receipt, members)
        receipt["reconstruction_verified"] = (restored == len(members))
        receipt_file = pending / "receipt.json"
        receipt_file.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        os.chmod(receipt_file, 0o600)
        os.chmod(pending, 0o700)
        # A version is immutable; concurrent owners must not silently replace one.
        if version.exists():
            raise ValueError("SHARD_CONCURRENT_VERSION_PRESENT")
        os.rename(pending, version)
    return {"recipe": recipe, "created": True, "parts": len(parts), "verified_members": restored}

def cycle(root, recipes=RECIPES):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("SHARD_FACTORY_ROOT_INVALID")
    results = [build_one(root, name) for name in recipes]
    return {"schema": SCHEMA, "products": results,
            "products_verified": len(results), "total_parts": sum(x["parts"] for x in results),
            "all_source_members_restored": sum(x["verified_members"] for x in results),
            "publications": 0, "sales": 0}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-private-root", required=True)
    args = parser.parse_args()
    report = cycle(args.factory_private_root)
    print("FACTORY_PRIVATE_SHARDS=" + json.dumps(report, sort_keys=True))

if __name__ == "__main__":
    main()
