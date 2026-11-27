#!/usr/bin/env python3
"""Reversible homepage-only localization of the MOJ PROP language-link labels.

The existing localized pages and their URLs are preserved. Visible labels name
the localized prop-trading concept; each link retains its correct lang value
and an accessible language label. This file does not run during import.
"""
from __future__ import annotations

import getpass
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

TARGET = Path(
    "/home/zomorod2/mojplaywin.com/"
    "design-preview-20261017/production-home-20261017.html"
)
PRIVATE = Path("/home/zomorod2/.private_mojplaywin_main_agents")
BUNDLE = PRIVATE / "mpw-home-prop-labels-20261124"
BEFORE = BUNDLE / "production-home.before"
MANIFEST = BUNDLE / "manifest.json"

# Exact output of the already-recorded 2026-11-22 homepage SEO release.
BASE_SHA256 = "3b2b8dd9271ba059cf5df1dff6c09533100cceb1730ae5f30993a443e0be87f5"
BASE_BYTES = 267908

OLD_LINK = (
    '      <nav class="mpw-mojprop-language-links" aria-label="MOJ PROP language editions">'
    '<span>MOJ PROP in 20 languages:</span> '
    '<a href="/moj-prop/" lang="en">English</a> '
    '<a href="/moj-prop/languages/zh/" lang="zh">简体中文</a> '
    '<a href="/moj-prop/languages/hi/" lang="hi">हिन्दी</a> '
    '<a href="/moj-prop/languages/es/" lang="es">Español</a> '
    '<a href="/moj-prop/languages/ar/" lang="ar" dir="rtl">العربية</a> '
    '<a href="/moj-prop/languages/fr/" lang="fr">Français</a> '
    '<a href="/moj-prop/languages/bn/" lang="bn">বাংলা</a> '
    '<a href="/moj-prop/languages/pt/" lang="pt">Português</a> '
    '<a href="/moj-prop/languages/id/" lang="id">Bahasa Indonesia</a> '
    '<a href="/moj-prop/languages/ur/" lang="ur" dir="rtl">اردو</a> '
    '<a href="/moj-prop/languages/ru/" lang="ru">Русский</a> '
    '<a href="/moj-prop/languages/de/" lang="de">Deutsch</a> '
    '<a href="/moj-prop/languages/ja/" lang="ja">日本語</a> '
    '<a href="/moj-prop/languages/ar-eg/" lang="ar-EG" dir="rtl">مصرى</a> '
    '<a href="/moj-prop/languages/mr/" lang="mr">मराठी</a> '
    '<a href="/moj-prop/languages/vi/" lang="vi">Tiếng Việt</a> '
    '<a href="/moj-prop/languages/te/" lang="te">తెలుగు</a> '
    '<a href="/moj-prop/languages/sw/" lang="sw">Kiswahili</a> '
    '<a href="/moj-prop/languages/tr/" lang="tr">Türkçe</a> '
    '<a href="/moj-prop/languages/pcm/" lang="pcm">Naijá Pidgin</a>'
    "</nav>"
)

NEW_LINK = (
    '      <nav class="mpw-mojprop-language-links" aria-label="MOJ PROP editions">'
    '<span>MOJ PROP ·</span> '
    '<a href="/moj-prop/" lang="en" aria-label="English edition">Prop trading</a> '
    '<a href="/moj-prop/languages/zh/" lang="zh" aria-label="Simplified Chinese edition">自营交易</a> '
    '<a href="/moj-prop/languages/hi/" lang="hi" aria-label="Hindi edition">प्रॉप ट्रेडिंग</a> '
    '<a href="/moj-prop/languages/es/" lang="es" aria-label="Spanish edition">Trading por cuenta propia</a> '
    '<a href="/moj-prop/languages/ar/" lang="ar" dir="rtl" aria-label="Arabic edition">تداول لحساب الشركة</a> '
    '<a href="/moj-prop/languages/fr/" lang="fr" aria-label="French edition">Trading pour compte propre</a> '
    '<a href="/moj-prop/languages/bn/" lang="bn" aria-label="Bengali edition">প্রপ ট্রেডিং</a> '
    '<a href="/moj-prop/languages/pt/" lang="pt" aria-label="Portuguese edition">Trading por conta própria</a> '
    '<a href="/moj-prop/languages/id/" lang="id" aria-label="Indonesian edition">Perdagangan prop</a> '
    '<a href="/moj-prop/languages/ur/" lang="ur" dir="rtl" aria-label="Urdu edition">پراپ ٹریڈنگ</a> '
    '<a href="/moj-prop/languages/ru/" lang="ru" aria-label="Russian edition">Проп-трейдинг</a> '
    '<a href="/moj-prop/languages/de/" lang="de" aria-label="German edition">Eigenhandel</a> '
    '<a href="/moj-prop/languages/ja/" lang="ja" aria-label="Japanese edition">プロップトレーディング</a> '
    '<a href="/moj-prop/languages/ar-eg/" lang="ar-EG" dir="rtl" aria-label="Egyptian Arabic edition">تداول لحساب الشركة</a> '
    '<a href="/moj-prop/languages/mr/" lang="mr" aria-label="Marathi edition">प्रॉप ट्रेडिंग</a> '
    '<a href="/moj-prop/languages/vi/" lang="vi" aria-label="Vietnamese edition">Giao dịch tự doanh</a> '
    '<a href="/moj-prop/languages/te/" lang="te" aria-label="Telugu edition">స్వంత నిధుల ట్రేడింగ్</a> '
    '<a href="/moj-prop/languages/sw/" lang="sw" aria-label="Swahili edition">Biashara ya mtaji wa kampuni</a> '
    '<a href="/moj-prop/languages/tr/" lang="tr" aria-label="Turkish edition">Öz sermayeli işlem</a> '
    '<a href="/moj-prop/languages/pcm/" lang="pcm" aria-label="Nigerian Pidgin edition">Prop trading</a>'
    "</nav>"
)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def derive(source: bytes) -> bytes:
    if len(source) != BASE_BYTES or digest(source) != BASE_SHA256:
        raise ValueError("LIVE_SOURCE_SHA_MISMATCH")
    text = source.decode("utf-8")
    if text.count(OLD_LINK) != 1:
        raise ValueError("EXPECTED_LANGUAGE_NAV_NOT_UNIQUE")
    candidate = text.replace(OLD_LINK, NEW_LINK, 1).encode("utf-8")
    if candidate == source or text.count(NEW_LINK) != 0:
        raise ValueError("NO_UNIQUE_NAV_CHANGE")
    return candidate


