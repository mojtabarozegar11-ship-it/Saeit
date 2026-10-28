#!/usr/bin/env python3
"""Build a verifiable, offline-capable web preview from the *tested* game assets.

No live deployment, wallet, token transaction or production data is involved.
The package is emitted only after the CI model-download and browser QA steps.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from deploy import ASSETS

MODEL_SIZES = {
    "soldier-rigged-ccby.glb": 3094592,
    "m24-sniper-ccby.glb": 1247684,
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build_preview(source_dir, output_path, assets, expected_sizes=None):
    root = Path(source_dir)
    output = Path(output_path)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("preview source directory missing or symlinked")
    root = root.resolve()
    if not assets or len(assets) != len(set(assets)):
        raise ValueError("preview asset list empty or contains duplicates")
    payload = {}
    for rel in assets:
        if not isinstance(rel, str) or not rel or "\\" in rel:
            raise ValueError("unsafe preview asset name")
        path = Path(rel)
        if path.is_absolute() or ".." in path.parts or path.as_posix() != rel:
            raise ValueError("unsafe preview asset path: " + rel)
        if any((root.joinpath(*path.parts[:n])).is_symlink()
               for n in range(1, len(path.parts) + 1)):
            raise ValueError("symlinked preview asset: " + rel)
        source = root / path
        if not source.is_file() or not source.resolve().is_relative_to(root):
            raise ValueError("missing or escaping preview asset: " + rel)
        data = source.read_bytes()
        if not data:
            raise ValueError("empty preview asset: " + rel)
        if expected_sizes and rel in expected_sizes and len(data) != expected_sizes[rel]:
            raise ValueError("incomplete preview model: " + rel)
        payload[rel] = data

    manifest = {
        "format": "ramadan-war-offline-preview-v1",
        "payment_status": "disabled",
        "files": {name: {"sha256": sha(data), "bytes": len(data)}
                  for name, data in sorted(payload.items())},
    }
    manifest_data = (json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":")) + "\n").encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_symlink() or output.resolve() == root or output.is_relative_to(root):
        raise ValueError("preview archive must be outside game source")
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for rel, data in sorted(payload.items()):
            info = ZipInfo("ramadan-war/" + rel, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
        info = ZipInfo("ramadan-war/preview-manifest.json",
                       date_time=(2020, 1, 1, 0, 0, 0))
        info.compress_type = ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        archive.writestr(info, manifest_data)

    with ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("preview ZIP CRC validation failed")
        expected_names = {"ramadan-war/" + name for name in payload}
        expected_names.add("ramadan-war/preview-manifest.json")
        if set(archive.namelist()) != expected_names:
            raise RuntimeError("preview ZIP asset list mismatch")
        if archive.read("ramadan-war/preview-manifest.json") != manifest_data:
            raise RuntimeError("preview manifest mismatch")
        for rel, data in payload.items():
            if sha(archive.read("ramadan-war/" + rel)) != sha(data):
                raise RuntimeError("preview archive SHA-256 mismatch: " + rel)
    return {"asset_count": len(payload), "archive_sha256": sha(output.read_bytes()),
            "archive_bytes": output.stat().st_size}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = build_preview(Path(__file__).resolve().parent, args.output, ASSETS, MODEL_SIZES)
    print("RAMADAN_PLAYABLE_PREVIEW_ZIP=PASS " + json.dumps(result, sort_keys=True),
          flush=True)
