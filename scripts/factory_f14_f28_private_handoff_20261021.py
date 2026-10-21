#!/usr/bin/env python3
"""Fail-closed, hash-verifiable PRIVATE F14/F28 source handoff. No storefront interaction."""
import argparse
import hashlib
import io
import json
import os
import shutil
import tarfile
import tempfile
from pathlib import Path

SCHEMA = "saeit.factory.f14-f28-private-handoff.v1"
RECEIPT_SCHEMA = "saeit.factory.f14-f28-private-receipt.v1"
SOURCE = {
    "F14": "fab699b275f04ce69912c56e7d0a881ef9ee2d8d",
    "F28": "458052d5663102f0cc896047e1cad171bb80ef24",
}
MAP = {
    "F14/index.html": ("F14", "product_recipes/rootline_bloom_defense/index.html"),
    "F14/game.css": ("F14", "product_recipes/rootline_bloom_defense/game.css"),
    "F14/engine.js": ("F14", "product_recipes/rootline_bloom_defense/engine.js"),
    "F14/game.js": ("F14", "product_recipes/rootline_bloom_defense/game.js"),
    "F14/COMMERCIAL_PILOT.md": ("F14", "product_recipes/rootline_bloom_defense/COMMERCIAL_PILOT.md"),
    "F28/greenhouse_margin_lab_pilot.html": ("F28", "product_recipes/greenhouse_crop_margin/greenhouse_margin_lab_pilot.html"),
    "F28/COMMERCIAL_PILOT.md": ("F28", "product_recipes/greenhouse_crop_margin/COMMERCIAL_PILOT.md"),
}
FALSE_FLAGS = ("published", "payment_enabled", "commercially_approved",
               "specialist_review_passed", "rights_cleared", "owner_publication_approval")
MAX_ARCHIVE = 2_000_000

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def manifest(files):
    return {"schema": SCHEMA, "source_commits": SOURCE, "file_hashes": files,
            **{key: False for key in FALSE_FLAGS}}

def build(f14, f28, archive_path):
    roots = {"F14": Path(f14), "F28": Path(f28)}
    for family, commit in SOURCE.items():
        root = roots[family]
        assert root.is_dir() and not root.is_symlink()
        assert (root / ".git").exists()
        import subprocess
        seen = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"],
                                       text=True, timeout=15).strip()
        assert seen == commit, "SOURCE_COMMIT_MISMATCH:" + family
    files, items = {}, {}
    for name, (family, path) in MAP.items():
        source = roots[family] / path
        assert source.is_file() and not source.is_symlink(), name
        data = source.read_bytes()
        assert 100 <= len(data) <= 500_000, name
        items[name] = data
        files[name] = digest(data)
    items["manifest.json"] = (json.dumps(manifest(files), sort_keys=True,
                                         indent=2) + "\n").encode("utf-8")
    out = Path(archive_path)
    assert not out.is_symlink() and not out.exists()
    with tarfile.open(out, "w:gz", compresslevel=8, format=tarfile.PAX_FORMAT) as tar:
        for name in sorted(items):
            value = items[name]
            info = tarfile.TarInfo(name)
            info.size = len(value)
            info.mode = 0o600
            info.mtime = 0
            tar.addfile(info, io.BytesIO(value))
    assert out.stat().st_size < MAX_ARCHIVE
    return {"archive_sha256": digest(out.read_bytes()), "members": len(items)}

def verify(archive_path, expected_sha, private_root):
    archive = Path(archive_path)
    assert (archive.is_file() and not archive.is_symlink()
            and 100 < archive.stat().st_size < MAX_ARCHIVE)
    actual = digest(archive.read_bytes())
    assert actual == expected_sha, "ARCHIVE_SHA_MISMATCH"
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        assert len(members) == len(MAP)+1
        assert {m.name for m in members} == set(MAP) | {"manifest.json"}
        assert all(m.isfile() and not m.issym() and not m.islnk()
                   and 100 <= m.size <= 500_000 for m in members)
        data = {}
        for member in members:
            stream = tar.extractfile(member)
            assert stream is not None
            blob = stream.read(500001)
            assert len(blob) == member.size
            data[member.name] = blob
    source_manifest = json.loads(data["manifest.json"])
    assert source_manifest["schema"] == SCHEMA
    assert source_manifest["source_commits"] == SOURCE
    assert set(source_manifest["file_hashes"]) == set(MAP)
    assert all(source_manifest[key] is False for key in FALSE_FLAGS)
    assert all(digest(data[name]) == source_manifest["file_hashes"][name]
               for name in MAP)
    root = Path(private_root)
    assert root.is_dir() and not root.is_symlink()
    assert shutil.disk_usage(root).free >= 1024 * 1024 * 1024, "LOW_DISK"
    private = root / "product-commercial-pilots"
    assert not private.is_symlink()
    private.mkdir(mode=0o700, exist_ok=True)
    os.chmod(private, 0o700)
    target = private / ("f14-f28-" + actual[:24])
    receipt = {"schema": RECEIPT_SCHEMA, "archive_sha256": actual,
               "source_commits": SOURCE, "files_verified": len(MAP),
               "private_only": True, "status": "technical_stage_only",
               **{key: False for key in FALSE_FLAGS}}
    if not target.exists():
        temp = Path(tempfile.mkdtemp(prefix=".staged-", dir=private))
        try:
            for name, blob in data.items():
                p = temp / name
                p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                with p.open("xb") as fd:
                    fd.write(blob)
                    fd.flush()
                    os.fsync(fd.fileno())
                os.chmod(p, 0o600)
            p = temp / "receipt.json"
            p.write_text(json.dumps(receipt, sort_keys=True, indent=2)+"\n")
            os.chmod(p, 0o600)
            os.rename(temp, target)
        finally:
            if temp.exists():
                shutil.rmtree(temp)
    assert target.is_dir() and not target.is_symlink()
    for name in MAP:
        p = target / name
        assert p.is_file() and not p.is_symlink()
        assert digest(p.read_bytes()) == source_manifest["file_hashes"][name]
    receipt_path = target / "receipt.json"
    assert receipt_path.is_file() and not receipt_path.is_symlink()
    assert json.loads(receipt_path.read_text()) == receipt
    return receipt

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    for name in ("f14", "f28", "archive"):
        b.add_argument("--" + name, required=True)
    v = sub.add_parser("verify")
    for name in ("archive", "expected-sha", "private-root"):
        v.add_argument("--" + name, required=True)
    a = ap.parse_args()
    if a.cmd == "build":
        print("FACTORY_PRIVATE_PILOT_BUILD=" + json.dumps(
            build(a.f14, a.f28, a.archive), sort_keys=True))
    else:
        result = verify(a.archive, a.expected_sha, a.private_root)
        print("FACTORY_PRIVATE_PILOT_RECEIPT=" + json.dumps(result, sort_keys=True))
        print("FACTORY_PRIVATE_PILOT_HASH_READBACK=PASS")
        print("FACTORY_PRIVATE_PILOT_PUBLIC_SALES=0")

if __name__ == "__main__":
    main()
