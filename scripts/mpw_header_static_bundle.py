#!/usr/bin/env python3
"""Create an exact, offline MojPlayWin header repair handoff archive.

No network access, SSH, deployment, Django import, or production mutation.
The resulting archive can later be staged by the existing pinned cPanel relay
after a separately authorized release decision.
"""

import argparse
import hashlib
import io
import json
import os
import tarfile
import tempfile
from pathlib import Path

if __package__:
    from .mpw_header_static_manifest_repair import EXPECTED_GIT_BLOB, git_blob_sha
else:
    from mpw_header_static_manifest_repair import EXPECTED_GIT_BLOB, git_blob_sha

JPEG = "core/static/site/mojplaywin-header-emblem.jpg"
REPAIR = "scripts/mpw_header_static_manifest_repair.py"
MEMBERS = ("mojplaywin-header-emblem.jpg", "mpw_header_static_manifest_repair.py", "bundle.json")


def _source(repo, name):
    target = repo / name
    if (target.is_symlink() or target.parent.is_symlink() or
            not target.is_file() or target.stat().st_size > 1_000_000):
        raise RuntimeError("Unsafe or missing bundle source")
    return target.read_bytes()


def _add_bytes(archive, name, raw):
    member = tarfile.TarInfo(name)
    member.mode = 0o644
    member.size = len(raw)
    member.mtime = 0
    member.uid = member.gid = 0
    member.uname = member.gname = ""
    archive.addfile(member, io.BytesIO(raw))


def build_bundle(repo, output, expected_blob=EXPECTED_GIT_BLOB):
    repo, output = Path(repo), Path(output)
    if repo.is_symlink() or not repo.is_dir() or output.is_symlink() or output.exists():
        raise RuntimeError("Unsafe or occupied bundle destination")
    if output.parent.is_symlink() or not output.parent.is_dir():
        raise RuntimeError("Unsafe output parent")
    jpeg, script = _source(repo, JPEG), _source(repo, REPAIR)
    if (git_blob_sha(jpeg) != expected_blob or len(jpeg) < 1_000 or
            not jpeg.startswith(b"\xff\xd8") or not jpeg.endswith(b"\xff\xd9")):
        raise RuntimeError("Image does not match pinned Git source")
    if b"def rollback(" not in script or b"EXPECTED_GIT_BLOB" not in script:
        raise RuntimeError("Repair utility incomplete")
    manifest = {
        "scope": "mojplaywin-header-only",
        "image_git_blob": expected_blob,
        "image_sha256": hashlib.sha256(jpeg).hexdigest(),
        "script_sha256": hashlib.sha256(script).hexdigest(),
        "release_mode": "manual-only",
    }
    data = json.dumps(manifest, sort_keys=True).encode("utf-8")
    fd, temp_name = tempfile.mkstemp(prefix=".mpw-header-bundle-", suffix=".tar.gz", dir=output.parent)
    os.close(fd)
    try:
        with tarfile.open(temp_name, "w:gz") as archive:
            _add_bytes(archive, MEMBERS[0], jpeg)
            _add_bytes(archive, MEMBERS[1], script)
            _add_bytes(archive, MEMBERS[2], data)
        with tarfile.open(temp_name, "r:gz") as archive:
            names = archive.getnames()
            if names != list(MEMBERS) or not all(m.isfile() and not m.issym() and not m.islnk()
                                                   for m in archive.getmembers()):
                raise RuntimeError("Archive member allowlist mismatch")
            for filename, expected in ((MEMBERS[0], jpeg), (MEMBERS[1], script), (MEMBERS[2], data)):
                if archive.extractfile(filename).read() != expected:
                    raise RuntimeError("Archive content mismatch")
        # Atomic create-only publication; never replace an existing archive.
        os.link(temp_name, output)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return {"status": "prepared_only", "manual_release_required": True,
            "archive_files": list(MEMBERS), "image_git_blob": expected_blob,
            "bytes": output.stat().st_size, "production_mutated": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(build_bundle(args.repo, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
