#!/usr/bin/env python3
"""Backed-up, one-template bilingual public FAQ release for independent personal V17.

Only adds English/Persian public professional questions to the existing About page.
No Post edits, media changes, schema rewrites, new routes, other apps or domains.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import sys
from pathlib import Path

APP = Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
REL = Path("templates/personal_site/core/about.html")
MARK = 'id="mpw-public-personal-faq-20261016"'
BLOCK_RE = re.compile(r"{%\s*(block(?:\s+\w+)?|endblock(?:\s+\w+)?)\s*%}")

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def load_faq(path: Path) -> list[dict]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Safe, staged public FAQ file required")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("version") != 1 or obj.get("target") != "https://mojplaywin.com/mojtaba.roozegar/":
        raise ValueError("Wrong personal FAQ scope")
    rows = obj.get("questions", [])
    if len(rows) != 8 or [r.get("id") for r in rows] != list(range(1, 9)):
        raise ValueError("Eight ordered questions required")
    for row in rows:
        for lang in ("en", "fa"):
            qa = row[lang]
            if not isinstance(qa["question"], str) or not isinstance(qa["answer"], str):
                raise ValueError("Non-text FAQ content")
            if len(qa["question"]) < 10 or len(qa["answer"]) < 35:
                raise ValueError("Incomplete FAQ answer")
            if any(token in (qa["question"] + qa["answer"]).lower()
                   for token in ("<script", "javascript:", "http://", "password", "private key")):
                raise ValueError("Unsafe public answer")
    return rows

def block_markup(rows: list[dict]) -> str:
    out = [
        '<section ' + MARK + ' aria-labelledby="mpw-personal-faq-title" '
        'style="max-width:1160px;margin:48px auto;padding:clamp(18px,3vw,36px);'
        'border:2px solid #c5a270;border-radius:18px;background:#171615;color:#f4e8d6">',
        '<h2 id="mpw-personal-faq-title" style="color:#efcd95;font:700 clamp(25px,3vw,36px)/1.35 Georgia,serif">'
        'About Mojtaba Roozegar · پرسش‌های متداول درباره مجتبی روزگار</h2>',
        '<p style="line-height:1.8">Professional background, research, websites, '
        'public writing and collaboration · معرفی حرفه‌ای، پژوهش‌ها، آثار و راه‌های همکاری</p>',
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:22px">',
    ]
    for language, label in (("en", "English"), ("fa", "فارسی")):
        direction = "rtl" if language == "fa" else "ltr"
        out.append(f'<div lang="{language}" dir="{direction}" aria-label="{label}" '
                   'style="display:flex;flex-direction:column;gap:14px">')
        for row in rows:
            question = html.escape(row[language]["question"], quote=True)
            answer = html.escape(row[language]["answer"], quote=True)
            out.append('<article style="background:#24221e;padding:18px;border-radius:11px;'
                       'border:1px solid #765e3d">'
                       f'<h3 style="font:650 17px/1.6 system-ui,sans-serif;color:#f1cc92">{question}</h3>'
                       f'<p style="font:15px/1.9 system-ui,sans-serif">{answer}</p></article>')
        out.append('</div>')
    out.extend([
        '</div>',
        '<p style="margin-top:22px;font:15px/1.85 system-ui,sans-serif">'
        '<a style="color:#f1cf96;text-decoration:underline" href="/mojtaba.roozegar/blog/">'
        'Read the research journal</a> · '
        '<a style="color:#f1cf96;text-decoration:underline" href="/mojtaba.roozegar/contact/">'
        'Professional enquiries / درخواست همکاری</a></p>',
        '</section>',
    ])
    return "\n".join(out)

def patch(source: str, rows: list[dict]) -> str:
    if MARK in source:
        raise ValueError("Public FAQ already installed; refuse duplicate")
    start_token = "{% block content %}"
    if source.count(start_token) != 1:
        raise ValueError("Unrecognized independent personal About template")
    start = source.index(start_token) + len(start_token)
    depth = 0
    end = None
    for match in BLOCK_RE.finditer(source, start):
        keyword = match.group(1).split()[0]
        if keyword == "block":
            depth += 1
        elif depth:
            depth -= 1
        else:
            end = match.start()
            break
    if end is None:
        raise ValueError("Could not match personal About content block")
    return source[:end] + "\n" + block_markup(rows) + "\n" + source[end:]

def safe_template(app: Path) -> Path:
    if app != APP or app.is_symlink() or not (app / "manage.py").is_file():
        raise ValueError("Only original independent personal V17 is permitted")
    path = app / REL
    if path.is_symlink() or not path.is_file() or path.resolve() != path:
        raise ValueError("Personal About template unavailable or unsafe")
    return path

def django_init(app: Path):
    sys.path.insert(0, str(app))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()

def data_fingerprint():
    from core.models import Post
    posts = list(Post.objects.order_by("pk").values())
    count = sum(bool(p.get("published")) for p in posts)
    if count < 93:
        raise ValueError("At least 93 published personal articles required")
    return count, sha(json.dumps(posts, default=str, sort_keys=True,
                                 ensure_ascii=False).encode("utf-8"))

def image_fingerprint(app: Path):
    roots = (app / "static" / "personal_site", app / "media",
             app / "staticfiles" / "personal_site")
    images = []
    for root in roots:
        if not root.exists():
            continue
        if root.is_symlink() or not root.is_dir():
            raise ValueError("Unsafe media root")
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise ValueError("Protected media symlink present")
            if path.is_file() and path.suffix.lower() in {
                ".jpg", ".jpeg", ".png", ".webp", ".svg", ".avif"
            }:
                images.append((str(path.relative_to(app)), sha(path.read_bytes())))
    if len(images) < 300:
        raise ValueError("Protected original photo inventory unexpectedly small")
    return len(images), sha(json.dumps(images, sort_keys=True).encode())

def check_template_compile(template):
    from django.template import engines
    engines["django"].engine.from_string(template)

def install(app: Path, content: Path, backup: Path):
    template = safe_template(app)
    rows = load_faq(content)
    original = template.read_bytes()
    proposed = patch(original.decode("utf-8"), rows).encode("utf-8")
    if not proposed.startswith(original[:20]) or proposed.count(MARK.encode()) != 1:
        raise ValueError("Unsafe About template modification")
    django_init(app)
    check_template_compile(proposed.decode("utf-8"))
    posts_count, posts_sha = data_fingerprint()
    images_count, images_sha = image_fingerprint(app)
    if backup.is_symlink() or backup.exists():
        raise ValueError("Protected backup must be new")
    backup.mkdir(parents=True, mode=0o700)
    saved = backup / "about.html"
    saved.write_bytes(original)
    saved.chmod(0o600)
    if saved.read_bytes() != original:
        raise ValueError("Backup verification failed")
    manifest = {"original": sha(original), "installed": sha(proposed),
                "posts_count": posts_count, "posts_sha": posts_sha,
                "images_count": images_count, "images_sha": images_sha,
                "question_count": len(rows)}
    mpath = backup / "manifest.json"
    mpath.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    mpath.chmod(0o600)
    if sha(template.read_bytes()) != manifest["original"]:
        raise ValueError("Concurrent edit before installation")
    staged = template.with_name("about.html.personal-faq-temp")
    if staged.exists() or staged.is_symlink():
        raise ValueError("Temporary template collision")
    try:
        staged.write_bytes(proposed)
        staged.chmod(template.stat().st_mode & 0o777)
        if sha(staged.read_bytes()) != manifest["installed"]:
            raise ValueError("Staging hash mismatch")
        os.replace(staged, template)
        verify(app, backup)
    except BaseException:
        if sha(template.read_bytes()) == manifest["installed"]:
            shutil.copy2(saved, template)
        if staged.exists() and staged.is_file() and not staged.is_symlink():
            staged.unlink()
        raise
    if (app / "tmp").is_dir():
        (app / "tmp" / "restart.txt").touch()
    print("PERSONAL_PUBLIC_FAQ_INSTALLED=yes", flush=True)
    print("PERSONAL_PUBLIC_FAQ_BACKUP=" + str(backup), flush=True)

def verify(app: Path, backup: Path):
    template = safe_template(app)
    if backup.is_symlink() or not (backup / "manifest.json").is_file():
        raise ValueError("Backup missing")
    m = json.loads((backup / "manifest.json").read_text())
    if sha((backup / "about.html").read_bytes()) != m["original"]:
        raise ValueError("Original backup changed")
    if sha(template.read_bytes()) != m["installed"] or template.read_bytes().count(MARK.encode()) != 1:
        raise ValueError("Expected public FAQ not installed")
    django_init(app)
    check_template_compile(template.read_text(encoding="utf-8"))
    published, post_sha = data_fingerprint()
    image_count, image_sha = image_fingerprint(app)
    if (published, post_sha, image_count, image_sha) != (
        m["posts_count"], m["posts_sha"], m["images_count"], m["images_sha"]
    ):
        raise ValueError("Protected Post or image inventory changed")
    print("PERSONAL_PUBLIC_FAQ_93_POSTS_300_IMAGES_PRESERVED=yes", flush=True)

def rollback(app: Path, backup: Path):
    template = safe_template(app)
    m = json.loads((backup / "manifest.json").read_text())
    saved = backup / "about.html"
    if sha(saved.read_bytes()) != m["original"]:
        raise ValueError("Backup content changed; refuse rollback")
    if sha(template.read_bytes()) != m["installed"]:
        raise ValueError("Live About template modified by another release; refuse overwrite")
    staged = template.with_name("about.html.personal-faq-restore")
    if staged.exists() or staged.is_symlink():
        raise ValueError("Rollback temporary path collision")
    shutil.copy2(saved, staged)
    os.replace(staged, template)
    if (app / "tmp").is_dir():
        (app / "tmp" / "restart.txt").touch()
    print("PERSONAL_PUBLIC_FAQ_ROLLBACK_SUCCESS=yes", flush=True)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=("check", "install", "verify", "rollback"))
    p.add_argument("--app", type=Path, default=APP)
    p.add_argument("--content", type=Path)
    p.add_argument("--backup", type=Path)
    a = p.parse_args()
    if a.action == "check":
        if not a.content:
            p.error("--content required")
        rows = load_faq(a.content)
        if block_markup(rows).count("<article ") != 16:
            raise ValueError("Expected eight original Q&A pairs in each language")
        print("PERSONAL_PUBLIC_FAQ_CONTENT_VALID=yes", flush=True)
    elif a.action == "install":
        if not a.content or not a.backup:
            p.error("--content and --backup required")
        install(a.app, a.content, a.backup)
    elif a.action == "verify":
        if not a.backup:
            p.error("--backup required")
        verify(a.app, a.backup)
    elif a.action == "rollback":
        if not a.backup:
            p.error("--backup required")
        rollback(a.app, a.backup)

if __name__ == "__main__":
    main()
