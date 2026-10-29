#!/usr/bin/env python3
"""S-01 -> G-01: independent read-only gate for a Ramadan War CI preview ZIP.

Only verifies an offline artifact. No deployment, payment, secrets, or server writes.
Require exact Git blob SHA of the tested game.js and CI merge revision supplied by G.
"""
import argparse
import hashlib
import io
import json
import re
import stat
from pathlib import PurePosixPath
from zipfile import ZipFile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def checked_entries(archive, expected):
    infos = archive.infolist()
    # Bound decompression before CRC or payload reads. An exact manifest alone
    # does not prevent a compressed preview from exhausting runner memory.
    if len(infos) > 100 or sum(i.file_size for i in infos) > 96_000_000:
        raise ValueError("preview archive exceeds bounded extraction budget")
    if any(i.file_size > 1_000_000 and
           i.file_size > max(i.compress_size, 1) * 1000 for i in infos):
        raise ValueError("preview archive compression ratio unsafe")
    names = [i.filename for i in infos]
    if len(names) != len(set(names)) or (expected is not None and set(names) != expected):
        raise ValueError("archive entry set differs from manifest")
    for info in infos:
        name = info.filename
        path = PurePosixPath(name)
        if (not name or name.startswith("/") or "\\" in name or
                ".." in path.parts or path.as_posix() != name or
                name.endswith("/") or (info.external_attr >> 16) & 0o170000 == stat.S_IFLNK):
            raise ValueError("unsafe archive entry")
        if info.file_size > 12_000_000:
            raise ValueError("unexpectedly large preview asset")
    if archive.testzip() is not None:
        raise ValueError("archive CRC failed")


def verify(outer_bytes, expected_revision, expected_game_blob):
    if not re.fullmatch(r"[0-9a-f]{40}", expected_revision):
        raise ValueError("expected CI revision must be a full SHA-1")
    if not re.fullmatch(r"[0-9a-f]{40}", expected_game_blob):
        raise ValueError("expected game.js Git blob must be a full SHA-1")
    with ZipFile(io.BytesIO(outer_bytes)) as outer:
        checked_entries(outer, {"ramadan-war-preview.zip"})
        inner_bytes = outer.read("ramadan-war-preview.zip")
    with ZipFile(io.BytesIO(inner_bytes)) as inner:
        # Validate the entire nested ZIP's metadata and CRC before reading
        # even its manifest; untrusted manifest bytes cannot bypass limits.
        checked_entries(inner, None)
        root = "ramadan-war/"
        manifest_name = root + "preview-manifest.json"
        readme_name = root + "PLAY-README.txt"
        manifest = json.loads(inner.read(manifest_name))
        if (manifest.get("format") != "ramadan-war-offline-preview-v1" or
                manifest.get("payment_status") != "disabled" or
                manifest.get("source_revision") != expected_revision):
            raise ValueError("preview provenance or payment status mismatch")
        assets = manifest.get("files")
        if not isinstance(assets, dict) or len(assets) < 25:
            raise ValueError("missing expected preview assets")
        expected = {root + name for name in assets} | {manifest_name, readme_name}
        checked_entries(inner, expected)
        for name, info in assets.items():
            if not isinstance(info, dict) or not isinstance(name, str):
                raise ValueError("invalid manifest record")
            data = inner.read(root + name)
            if len(data) != info.get("bytes") or digest(data) != info.get("sha256"):
                raise ValueError("manifest digest/length mismatch: " + name)
        if git_blob(inner.read(root + "game.js")) != expected_game_blob:
            raise ValueError("artifact game.js differs from reviewed Git commit")
        if b"Revision: " + expected_revision.encode() not in inner.read(readme_name):
            raise ValueError("launch guide revision mismatch")
        policy = inner.read(root + "moj1-commerce-policy.mjs")
        if not all(flag in policy for flag in (
                b"checkoutEnabled:false", b"ownerApproved:false",
                b"verifiedBackend:false", b"contractAddress:null")):
            raise ValueError("payment policy is not demonstrably disabled")
        for required in ("index.html", "engine3d.js", "THREE-LICENSE.txt", "ASSET-CREDITS.md"):
            if required not in assets:
                raise ValueError("required runtime or attribution file missing")
        return {
            "result": "PASS_INTERNAL_PREVIEW_ONLY",
            "inner_sha256": digest(inner_bytes),
            "asset_count": len(assets),
            "revision": expected_revision,
            "game_blob": expected_game_blob,
            "payment_enabled": False,
            "live_deployed": False,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_zip")
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--expected-game-blob", required=True)
    args = parser.parse_args()
    from pathlib import Path
    print(json.dumps(verify(
        Path(args.artifact_zip).read_bytes(),
        args.expected_revision, args.expected_game_blob,
    ), sort_keys=True))
