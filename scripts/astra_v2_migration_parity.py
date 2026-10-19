#!/usr/bin/env python3
"""Read-only cross-branch migration parity gate; no Django or DB operations.

The reference folder is checked out from the historical, VPS-aligned Saeit
branch in an isolated GitHub Actions workspace, never merged automatically.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re

PATTERN=re.compile(r"^(\d{4})_([A-Za-z0-9_]+)\.py$")
MIN_BASE=39
MAX_REFERENCE=48


def inventory(directory):
    directory=Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("migration folder unavailable or symlinked")
    data={}
    for file in directory.iterdir():
        if file.is_symlink():
            raise ValueError("migration file symlink")
        found=PATTERN.fullmatch(file.name)
        if not found:
            continue
        if not file.is_file() or file.stat().st_size>500_000:
            raise ValueError("oversized or unsafe migration")
        num=int(found.group(1))
        if num in data:
            raise ValueError("duplicate migration number")
        source=file.read_bytes()
        ast.parse(source.decode("utf-8"),filename=file.name)
        data[num]={"file":file.name,"sha256":hashlib.sha256(source).hexdigest()}
    return data


def parity(current_dir,reference_dir):
    current=inventory(current_dir)
    historical=inventory(reference_dir)
    if MIN_BASE not in current or MIN_BASE not in historical:
        raise ValueError("common 0039 ancestor missing")
    common_sha_match=(current[MIN_BASE]["sha256"]==historical[MIN_BASE]["sha256"])
    expected=[n for n in range(MIN_BASE+1,MAX_REFERENCE+1)]
    missing=[historical[n]["file"] for n in expected if n in historical and n not in current]
    missing_in_reference=[n for n in expected if n not in historical]
    conflict=[n for n in sorted(set(current)&set(historical))
              if current[n]["sha256"]!=historical[n]["sha256"]]
    code_at_reference=None
    if MAX_REFERENCE in historical:
        code_at_reference=historical[MAX_REFERENCE]["file"]
    next_safe_step=(
        "RECONCILE_FROM_TRUSTED_0048_SOURCE_AND_TEST_ON_DISPOSABLE_COPY"
        if not missing_in_reference and common_sha_match
        else "BLOCKED_REVIEW_MIGRATION_LINEAGE_MANUALLY"
    )
    return {
        "mode":"read_only_no_cherry_pick_no_migration",
        "current_last_migration_number":max(current),
        "reference_last_migration_number":max(historical),
        "common_0039_sha_equal":common_sha_match,
        "missing_current_0040_to_0048":missing,
        "missing_reference_0040_to_0048":missing_in_reference,
        "same_number_divergent_migrations":conflict,
        "reference_0048_file":code_at_reference,
        "automatic_merge_permitted":False,
        "production_migration_permitted":False,
        "stage45_cutover_permitted":False,
        "next_step":next_safe_step,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--current-dir",required=True)
    p.add_argument("--reference-dir",required=True)
    a=p.parse_args()
    print(json.dumps(parity(a.current_dir,a.reference_dir),sort_keys=True,indent=2))


if __name__=="__main__":
    main()
