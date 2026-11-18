#!/usr/bin/env python3
"""Build a reproducible, NO-DEPLOY B2B static publication bundle.

Includes only two explicitly listed public HTML files from this exact checkout.
It never connects to a host, reads private data, or deploys a live page.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import zipfile

HERE = Path(__file__).resolve().parents[1]
PAGES = {
    "b2b/index.html": "public/b2b/index.html",
    "b2b/privacy/index.html": "public/b2b/privacy/index.html",
}
MAX_BYTES = 128 * 1024
FIXED_DATE = (2026, 11, 18, 0, 0, 0)


def _load_exact(root: Path) -> dict[str, bytes]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("unsafe source root")
    pages = {}
    for member, relative in PAGES.items():
        source = root
        for component in Path(relative).parts:
            source = source / component
            meta = source.lstat()
            if stat.S_ISLNK(meta.st_mode):
                raise ValueError("symbolic link forbidden")
            if source != root / relative and not stat.S_ISDIR(meta.st_mode):
                raise ValueError("non-directory parent")
        if not stat.S_ISREG(meta.st_mode) or meta.st_size <= 0 or meta.st_size > MAX_BYTES:
            raise ValueError("unsafe HTML source")
        raw = source.read_bytes()
        if len(raw) != meta.st_size:
            raise ValueError("HTML source changed during read")
        txt = raw.decode("utf-8")
        if "<!doctype html>" not in txt.lower() or 'lang="en"' not in txt:
            raise ValueError("invalid English HTML")
        if "<form" in txt.lower() or "zomorodmelal@gmail.com" not in txt:
            raise ValueError("unreviewed form or lost official email")
        if member == "b2b/index.html":
            if 'href="/b2b/privacy/"' not in txt or "mailto:zomorodmelal@gmail.com" not in txt:
                raise ValueError("missing contact/privacy link")
        if member == "b2b/privacy/index.html" and "/b2b/" not in txt:
            raise ValueError("missing return path")
        pages[member] = raw
    return pages


def manifest_for(pages: dict[str, bytes], source_sha: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("invalid pinned commit SHA")
    return {
        "schema": "zomorod.b2b.mailonly.static_bundle.v1",
        "source_commit": source_sha,
        "production_deployed": False,
        "approved_for_payments": False,
        "safe_scope": "create-only-b2b-pages-no-homepage-overwrite",
        "files": {k: {
            "size": len(v),
            "sha256": hashlib.sha256(v).hexdigest()
        } for k, v in sorted(pages.items())}
    }


def _member(name: str, data: bytes) -> tuple[zipfile.ZipInfo, bytes]:
    info = zipfile.ZipInfo(name, FIXED_DATE)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info, data


def archive_bytes(root: Path, source_sha: str) -> bytes:
    pages = _load_exact(root)
    manifest = manifest_for(pages, source_sha)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, raw in sorted(pages.items()):
            info, data = _member(name, raw)
            bundle.writestr(info, data)
        info, data = _member("MANIFEST.json",
            (json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2)+"\n").encode("utf-8"))
        bundle.writestr(info, data)
    return out.getvalue()


def verify_archive(raw: bytes, source_sha: str) -> dict:
    with zipfile.ZipFile(io.BytesIO(raw), "r") as bundle:
        if sorted(bundle.namelist()) != sorted([*PAGES, "MANIFEST.json"]):
            raise ValueError("unexpected file added to bundle")
        if bundle.testzip() is not None:
            raise ValueError("corrupt ZIP")
        manifest = json.loads(bundle.read("MANIFEST.json"))
        if manifest["source_commit"] != source_sha or manifest["production_deployed"] is not False:
            raise ValueError("incorrect release metadata")
        if sorted(manifest["files"]) != sorted(PAGES):
            raise ValueError("manifest missing an expected file")
        for member in PAGES:
            raw_member = bundle.read(member)
            proof = manifest["files"][member]
            if len(raw_member) != proof["size"] or hashlib.sha256(raw_member).hexdigest() != proof["sha256"]:
                raise ValueError("asset hash mismatch")
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Build source-only B2B pages; NEVER deploy")
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", help="artifact ZIP path, GitHub runner only")
    args = parser.parse_args()
    data = archive_bytes(HERE, args.source_sha)
    manifest = verify_archive(data, args.source_sha)
    if args.output:
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise ValueError("ZIP creation available only on GitHub Actions, never directly on cPanel")
        destination = Path(args.output)
        tmp = Path(os.environ.get("RUNNER_TEMP", "/nonexistent"))
        if not tmp.is_absolute() or tmp.is_symlink() or not tmp.is_dir() or destination.parent != tmp or destination.suffix != ".zip":
            raise ValueError("ZIP output must be a direct child of RUNNER_TEMP")
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
    print("ZOMOROD_B2B_STATIC_PACKAGE="+json.dumps({
        "schema":manifest["schema"],"files":manifest["files"],
        "source_commit":manifest["source_commit"],
        "zip_sha256":hashlib.sha256(data).hexdigest(),
        "zip_bytes":len(data),"production_deployed":False,
    },sort_keys=True))


if __name__ == "__main__":
    main()
