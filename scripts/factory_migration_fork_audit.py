#!/usr/bin/env python3
"""Compare factory migration histories without importing Django or touching a DB.

This identifies source-history forks only. It cannot establish which migrations
were applied on a live VPS and must never authorize a migration or deployment.
"""

import argparse
import ast
import hashlib
import json
import re
from pathlib import Path


SCHEMA = "saeit.factory.migration-fork-audit.v1"
MAX_MIGRATIONS = 400
MAX_MIGRATION_BYTES = 1_000_000
MIGRATION_NAME = re.compile(r"^[0-9]{4}_[a-zA-Z0-9_]+\.py$")


def _dependencies(tree):
    """Read static same-app dependency tuples, never evaluate migration code."""
    deps = set()
    for cls in tree.body:
        if not isinstance(cls, ast.ClassDef) or cls.name != "Migration":
            continue
        for stmt in cls.body:
            if not isinstance(stmt, ast.Assign) or not any(
                isinstance(target, ast.Name) and target.id == "dependencies"
                for target in stmt.targets
            ):
                continue
            if not isinstance(stmt.value, (ast.List, ast.Tuple)):
                return None
            for item in stmt.value.elts:
                if not isinstance(item, ast.Tuple) or len(item.elts) != 2:
                    # An external swappable_dependency is expected; no code is run.
                    continue
                app, name = item.elts
                if (isinstance(app, ast.Constant) and app.value == "core"
                        and isinstance(name, ast.Constant)
                        and isinstance(name.value, str)):
                    deps.add(name.value)
            return sorted(deps)
    return None


def _inventory(root, side):
    folder = Path(root) / "core" / "migrations"
    blockers = []
    files = {}
    if folder.is_symlink() or not folder.is_dir():
        blockers.append({"code": "MIGRATION_DIR_UNAVAILABLE", "side": side})
        return files, blockers
    candidates = sorted(p for p in folder.iterdir()
                        if MIGRATION_NAME.fullmatch(p.name))
    if len(candidates) > MAX_MIGRATIONS:
        blockers.append({"code": "MIGRATION_LIMIT_EXCEEDED", "side": side})
        return files, blockers
    for path in candidates:
        name = path.stem
        try:
            safe_file = (not path.is_symlink() and path.is_file()
                         and path.stat().st_size <= MAX_MIGRATION_BYTES)
        except OSError:
            safe_file = False
        if not safe_file:
            blockers.append({"code": "MIGRATION_FILE_UNSAFE", "side": side,
                             "component": name})
            continue
        try:
            raw = path.read_bytes()
            tree = ast.parse(raw.decode("utf-8"), filename=path.name)
        except (OSError, UnicodeError, SyntaxError):
            blockers.append({"code": "MIGRATION_UNREADABLE", "side": side,
                             "component": name})
            continue
        deps = _dependencies(tree)
        if deps is None:
            blockers.append({"code": "MIGRATION_DEPS_UNVERIFIED", "side": side,
                             "component": name})
            continue
        files[name] = {"sha256": hashlib.sha256(raw).hexdigest(), "deps": deps}
    for name, data in files.items():
        for dependency in data["deps"]:
            if dependency not in files and dependency not in {"__first__", "__latest__"}:
                blockers.append({"code": "MIGRATION_PARENT_MISSING", "side": side,
                                 "component": name, "dependency": dependency})
    return files, blockers


def audit(current_root, reference_root):
    current, current_errors = _inventory(current_root, "current")
    reference, reference_errors = _inventory(reference_root, "reference")
    shared = sorted(set(current) & set(reference))
    changed = [name for name in shared
               if current[name]["sha256"] != reference[name]["sha256"]]
    current_only = sorted(set(current) - set(reference))
    reference_only = sorted(set(reference) - set(current))
    reference_by_number = {}
    for name in reference:
        reference_by_number.setdefault(name[:4], set()).add(name)
    number_collisions = [
        {"number": name[:4], "current": name,
         "reference": sorted(reference_by_number[name[:4]])}
        for name in current_only if reference_by_number.get(name[:4])
    ]
    blockers = current_errors + reference_errors
    if not current:
        blockers.append({"code": "MIGRATION_HISTORY_EMPTY", "side": "current"})
    if not reference:
        blockers.append({"code": "MIGRATION_HISTORY_EMPTY", "side": "reference"})
    if current and reference and not shared:
        blockers.append({"code": "MIGRATION_SHARED_ANCESTOR_MISSING",
                         "component": "core"})
    blockers.extend({"code": "MIGRATION_CONTENT_DIVERGED", "component": name}
                    for name in changed)
    if current_only and reference_only:
        blockers.append({"code": "UNRECONCILED_MIGRATION_BRANCHES",
                         "component": "core"})
    blockers.sort(key=lambda x: (x["code"], x.get("side", ""),
                                 x.get("component", "")))
    return {
        "schema": SCHEMA,
        "mode": "offline_source_read_only",
        "live_vps_verified": False,
        "database_schema_verified": False,
        "production_ready": False,
        "status": "blocked" if blockers else "no_source_fork_detected",
        "current_count": len(current),
        "reference_count": len(reference),
        "identical_shared_count": len(shared) - len(changed),
        "changed_shared_files": changed,
        "current_only": current_only,
        "reference_only": reference_only,
        "same_number_different_files": number_collisions,
        "blockers": blockers,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-root", type=Path, required=True)
    parser.add_argument("--reference-root", type=Path, required=True)
    args = parser.parse_args(argv)
    result = audit(args.current_root, args.reference_root)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 2 if result["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
