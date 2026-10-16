#!/usr/bin/env python3
"""Append exactly ten evidence-qualified English AI-style FAQ answers to personal About.

No new page, views, database mutations, automated visitor answers, external bot
calls or other host domains. Strict byte preservation outside existing FAQ.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
from urllib.parse import urlparse

APP = Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
ABOUT = Path("templates/personal_site/core/about.html")
FAQ_ID = 'id="mpw-public-personal-faq-20261016"'
ENGLISH_ID = 'id="mpw-personal-english-questions-v2-20261016"'
FORM_ID = 'id="mpw-personal-ask-question-v2-20261016"'
NEW_ID = 'id="mpw-about-ai-questions-batch-01-20261016"'
SECTION = re.compile(r'<section\s+id="mpw-public-personal-faq-20261016"[^>]*>.*?</section>', re.S)
PERSIAN = re.compile(r"[\u0600-\u06FF]")
FORM_WRAPPER = '<div style="background:#24221e;border:1px solid #b98d54;border-radius:14px;'
SITE = "https://mojplaywin.com/mojtaba.roozegar/"
ALLOWED_PATHS = frozenset(("about/", "resume/", "projects/", "stories/", "contact/"))
VALID_TOPICS = frozenset(("Education", "Agricultural Economics", "Leadership",
    "Digital Enterprise", "Web Engineering", "Project Status", "Professional Experience",
    "Writing", "Verification", "Collaboration"))

def sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()

def dependencies():
    # Trusted, previously deployed safeguards are imported from staged copies.
    local = Path(__file__).with_name("mojtaba_about_english_questions_upgrade.py")
    if not local.is_file() or local.is_symlink():
        raise ValueError("Original English-only About guard missing")
    spec = importlib.util.spec_from_file_location("personal_faq_guard", local)
    if not spec or not spec.loader:
        raise ValueError("Cannot load personal-only guard")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.base_module()

def read_batch(path: Path) -> list[dict]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Staged public questions file required")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (data.get("version"), data.get("batch"), data.get("target")) != (
        1, 1, SITE + "about/"
    ):
        raise ValueError("Wrong About batch version, number or destination")
    rows = data.get("questions", [])
    if not isinstance(rows, list) or len(rows) != 10 or [r.get("id") for r in rows] != list(range(9, 19)):
        raise ValueError("Exactly ten sequential new questions required")
    q_seen = set()
    for row in rows:
        question = row["question"]
        answer = row["answer"]
        source_url = row["source_url"]
        if not isinstance(question, str) or not isinstance(answer, str) or not isinstance(source_url, str):
            raise ValueError("Missing text fields")
        if (len(question) < 25 or len(answer) < 120 or len(answer) > 1600
                or PERSIAN.search(question+answer)):
            raise ValueError("Questions must be substantial, verified English-only prose")
        if re.search(r"<|>|javascript:|password|secret.?key", question+answer, re.I):
            raise ValueError("Unexpected markup or private data in public text")
        norm = re.sub(r"[^a-z0-9]+", "", question.lower())
        if norm in q_seen:
            raise ValueError("Duplicate question in batch")
        q_seen.add(norm)
        if row.get("topic") not in VALID_TOPICS:
            raise ValueError("Topic not validated")
        if not source_url.startswith(SITE) or source_url[len(SITE):] not in ALLOWED_PATHS:
            raise ValueError("Only verified existing personal site sources allowed")
    return rows

def render_batch(rows: list[dict]) -> str:
    out = [
        '<div ' + NEW_ID + ' lang="en" dir="ltr" aria-labelledby="mpw-faq-batch-01-heading" '
        'style="margin-top:30px;padding-top:26px;border-top:1px solid #765e3d">',
        '<h3 id="mpw-faq-batch-01-heading" style="font:700 24px/1.35 Georgia,serif;'
        'color:#efcd95;margin:0 0 12px">More Questions People May Ask AI Assistants</h3>',
        '<p style="font:15px/1.75 system-ui,sans-serif;color:#e5d7c4;margin:0 0 18px">'
        'Ten additional public-interest questions with evidence-qualified answers. '
        'These are suggested questions, not private queries or verified search trends.</p>',
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:16px">',
    ]
    for row in rows:
        q = html.escape(row["question"], quote=True)
        a = html.escape(row["answer"], quote=True)
        link = html.escape(row["source_url"], quote=True)
        topic = html.escape(row["topic"], quote=True)
        out.append(
            '<article data-ai-faq-id="' + str(row["id"]) + '" '
            'style="background:#24221e;border:1px solid #765e3d;'
            'border-radius:12px;padding:20px">'
            '<p style="font:600 12px/1.5 system-ui,sans-serif;'
            'letter-spacing:.06em;text-transform:uppercase;color:#e2c187;margin:0 0 10px">'
            + topic + '</p>'
            '<h4 style="font:650 18px/1.55 system-ui,sans-serif;'
            'color:#f1cc92;margin:0 0 10px">' + q + '</h4>'
            '<p style="font:15px/1.85 system-ui,sans-serif;'
            'color:#f2e9dc;margin:0 0 10px">' + a + '</p>'
            '<a href="' + link + '" style="font:600 14px/1.5 system-ui,sans-serif;'
            'color:#f1d29a;text-decoration:underline">Read related source page</a>'
            '</article>'
        )
    out.append('</div></div>')
    html_out = "\n".join(out)
    if len(rows) != 10 or html_out.count("data-ai-faq-id") != 10 or PERSIAN.search(html_out):
        raise ValueError("English AI Q&A batch output invalid")
    return html_out

def patch(source: str, rows: list[dict]) -> str:
    if source.count(FAQ_ID) != 1 or source.count(ENGLISH_ID) != 1 or source.count(FORM_ID) != 1:
        raise ValueError("Unexpected personal English About FAQ markers")
    if NEW_ID in source:
        raise ValueError("Batch one already installed; do not duplicate")
    matches = list(SECTION.finditer(source))
    if len(matches) != 1:
        raise ValueError("Expected exactly one existing FAQ section")
    match = matches[0]
    original_section = match.group()
    if PERSIAN.search(original_section) or original_section.count("<article") != 8:
        raise ValueError("Existing eight English answers were modified")
    if original_section.count(FORM_WRAPPER) != 1:
        raise ValueError("Original inline question form container changed")
    if original_section.count("{% csrf_token %}") != 1:
        raise ValueError("Original Django CSRF form absent")
    change = render_batch(rows) + "\n"
    patched = original_section.replace(FORM_WRAPPER, change + FORM_WRAPPER, 1)
    if patched.count("<article") != 18 or patched.count(FORM_ID) != 1:
        raise ValueError("Could not preserve original questions and form")
    return source[:match.start()] + patched + source[match.end():]

def verify(app: Path, backup: Path):
    guard = dependencies()
    template = guard.safe_template(app)
    manifest = json.loads((backup/"manifest.json").read_text(encoding="utf-8"))
    saved = (backup/"about.html").read_bytes()
    actual = template.read_bytes()
    if sha(saved) != manifest["before"] or sha(actual) != manifest["after"]:
        raise ValueError("Protected About backup/current hashes do not match")
    guard.django_init(app)
    guard.check_template_compile(actual.decode("utf-8"))
    published, articles_digest = guard.data_fingerprint()
    images, images_digest = guard.image_fingerprint(app)
    if [published, articles_digest, images, images_digest] != manifest["protected"]:
        raise ValueError("Protected posts or media changed")
    section = SECTION.search(actual.decode("utf-8"))
    if not section or PERSIAN.search(section.group()) or section.group().count("<article") != 18:
        raise ValueError("English FAQ batch corrupt or missing")
    if section.group().count(NEW_ID) != 1 or section.group().count(FORM_ID) != 1:
        raise ValueError("Batch or form duplicated/removed")
    for seq in range(9, 19):
        if section.group().count('data-ai-faq-id="' + str(seq) + '"') != 1:
            raise ValueError("Batch answer missing: " + str(seq))
    print("PERSONAL_AI_FAQ_BATCH_01_VERIFIED=yes", flush=True)
    print("PERSONAL_AI_FAQ_PUBLISHED_ARTICLES_PRESERVED="+str(published),flush=True)
    print("PERSONAL_AI_FAQ_IMAGES_PRESERVED="+str(images),flush=True)

def install(app: Path, source: Path, backup: Path):
    guard = dependencies()
    template = guard.safe_template(app)
    original = template.read_bytes()
    proposed = patch(original.decode("utf-8"), read_batch(source)).encode("utf-8")
    guard.django_init(app)
    guard.check_template_compile(proposed.decode("utf-8"))
    article_count, article_sha = guard.data_fingerprint()
    images_count, images_sha = guard.image_fingerprint(app)
    if backup.exists() or backup.is_symlink():
        raise ValueError("Refuse existing backup directory")
    backup.mkdir(parents=True,mode=0o700)
    saved = backup/"about.html"
    saved.write_bytes(original)
    saved.chmod(0o600)
    if saved.read_bytes() != original:
        raise ValueError("Backup verification failed")
    manifest = {"before":sha(original), "after":sha(proposed),
                "protected":[article_count,article_sha,images_count,images_sha],
                "added_questions":10, "previous_questions":8}
    (backup/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    if sha(template.read_bytes()) != manifest["before"]:
        raise ValueError("Concurrent template modification; refuse")
    staging = template.with_name("about.html.ai-faq-batch-01.stage")
    if staging.exists() or staging.is_symlink():
        raise ValueError("Staging collision")
    installed = False
    try:
        staging.write_bytes(proposed)
        staging.chmod(template.stat().st_mode & 0o777)
        if sha(staging.read_bytes()) != manifest["after"]:
            raise ValueError("Staging hash failed")
        os.replace(staging,template)
        installed = True
        verify(app,backup)
    except BaseException:
        if installed and sha(template.read_bytes()) == manifest["after"]:
            shutil.copy2(saved,template)
            print("PERSONAL_AI_FAQ_BATCH_01_AUTO_ROLLBACK=yes",flush=True)
        if staging.exists() and not staging.is_symlink():
            staging.unlink()
        raise
    if (app/"tmp").is_dir():
        (app/"tmp"/"restart.txt").touch()
    print("PERSONAL_AI_FAQ_BATCH_01_INSTALLED=yes",flush=True)
    print("PERSONAL_AI_FAQ_BATCH_01_BACKUP="+str(backup),flush=True)

def rollback(app: Path, backup: Path):
    guard = dependencies()
    template = guard.safe_template(app)
    manifest = json.loads((backup/"manifest.json").read_text())
    saved = backup/"about.html"
    if sha(saved.read_bytes()) != manifest["before"]:
        raise ValueError("Backup hash invalid")
    if sha(template.read_bytes()) != manifest["after"]:
        raise ValueError("Other template changes detected; refuse overwriting them")
    temp = template.with_name("about.html.ai-faq-batch-01.restore")
    if temp.exists() or temp.is_symlink():
        raise ValueError("Rollback staging collision")
    shutil.copy2(saved,temp)
    os.replace(temp,template)
    if (app/"tmp").is_dir():
        (app/"tmp"/"restart.txt").touch()
    print("PERSONAL_AI_FAQ_BATCH_01_ROLLBACK=success",flush=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action",choices=("check","install","verify","rollback"))
    parser.add_argument("--app",type=Path,default=APP)
    parser.add_argument("--source",type=Path)
    parser.add_argument("--backup",type=Path)
    args = parser.parse_args()
    if args.action=="check":
        if not args.source:parser.error("--source is required")
        render_batch(read_batch(args.source))
        print("PERSONAL_AI_FAQ_BATCH_01_SOURCE=valid")
    elif args.action=="install":
        if not args.source or not args.backup:parser.error("--source and --backup required")
        install(args.app,args.source,args.backup)
    else:
        if not args.backup:parser.error("--backup required")
        if args.action=="verify":
            verify(args.app,args.backup)
        else:
            rollback(args.app,args.backup)

if __name__=="__main__":
    main()
