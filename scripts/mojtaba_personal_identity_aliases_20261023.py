#!/usr/bin/env python3
"""Guarded metadata-only identity update for the independent personal site.

Updates the existing ProfilePage/Person JSON-LD in the shared Django base,
preserving every other template byte. Portrait URL is the verified original
owner-selected photo already served on the site, never a generated likeness.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile


APP = Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
BASE = APP / "templates/personal_site/base.html"
RESTART = APP / "tmp/restart.txt"
BACKUP_ROOT = Path("/home/zomorod2/.backups/mojtaba-name-identity-20261023")
PHOTO = (
    "https://mojplaywin.com/mojtaba.roozegar/assets/personal_site/"
    "official_profile_20261016/portrait.2935ce8cb70d.webp"
)
IDENTIFIER = "https://mojplaywin.com/mojtaba.roozegar/#person"
NAMES = (
    "روزگار", "Roozegar", "مجتبی روزگار", "Mojtaba Roozegar",
    "Mojtaba Rozegar", "Rozegar", "دکتر مجتبی روزگار",
    "Dr. Mojtaba Roozegar", "Dr. Mojtaba Rozegar", "Dr.mojtaba.rozegar",
)
SCRIPT = re.compile(
    r'(<script\s+type="application/ld\+json"\s*>)(.*?)(</script>)',
    re.DOTALL | re.IGNORECASE,
)


def sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def upgrade(source: str) -> str:
    matches = list(SCRIPT.finditer(source))
    selected = []
    for match in matches:
        try:
            data = json.loads(match.group(2))
        except json.JSONDecodeError:
            continue
        person = data.get("mainEntity") if data.get("@type") == "ProfilePage" else None
        if isinstance(person, dict) and person.get("@id") == IDENTIFIER:
            selected.append((match, data, person))
    if len(selected) != 1:
        raise ValueError("EXACTLY_ONE_PERSONAL_PROFILEPAGE_REQUIRED")
    match, data, person = selected[0]
    if person.get("name") != "Mojtaba Roozegar":
        raise ValueError("PERSON_IDENTITY_MISMATCH")
    existing = person.get("alternateName", [])
    if isinstance(existing, str):
        existing = [existing]
    if not isinstance(existing, list) or not all(isinstance(v, str) for v in existing):
        raise ValueError("UNSUPPORTED_ALTERNATE_NAME_SHAPE")
    person["alternateName"] = list(dict.fromkeys(existing + list(NAMES)))
    person["honorificPrefix"] = "Dr."
    person["image"] = PHOTO
    data["inLanguage"] = data.get("inLanguage") or "en"
    replacement = (
        match.group(1)
        + json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        + match.group(3)
    )
    result = source[:match.start()] + replacement + source[match.end():]
    if result.count("{%") != source.count("{%"):
        raise ValueError("DJANGO_TEMPLATE_TAG_COUNT_CHANGED")
    if result.count("<script") != source.count("<script"):
        raise ValueError("SCRIPT_COUNT_CHANGED")
    if "https://mojplaywin.com/mojtaba.roozegar/" not in result:
        raise ValueError("CANONICAL_IDENTITY_LOST")
    return result


def _atomic(path: Path, blob: bytes, mode: int) -> None:
    fd, temp = tempfile.mkstemp(prefix=".identity-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(blob)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.lexists(temp):
            os.unlink(temp)


def _paths(run: str) -> Path:
    if not re.fullmatch(r"[0-9]{6,24}", run):
        raise ValueError("INVALID_RUN_ID")
    if not APP.is_dir() or not (APP / "manage.py").is_file():
        raise ValueError("PERSONAL_APP_IDENTITY_MISMATCH")
    if not BASE.is_file() or BASE.is_symlink() or BASE.resolve() != BASE:
        raise ValueError("PERSONAL_BASE_TEMPLATE_UNAVAILABLE")
    if RESTART.is_symlink() or not RESTART.parent.is_dir():
        raise ValueError("PASSENGER_RESTART_PATH_INVALID")
    if BACKUP_ROOT.is_symlink():
        raise ValueError("BACKUP_ROOT_SYMLINK")
    return BACKUP_ROOT / run


def _validate_template(template: str) -> None:
    sys.path.insert(0, str(APP))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.template import engines
    engines["django"].engine.from_string(template)


def install(run: str) -> None:
    backup = _paths(run)
    before = BASE.read_bytes()
    text = before.decode("utf-8")
    after = upgrade(text).encode("utf-8")
    _validate_template(after.decode("utf-8"))
    if backup.exists() or backup.is_symlink():
        raise ValueError("BACKUP_RUN_ALREADY_EXISTS")
    backup.mkdir(mode=0o700, parents=True)
    _atomic(backup / "base.before", before, 0o600)
    data = {"run": run, "before": sha(before), "after": sha(after)}
    _atomic(
        backup / "manifest.json",
        json.dumps(data, sort_keys=True).encode("ascii"),
        0o600,
    )
    try:
        if sha(BASE.read_bytes()) != data["before"]:
            raise ValueError("CONCURRENT_BASE_TEMPLATE_CHANGE")
        _atomic(BASE, after, stat.S_IMODE(BASE.stat().st_mode))
        if sha(BASE.read_bytes()) != data["after"]:
            raise ValueError("SEO_TEMPLATE_WRITE_FAILED")
        RESTART.touch()
        print("MOJTABA_PERSONAL_ALIASES_AND_ORIGINAL_PHOTO_SCHEMA=INSTALLED")
        print("MOJTABA_PERSONAL_SEO_BACKUP=" + str(backup))
    except Exception:
        rollback(run)
        raise


def rollback(run: str) -> None:
    backup = _paths(run)
    manifest = backup / "manifest.json"
    if not manifest.is_file() or manifest.is_symlink():
        raise ValueError("ROLLBACK_MANIFEST_MISSING")
    data = json.loads(manifest.read_text(encoding="ascii"))
    original = (backup / "base.before").read_bytes()
    if data["run"] != run or sha(original) != data["before"]:
        raise ValueError("ROLLBACK_ORIGINAL_MISMATCH")
    current = BASE.read_bytes()
    if sha(current) not in (data["before"], data["after"]):
        raise ValueError("ROLLBACK_CONCURRENT_MODIFICATION")
    if sha(current) == data["after"]:
        _atomic(BASE, original, stat.S_IMODE(BASE.stat().st_mode))
        RESTART.touch()
    if sha(BASE.read_bytes()) != data["before"]:
        raise ValueError("ROLLBACK_VERIFICATION_FAILED")
    print("MOJTABA_PERSONAL_SEO_ROLLBACK=PASS")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "install":
        install(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "rollback":
        rollback(sys.argv[2])
    else:
        raise SystemExit("Usage: script.py install RUN_ID | rollback RUN_ID")