def read_target() -> tuple[bytes, int]:
    if getpass.getuser() != "zomorod2":
        raise ValueError("OWNER_CPANEL_USER_REQUIRED")
    if TARGET.is_symlink() or not TARGET.is_file() or TARGET.parent.is_symlink():
        raise ValueError("UNSAFE_TARGET")
    metadata = TARGET.stat()
    if metadata.st_uid != os.geteuid() or metadata.st_nlink != 1:
        raise ValueError("UNVERIFIED_TARGET_OWNERSHIP")
    return TARGET.read_bytes(), stat.S_IMODE(metadata.st_mode)


def atomic_replace(data: bytes, mode: int) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=TARGET.parent, prefix=".mpw-prop-labels-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, TARGET)
        temporary = None
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def apply_change() -> None:
    before, mode = read_target()
    candidate = derive(before)
    if BUNDLE.exists() or BUNDLE.is_symlink():
        raise ValueError("ROLLBACK_BUNDLE_ALREADY_EXISTS")
    BUNDLE.mkdir(parents=True, mode=0o700)
    BEFORE.write_bytes(before)
    os.chmod(BEFORE, 0o600)
    MANIFEST.write_text(
        json.dumps(
            {
                "target": str(TARGET),
                "before_sha256": digest(before),
                "after_sha256": digest(candidate),
                "before_bytes": len(before),
                "after_bytes": len(candidate),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    os.chmod(MANIFEST, 0o600)
    atomic_replace(candidate, mode)
    current, _ = read_target()
    if current != candidate:
        raise RuntimeError("POST_WRITE_VERIFICATION_FAILED")


def rollback_change() -> None:
    current, mode = read_target()
    if not MANIFEST.is_file() or MANIFEST.is_symlink():
        raise ValueError("PRIVATE_ROLLBACK_MANIFEST_MISSING")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if digest(current) != manifest.get("after_sha256"):
        raise ValueError("LIVE_SOURCE_CHANGED_SINCE_RELEASE")
    if not BEFORE.is_file() or BEFORE.is_symlink():
        raise ValueError("PRIVATE_ROLLBACK_MISSING")
    previous = BEFORE.read_bytes()
    if digest(previous) != manifest.get("before_sha256"):
        raise ValueError("PRIVATE_ROLLBACK_SHA_MISMATCH")
    atomic_replace(previous, mode)
    restored, _ = read_target()
    if digest(restored) != manifest["before_sha256"]:
        raise RuntimeError("ROLLBACK_VERIFICATION_FAILED")


def main(argv: list[str]) -> int:
    if argv == ["--check"]:
        source, _ = read_target()
        candidate = derive(source)
        print(json.dumps({"mode": "check", "before": digest(source), "after": digest(candidate)}))
        return 0
    if argv == ["--apply"]:
        apply_change()
        print(json.dumps({"mode": "apply", "after": digest(TARGET.read_bytes())}))
        return 0
    if argv == ["--rollback"]:
        rollback_change()
        print(json.dumps({"mode": "rollback", "after": digest(TARGET.read_bytes())}))
        return 0
    raise SystemExit("usage: --check | --apply | --rollback")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
