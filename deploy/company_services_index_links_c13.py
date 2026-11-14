#!/usr/bin/env python3
"""Single-file additive cPanel services navigation patch, SHA-pinned and reversible.

No Django, PHP, payment, lead database, rewrite, theme or third-party changes.
Only six real, already-live service links are added before </body> of the
previously verified ~/public_html/services/index.html. Private backup outside
webroot precedes atomic replacement. Only the cPanel owner may execute.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import sys

ROOT = Path.home() / "public_html" / "services"
INDEX = ROOT / "index.html"
RECOVERY = Path.home() / ".c13-services-index-recovery"
BACKUP = RECOVERY / "index.before.html"
MANIFEST = RECOVERY / "manifest.json"
TMP = ROOT / ".c13-index-atomic.tmp"
EXPECTED_ORIGINAL = "9c446a09f66ab91c3ce1dd70f1aef4105202bb1a7aed53c0463f3e99eb80ca80"
CODES = ("AGR-01", "RS-01", "RS-02", "RS-03", "WEB-01", "SEO-01")
TITLES = (
    "تحلیل اقتصاد و سودآوری مزرعه",
    "ممیزی شاخص‌های پژوهش کشاورزی",
    "ممیزی سناریوی آبیاری",
    "طراحی آزمایش و بررسی اقتصادی تحقیق",
    "طراحی مسیر درخواست و فروش کسب‌وکار",
    "ممیزی فنی و محتوایی سئو",
)

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def fail(code: str) -> None:
    print("ZM_C13_SERVICES_NAV_STATE=" + code)
    raise SystemExit(72)

def owned_regular(path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    meta = path.stat()
    return stat.S_ISREG(meta.st_mode) and meta.st_uid == os.getuid() and 0 < meta.st_size < 250_000

def dir_ok(path: Path) -> bool:
    if path.is_symlink() or not path.is_dir():
        return False
    meta=path.stat()
    return stat.S_ISDIR(meta.st_mode) and meta.st_uid == os.getuid()

def base_guard() -> None:
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        fail("WRONG_OWNER")
    if not dir_ok(ROOT) or not owned_regular(INDEX):
        fail("PUBLIC_INDEX_IDENTITY_FAILED")
    if TMP.exists() or TMP.is_symlink():
        fail("ATOMIC_TEMP_COLLISION")

def html_insert(old: bytes) -> bytes:
    if sha(old) != EXPECTED_ORIGINAL:
        fail("SOURCE_HASH_CHANGED_REFUSE_TO_TOUCH")
    lower = old.lower()
    if lower.count(b"</body>") != 1 or b"<html" not in lower:
        fail("HTML_ANCHOR_MISSING_OR_AMBIGUOUS")
    if b'id="service-offers-heading"' in old or b"/services/scope/" in old:
        fail("OFFERS_ALREADY_PRESENT")
    entries = "\n".join(
        f'<li><a href="/services/scope/{code}/">{title}</a> <small>({code})</small></li>'
        for code, title in zip(CODES, TITLES)
    )
    block = f"""
<section id="zm-commercial-six-c13" dir="rtl" aria-labelledby="service-offers-heading" style="max-width:1100px;margin:2rem auto;padding:1.25rem;border:1px solid #d7e5df;border-radius:16px;background:#f7fbf8;color:#143b31;line-height:1.9">
  <h2 id="service-offers-heading" style="font-size:1.45rem">۶ خدمت تخصصی قابل استعلام زمرد ملل</h2>
  <p>دامنه، مدارک لازم و خروجی هر خدمت را بررسی کنید. ثبت استعلام به‌معنای سفارش قطعی یا تعهد به قیمت نیست.</p>
  <ul>{entries}</ul>
  <p>خدمات از طریق فرم رسمی فعلی شرکت بررسی می‌شوند؛ در مرحله استعلام پرداختی لازم نیست.</p>
</section>
""".encode("utf-8")
    offset = lower.rfind(b"</body>")
    return old[:offset] + block + old[offset:]

def exclusive(path: Path, data: bytes, mode: int) -> None:
    fd = os.open(str(path), os.O_WRONLY | os.O_EXCL | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), mode)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())

def apply() -> None:
    base_guard()
    if RECOVERY.exists() or RECOVERY.is_symlink():
        fail("RECOVERY_LOCATION_ALREADY_EXISTS")
    old = INDEX.read_bytes()
    changed = html_insert(old)
    original_mode = stat.S_IMODE(INDEX.stat().st_mode)
    if not (original_mode & stat.S_IRUSR):
        fail("UNEXPECTED_FILE_MODE")
    RECOVERY.mkdir(mode=0o700)
    try:
        exclusive(BACKUP, old, 0o600)
        manifest = {
            "schema": "ZM_C13_SERVICES_NAV_V1",
            "before_sha256": sha(old),
            "after_sha256": sha(changed),
            "mode": original_mode,
            "six_services": list(CODES),
            "backup_outside_public_webroot": True,
        }
        exclusive(MANIFEST, (json.dumps(manifest, sort_keys=True) + "\n").encode("utf-8"), 0o600)
        exclusive(TMP, changed, original_mode)
        if sha(INDEX.read_bytes()) != EXPECTED_ORIGINAL:
            fail("SOURCE_CHANGED_CONCURRENTLY")
        os.replace(TMP, INDEX)
        os.chmod(INDEX, original_mode)
    finally:
        if TMP.exists() and not TMP.is_symlink():
            TMP.unlink()
    print("ZM_C13_SERVICES_NAV_SIX_LINKS_ADDED=true")
    print("ZM_C13_SERVICES_NAV_OLD_SHA256="+sha(old))
    print("ZM_C13_SERVICES_NAV_NEW_SHA256="+sha(changed))
    print("ZM_C13_SERVICES_NAV_PRIVATE_BACKUP=true")
    print("ZM_C13_SERVICES_NAV_OTHER_PAGES_UNMODIFIED=true")

def rollback() -> None:
    base_guard()
    if not dir_ok(RECOVERY) or not owned_regular(BACKUP) or not owned_regular(MANIFEST):
        fail("BACKUP_UNAVAILABLE")
    evidence = json.loads(MANIFEST.read_text("utf-8"))
    if evidence.get("schema") != "ZM_C13_SERVICES_NAV_V1":
        fail("INVALID_MANIFEST")
    before = BACKUP.read_bytes()
    live = INDEX.read_bytes()
    if sha(before) != evidence.get("before_sha256") or sha(live) != evidence.get("after_sha256"):
        fail("HASH_CHANGED_ROLLBACK_REFUSED")
    exclusive(TMP, before, evidence["mode"])
    os.replace(TMP, INDEX)
    os.chmod(INDEX, evidence["mode"])
    print("ZM_C13_SERVICES_NAV_ROLLBACK_ORIGINAL_RESTORED=true")
    # Preserve private backup and manifest for audit; never delete customer data.

def main() -> None:
    os.umask(0o077)
    if len(sys.argv) != 2:
        fail("MODE_REQUIRED")
    if sys.argv[1] == "apply":
        apply()
    elif sys.argv[1] == "rollback":
        rollback()
    else:
        fail("UNAUTHORIZED_MODE")

if __name__ == "__main__":
    main()
