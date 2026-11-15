#!/usr/bin/env python3
"""R01 frozen-source manifest verifier. Offline, read-only, no field-data claims.

Usage: python research/irrigation_synthetic_audit/verify_frozen_manifest.py MANIFEST.json
Manifest schema:
{"schema_version":1,"study":"R01","artifacts":[
 {"role":"input","path":"inputs/C.csv","sha256":"64 lowercase hex chars","bytes":123},
 {"role":"generator","path":"code/generator.py","sha256":"...","bytes":123},
 {"role":"config","path":"config.json","sha256":"...","bytes":123},
 {"role":"output","path":"outputs/C.csv","sha256":"...","bytes":123}
]}
Paths are relative to the manifest directory. Never publish private inputs.
This tool verifies file identity, NOT experimental validity or generator replay.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROLES = {"input", "generator", "config", "output", "analysis", "table"}
SHA = re.compile(r"[0-9a-f]{64}\Z")

def verify(manifest_path):
    errors = []
    def check(ok, message):
        if not ok:
            errors.append(message)
        return bool(ok)
    root = manifest_path.parent.resolve()
    try:
        raw = manifest_path.read_bytes()
        data = json.loads(raw)
    except (OSError, UnicodeError, ValueError) as exc:
        return ["manifest unreadable or invalid JSON: " + str(exc)]
    if not check(isinstance(data, dict), "root must be object"):
        return errors
    check(data.get("schema_version") == 1, "schema_version must be 1")
    check(data.get("study") == "R01", "study must be R01")
    artifacts = data.get("artifacts")
    if not check(isinstance(artifacts, list), "artifacts must be array"):
        return errors
    check(bool(artifacts), "artifacts must be nonempty")
    seen = set()
    roles = set()
    for i, item in enumerate(artifacts):
        tag = "artifacts[%d]" % i
        if not check(isinstance(item, dict), tag + " must be object"):
            continue
        role = item.get("role")
        if check(isinstance(role, str) and role in ROLES, tag + " invalid role"):
            roles.add(role)
        path = item.get("path")
        if not check(isinstance(path, str) and bool(path) and "\\x00" not in path,
                     tag + " invalid path"):
            continue
        relative = Path(path)
        if not check(not relative.is_absolute(), tag + " absolute path forbidden"):
            continue
        if not check(".." not in relative.parts, tag + " parent traversal forbidden"):
            continue
        if not check(path not in seen, tag + " duplicate path"):
            continue
        seen.add(path)
        resolved = (root / relative).resolve()
        if not check(resolved.is_relative_to(root), tag + " path escapes manifest root"):
            continue
        if not check(resolved.is_file(), tag + " missing/non-file artifact"):
            continue
        if not check(not resolved.is_symlink(), tag + " symlink forbidden"):
            continue
        size = item.get("bytes")
        if not check(type(size) is int and size >= 0, tag + " invalid byte count"):
            continue
        if not check(resolved.stat().st_size == size, tag + " byte count mismatch"):
            continue
        expected = item.get("sha256")
        if not check(isinstance(expected, str) and SHA.fullmatch(expected),
                     tag + " invalid SHA-256"):
            continue
        digest = hashlib.sha256()
        with resolved.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        check(digest.hexdigest() == expected, tag + " SHA-256 mismatch")
    check("input" in roles, "missing input role")
    check("generator" in roles, "missing generator role")
    check("config" in roles, "missing config role")
    check("output" in roles, "missing output role")
    return errors

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    failures = verify(args.manifest)
    for failure in failures:
        print("FAIL:", failure, file=sys.stderr)
    if failures:
        print("BLOCKED: %d integrity violations" % len(failures), file=sys.stderr)
        return 1
    print("PASS: manifest file identity verified; model validity NOT established")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
