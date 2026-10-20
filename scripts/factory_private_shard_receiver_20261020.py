#!/usr/bin/env python3
"""Independent, private cPanel proof of lossless factory transport only.
Never touches document roots, Django, payment records or product listings.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tarfile
import tempfile
import zipfile

RECIPES = frozenset((
    "fieldwork_arithmetic_assessment_packs",
    "fieldwork_arithmetic_mini_courses",
    "fieldwork_arithmetic_teacher_kits",
    "fieldwork_offline_operations_guides",
    "fieldwork_vector_illustration_suite",
))
SHA = re.compile(r"^[a-f0-9]{64}$")
PART = re.compile(r"^part-[0-9]{3}\.zip$")
RECEIPT_SCHEMA = "saeit.factory.private-lossless-shards.v1"
BATCH_SCHEMA = "saeit.factory.cpanel-private-transport-proof.v1"
MAX_TAR = 160 * 1024 * 1024
MAX_PACKAGE = 25 * 1024 * 1024
MAX_UNPACKED = 100 * 1024 * 1024
MAX_FILES = 80

def sha(data):
    return hashlib.sha256(data).hexdigest()

def file_sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for b in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()

def strict_private_dir(path):
    if path.is_symlink():
        raise ValueError("CPANEL_PRIVATE_DESTINATION_SYMLINK")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.is_dir() or path.is_symlink():
        raise ValueError("CPANEL_PRIVATE_DESTINATION_INVALID")
    os.chmod(path, 0o700)

def verify(root):
    products = []
    total_parts = 0
    total_members = 0
    for recipe in sorted(RECIPES):
        directory = root / "private-transport-shards" / recipe
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError("CPANEL_COLLECTION_MISSING")
        versions = list(directory.iterdir())
        if len(versions) != 1 or versions[0].is_symlink() or not versions[0].is_dir():
            raise ValueError("CPANEL_COLLECTION_VERSION_INVALID")
        version = versions[0]
        if not SHA.fullmatch(version.name):
            raise ValueError("CPANEL_COLLECTION_VERSION_HASH_INVALID")
        receipt_path = version / "receipt.json"
        if receipt_path.is_symlink() or not receipt_path.is_file() or receipt_path.stat().st_size > 200000:
            raise ValueError("CPANEL_COLLECTION_RECEIPT_MISSING")
        doc = json.loads(receipt_path.read_text(encoding="utf8"))
        if (doc.get("schema") != RECEIPT_SCHEMA or doc.get("recipe") != recipe or
            doc.get("original_zip_sha256") != version.name or
            doc.get("reconstruction_verified") is not True or
            doc.get("technical_transfer_only") is not True or
            doc.get("commercial_review_complete") is not False or
            doc.get("owner_publication_approval") is not False or
            doc.get("public_distribution_allowed") is not False or
            doc.get("sale_enabled") is not False):
            raise ValueError("CPANEL_COLLECTION_COMMERCIAL_GATE_OR_PROVENANCE")
        files = doc.get("files")
        parts = doc.get("parts")
        if (not isinstance(files, list) or not 80 < len(files) <= 600 or
            not isinstance(parts, list) or len(parts) < 2 or len(parts) > 8 or
            doc.get("original_files") != len(files)):
            raise ValueError("CPANEL_COLLECTION_FILE_INDEX_INVALID")
        expected = {}
        for entry in files:
            if not isinstance(entry, dict):
                raise ValueError("CPANEL_COLLECTION_FILE_ITEM_INVALID")
            name = entry.get("name")
            digest = entry.get("sha256")
            size = entry.get("bytes")
            if (not isinstance(name, str) or not name.startswith(recipe + "/") or
                "\\" in name or any(s in ("", ".", "..") for s in name.split("/")) or
                not isinstance(digest, str) or not SHA.fullmatch(digest) or
                type(size) is not int or size < 0 or size > MAX_PACKAGE or name in expected):
                raise ValueError("CPANEL_COLLECTION_FILE_ENTRY_UNSAFE")
            expected[name] = (digest, size)
        verified = set()
        used = set()
        for part in parts:
            if not isinstance(part, dict):
                raise ValueError("CPANEL_PART_RECORD_INVALID")
            name = part.get("file")
            digest = part.get("sha256")
            if (not isinstance(name, str) or not PART.fullmatch(name) or name in used or
                not isinstance(digest, str) or not SHA.fullmatch(digest) or
                type(part.get("members")) is not int or not 1 <= part["members"] <= MAX_FILES):
                raise ValueError("CPANEL_PART_RECORD_INVALID")
            used.add(name)
            target = version / name
            if target.is_symlink() or not target.is_file() or not 0 < target.stat().st_size <= MAX_PACKAGE:
                raise ValueError("CPANEL_PART_FILE_INVALID")
            if file_sha(target) != digest:
                raise ValueError("CPANEL_PART_DIGEST_MISMATCH")
            with zipfile.ZipFile(target) as z:
                infos = z.infolist()
                if (len(infos) != part["members"] or len(infos) > MAX_FILES or
                    sum(i.file_size for i in infos) > MAX_UNPACKED or z.testzip() is not None):
                    raise ValueError("CPANEL_PART_ARCHIVE_INVALID")
                for info in infos:
                    name = info.filename
                    if (name not in expected or name in verified or info.is_dir() or info.flag_bits & 1 or
                        (info.external_attr >> 16) & 0o170000 == 0o120000):
                        raise ValueError("CPANEL_PART_MEMBER_UNSAFE")
                    raw = z.read(info)
                    if (len(raw), sha(raw)) != (expected[name][1], expected[name][0]):
                        raise ValueError("CPANEL_PART_MEMBER_HASH_MISMATCH")
                    verified.add(name)
        if verified != set(expected):
            raise ValueError("CPANEL_PARTS_DO_NOT_RECONSTRUCT_ORIGINAL")
        actual = {x.name for x in version.iterdir()}
        if actual != used | {"receipt.json"}:
            raise ValueError("CPANEL_EXTRA_UNTRUSTED_PACKAGE_FILE")
        total_parts += len(parts)
        total_members += len(verified)
        products.append({"recipe": recipe, "original_sha256": version.name,
                         "shards": len(parts), "reconstructed_files": len(verified)})
    if len(products) != 5 or total_parts != 10 or total_members != 485:
        raise ValueError("CPANEL_COLLECTION_BATCH_SIZE_MISMATCH")
    return {"schema": BATCH_SCHEMA, "products_verified": len(products),
            "shards_verified": total_parts, "files_reconstructed": total_members,
            "products": products, "private_reconstruction_passed": True,
            "publicly_published": False, "store_product_created": False,
            "customer_payment_created": False, "independent_content_review": False,
            "owner_publication_approval": False}

def receive(archive_file, dest_root):
    archive_file = Path(archive_file)
    dest_root = Path(dest_root)
    if (archive_file.is_symlink() or not archive_file.is_file() or
        not 0 < archive_file.stat().st_size <= MAX_TAR):
        raise ValueError("CPANEL_INPUT_ARCHIVE_UNSAFE")
    strict_private_dir(dest_root)
    archive_sha = file_sha(archive_file)
    final = dest_root / archive_sha
    if final.is_symlink():
        raise ValueError("CPANEL_BATCH_SYMLINK")
    if final.exists():
        receipt = final / "verification.json"
        if not receipt.is_file() or receipt.is_symlink():
            raise ValueError("CPANEL_PRIOR_RECEIPT_INVALID")
        existing = verify(final)
        recorded = json.loads(receipt.read_text(encoding="utf8"))
        if recorded != dict(existing, encrypted_transport_archive_sha256=archive_sha):
            raise ValueError("CPANEL_PRIOR_RECEIPT_CONFLICT")
        return recorded
    with tempfile.TemporaryDirectory(prefix=".private-collection-", dir=str(dest_root)) as temporary:
        stage = Path(temporary)
        seen = set()
        total = 0
        with tarfile.open(archive_file, mode="r:gz") as stream:
            entries = stream.getmembers()
            if len(entries) > 50:
                raise ValueError("CPANEL_TAR_TOO_MANY_ENTRIES")
            for member in entries:
                normalized = member.name.rstrip("/")
                segments = normalized.split("/")
                if not segments or segments[0] != "private-transport-shards":
                    raise ValueError("CPANEL_TAR_PATH_INVALID")
                if (len(segments) > 4 or any(x in ("", ".", "..") for x in segments) or
                    "\\" in normalized or member.issym() or member.islnk() or
                    member.isdev() or member.isfifo()):
                    raise ValueError("CPANEL_TAR_MEMBER_UNSAFE")
                if member.isdir():
                    continue
                if (not member.isfile() or len(segments) != 4 or
                    segments[1] not in RECIPES or not SHA.fullmatch(segments[2]) or
                    not (segments[3] == "receipt.json" or PART.fullmatch(segments[3])) or
                    not 0 < member.size <= MAX_PACKAGE):
                    raise ValueError("CPANEL_TAR_FILE_UNSAFE")
                if normalized in seen:
                    raise ValueError("CPANEL_TAR_DUPLICATE_FILE")
                seen.add(normalized)
                total += member.size
                if total > MAX_TAR:
                    raise ValueError("CPANEL_TAR_EXTRACT_LIMIT")
                out = stage.joinpath(*segments)
                out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                with stream.extractfile(member) as source, out.open("xb") as target:
                    shutil.copyfileobj(source, target, length=1024 * 1024)
                os.chmod(out, 0o600)
        if len(seen) != 15:
            raise ValueError("CPANEL_TAR_FILE_COUNT_MISMATCH")
        report = verify(stage)
        report = dict(report, encrypted_transport_archive_sha256=archive_sha)
        proof = stage / "verification.json"
        proof.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf8")
        os.chmod(proof, 0o600)
        if final.exists():
            raise ValueError("CPANEL_CONCURRENT_BATCH")
        os.rename(stage, final)
    return report

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tar", required=True)
    parser.add_argument("--private-root", required=True)
    a = parser.parse_args()
    report = receive(a.tar, a.private_root)
    print("CPANEL_REAL_PRIVATE_SHARD_RECEIPT=" + json.dumps(report, sort_keys=True))

if __name__ == "__main__":
    main()
