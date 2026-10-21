#!/usr/bin/env python3
"""Scoped, reversible fix for the four original portrait cards on Mojtaba's About page."""
from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

APP = Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
TARGET = APP / "templates/personal_site/core/about.html"
BACKUP_ROOT = Path("/home/zomorod2/.backups/mojtaba-about-four-photo-fit")
OLD = ".mpw-inner .mpw-card img{width:100%;height:285px;object-fit:cover;display:block;background:#182837}"
NEW = ".mpw-inner .mpw-card img{width:100%;height:auto;aspect-ratio:1/1;object-fit:contain;display:block;background:#182837}.mpw-inner .mpw-card:nth-child(even) img{aspect-ratio:1229/1536}"
SCOPE = 'id="mpw-inner-content-20261015"'


def ensure_target() -> None:
    if APP.is_symlink() or not (APP / "manage.py").is_file():
        raise RuntimeError("Personal Django app not verified")
    if TARGET.is_symlink() or not TARGET.is_file():
        raise RuntimeError("About template missing or unsafe")


def candidate() -> tuple[str, str]:
    ensure_target()
    original = TARGET.read_text(encoding="utf-8")
    if original.count(SCOPE) != 1:
        raise RuntimeError("About page content marker changed")
    if original.count('<article class="mpw-card">') != 4:
        raise RuntimeError("Expected exactly four original portrait cards")
    if original.count(OLD) != 1 or NEW in original:
        raise RuntimeError("Expected original image CSS not found; refusing blind modification")
    updated = original.replace(OLD, NEW, 1)
    if updated.count(NEW) != 1:
        raise RuntimeError("Targeted replacement did not apply")
    return original, updated


def write_atomic(data: str) -> None:
    temp = TARGET.with_name(TARGET.name + ".about-photo-fit-new")
    if temp.exists() or temp.is_symlink():
        raise RuntimeError("Temporary target already exists")
    try:
        temp.write_text(data, encoding="utf-8")
        os.chmod(temp, TARGET.stat().st_mode & 0o777)
        os.replace(temp, TARGET)
    finally:
        if temp.exists():
            temp.unlink()


def backup_path(run_id: str) -> Path:
    if not run_id.isdecimal() or len(run_id) > 32:
        raise ValueError("Unsafe GitHub run ID")
    return BACKUP_ROOT / run_id / "about.html"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("check", "install", "rollback"))
    p.add_argument("run_id")
    args = p.parse_args()
    ensure_target()
    saved = backup_path(args.run_id)
    if args.mode == "rollback":
        if saved.is_symlink() or not saved.is_file():
            raise RuntimeError("Verified backup unavailable; no rollback attempted")
        write_atomic(saved.read_text(encoding="utf-8"))
        print("ABOUT_FOUR_PHOTOS_ONLY_ROLLED_BACK=yes")
        return

    original, updated = candidate()
    print("ORIGINAL_FOUR_CARDS_CONFIRMED=yes")
    print("UNRELATED_TEMPLATES_UNTOUCHED=yes")
    if args.mode == "check":
        return
    if saved.exists() or saved.is_symlink():
        raise RuntimeError("Backup already exists")
    saved.parent.mkdir(parents=True, mode=0o700, exist_ok=False)
    shutil.copy2(TARGET, saved)
    if saved.read_text(encoding="utf-8") != original:
        raise RuntimeError("Backup content mismatch")
    write_atomic(updated)
    if TARGET.read_text(encoding="utf-8") != updated:
        raise RuntimeError("Post-install bytes mismatch")
    print("FOUR_ABOUT_PHOTOS_FULL_FIT_INSTALLED=yes")
    print("BACKUP=" + str(saved))


if __name__ == "__main__":
    main()
