#!/usr/bin/env python3
"""Hash-pinned, reversible MOJ PROP homepage SEO upgrade for 20 languages.

The live homepage is a separate static surface. This source-only deployer
changes only that file, keeps a private rollback copy, and never touches
Django, Passenger, payments, CRM, email, social accounts, or child sites.
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
BUNDLE = PRIVATE / "mpw-home-seo-20lang-20261122"
BEFORE = BUNDLE / "production-home.before"
MANIFEST = BUNDLE / "manifest.json"

BASE_SHA256 = "b76f16876d093900f6f855c5771f6ff3ebe374450a0c373dcb57f47635e0bc07"
CANDIDATE_SHA256 = "3b2b8dd9271ba059cf5df1dff6c09533100cceb1730ae5f30993a443e0be87f5"
BASE_BYTES = 266520
CANDIDATE_BYTES = 267908

OLD_H1 = '        <h1 id="mw-home-title">Moj <em>Play</em> Win</h1>'
NEW_H1 = '        <h1 id="mw-home-title">MOJ <em>PROP</em></h1>'
OLD_SUBTITLE = '        <h2 class="mpo-hero-subtitle">Innovative Digital Solutions for a Smarter World</h2>'
NEW_SUBTITLE = '        <h2 class="mpo-hero-subtitle">Simulated Trading Challenge &amp; Risk Management</h2>'
OLD_LEAD = (
    "        <p>Explore modern website development, original games, AI-powered tools, "
    "research and digital products for creators and businesses worldwide.</p>"
)
NEW_LEAD = (
    "        <p>MOJ PROP by MojPlayWin presents a transparent, simulation-first trading "
    "challenge focused on virtual capital, risk limits, trading discipline and documented "
    "performance. Read the rules before deciding; no guaranteed profit or real funded "
    "account is implied.</p>"
)
OLD_LANGUAGE_LINK = (
    '      <a class="mpw-mojprop-secondary" href="/moj-prop/languages/">'
    "MOJ PROP · 20 languages</a>"
)
NEW_LANGUAGE_LINK = (
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


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def once(source: str, old: str, new: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f"expected one source anchor, found {count}: {old[:80]}")
    return source.replace(old, new, 1)


def derive(source: bytes) -> bytes:
    if len(source) != BASE_BYTES or digest(source) != BASE_SHA256:
        raise ValueError("LIVE_SOURCE_SHA_MISMATCH")
    text = source.decode("utf-8")
    if text.count('id="mpw-mojprop-spotlight-20261121"') != 1:
        raise ValueError("MOJ_PROP_SPOTLIGHT_MISSING")
    text = once(text, OLD_H1, NEW_H1)
    text = once(text, OLD_SUBTITLE, NEW_SUBTITLE)
    text = once(text, OLD_LEAD, NEW_LEAD)
    text = once(text, OLD_LANGUAGE_LINK, NEW_LANGUAGE_LINK)
    candidate = text.encode("utf-8")
    if len(candidate) != CANDIDATE_BYTES or digest(candidate) != CANDIDATE_SHA256:
        raise ValueError("CANDIDATE_SHA_MISMATCH")
    if candidate.replace(NEW_H1.encode(), OLD_H1.encode(), 1) == candidate:
        raise ValueError("REVERSIBILITY_CHECK_FAILED")
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
            dir=TARGET.parent, prefix=".mpw-home-seo-", delete=False
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
    if BUNDLE.exists():
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
    if digest(current) != CANDIDATE_SHA256:
        raise ValueError("LIVE_SOURCE_IS_NOT_THIS_RELEASE")
    if not BEFORE.is_file() or BEFORE.is_symlink():
        raise ValueError("PRIVATE_ROLLBACK_MISSING")
    previous = BEFORE.read_bytes()
    if digest(previous) != BASE_SHA256:
        raise ValueError("PRIVATE_ROLLBACK_SHA_MISMATCH")
    atomic_replace(previous, mode)
    restored, _ = read_target()
    if digest(restored) != BASE_SHA256:
        raise RuntimeError("ROLLBACK_VERIFICATION_FAILED")


def main(argv: list[str]) -> int:
    if argv == ["--check"]:
        source, _ = read_target()
        candidate = derive(source)
        print(json.dumps({"mode": "check", "before": digest(source), "after": digest(candidate)}))
        return 0
    if argv == ["--apply"]:
        apply_change()
        print(json.dumps({"mode": "apply", "after": CANDIDATE_SHA256}))
        return 0
    if argv == ["--rollback"]:
        rollback_change()
        print(json.dumps({"mode": "rollback", "after": BASE_SHA256}))
        return 0
    raise SystemExit("usage: --check | --apply | --rollback")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
