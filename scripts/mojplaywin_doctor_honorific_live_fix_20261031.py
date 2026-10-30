#!/usr/bin/env python3
"""Surgical, reversible correction of the MojPlayWin founder's public honorific.

Executed only via the pinned private GitHub Actions -> VPS -> cPanel path.
Keeps the existing HTML, image galleries, routes, and styling unchanged.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

PAGE = Path("/home/zomorod2/Saeit/design-preview-20261017/professor-mojtaba-roozegar-20261018.html")
BACKUP_ROOT = Path("/home/zomorod2")
MARKER = "MOJPLAYWIN_PROFESSOR_MOJTabA_ROOZEGAR_PROFILE_20261018"
OLD_SENTENCE = (
    "The public materials currently consulted do not include degree-certificate images, "
    "dates of enrolment, an authenticated thesis record or confirmation of a formal "
    "professorial appointment. The designation “Professor” in this heading follows the "
    "owner's requested form of address; it is not presented as proof of a university faculty rank."
)
NEW_SENTENCE = (
    "The public materials currently consulted do not include degree-certificate images, "
    "dates of enrolment or an authenticated thesis record. The appropriate form of address "
    "is “Dr.”, based on the owner's reported PhD; no university faculty appointment is claimed."
)
OLD_RANK = (
    "institutional credential verification and proof of appointment to a professorial rank "
    "are not available in the material reviewed for this publication."
)
NEW_RANK = (
    "independent credential verification is not available in the material reviewed for "
    "this publication; no university faculty rank is claimed."
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_run_id(value: str) -> str:
    if not re.fullmatch(r"[0-9]{6,25}", value):
        raise RuntimeError("Invalid GitHub run identifier")
    return value


def backup_path(run_id: str) -> Path:
    return BACKUP_ROOT / (".mpw-doctor-honorific-" + run_id + ".bak.html")


def state_path(run_id: str) -> Path:
    return BACKUP_ROOT / (".mpw-doctor-honorific-" + run_id + ".json")


def check_page() -> None:
    if not PAGE.is_file() or PAGE.is_symlink() or PAGE.parent.is_symlink():
        raise RuntimeError("Expected regular public profile file is missing")
    if PAGE.stat().st_size < 24000 or PAGE.stat().st_size > 250000:
        raise RuntimeError("Unexpected live profile file size")


def check_invariants(content: str) -> None:
    for required in (
        MARKER,
        "mpw-sport-white-selection-20261018",
        "Universiti Putra Malaysia",
        "official_profile_20261016/portrait.2935ce8cb70d.webp",
        "Casual sport portrait",
        "Outdoor sport-jacket portrait",
        "White-shirt portrait",
    ):
        if required not in content:
            raise RuntimeError("Profile guard failed: " + required)
    if len(re.findall(r"<h1\b", content, re.I)) != 1:
        raise RuntimeError("Unexpected number of page headings")
    if content.count('class="mpw-sport-white-card ') != 3:
        raise RuntimeError("Unexpected portrait gallery size")


def correction(content: str) -> str:
    check_invariants(content)
    if content.count("Professor Mojtaba Roozegar") < 3:
        raise RuntimeError("Expected uncorrected public profile was not found")
    if content.count(OLD_SENTENCE) != 1 or content.count(OLD_RANK) != 1:
        raise RuntimeError("Cannot safely match old qualification note")
    updated = content.replace("Professor Mojtaba Roozegar", "Dr. Mojtaba Roozegar")
    updated = updated.replace(OLD_SENTENCE, NEW_SENTENCE).replace(OLD_RANK, NEW_RANK)
    updated = updated.replace("پروفسور مجتبی روزگار", "دکتر مجتبی روزگار")
    updated = updated.replace("پرفسور مجتبی روزگار", "دکتر مجتبی روزگار")
    check_invariants(updated)
    if "Professor Mojtaba Roozegar" in updated or OLD_SENTENCE in updated:
        raise RuntimeError("Incorrect title survived correction")
    if "<h1" not in updated or "Dr. Mojtaba Roozegar" not in updated:
        raise RuntimeError("Corrected visible title missing")
    if "honorificPrefix" not in updated or '"Dr."' not in updated:
        raise RuntimeError("Existing structured title missing")
    return updated


def atomic_write(path: Path, data: bytes, mode: int) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".mpw-honorific-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            os.fchmod(output.fileno(), mode)
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def exclusive_backup(path: Path, data: bytes) -> None:
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())


def install(run_id: str) -> None:
    check_page()
    before = PAGE.read_bytes()
    after = correction(before.decode("utf-8")).encode("utf-8")
    original_sha = digest(before)
    revised_sha = digest(after)
    if backup_path(run_id).exists() or state_path(run_id).exists():
        raise RuntimeError("Run-specific backup/state already exists")
    exclusive_backup(backup_path(run_id), before)
    state = {
        "run_id": run_id,
        "target": str(PAGE),
        "old_sha256": original_sha,
        "new_sha256": revised_sha,
    }
    atomic_write(state_path(run_id), json.dumps(state, sort_keys=True).encode(), 0o600)
    if digest(PAGE.read_bytes()) != original_sha:
        raise RuntimeError("Live target changed after backup; refusing write")
    atomic_write(PAGE, after, 0o644)
    if digest(PAGE.read_bytes()) != revised_sha:
        raise RuntimeError("Post-write readback failed")
    print(json.dumps({"status": "DOCTOR_TITLE_APPLIED", **state}))


def rollback(run_id: str) -> None:
    check_page()
    state = json.loads(state_path(run_id).read_text("utf-8"))
    if state.get("run_id") != run_id or state.get("target") != str(PAGE):
        raise RuntimeError("Rollback metadata mismatch")
    current = PAGE.read_bytes()
    previous = backup_path(run_id).read_bytes()
    if digest(current) != state.get("new_sha256") or digest(previous) != state.get("old_sha256"):
        raise RuntimeError("Rollback refused: content changed or backup invalid")
    atomic_write(PAGE, previous, 0o644)
    print(json.dumps({"status": "DOCTOR_TITLE_ROLLED_BACK", "sha256": digest(PAGE.read_bytes())}))


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("install", "rollback"):
        raise SystemExit("Usage: <script> install|rollback <numeric_run_id>")
    run = safe_run_id(sys.argv[2])
    (install if sys.argv[1] == "install" else rollback)(run)
