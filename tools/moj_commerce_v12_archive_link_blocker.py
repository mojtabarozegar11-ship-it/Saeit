#!/usr/bin/env python3
"""Single-pass read-only recovery blocker classifier for verified MojPlayWin TAR.

Read decrypted TAR from stdin *only* via authenticated VPS GPG stream over
host-key-pinned SSH. Disclose no file names, links, targets, paths, credentials
or data to CI logs. The extractor and live site are untouched.
"""
from __future__ import annotations
import json
import posixpath
import re
import sys
import tarfile
from pathlib import PurePosixPath

ROOTS = {"Saeit-staging", "mojplaywin.com"}
MAX_MEMBERS = 150000
MAX_SIZE = 10 * 1024**3
VENV_NAMES = {".venv", "venv", ".virtualenv", "virtualenv", "env"}


def interpreter_rebuildable(link_name: str, link_target: str) -> bool:
    """Only external Python binary links inside a recorded VENV bin folder.

    We never restore the external link as-is. A new virtual environment is a
    separate, independently tested runtime artifact, not an external symlink.
    """
    parts = PurePosixPath(link_name).parts
    leaf = parts[-1] if parts else ""
    if len(parts) < 4 or parts[-2] != "bin" or parts[-3] not in VENV_NAMES:
        return False
    if not re.fullmatch(r"python(?:3(?:\.\d+)?)?", leaf):
        return False
    return bool(re.fullmatch(
        r"/(?:usr/bin|usr/local/bin|opt/alt/python\d+/bin)/python(?:3(?:\.\d+)?)?",
        link_target))


def classify(stream):
    count = {"regular": 0, "directories": 0, "symlinks": 0,
             "absolute_links": 0, "derived_python_venv_links": 0,
             "unsafe_external_links": 0, "relative_links": 0,
             "absolute_links_to_backed_root": 0, "absolute_links_other_home": 0,
             "absolute_links_system_runtime": 0, "absolute_links_elsewhere": 0,
             "absolute_link_target_present_as_archive_member": 0,
             "hardlinks": 0, "special": 0, "total_file_bytes": 0}
    roots, seen = set(), set()
    eligible_absolute_targets = []
    with tarfile.open(fileobj=stream, mode="r|") as archive:
        for member in archive:
            if len(seen) >= MAX_MEMBERS:
                raise RuntimeError("member_limit")
            name = member.name
            if not name or name.startswith("/") or name.startswith("./"):
                raise RuntimeError("unsafe_member")
            parts = PurePosixPath(name).parts
            if not parts or parts[0] not in ROOTS or ".." in parts:
                raise RuntimeError("unsafe_member")
            normalized = "/".join(parts)
            if normalized in seen:
                raise RuntimeError("duplicate_member")
            seen.add(normalized)
            roots.add(parts[0])
            if member.isfile():
                count["regular"] += 1
                count["total_file_bytes"] += member.size
                if count["total_file_bytes"] > MAX_SIZE:
                    raise RuntimeError("size_limit")
            elif member.isdir():
                count["directories"] += 1
            elif member.issym():
                count["symlinks"] += 1
                target = member.linkname
                if not isinstance(target, str):
                    raise RuntimeError("link_type")
                if target.startswith("/"):
                    count["absolute_links"] += 1
                    if interpreter_rebuildable(normalized, target):
                        count["derived_python_venv_links"] += 1
                    else:
                        count["unsafe_external_links"] += 1
                    absolute = PurePosixPath(target)
                    parts_target = absolute.parts
                    if len(parts_target) >= 4 and parts_target[:3] == ("/", "home", "zomorod2") and parts_target[3] in ROOTS:
                        count["absolute_links_to_backed_root"] += 1
                        eligible_absolute_targets.append("/".join(parts_target[3:]))
                    elif len(parts_target) >= 3 and parts_target[:3] == ("/", "home", "zomorod2"):
                        count["absolute_links_other_home"] += 1
                    elif len(parts_target) > 2 and parts_target[1] in ("opt", "usr"):
                        count["absolute_links_system_runtime"] += 1
                    else:
                        count["absolute_links_elsewhere"] += 1
                else:
                    dest = posixpath.normpath(posixpath.join(*parts[:-1], target))
                    if PurePosixPath(dest).parts[0] not in ROOTS or ".." in PurePosixPath(dest).parts:
                        count["unsafe_external_links"] += 1
                    count["relative_links"] += 1
            elif member.islnk():
                count["hardlinks"] += 1
            else:
                count["special"] += 1
    count["absolute_link_target_present_as_archive_member"] = sum(
        1 for member in eligible_absolute_targets if member in seen)
    # Drain footer to let upstream GPG verifier independently authenticate EOF.
    while stream.read(131072):
        pass
    return {
        "classification": "MOJ_COMMERCE_V12_ABSOLUTE_LINK_BLOCKER_READONLY",
        "verified_archive_roots": sorted(roots) == sorted(ROOTS),
        "counters": count,
        "all_absolute_links_derived_interpreter_dependencies":
            (count["absolute_links"] > 0 and
             count["absolute_links"] == count["derived_python_venv_links"] and
             count["unsafe_external_links"] == 0),
        "runtime_venv_rebuilt": False,
        "functional_restore_verified": False,
        "backup_key_exported": False,
        "live_site_modified": False,
        "release_permitted": False,
    }


if __name__ == "__main__":
    try:
        if sys.argv[1:] != ["archive"]:
            raise ValueError("invalid_mode")
        print(json.dumps(classify(sys.stdin.buffer), sort_keys=True))
    except Exception:
        print(json.dumps({"classification": "MOJ_COMMERCE_V12_LINK_BLOCKER_UNVERIFIED",
                          "release_permitted": False, "error": "SANITIZED_FAILURE"}))
        raise SystemExit(1)
