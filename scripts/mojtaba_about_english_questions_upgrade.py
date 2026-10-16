#!/usr/bin/env python3
"""Replace only the published bilingual FAQ inside personal V17 About with English Q&A.

The inline "Ask a Question" form POSTs to the site's EXISTING protected contact
handler; questions are reviewed, not answered automatically by a fabricated AI.
No DB/model/view/URL changes; 93+ articles and all images are hash-protected.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import json
import os
import re
import shutil
from pathlib import Path

APP = Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
FAQ_ID = 'id="mpw-public-personal-faq-20261016"'
UPGRADE_ID = 'id="mpw-personal-english-questions-v2-20261016"'
FORM_ID = 'id="mpw-personal-ask-question-v2-20261016"'
FAQ_SECTION = re.compile(
    r'<section\s+id="mpw-public-personal-faq-20261016"(?=[\s>])[^>]*>.*?</section>',
    re.S
)
PERSIAN_CHARS = re.compile(r"[\u0600-\u06FF]")
CONTACT = "/mojtaba.roozegar/contact/"
BLOG = "/mojtaba.roozegar/blog/"

def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def base_module():
    path = Path(__file__).with_name("mojtaba_personal_public_faq_safe_publish.py")
    if path.is_symlink() or not path.is_file():
        raise ValueError("Original protected personal FAQ publisher missing")
    spec = importlib.util.spec_from_file_location("personal_faq_original", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod

def english_rows(content: Path) -> list[tuple[str, str]]:
    if content.is_symlink() or not content.is_file():
        raise ValueError("Public FAQ source missing")
    payload = json.loads(content.read_text(encoding="utf-8"))
    if payload.get("version") != 1 or payload.get("target") != (
        "https://mojplaywin.com/mojtaba.roozegar/"
    ):
        raise ValueError("Unexpected public FAQ source")
    entries = payload.get("questions", [])
    if [entry.get("id") for entry in entries] != list(range(1, 9)):
        raise ValueError("All eight existing questions are required")
    result = []
    for entry in entries:
        q = entry["en"]["question"].strip()
        a = entry["en"]["answer"].replace(" (مجتبی روزگار)", "").strip()
        if len(q) < 12 or len(a) < 40 or PERSIAN_CHARS.search(q + a):
            raise ValueError("Only substantive English questions and answers allowed")
        result.append((q, a))
    return result

def markup(rows: list[tuple[str, str]]) -> str:
    out = [
        '<section ' + FAQ_ID + ' lang="en" dir="ltr" aria-labelledby="mpw-personal-faq-title" '
        'style="max-width:1160px;margin:48px auto;padding:clamp(20px,3vw,38px);'
        'background:#171615;color:#f4e8d6;border:2px solid #c5a270;border-radius:18px">',
        '<div ' + UPGRADE_ID + '>',
        '<h2 id="mpw-personal-faq-title" style="font:700 clamp(26px,3vw,36px)/1.35 Georgia,serif;'
        'color:#efcd95;margin:0 0 12px">Frequently Asked Questions</h2>',
        '<p style="font:16px/1.8 system-ui,sans-serif;margin:0 0 28px">'
        'Explore Mojtaba Roozegar’s professional background, research, projects,'
        ' writing and opportunities for collaboration.</p>',
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));'
        'gap:16px">',
    ]
    for q, a in rows:
        out.append(
            '<article style="background:#24221e;border:1px solid #765e3d;border-radius:12px;'
            'padding:20px">'
            '<h3 style="font:650 18px/1.5 system-ui,sans-serif;color:#f1cc92;margin:0 0 10px">'
            + html.escape(q, quote=True) + '</h3>'
            '<p style="font:15px/1.85 system-ui,sans-serif;margin:0;color:#f2e9dc">'
            + html.escape(a, quote=True) + '</p></article>'
        )
    out.extend([
        '</div>',
        '<div style="background:#24221e;border:1px solid #b98d54;border-radius:14px;'
        'padding:clamp(16px,3vw,28px);margin-top:28px">',
        '<h3 style="font:700 23px/1.4 Georgia,serif;color:#f1cc92;margin:0 0 8px">'
        'Ask a Question</h3>',
        '<p style="font:15px/1.7 system-ui,sans-serif;margin:0 0 20px">'
        'Have a question about Mojtaba Roozegar’s professional work? '
        'Send it for review. Approved factual answers may be added to this page.'
        '</p>',
        '<form ' + FORM_ID + ' method="post" action="' + CONTACT + '" '
        'style="display:grid;gap:16px;max-width:760px">',
        '{% csrf_token %}',
        '<input name="website" type="hidden" value="">',
        '<input name="subject" type="hidden" value="Question from personal About page">',
        '<label for="mpw-faq-name" style="display:grid;gap:7px;font:600 15px/1.6 system-ui,sans-serif">'
        'Your name'
        '<input id="mpw-faq-name" type="text" name="name" maxlength="120" required '
        'autocomplete="name" placeholder="Your name" '
        'style="width:100%;box-sizing:border-box;border:1px solid #b99a68;border-radius:9px;'
        'padding:12px 14px;background:#f8f2e7;color:#161616;font:16px system-ui,sans-serif">'
        '</label>',
        '<label for="mpw-faq-email" style="display:grid;gap:7px;font:600 15px/1.6 system-ui,sans-serif">'
        'Email address'
        '<input id="mpw-faq-email" type="email" name="email" maxlength="254" required '
        'autocomplete="email" placeholder="you@example.com" '
        'style="width:100%;box-sizing:border-box;border:1px solid #b99a68;border-radius:9px;'
        'padding:12px 14px;background:#f8f2e7;color:#161616;font:16px system-ui,sans-serif">'
        '</label>',
        '<label for="mpw-faq-message" style="display:grid;gap:7px;font:600 15px/1.6 system-ui,sans-serif">'
        'Your question'
        '<textarea id="mpw-faq-message" name="message" rows="4" minlength="10" maxlength="5000" '
        'required placeholder="What would you like to know?" '
        'style="width:100%;box-sizing:border-box;border:1px solid #b99a68;border-radius:9px;'
        'padding:12px 14px;background:#f8f2e7;color:#161616;font:16px/1.6 system-ui,sans-serif;'
        'resize:vertical"></textarea></label>',
        '<button type="submit" style="justify-self:start;background:#d6b377;color:#191612;'
        'border:1px solid #f2d6a5;border-radius:9px;padding:12px 22px;'
        'font:700 15px/1.4 system-ui,sans-serif;cursor:pointer">'
        'Submit question</button>',
        '</form>',
        '<p style="font:13px/1.6 system-ui,sans-serif;margin:14px 0 0;color:#e4d3bb">'
        'Questions are sent through the existing secure contact form; '
        'there is no automatic AI reply or public posting of submitted details.</p>',
        '</div>',
        '<p style="margin:26px 0 0;font:15px/1.8 system-ui,sans-serif">'
        '<a href="' + BLOG + '" style="color:#f1cf96;text-decoration:underline">'
        'Browse research and articles</a> · '
        '<a href="' + CONTACT + '" style="color:#f1cf96;text-decoration:underline">'
        'Contact Mojtaba Roozegar</a></p>',
        '</div></section>'
    ])
    rendered = "\n".join(out)
    if PERSIAN_CHARS.search(rendered):
        raise ValueError("Non-English visible text in FAQ markup")
    return rendered

def patch(original: str, rows: list[tuple[str, str]]) -> str:
    if original.count(FAQ_ID) != 1 or UPGRADE_ID in original or FORM_ID in original:
        raise ValueError("Expected one original bilingual FAQ and no prior upgrade")
    matches = list(FAQ_SECTION.finditer(original))
    if len(matches) != 1:
        raise ValueError("Original bilingual FAQ section layout changed")
    old = matches[0].group()
    if old.count("<section") != 1 or old.count("<article") != 16:
        raise ValueError("Original 16 bilingual FAQ items changed")
    if 'lang="fa"' not in old or 'lang="en"' not in old:
        raise ValueError("Expected original English and Persian groups")
    rendered = markup(rows)
    candidate = original[:matches[0].start()] + rendered + original[matches[0].end():]
    if len(candidate) <= 1000 or candidate.count(FAQ_ID) != 1:
        raise ValueError("Unsafe FAQ replacement")
    # Every byte outside the designated FAQ section must be retained.
    if not candidate.startswith(original[:matches[0].start()]) or (
        not candidate.endswith(original[matches[0].end():])
    ):
        raise ValueError("Unrelated original personal biography modified")
    return candidate

def verify(app: Path, backup: Path):
    old = base_module()
    path = old.safe_template(app)
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    if digest((backup / "about.html").read_bytes()) != manifest["before"]:
        raise ValueError("Backup hash mismatch")
    content = path.read_bytes()
    if digest(content) != manifest["after"]:
        raise ValueError("Published About differs from reviewed patch")
    old.django_init(app)
    old.check_template_compile(content.decode("utf-8"))
    count, post_sha = old.data_fingerprint()
    image_count, image_sha = old.image_fingerprint(app)
    if (count, post_sha, image_count, image_sha) != tuple(manifest["protected"]):
        raise ValueError("Article/database/image inventory changed")
    match = FAQ_SECTION.search(content.decode("utf-8"))
    if not match or PERSIAN_CHARS.search(match.group()):
        raise ValueError("Published English FAQ missing or contains Persian")
    if match.group().count("<article") != 8 or FORM_ID not in match.group():
        raise ValueError("Unexpected visible Q&A or form layout")
    print("PERSONAL_ABOUT_ENGLISH_VERIFY=passed", flush=True)
    print("PERSONAL_ARTICLES_PRESERVED=" + str(count), flush=True)
    print("PERSONAL_IMAGES_PRESERVED=" + str(image_count), flush=True)

def install(app: Path, source: Path, backup: Path):
    old = base_module()
    path = old.safe_template(app)
    original = path.read_bytes()
    candidate = patch(original.decode("utf-8"), english_rows(source)).encode("utf-8")
    old.django_init(app)
    old.check_template_compile(candidate.decode("utf-8"))
    count, posts = old.data_fingerprint()
    images, pics = old.image_fingerprint(app)
    if backup.exists() or backup.is_symlink():
        raise ValueError("Immutable backup destination already exists")
    backup.mkdir(parents=True, mode=0o700)
    saved = backup / "about.html"
    saved.write_bytes(original)
    saved.chmod(0o600)
    if saved.read_bytes() != original:
        raise ValueError("Backup not verified")
    metadata = {"before": digest(original), "after": digest(candidate),
                "protected": [count, posts, images, pics]}
    (backup / "manifest.json").write_text(json.dumps(metadata, indent=2))
    if digest(path.read_bytes()) != metadata["before"]:
        raise ValueError("Concurrent About edit; refusing update")
    staging = path.with_name("about.html.english-qa-stage")
    if staging.exists() or staging.is_symlink():
        raise ValueError("Unsafe staging path already occupied")
    installed = False
    try:
        staging.write_bytes(candidate)
        staging.chmod(path.stat().st_mode & 0o777)
        if digest(staging.read_bytes()) != metadata["after"]:
            raise ValueError("Staged content checksum mismatch")
        os.replace(staging, path)
        installed = True
        verify(app, backup)
    except BaseException:
        if installed and digest(path.read_bytes()) == metadata["after"]:
            shutil.copy2(saved, path)
            print("PERSONAL_ABOUT_ENGLISH_AUTO_ROLLBACK=done", flush=True)
        if staging.exists() and not staging.is_symlink():
            staging.unlink()
        raise
    if (app / "tmp").is_dir():
        (app / "tmp/restart.txt").touch()
    print("PERSONAL_ABOUT_ENGLISH_INSTALLED=yes", flush=True)
    print("PERSONAL_ABOUT_ENGLISH_BACKUP=" + str(backup), flush=True)

def rollback(app: Path, backup: Path):
    old = base_module()
    path = old.safe_template(app)
    manifest = json.loads((backup / "manifest.json").read_text())
    saved = backup / "about.html"
    if digest(saved.read_bytes()) != manifest["before"]:
        raise ValueError("Backup corrupted")
    if digest(path.read_bytes()) != manifest["after"]:
        raise ValueError("Another edit occurred, refuse destructive rollback")
    stage = path.with_name("about.html.english-qa-rollback")
    if stage.exists() or stage.is_symlink():
        raise ValueError("Rollback collision")
    shutil.copy2(saved, stage)
    os.replace(stage, path)
    if (app / "tmp").is_dir():
        (app / "tmp/restart.txt").touch()
    print("PERSONAL_ABOUT_ENGLISH_ROLLBACK=success", flush=True)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=("check", "install", "verify", "rollback"))
    p.add_argument("--app", type=Path, default=APP)
    p.add_argument("--source", type=Path)
    p.add_argument("--backup", type=Path)
    a = p.parse_args()
    if a.action == "check":
        if not a.source:
            p.error("check requires --source")
        faq = markup(english_rows(a.source))
        if faq.count("<article") != 8 or FORM_ID not in faq or "{% csrf_token %}" not in faq:
            raise ValueError("English Q&A or secure form incomplete")
        print("PERSONAL_ABOUT_ENGLISH_SOURCE_CHECK=passed")
        return
    if not a.backup:
        p.error("--backup required")
    if a.action == "install":
        if not a.source:
            p.error("install requires --source")
        install(a.app, a.source, a.backup)
    elif a.action == "verify":
        verify(a.app, a.backup)
    else:
        rollback(a.app, a.backup)

if __name__ == "__main__":
    main()
