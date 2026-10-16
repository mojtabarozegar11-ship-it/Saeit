#!/usr/bin/env python3
"""Publish the ten explicitly owner-approved, English-only FAQ 29–38 in About.

Only appends within the existing personal About FAQ; no other pages, Post rows,
views, routers, images, domains, or automated AI responders. Backup-first,
SHA-checked deployment and strict rollback on failure.
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

APP = Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
ABOUT = Path("templates/personal_site/core/about.html")
SITE = "https://mojplaywin.com/mojtaba.roozegar/"
FAQ_ID = 'id="mpw-public-personal-faq-20261016"'
ENGLISH_ID = 'id="mpw-personal-english-questions-v2-20261016"'
FORM_ID = 'id="mpw-personal-ask-question-v2-20261016"'
FIRST_BATCH_ID = 'id="mpw-about-ai-questions-batch-01-20261016"'
SECOND_BATCH_ID = 'id="mpw-about-ai-questions-batch-02-20261016"'
THIRD_BATCH_ID = 'id="mpw-about-ai-questions-batch-03-20261016"'
FORM_WRAPPER = '<div style="background:#24221e;border:1px solid #b98d54;border-radius:14px;'
SECTION = re.compile(r'<section\s+id="mpw-public-personal-faq-20261016"[^>]*>.*?</section>', re.S)
PERSIAN = re.compile(r"[\u0600-\u06FF]")
TOPICS = frozenset({
    "Research Translation", "Agricultural Data", "AI Validation",
    "Data and Intellectual Property", "Specialist E-commerce",
    "Hospitality Technology", "Website Acceptance Criteria",
    "Enterprise Project Delivery", "Scientific Communication",
    "Due Diligence and Collaboration",
})
SOURCE_PAGES = frozenset({"about/", "resume/", "projects/", "contact/"})

def checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def guard_module():
    original = Path(__file__).with_name("mojtaba_personal_public_faq_safe_publish.py")
    if not original.is_file() or original.is_symlink():
        raise ValueError("Existing safety guard is missing")
    spec = importlib.util.spec_from_file_location("personal_safe_faq_guard_batch03", original)
    if not spec or not spec.loader:
        raise ValueError("Unable to load safety guard")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def read_batch(path: Path) -> list[dict]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Batch-three content must be a regular staged file")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (data.get("version"), data.get("batch"), data.get("target")) != (
            1, 3, SITE + "about/"):
        raise ValueError("Wrong batch or target; refusing to change other pages")
    if "approved" not in data.get("approval", "").lower():
        raise ValueError("Missing user's explicit approval for the Persian originals")
    questions = data.get("questions")
    if not isinstance(questions, list) or len(questions) != 10:
        raise ValueError("Exactly ten new questions required")
    if [q.get("id") for q in questions] != list(range(29, 39)):
        raise ValueError("Expected only question IDs 29 through 38")
    normalized = set()
    for entry in questions:
        q, a = entry.get("question"), entry.get("answer")
        topic, source = entry.get("topic"), entry.get("source_url")
        if not all(isinstance(x, str) for x in (q, a, topic, source)):
            raise ValueError("Incomplete new question")
        if len(q) < 25 or len(a) < 130 or len(a) > 1650:
            raise ValueError("Incomplete answer or headline")
        if PERSIAN.search(q+a) or re.search(r"[<>]|javascript:|password|private.?key", q+a, re.I):
            raise ValueError("English-only safe factual prose required")
        key = re.sub(r"[^a-z0-9]", "", q.lower())
        if key in normalized:
            raise ValueError("Duplicate question")
        normalized.add(key)
        if topic not in TOPICS or source not in {SITE+p for p in SOURCE_PAGES}:
            raise ValueError("Source must be an existing independent personal page")
    return questions

def render_batch(rows: list[dict]) -> str:
    output = [
        '<div ' + THIRD_BATCH_ID + ' lang="en" dir="ltr" '
        'aria-labelledby="mpw-faq-batch03-heading" style="margin-top:30px;'
        'padding-top:26px;border-top:1px solid #765e3d">',
        '<h3 id="mpw-faq-batch03-heading" style="font:700 24px/1.4 Georgia,serif;'
        'color:#efcd95;margin:0 0 12px">Evidence, Digital Business &amp; Professional Practice — More Questions</h3>',
        '<p style="font:15px/1.75 system-ui,sans-serif;color:#e5d7c4;margin:0 0 18px">'
        'Ten further evidence-qualified questions and answers, translated from '
        'the owner-approved Persian originals. These are suggested questions, not '
        'records of private AI conversations.</p>',
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,'
        'minmax(min(100%,320px),1fr));gap:16px">',
    ]
    for entry in rows:
        q = html.escape(entry["question"], quote=True)
        a = html.escape(entry["answer"], quote=True)
        topic = html.escape(entry["topic"], quote=True)
        link = html.escape(entry["source_url"], quote=True)
        output.append(
            '<article data-ai-faq-id="' + str(entry["id"]) + '" '
            'style="background:#24221e;border:1px solid #765e3d;'
            'border-radius:12px;padding:20px">'
            '<p style="font:600 12px/1.5 system-ui,sans-serif;letter-spacing:.06em;'
            'text-transform:uppercase;color:#e2c187;margin:0 0 10px">'
            + topic + '</p>'
            '<h4 style="font:650 18px/1.55 system-ui,sans-serif;'
            'color:#f1cc92;margin:0 0 10px">' + q + '</h4>'
            '<p style="font:15px/1.85 system-ui,sans-serif;color:#f2e9dc;'
            'margin:0 0 10px">' + a + '</p>'
            '<a href="' + link + '" style="font:600 14px/1.5 '
            'system-ui,sans-serif;color:#f1d29a;text-decoration:underline">'
            'Read related source page</a></article>'
        )
    output.append("</div></div>")
    result = "\n".join(output)
    if PERSIAN.search(result) or result.count('data-ai-faq-id="') != 10:
        raise ValueError("Invalid English batch-three output")
    return result

def patch(original: str, questions: list[dict]) -> str:
    required = (FAQ_ID, ENGLISH_ID, FIRST_BATCH_ID, SECOND_BATCH_ID, FORM_ID)
    if any(original.count(marker) != 1 for marker in required):
        raise ValueError("Previous twenty-eight FAQ entries or form not in expected layout")
    if THIRD_BATCH_ID in original:
        raise ValueError("Batch three already present; refusing duplicate publication")
    matches = list(SECTION.finditer(original))
    if len(matches) != 1:
        raise ValueError("Expected exactly one existing personal About FAQ")
    old = matches[0].group()
    if PERSIAN.search(old) or old.count("<article") != 28:
        raise ValueError("The 28 English FAQ answers must remain intact")
    if old.count('data-ai-faq-id="') != 20 or old.count(FORM_WRAPPER) != 1:
        raise ValueError("Earlier batches or existing form structure changed")
    if old.count("{% csrf_token %}") != 1:
        raise ValueError("Existing question form CSRF protection missing")
    for i in range(9, 29):
        if old.count('data-ai-faq-id="' + str(i) + '"') != 1:
            raise ValueError("Prior question missing: " + str(i))
    modified = old.replace(FORM_WRAPPER, render_batch(questions) + "\n" + FORM_WRAPPER, 1)
    if (modified.count("<article") != 38 or modified.count(FORM_ID) != 1 or
            modified.count(FIRST_BATCH_ID) != 1 or
            modified.count(SECOND_BATCH_ID) != 1 or
            modified.count(THIRD_BATCH_ID) != 1):
        raise ValueError("Result failed FAQ preservation invariants")
    updated = original[:matches[0].start()] + modified + original[matches[0].end():]
    if updated.count(FAQ_ID) != 1 or PERSIAN.search(modified):
        raise ValueError("Invalid personal About update")
    return updated

def validate_live(app: Path, backup: Path):
    guard = guard_module()
    template = guard.safe_template(app)
    manifest = json.loads((backup/"manifest.json").read_text(encoding="utf-8"))
    if checksum((backup/"about.html").read_bytes()) != manifest["before"]:
        raise ValueError("Original About backup checksum changed")
    raw = template.read_bytes()
    if checksum(raw) != manifest["after"]:
        raise ValueError("Live About template does not match approved update")
    guard.django_init(app)
    guard.check_template_compile(raw.decode("utf-8"))
    published, article_sha = guard.data_fingerprint()
    images, image_sha = guard.image_fingerprint(app)
    if [published, article_sha, images, image_sha] != manifest["protected"]:
        raise ValueError("Published articles or original images changed")
    section = SECTION.search(raw.decode("utf-8"))
    if not section:
        raise ValueError("FAQ section lost")
    area = section.group()
    if (PERSIAN.search(area) or area.count("<article") != 38 or
            area.count(FORM_ID) != 1 or area.count(FIRST_BATCH_ID) != 1 or
            area.count(SECOND_BATCH_ID) != 1 or
            area.count(THIRD_BATCH_ID) != 1):
        raise ValueError("Prior FAQ or English form altered")
    for i in range(9, 39):
        if area.count('data-ai-faq-id="' + str(i) + '"') != 1:
            raise ValueError("A previous or new question is missing: " + str(i))
    print("PERSONAL_AI_FAQ_BATCH_03_VERIFIED=yes", flush=True)
    print("PERSONAL_AI_FAQ_PUBLISHED_ARTICLES_PRESERVED="+str(published), flush=True)
    print("PERSONAL_AI_FAQ_IMAGES_PRESERVED="+str(images), flush=True)

def install(app: Path, source: Path, backup: Path):
    guard = guard_module()
    template = guard.safe_template(app)
    original = template.read_bytes()
    updated = patch(original.decode("utf-8"), read_batch(source)).encode("utf-8")
    guard.django_init(app)
    guard.check_template_compile(updated.decode("utf-8"))
    posts, post_sha = guard.data_fingerprint()
    images, images_sha = guard.image_fingerprint(app)
    if backup.is_symlink() or backup.exists():
        raise ValueError("Protected backup destination already exists")
    backup.mkdir(mode=0o700,parents=True)
    saved = backup/"about.html"
    saved.write_bytes(original)
    saved.chmod(0o600)
    if saved.read_bytes() != original:
        raise ValueError("Backup verification failed")
    meta = {"before":checksum(original), "after":checksum(updated),
            "protected":[posts,post_sha,images,images_sha],
            "prior_questions":28, "new_questions":10}
    mpath = backup/"manifest.json"
    mpath.write_text(json.dumps(meta,indent=2),encoding="utf-8")
    mpath.chmod(0o600)
    if checksum(template.read_bytes()) != meta["before"]:
        raise ValueError("Concurrent template change; refusing update")
    stage = template.with_name("about.html.ai-faq-batch-03.stage")
    if stage.exists() or stage.is_symlink():
        raise ValueError("Template staging collision")
    replaced = False
    try:
        stage.write_bytes(updated)
        stage.chmod(template.stat().st_mode & 0o777)
        if checksum(stage.read_bytes()) != meta["after"]:
            raise ValueError("Staging check failed")
        os.replace(stage,template)
        replaced = True
        validate_live(app, backup)
    except BaseException:
        if replaced and checksum(template.read_bytes()) == meta["after"]:
            shutil.copy2(saved,template)
            print("PERSONAL_AI_FAQ_BATCH_03_AUTO_ROLLBACK=yes",flush=True)
        if stage.exists() and not stage.is_symlink():
            stage.unlink()
        raise
    if (app/"tmp").is_dir():
        (app/"tmp"/"restart.txt").touch()
    print("PERSONAL_AI_FAQ_BATCH_03_INSTALLED=yes",flush=True)
    print("PERSONAL_AI_FAQ_BATCH_03_BACKUP="+str(backup),flush=True)

def rollback(app: Path, backup: Path):
    guard=guard_module()
    template=guard.safe_template(app)
    meta=json.loads((backup/"manifest.json").read_text())
    saved=backup/"about.html"
    if checksum(saved.read_bytes()) != meta["before"]:
        raise ValueError("Rollback backup invalid")
    if checksum(template.read_bytes()) != meta["after"]:
        raise ValueError("Refusing to overwrite more recent modifications")
    stage=template.with_name("about.html.ai-faq-batch-03.restore")
    if stage.exists() or stage.is_symlink():
        raise ValueError("Rollback staging collision")
    shutil.copy2(saved,stage)
    os.replace(stage,template)
    if (app/"tmp").is_dir():
        (app/"tmp"/"restart.txt").touch()
    print("PERSONAL_AI_FAQ_BATCH_03_ROLLBACK=success",flush=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=("check","install","verify","rollback"))
    parser.add_argument("--app",type=Path,default=APP)
    parser.add_argument("--source",type=Path)
    parser.add_argument("--backup",type=Path)
    args=parser.parse_args()
    if args.action=="check":
        if not args.source: parser.error("--source required")
        render_batch(read_batch(args.source))
        print("PERSONAL_AI_FAQ_BATCH_03_SOURCE=valid")
    elif args.action=="install":
        if not args.source or not args.backup: parser.error("--source and --backup required")
        install(args.app,args.source,args.backup)
    else:
        if not args.backup: parser.error("--backup required")
        if args.action=="verify":
            validate_live(args.app,args.backup)
        else:
            rollback(args.app,args.backup)

if __name__=="__main__":
    main()
