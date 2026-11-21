#!/usr/bin/env python3
"""Show owner-reported historical research count separately from verified records.

Only patches the existing public research-project index.html. Never modifies
projects.json, evidence, approvals, or any other public/private document.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

MARKER = "zm-owner-reported-projects-20261023"
REGISTRY_MARKER = "zm-research-project-directory-20261023"
ANCHOR = '<div class="zm-registry-overview" role="group" aria-label="شاخص‌های ثبت پروژه">'
CARD = """<aside id="zm-owner-reported-projects-20261023" class="zm-owner-research-summary" role="note" aria-label="آمار اعلامی پروژه‌های پژوهشی شرکت">
<span class="zm-owner-research-eyebrow">آمار تاریخی اعلام‌شده از سوی مدیریت شرکت · مستقل از فهرست مستندات عمومی</span>
<div class="zm-owner-research-number">۱٬۴۵۷ <span>پروژه پژوهشی و تحقیقات علمی انجام‌شده</span></div>
<p>بر اساس اعلام مدیریت شرکت کشت و صنعت زمرد ملل، این تعداد پروژه از <strong>آبان ۱۳۹۸ تا ۲۳ اکتبر ۲۰۲۶</strong> انجام شده است. این آمار هنوز به‌صورت پرونده‌به‌پرونده در سامانه عمومی راستی‌آزمایی نشده و به معنای انتشار یا تأیید مستقل ۱٬۴۵۷ شناسنامه نیست. شمار پرونده‌های دارای مدارک و مجوز انتشار، به‌صورت جداگانه در پایین نمایش داده می‌شود.</p>
</aside>"""
STYLE = """<style id="zm-owner-research-summary-style-20261023">
.zm-owner-research-summary{border:1px solid rgba(222,188,99,.5);border-radius:20px;background:linear-gradient(120deg,rgba(53,88,59,.42),rgba(18,42,23,.4));padding:clamp(18px,3vw,32px);margin:22px 0 24px}
.zm-owner-research-eyebrow{display:block;color:#e7ce88;font-size:.92rem;line-height:1.9}
.zm-owner-research-number{color:#f6d990;font-weight:800;font-size:clamp(34px,4vw,52px);line-height:1.6;font-variant-numeric:tabular-nums}
.zm-owner-research-number span{font-size:clamp(16px,1.7vw,22px);color:#f5edd9;font-weight:600}
.zm-owner-research-summary p{line-height:2;max-width:95ch}
</style>"""

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def rewrite(data: bytes) -> bytes:
    source = data.decode("utf-8")
    assert REGISTRY_MARKER in source and "zm-registry-count" in source, "missing published registry"
    assert source.count(ANCHOR) == 1, "missing/duplicate historical-count anchor"
    assert MARKER not in source, "historical count already applied"
    assert source.count("</head>") == 1
    changed = source.replace(ANCHOR, CARD + "\n" + ANCHOR, 1)
    changed = changed.replace("</head>", STYLE + "\n</head>", 1)
    assert changed.count(MARKER) == 1
    assert "۱٬۴۵۷" in changed and "۱۳۴۵" not in CARD
    assert changed.count('id="zm-registry-count"') == source.count('id="zm-registry-count"')
    return changed.encode("utf-8")

def target_path() -> Path:
    root = Path.home() / "public_html"
    target = root / "research" / "projects" / "index.html"
    assert root.is_dir() and not root.is_symlink()
    assert target.is_file() and not target.is_symlink()
    return target

def backup_dir(raw: str) -> Path:
    home = Path.home().resolve()
    root = home / "public_html"
    location = Path(raw)
    assert location.is_absolute() and not location.is_symlink()
    resolved = location.resolve()
    assert resolved.is_relative_to(home) and not resolved.is_relative_to(root)
    return location

def atomic_replace(path: Path, content: bytes):
    temp = path.with_name(".index.research-count-next-20261023")
    assert not temp.exists() and not temp.is_symlink()
    try:
        with temp.open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, 0o644)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()

def publish(raw: str):
    target = target_path()
    backup = backup_dir(raw)
    assert not backup.exists(), "backup already exists"
    before = target.read_bytes()
    after = rewrite(before)
    backup.mkdir(parents=True, mode=0o700)
    (backup / "before.html").write_bytes(before)
    manifest = {"before": digest(before), "after": digest(after), "path": "research/projects/index.html"}
    (backup / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    try:
        assert digest(target.read_bytes()) == manifest["before"], "concurrent page edit"
        atomic_replace(target, after)
        verify(raw)
    except BaseException:
        if digest(target.read_bytes()) == manifest["after"]:
            atomic_replace(target, before)
        raise
    print("OWNER_RESEARCH_COUNT_PUBLISHED=1457")

def verify(raw: str):
    target = target_path()
    backup = backup_dir(raw)
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    content = target.read_bytes()
    assert digest(content) == manifest["after"], "unexpected public edit"
    assert content.count(MARKER.encode("utf-8")) == 1
    assert "۱٬۴۵۷".encode("utf-8") in content
    assert "آمار تاریخی اعلام‌شده".encode("utf-8") in content
    assert "پرونده عمومی دارای مجوز انتشار".encode("utf-8") in content
    print("OWNER_RESEARCH_COUNT_VERIFY=success")

def rollback(raw: str):
    target = target_path()
    backup = backup_dir(raw)
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    before = (backup / "before.html").read_bytes()
    assert digest(before) == manifest["before"]
    assert digest(target.read_bytes()) == manifest["after"], "concurrent page edit: cannot overwrite"
    atomic_replace(target, before)
    assert digest(target.read_bytes()) == manifest["before"]
    print("OWNER_RESEARCH_COUNT_ROLLBACK=success")

def selftest():
    fixture = ('<html><head></head><body><main id="zm-research-project-directory-20261023">'
               + ANCHOR + '<div><strong id="zm-registry-count">۰</strong>'
               '<span>پرونده عمومی دارای مجوز انتشار</span></div></div></main></body></html>').encode()
    revised = rewrite(fixture)
    assert revised.count(MARKER.encode()) == 1
    assert "۱٬۴۵۷".encode() in revised and b'zm-registry-count' in revised
    assert "آبان ۱۳۹۸".encode() in revised and "۲۳ اکتبر ۲۰۲۶".encode() in revised
    try:
        rewrite(revised)
        raise AssertionError("duplicate claim allowed")
    except AssertionError as error:
        assert "already applied" in str(error)
    print("OWNER_RESEARCH_COUNT_SELFTEST=passed")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["selftest", "publish", "verify", "rollback"])
    parser.add_argument("--backup", default="")
    args = parser.parse_args()
    if args.action == "selftest":
        selftest()
    else:
        assert args.backup
        {"publish": publish, "verify": verify, "rollback": rollback}[args.action](args.backup)
