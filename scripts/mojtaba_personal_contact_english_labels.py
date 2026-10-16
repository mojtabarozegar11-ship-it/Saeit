#!/usr/bin/env python3
"""Conservative English-label-only change to Mojtaba personal V17 contact form.

No views, routes, fields, validation, email handling, database, style or other sites.
Fails closed if the current source differs from the four observed labels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import sys

APP = Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
CANDIDATES = (
    "core/forms.py",
    "templates/personal_site/core/contact.html",
    "templates/personal_site/contact.html",
    "core/views.py",
)
LABELS = {
    "نام فرستنده": "Your Name",
    "ایمیل": "Email Address",
    "موضوع": "Subject",
    "متن پیام": "Your Message",
}
BACKUP_FILE = "original-contact-label-source"
META_FILE = "manifest.json"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_file(root: Path, rel: str) -> Path:
    if rel not in CANDIDATES:
        raise ValueError("Target outside personal contact allowlist")
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Personal app root not a regular directory")
    path = root / rel
    if path.is_symlink() or not path.is_file() or path.resolve() != path:
        raise ValueError("Missing/unsafe personal contact source")
    return path


def plan(root: Path):
    candidates = []
    for rel in CANDIDATES:
        path = root / rel
        if not path.exists():
            continue
        path = safe_file(root, rel)
        before = path.read_text(encoding="utf-8")
        counts = [before.count(label) for label in LABELS]
        if all(count == 1 for count in counts):
            if not (("forms.py" in rel and "forms." in before) or
                    ("contact.html" in rel and ("<label" in before or ".label_tag" in before)) or
                    (rel == "core/views.py" and "contact" in before)):
                raise ValueError("Candidate has no recognizable contact structure")
            after = before
            for fa, en in LABELS.items():
                after = after.replace(fa, en)
            assert before != after
            assert after.count("Your Message") >= 1
            for fa, en in LABELS.items():
                if after.count(en) < 1:
                    raise ValueError("Missing translated label")
            candidates.append((rel, before, after))
        elif any(count > 0 for count in counts):
            raise ValueError("Partial or ambiguous Persian contact labels: " + rel)
    # Model field verbose_names are deliberately left untouched. Override only
    # contact-page label_tag rendering, without changing form objects or the DB.
    if not candidates:
        rel = "templates/personal_site/core/contact.html"
        path = root / rel
        if path.exists():
            path = safe_file(root, rel)
            before = path.read_text(encoding="utf-8")
            replacements = (
                ("name", "Your Name"),
                ("email", "Email Address"),
                ("subject", "Subject"),
                ("message", "Your Message"),
            )
            matched = {}
            for field, label in replacements:
                pattern = r"\{\{\s*form\." + field + r"\.label_tag\s*\}\}"
                found = list(re.finditer(pattern, before))
                if len(found) != 1:
                    break
                matched[field] = (pattern, label)
            if len(matched) == 4:
                after = before
                for field, (pattern, label) in matched.items():
                    replacement = '<label for="{{ form.' + field + '.id_for_label }}">' + label + '</label>'
                    after, count = re.subn(pattern, lambda m: replacement, after)
                    if count != 1:
                        raise ValueError("Unexpected template replacement count")
                if after == before:
                    raise ValueError("No visible label change")
                candidates.append((rel, before, after))
    if len(candidates) != 1:
        print("READ_ONLY_PERSONAL_LABEL_SOURCE_DIAGNOSTIC_BEGIN", flush=True)
        reported = 0
        for path in sorted(root.rglob("*")):
            if path.suffix not in (".py", ".html") or path.is_symlink() or not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if any(part in rel.split("/") for part in ("media", "static", "venv", ".venv", "backups", "__pycache__")):
                continue
            try:
                txt = path.read_text(encoding="utf-8")
            except (UnicodeError, OSError):
                continue
            counts = [txt.count(s) for s in LABELS]
            if any(counts):
                print("READ_ONLY_LABEL_FILE=" + rel + " COUNTS=" + ",".join(map(str, counts)), flush=True)
                reported += 1
            if reported >= 30:
                break
        print("READ_ONLY_PERSONAL_LABEL_SOURCE_DIAGNOSTIC_END", flush=True)
        raise ValueError("Expected exactly one contact label source, found " + str(len(candidates)))
    return candidates[0]


def install(root: Path, backup: Path) -> None:
    rel, before, after = plan(root)
    source = safe_file(root, rel)
    if backup.is_symlink() or backup.exists():
        raise ValueError("Backup path must be new, non-symlink directory")
    backup.mkdir(parents=True, mode=0o700)
    shutil.copy2(source, backup / BACKUP_FILE)
    if (backup / BACKUP_FILE).read_bytes() != source.read_bytes():
        raise ValueError("Backup verification failed")
    metadata = {"relative": rel, "before": sha(before), "after": sha(after)}
    (backup / META_FILE).write_text(json.dumps(metadata, sort_keys=True), encoding="utf-8")
    original_stat = source.stat()
    temp = source.with_name(source.name + ".english-translation.tmp")
    if temp.exists() or temp.is_symlink():
        raise ValueError("Unexpected temporary file already exists")
    try:
        temp.write_text(after, encoding="utf-8")
        os.chmod(temp, original_stat.st_mode & 0o777)
        if sha(temp.read_text(encoding="utf-8")) != metadata["after"]:
            raise ValueError("Temporary translation mismatch")
        os.replace(temp, source)
    finally:
        if temp.exists():
            temp.unlink()
    print("PERSONAL_CONTACT_LABELS_CHANGED=4", flush=True)
    print("PERSONAL_CONTACT_TARGET=" + rel, flush=True)
    print("BACKUP_SAVED=yes", flush=True)


def rollback(root: Path, backup: Path) -> None:
    meta = json.loads((backup / META_FILE).read_text(encoding="utf-8"))
    source = safe_file(root, meta["relative"])
    previous = (backup / BACKUP_FILE).read_text(encoding="utf-8")
    if sha(previous) != meta["before"]:
        raise ValueError("Cannot trust backup checksum")
    current = source.read_text(encoding="utf-8")
    if sha(current) not in (meta["after"], meta["before"]):
        raise ValueError("Source changed by another process; manual recovery required")
    temp = source.with_name(source.name + ".translation-rollback.tmp")
    if temp.exists() or temp.is_symlink():
        raise ValueError("Unsafe rollback temporary path")
    shutil.copy2(backup / BACKUP_FILE, temp)
    os.replace(temp, source)
    if sha(source.read_text(encoding="utf-8")) != meta["before"]:
        raise ValueError("Rollback checksum mismatch")
    print("PERSONAL_CONTACT_ROLLBACK_VERIFIED=yes", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("check", "install", "rollback"))
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    if args.mode == "check":
        rel, before, after = plan(APP)
        print("PERSONAL_CONTACT_SOURCE_VERIFIED=" + rel)
        print("LABELS_FROM_FA_TO_EN=" + str(sum(before.count(x) for x in LABELS)))
        print("PROPOSED_CHANGE_BYTES=" + str(len(after.encode()) - len(before.encode())))
    elif args.mode == "install":
        if args.backup is None:
            parser.error("--backup is required")
        install(APP, args.backup)
    else:
        if args.backup is None:
            parser.error("--backup is required")
        rollback(APP, args.backup)


if __name__ == "__main__":
    main()
