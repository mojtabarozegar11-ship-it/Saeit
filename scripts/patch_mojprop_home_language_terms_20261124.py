#!/usr/bin/env python3
"""Replace visible language names with the localized word "Prop" only.

The homepage route is an owner-maintained static Apache surface. This
fail-closed patch changes one exact navigation block, keeps every language
URL and lang attribute unchanged, writes a private rollback copy, and refuses
unexpected markup.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

TARGET = Path("/home/zomorod2/mojplaywin.com/design-preview-20261017/production-home-20261017.html")
BACKUPS = Path("/home/zomorod2/.mojplaywin-moj-prop-language-term-backups-v1")
SCHEMA = "mojprop.home-language-terms.v1"
NAV_RE = re.compile(
    r'<nav class="mpw-mojprop-language-links" aria-label="MOJ PROP language editions">.*?</nav>',
    re.S,
)
OLD_VISIBLE = (
    "English", "简体中文", "हिन्दी", "Español", "العربية", "Français",
    "বাংলা", "Português", "Bahasa Indonesia", "اردو", "Русский", "Deutsch",
    "日本語", "مصرى", "मराठी", "Tiếng Việt", "తెలుగు", "Kiswahili",
    "Türkçe", "Naijá Pidgin",
)
NEW_VISIBLE = (
    "Prop", "普罗普", "प्रॉप", "Prop", "بروب", "Prop",
    "প্রপ", "Prop", "Prop", "پراپ", "Проп", "Prop",
    "プロップ", "بروب", "प्रॉप", "Prop", "ప్రాప్", "Prop",
    "Prop", "Prop",
)
LANG_CODES = (
    "en", "zh", "hi", "es", "ar", "fr", "bn", "pt", "id", "ur",
    "ru", "de", "ja", "ar-EG", "mr", "vi", "te", "sw", "tr", "pcm",
)


def fail(message: str) -> "NoReturn":
    raise RuntimeError(message)


def safe_id(value: str) -> str:
    if not re.fullmatch(r"[0-9]{1,20}", value):
        fail("Invalid deployment run ID")
    return value


def safe_sha(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        fail("Invalid deployment commit SHA")
    return value


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assert_target() -> None:
    if os.geteuid() <= 0:
        fail("Root execution is refused")
    if TARGET.is_symlink() or not TARGET.is_file() or TARGET.parent.is_symlink():
        fail("Homepage target is missing or symlinked")
    info = TARGET.stat()
    if info.st_uid != os.geteuid() or info.st_nlink != 1 or info.st_mode & 0o002:
        fail("Homepage ownership or permissions are unsafe")


def verify_backup_root(create: bool) -> None:
    parent = BACKUPS.parent
    if parent.is_symlink() or not parent.is_dir():
        fail("Backup parent is not trusted")
    parent_info = parent.stat()
    if parent_info.st_uid != os.geteuid() or parent_info.st_mode & stat.S_IWOTH:
        fail("Backup parent owner or mode is unsafe")
    if BACKUPS.is_symlink():
        fail("Backup root is symlinked")
    if BACKUPS.exists():
        info = BACKUPS.stat()
        if info.st_uid != os.geteuid() or info.st_mode & 0o077:
            fail("Backup root owner or mode is unsafe")
    elif create:
        BACKUPS.mkdir(mode=0o700)
    else:
        fail("Backup root is missing")


def expected_block() -> str:
    links = (
        ('/moj-prop/', 'en', 'English', ''),
        ('/moj-prop/languages/zh/', 'zh', '简体中文', ''),
        ('/moj-prop/languages/hi/', 'hi', 'हिन्दी', ''),
        ('/moj-prop/languages/es/', 'es', 'Español', ''),
        ('/moj-prop/languages/ar/', 'ar', 'العربية', ' dir="rtl"'),
        ('/moj-prop/languages/fr/', 'fr', 'Français', ''),
        ('/moj-prop/languages/bn/', 'bn', 'বাংলা', ''),
        ('/moj-prop/languages/pt/', 'pt', 'Português', ''),
        ('/moj-prop/languages/id/', 'id', 'Bahasa Indonesia', ''),
        ('/moj-prop/languages/ur/', 'ur', 'اردو', ' dir="rtl"'),
        ('/moj-prop/languages/ru/', 'ru', 'Русский', ''),
        ('/moj-prop/languages/de/', 'de', 'Deutsch', ''),
        ('/moj-prop/languages/ja/', 'ja', '日本語', ''),
        ('/moj-prop/languages/ar-eg/', 'ar-EG', 'مصرى', ' dir="rtl"'),
        ('/moj-prop/languages/mr/', 'mr', 'मराठी', ''),
        ('/moj-prop/languages/vi/', 'vi', 'Tiếng Việt', ''),
        ('/moj-prop/languages/te/', 'te', 'తెలుగు', ''),
        ('/moj-prop/languages/sw/', 'sw', 'Kiswahili', ''),
        ('/moj-prop/languages/tr/', 'tr', 'Türkçe', ''),
        ('/moj-prop/languages/pcm/', 'pcm', 'Naijá Pidgin', ''),
    )
    return (
        '<nav class="mpw-mojprop-language-links" aria-label="MOJ PROP language editions">'
        '<span>MOJ PROP in 20 languages:</span> ' +
        ' '.join(
            f'<a href="{href}" lang="{lang}"{direction}>{label}</a>'
            for href, lang, label, direction in links
        ) +
        '</nav>'
    )


def localized_block() -> str:
    links = (
        ('/moj-prop/', 'en', 'Prop', ''),
        ('/moj-prop/languages/zh/', 'zh', '普罗普', ''),
        ('/moj-prop/languages/hi/', 'hi', 'प्रॉप', ''),
        ('/moj-prop/languages/es/', 'es', 'Prop', ''),
        ('/moj-prop/languages/ar/', 'ar', 'بروب', ' dir="rtl"'),
        ('/moj-prop/languages/fr/', 'fr', 'Prop', ''),
        ('/moj-prop/languages/bn/', 'bn', 'প্রপ', ''),
        ('/moj-prop/languages/pt/', 'pt', 'Prop', ''),
        ('/moj-prop/languages/id/', 'id', 'Prop', ''),
        ('/moj-prop/languages/ur/', 'ur', 'پراپ', ' dir="rtl"'),
        ('/moj-prop/languages/ru/', 'ru', 'Проп', ''),
        ('/moj-prop/languages/de/', 'de', 'Prop', ''),
        ('/moj-prop/languages/ja/', 'ja', 'プロップ', ''),
        ('/moj-prop/languages/ar-eg/', 'ar-EG', 'بروب', ' dir="rtl"'),
        ('/moj-prop/languages/mr/', 'mr', 'प्रॉप', ''),
        ('/moj-prop/languages/vi/', 'vi', 'Prop', ''),
        ('/moj-prop/languages/te/', 'te', 'ప్రాప్', ''),
        ('/moj-prop/languages/sw/', 'sw', 'Prop', ''),
        ('/moj-prop/languages/tr/', 'tr', 'Prop', ''),
        ('/moj-prop/languages/pcm/', 'pcm', 'Prop', ''),
    )
    return (
        '<nav class="mpw-mojprop-language-links" aria-label="MOJ PROP language editions">'
        '<span>MOJ PROP:</span> ' +
        ' '.join(
            f'<a href="{href}" lang="{lang}"{direction}>{label}</a>'
            for href, lang, label, direction in links
        ) +
        '</nav>'
    )


def derive(raw: bytes) -> bytes:
    text = raw.decode("utf-8")
    matches = NAV_RE.findall(text)
    if len(matches) != 1:
        fail(f"Expected exactly one language navigation block, found {len(matches)}")
    old_block = matches[0]
    if old_block == localized_block():
        print("MOJ_PROP_LANGUAGE_TERMS_ALREADY_PATCHED")
        return raw
    if old_block != expected_block():
        fail("Language navigation differs from the reviewed name-list block")
    for value in OLD_VISIBLE:
        if value not in old_block:
            fail("A reviewed language name is missing")
    if len(re.findall(r"<a ", old_block)) != 20:
        fail("Expected exactly 20 language links")
    updated = text.replace(old_block, localized_block(), 1).encode("utf-8")
    if updated.count(localized_block().encode("utf-8")) != 1:
        fail("Localized language block verification failed")
    return updated


def atomic_write(data: bytes, mode: int) -> None:
    fd, name = tempfile.mkstemp(prefix=".mojprop-language-", dir=str(TARGET.parent))
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, TARGET)
    finally:
        if temporary.exists():
            temporary.unlink()


def deploy(run_id: str, commit_sha: str) -> None:
    run_id = safe_id(run_id)
    commit_sha = safe_sha(commit_sha)
    assert_target()
    verify_backup_root(create=True)
    backup = BACKUPS / ("home-language-" + run_id)
    if backup.exists():
        fail("A backup for this run already exists")
    before = TARGET.read_bytes()
    after = derive(before)
    if after == before:
        return
    backup.mkdir(mode=0o700)
    (backup / "production-home.before").write_bytes(before)
    os.chmod(backup / "production-home.before", 0o600)
    manifest = {
        "schema": SCHEMA,
        "run_id": run_id,
        "commit_sha": commit_sha,
        "target": str(TARGET),
        "before_sha": digest(before),
        "after_sha": digest(after),
        "before_bytes": len(before),
        "after_bytes": len(after),
        "rolled_back": False,
    }
    (backup / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.chmod(backup / "manifest.json", 0o600)
    atomic_write(after, TARGET.stat().st_mode & 0o777)
    if TARGET.read_bytes() != after:
        fail("Post-write verification failed")
    print("MOJ_PROP_LANGUAGE_TERMS_PATCH=PASS")
    print("MOJ_PROP_LANGUAGE_TERMS_BACKUP=" + str(backup))


def rollback(run_id: str) -> None:
    run_id = safe_id(run_id)
    assert_target()
    verify_backup_root(create=False)
    backup = BACKUPS / ("home-language-" + run_id)
    manifest_path = backup / "manifest.json"
    saved_path = backup / "production-home.before"
    if backup.is_symlink() or not backup.is_dir() or manifest_path.is_symlink() or saved_path.is_symlink():
        fail("Unsafe rollback backup")
    manifest = json.loads(manifest_path.read_text("utf-8"))
    if manifest.get("schema") != SCHEMA or manifest.get("run_id") != run_id:
        fail("Rollback identity mismatch")
    current = TARGET.read_bytes()
    if digest(current) != manifest.get("after_sha"):
        fail("Refusing rollback after subsequent homepage modification")
    previous = saved_path.read_bytes()
    if digest(previous) != manifest.get("before_sha"):
        fail("Rollback checksum mismatch")
    atomic_write(previous, int(manifest["before_bytes"] and (TARGET.stat().st_mode & 0o777)))
    if digest(TARGET.read_bytes()) != manifest.get("before_sha"):
        fail("Rollback verification failed")
    manifest["rolled_back"] = True
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("MOJ_PROP_LANGUAGE_TERMS_ROLLBACK=PASS")


def main() -> None:
    if len(sys.argv) == 4 and sys.argv[1] == "deploy":
        deploy(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == "rollback":
        rollback(sys.argv[2])
    else:
        fail("Usage: deploy RUN_ID COMMIT_SHA | rollback RUN_ID")


if __name__ == "__main__":
    main()
