#!/usr/bin/env python3
"""G-01 -> S-01: read-only review ZIP verification. Never deploys or touches sites."""
import hashlib
import json
import pathlib
import stat
import sys
import zipfile

REQUIRED = {"index.html", "game.js", "game.css", "engine3d.js",
            "save-validation.mjs", "campaign-backup.mjs",
            "moj1-commerce-policy.mjs", "preview-manifest.json",
            "m24-sniper-ccby.glb", "soldier-rigged-ccby.glb"}

def verify(path):
    path = pathlib.Path(path)
    result = {"stage": "READY_FOR_REVIEW", "deploy_authorized": False,
              "live_verified": False, "backup_restore_verified": False,
              "file": path.name}
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or len(names) > 150:
            raise ValueError("unsafe member count or duplicate names")
        if sum(m.file_size for m in z.infolist()) > 65_000_000:
            raise ValueError("uncompressed size exceeds limit")
        seen_casefold = set()
        for m in z.infolist():
            parts = pathlib.PurePosixPath(m.filename).parts
            if (len(parts) != 2 or parts[0] != "ramadan-war" or
                    parts[1] in (".", "..") or "\\" in m.filename or
                    any(ord(ch) < 32 for ch in m.filename)):
                raise ValueError("unsafe archive path")
            folded = m.filename.casefold()
            if folded in seen_casefold:
                raise ValueError("case-insensitive archive collision")
            seen_casefold.add(folded)
            if m.file_size > 15_000_000 or (m.file_size > 1_000_000 and
                    m.file_size > max(1, m.compress_size) * 250):
                raise ValueError("unsafe member size or compression ratio")
            if stat.S_IFMT(m.external_attr >> 16) == stat.S_IFLNK:
                raise ValueError("archive symlink forbidden")
        present = {n.removeprefix("ramadan-war/") for n in names}
        if REQUIRED - present:
            raise ValueError("missing runtime files: " + ",".join(sorted(REQUIRED - present)))
        manifest = json.loads(z.read("ramadan-war/preview-manifest.json"))
        if not manifest.get("version", "").startswith("G01-R"):
            raise ValueError("missing G-01 version")
        if set(manifest["files"]) != present - {"preview-manifest.json"}:
            raise ValueError("manifest does not cover every archive member")
        for name, meta in manifest["files"].items():
            data = z.read("ramadan-war/" + name)
            if len(data) != meta["bytes"] or hashlib.sha256(data).hexdigest() != meta["sha256"]:
                raise ValueError("manifest SHA mismatch: " + name)
        policy = z.read("ramadan-war/moj1-commerce-policy.mjs").decode("utf-8")
        if "MOJ1" not in policy or "false" not in policy:
            raise ValueError("disabled MOJ1 policy not found")
        result["checks"] = {"safe_archive": True, "manifest_sha256": True,
                            "runtime_complete": True, "disabled_moj1_policy_present": True}
        result["members"] = len(names)
        result["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python g01_s01_release_handoff_verify.py game.zip")
    try:
        print(json.dumps(verify(sys.argv[1]), indent=2))
    except (ValueError, KeyError, zipfile.BadZipFile) as exc:
        print(json.dumps({"stage": "BLOCKED", "deploy_authorized": False, "reason": str(exc)}))
        raise SystemExit(1)
