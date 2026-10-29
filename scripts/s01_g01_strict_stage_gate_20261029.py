#!/usr/bin/env python3
"""S-01 independent G-01 ZIP acceptance: read-only, never deploys or charges."""
import hashlib
import json
from pathlib import Path
from pathlib import PurePosixPath
import re
import stat
import sys
import zipfile

PREFIX = "ramadan-war/"
REQUIRED = {
    "index.html", "game.js", "game.css", "engine3d.js",
    "save-validation.mjs", "campaign-backup.mjs", "objective-navigation.mjs",
    "moj1-commerce-policy.mjs", "m24-sniper-ccby.glb",
    "soldier-rigged-ccby.glb",
}
POLICY_FLAGS = ("ownerApproved", "checkoutEnabled", "verifiedBackend")
MAX_MEMBERS = 150
MAX_UNCOMPRESSED = 65_000_000
MAX_ARCHIVE_BYTES = 100_000_000
MAX_MANIFEST_BYTES = 1_000_000


def verify(package):
    package = Path(package)
    if package.is_symlink() or not package.is_file() or package.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("UNSAFE_OR_OVERSIZED_ARCHIVE")
    with zipfile.ZipFile(package) as archive:
        members = archive.infolist()
        names = [item.filename for item in members]
        if not names or len(names) > MAX_MEMBERS or len(names) != len(set(names)):
            raise ValueError("INVALID_MEMBER_SET")
        # Web and extraction targets may be case-insensitive. Never allow two
        # different archive members to overwrite the same runtime asset.
        if len(set(name.casefold() for name in names)) != len(names):
            raise ValueError("CASEFOLD_MEMBER_COLLISION")
        if sum(item.file_size for item in members) > MAX_UNCOMPRESSED:
            raise ValueError("UNCOMPRESSED_SIZE_LIMIT")
        # A file that is also a parent directory can overwrite or obstruct
        # assets when unpacked by platform-specific staging extractors.
        files = {item.filename for item in members if not item.is_dir()}
        for name in names:
            segments = name.rstrip("/").split("/")
            if any("/".join(segments[:index]) in files
                   for index in range(1, len(segments))):
                raise ValueError("FILE_DIRECTORY_MEMBER_COLLISION")
        for item in members:
            # Browser/staging extractors only guarantee stored or deflated ZIP.
            # Reject other methods rather than silently shipping unusable assets.
            if item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise ValueError("UNSUPPORTED_ZIP_COMPRESSION")
            unix_mode = item.external_attr >> 16
            kind = stat.S_IFMT(unix_mode)
            if item.create_system == 3 and kind not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise ValueError("UNSAFE_ARCHIVE_MEMBER_TYPE")
            if item.file_size > 5_000_000 and item.compress_size * 100 < item.file_size:
                raise ValueError("SUSPICIOUS_COMPRESSION_RATIO")
            name = item.filename
            parts = PurePosixPath(name).parts
            if (not name.startswith(PREFIX) or "\\" in name or
                    any(p in ("", ".", "..") for p in name.rstrip("/").split("/")) or
                    "//" in name or name.startswith("/") or
                    (item.flag_bits & 0x1) or
                    stat.S_IFMT(item.external_attr >> 16) == stat.S_IFLNK):
                raise ValueError("UNSAFE_ARCHIVE_MEMBER")
        actual = {
            name.removeprefix(PREFIX) for name in names
            if not name.endswith("/") and name != PREFIX + "preview-manifest.json"
        }
        if not REQUIRED <= actual or PREFIX + "preview-manifest.json" not in names:
            raise ValueError("MISSING_REQUIRED_RUNTIME")
        if archive.getinfo(PREFIX + "preview-manifest.json").file_size > MAX_MANIFEST_BYTES:
            raise ValueError("OVERSIZED_MANIFEST")
        manifest = json.loads(archive.read(PREFIX + "preview-manifest.json"))
        if not isinstance(manifest, dict) or not re.fullmatch(
            r"G01-R[0-9]+(?:[._-][A-Za-z0-9]+)*", str(manifest.get("version", ""))
        ):
            raise ValueError("INVALID_VERSION")
        declared = manifest.get("files")
        if not isinstance(declared, dict) or set(declared) != actual:
            raise ValueError("MANIFEST_COVERAGE_MISMATCH")
        for name, metadata in declared.items():
            if (not isinstance(name, str) or name.startswith("/") or
                    ".." in PurePosixPath(name).parts or "\\" in name or
                    not isinstance(metadata, dict)):
                raise ValueError("INVALID_MANIFEST_PATH")
            data = archive.read(PREFIX + name)
            if (type(metadata.get("bytes")) is not int or
                    metadata["bytes"] != len(data) or
                    metadata.get("sha256") != hashlib.sha256(data).hexdigest()):
                raise ValueError("MANIFEST_DIGEST_MISMATCH")
        policy = archive.read(PREFIX + "moj1-commerce-policy.mjs").decode("utf-8")
        if not all(re.search(r"\b" + flag + r"\s*:\s*false\b", policy)
                   for flag in POLICY_FLAGS):
            raise ValueError("MOJ1_DISABLED_SOURCE_FLAGS_MISSING")
        if not re.search(r"\bcontractAddress\s*:\s*null\b", policy):
            raise ValueError("MOJ1_CONTRACT_MUST_BE_NULL")
    # Never buffer an untrusted ZIP in memory merely to calculate its digest.
    digest = hashlib.sha256()
    with package.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "schema": "s01-g01-stage-acceptance.v1",
        "status": "READY_FOR_REVIEW",
        "file_verified": True,
        "source_flags_only_not_runtime_payment_proof": True,
        "deploy_authorized": False,
        "live_verified": False,
        "member_count": len(names),
        "package_sha256": digest.hexdigest(),
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python s01_g01_strict_stage_gate_20261029.py package.zip")
    try:
        print(json.dumps(verify(sys.argv[1]), sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "BLOCKED", "deploy_authorized": False,
                          "reason": str(exc)}, sort_keys=True))
        raise SystemExit(2)
