#!/usr/bin/env python3
"""Minimal, reversible update to Zomorod Melal live /about/ research percentages.

Only the owner-declared percentage is changed. No finance, legal permits,
home page, templates, or any other site paths are changed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path

OLD_PARAGRAPH = "نزدیک به ۹۰ درصد فعالیت‌های آن به تحقیقات علمی، پژوهش‌های ژنتیکی و اصلاح نژاد اختصاص یافته است. معرفی مستقل"
NEW_PARAGRAPH = "۹۰ درصد فعالیت‌های آن به تحقیقات علمی، پژوهش‌های ژنتیکی و اصلاح نژاد اختصاص یافته است؛ ۱۰ درصد باقی‌مانده به سایر حوزه‌های فعالیت شرکت مربوط است و تفکیک جزئی آن اعلام نشده است. معرفی مستقل"
OLD_METRIC = "<strong>نزدیک به ۹۰٪</strong>"
NEW_METRIC = "<strong>۹۰٪</strong>"
MARKER = 'id="zm-about-official-20261018"'
REPLACEMENTS = ((OLD_PARAGRAPH, NEW_PARAGRAPH), (OLD_METRIC, NEW_METRIC))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rewrite(original: bytes) -> bytes:
    src = original.decode("utf-8")
    assert MARKER in src
    assert 'id="zm-owner-real-photo-style-20261018"' in src
    assert 'id="zm-about-comprehensive"' in src
    assert 'id="restored-earlier-corporate-content"' in src
    for old, new in REPLACEMENTS:
        assert src.count(old) == 1, f"Missing/duplicate baseline marker: {old[:35]}"
        assert new not in src
        src = src.replace(old, new, 1)
    updated = src.encode("utf-8")
    assert updated != original
    for old, new in REPLACEMENTS:
        assert old.encode("utf-8") not in updated
        assert updated.count(new.encode("utf-8")) == 1
    return updated


def location():
    root = Path.home() / "public_html"
    target = root / "about" / "index.html"
    assert root.is_dir() and not root.is_symlink()
    assert target.is_file() and not target.is_symlink()
    return root, target


def safe_backup_path(raw: str, root: Path) -> Path:
    path = Path(raw)
    assert path.is_absolute() and not path.is_symlink()
    assert path.resolve().is_relative_to(Path.home().resolve())
    assert not path.resolve().is_relative_to(root.resolve())
    return path


def atomic(target: Path, data: bytes):
    temp = target.with_name("." + target.name + ".research90-next")
    assert not temp.exists() and not temp.is_symlink()
    with temp.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temp, 0o644)
    os.replace(temp, target)


def publish(backup_raw: str):
    root, target = location()
    backup = safe_backup_path(backup_raw, root)
    original = target.read_bytes()
    updated = rewrite(original)
    assert not backup.exists()
    backup.mkdir(mode=0o700, parents=True)
    (backup / "before.html").write_bytes(original)
    manifest = {"before": digest(original), "after": digest(updated), "path": "about/index.html"}
    (backup / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    try:
        atomic(target, updated)
        verify(backup_raw)
    except BaseException:
        if digest(target.read_bytes()) == manifest["after"]:
            atomic(target, original)
        raise
    print("ABOUT_90_RESEARCH_PUBLISHED=yes")
    print("TARGET_ONLY=about/index.html")


def verify(backup_raw: str):
    root, target = location()
    backup = safe_backup_path(backup_raw, root)
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    current = target.read_bytes()
    assert digest(current) == manifest["after"]
    decoded = current.decode("utf-8")
    for _, new in REPLACEMENTS:
        assert decoded.count(new) == 1
    assert MARKER in decoded
    print("ABOUT_90_RESEARCH_VERIFIED=yes")


def rollback(backup_raw: str):
    root, target = location()
    backup = safe_backup_path(backup_raw, root)
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    prior = (backup / "before.html").read_bytes()
    assert digest(prior) == manifest["before"]
    assert digest(target.read_bytes()) == manifest["after"], "Concurrent update; do not overwrite."
    atomic(target, prior)
    assert digest(target.read_bytes()) == manifest["before"]
    print("ABOUT_90_RESEARCH_ROLLBACK=verified")


def selftest():
    fixture = '<html><section ' + MARKER + '><style id="zm-owner-real-photo-style-20261018"></style><div id="zm-about-comprehensive"></div><div id="restored-earlier-corporate-content"></div>'
    fixture += ''.join(old for old, _ in REPLACEMENTS) + '</section></html>'
    after = rewrite(fixture.encode("utf-8"))
    for _, new in REPLACEMENTS:
        assert after.decode("utf-8").count(new) == 1
    print("ABOUT_90_RESEARCH_SELFTEST=passed")


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
