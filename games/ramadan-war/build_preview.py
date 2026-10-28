#!/usr/bin/env python3
"""Build a verifiable, offline-capable web preview from the *tested* game assets.

No live deployment, wallet, token transaction or production data is involved.
The package is emitted only after the CI model-download and browser QA steps.
"""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

# Resolve the sibling release manifest explicitly: pytest or another app may
# already have imported an unrelated module named "deploy".
import importlib.util
_DEPLOY_SPEC = importlib.util.spec_from_file_location(
    "ramadan_preview_deploy", Path(__file__).with_name("deploy.py"))
_DEPLOY_MODULE = importlib.util.module_from_spec(_DEPLOY_SPEC)
_DEPLOY_SPEC.loader.exec_module(_DEPLOY_MODULE)
ASSETS = _DEPLOY_MODULE.ASSETS

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
        if not isinstance(rel, str) or not rel or rel == "preview-manifest.json" or "\\" in rel:
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
        "source_revision": (os.environ.get("GITHUB_SHA", "").lower()
                            if len(os.environ.get("GITHUB_SHA", "")) == 40
                            and all(c in "0123456789abcdef"
                                    for c in os.environ.get("GITHUB_SHA", "").lower())
                            else "unversioned"),
        "payment_status": "disabled",
        "files": {name: {"sha256": sha(data), "bytes": len(data)}
                  for name, data in sorted(payload.items())},
    }
    manifest_data = (json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":")) + "\n").encode("utf-8")

    # The browser's ES modules cannot reliably run from file:// URLs.
    # Ship an exact, self-contained launch recipe with every preview.
    readme_data = (
        "Ramadan War Web — standalone preview\n"
        "Revision: " + manifest["source_revision"] + "\n"
        "Extract this ZIP, then run from the extracted parent directory:\n"
        "  python3 -m http.server 8765 --directory ramadan-war\n"
        "On this computer open http://127.0.0.1:8765/. For a phone on the same LAN,\n"
        "open http://HOST_LAN_IP:8765/ (only on a trusted private network).\nUse a local HTTP server; file:// is unsupported.\n"
        "The game runs locally; no MOJ1 wallet or payment is enabled.\n"
        "This is a QA preview, not a verified public or commercial release.\n"
    ).encode("utf-8")

    # Never follow an output symlink or an existing linked ancestor. The final
    # archive must be outside the game tree even when the caller uses a relative
    # path or a directory alias.
    if any(part.is_symlink() for part in (output, *output.parents)):
        raise ValueError("symlinked preview output path")
    if output.resolve().is_relative_to(root):
        raise ValueError("preview archive must be outside game source")
    output.parent.mkdir(parents=True, exist_ok=True)
    if any(part.is_symlink() for part in (output, *output.parents)):
        raise ValueError("symlinked preview output path")

    # Do not truncate a previously verified preview if the new build fails,
    # runs out of space, or fails CRC/SHA validation. Publish atomically only
    # after every byte has been checked, and clean up incomplete temp files.
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w+b", dir=output.parent, prefix=".ramadan-preview-",
                suffix=".zip", delete=False) as temp:
            temp_path = Path(temp.name)
            with ZipFile(temp, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
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
                info = ZipInfo("ramadan-war/PLAY-README.txt",
                               date_time=(2020, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, readme_data)
            temp.flush()
            os.fsync(temp.fileno())

        with ZipFile(temp_path) as archive:
            if archive.testzip() is not None:
                raise RuntimeError("preview ZIP CRC validation failed")
            expected_names = {"ramadan-war/" + name for name in payload}
            expected_names.update({"ramadan-war/preview-manifest.json",
                                   "ramadan-war/PLAY-README.txt"})
            if len(archive.namelist()) != len(expected_names) or set(archive.namelist()) != expected_names:
                raise RuntimeError("preview ZIP asset list mismatch")
            if archive.read("ramadan-war/preview-manifest.json") != manifest_data:
                raise RuntimeError("preview manifest mismatch")
            if archive.read("ramadan-war/PLAY-README.txt") != readme_data:
                raise RuntimeError("preview launch guide mismatch")
            for rel, data in payload.items():
                if sha(archive.read("ramadan-war/" + rel)) != sha(data):
                    raise RuntimeError("preview archive SHA-256 mismatch: " + rel)
        archive_sha = sha(temp_path.read_bytes())
        archive_bytes = temp_path.stat().st_size
        if output.is_symlink() or any(p.is_symlink() for p in output.parents):
            raise ValueError("symlinked preview output path")
        os.replace(temp_path, output)
        temp_path = None
        return {"asset_count": len(payload), "archive_sha256": archive_sha,
                "archive_bytes": archive_bytes}
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = build_preview(Path(__file__).resolve().parent, args.output, ASSETS, MODEL_SIZES)
    print("RAMADAN_PLAYABLE_PREVIEW_ZIP=PASS " + json.dumps(result, sort_keys=True),
          flush=True)
