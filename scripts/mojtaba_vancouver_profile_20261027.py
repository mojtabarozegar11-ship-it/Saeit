#!/usr/bin/env python3
"""Owner-confirmed Vancouver residence and consolidated full professional profile.

User has explicitly confirmed Vancouver, British Columbia, Canada as residence.
Preserve academic detail, leadership and professional practice without asserting
unverified degrees, employment dates, publications or third-party affiliations.
Exact backup, hash checks, Django preflight and rollback are required.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

APP = Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
RELATIVES = (
    "templates/personal_site/core/about.html",
    "templates/personal_site/core/contact.html",
)
BACKUP_ROOT = Path("/home/zomorod2/.backups/mojtaba-residence-profession")
ABOUT_DESCRIPTION = (
    "Mojtaba Roozegar is an Iranian entrepreneur and researcher based in "
    "Vancouver, British Columbia, Canada. His reported academic background is "
    "a PhD in Agricultural Economics from Universiti Putra Malaysia (UPM), "
    "specializing in Production Economics and Farm Management. He is CEO "
    "of Zomorod Melal Agro-Industry Company and founder of MojPlayWin."
)
CONTACT_DESCRIPTION = (
    "Contact Mojtaba Roozegar in Vancouver, British Columbia, Canada "
    "for research, agribusiness, responsible technology and international "
    "professional collaboration."
)
SEO_OLD = "across international and remote teams"
SEO_NEW = "from Vancouver, British Columbia, Canada, and across international teams"
DESC_BLOCK = re.compile(r"{%\s*block\s+description\s*%}.*?{%\s*endblock\s*%}", re.S)
EXTENDS = re.compile(r"{%\s*extends\s+['\"][^'\"]+['\"]\s*%}")
CITY_CLAIM = re.compile(r"Vancouver|British Columbia|Canada", re.I)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strict_replace(src: str, old: str, new: str, label: str) -> str:
    if src.count(old) != 1:
        raise ValueError(label + " source changed (expected exactly one match)")
    return src.replace(old, new, 1)


def description(src: str, words: str) -> str:
    block = "{% block description %}" + words + "{% endblock %}"
    matches = list(DESC_BLOCK.finditer(src))
    if len(matches) == 1:
        return src[:matches[0].start()] + block + src[matches[0].end():]
    if matches:
        raise ValueError("Multiple description blocks")
    ext = EXTENDS.search(src)
    if not ext:
        raise ValueError("Parent template declaration missing")
    return src[:ext.end()] + "\n" + block + src[ext.end():]


def revise_about(src: str) -> str:
    out = description(src, ABOUT_DESCRIPTION)
    edits = (
        ("an entrepreneur and researcher from Iran, with an interest in research and professional collaboration across borders",
         "an Iranian entrepreneur and researcher living in Vancouver, British Columbia, Canada, with a focus on agricultural economics and international collaboration"),
        ("managing agricultural and scientific projects, and professional work in jewelry, gold coins, carpet trading, hospitality, research, writing and website development.",
         "leading agricultural and scientific projects and drawing on experience in gold and jewelry production and trade, coins, gemstones, specialist handwoven carpets, culinary arts and hospitality, research, writing, professional education and website development."),
        ("<div class=\"mpw-fact\"><dt>Field</dt><dd>Production Economics and Farm Management</dd></div>",
         "<div class=\"mpw-fact\"><dt>Field</dt><dd>Production Economics and Farm Management</dd></div>\n"
         "<div class=\"mpw-fact\"><dt>Current residence</dt><dd>Vancouver, British Columbia, Canada</dd></div>\n"
         "<div class=\"mpw-fact\"><dt>Leadership</dt><dd>CEO, Zomorod Melal Agro-Industry Company; founder, MojPlayWin</dd></div>"),
    )
    for old, new in edits:
        out = strict_replace(out, old, new, "About: " + old[:44])
    if out.count("Vancouver, British Columbia, Canada") < 2:
        raise ValueError("Owner-confirmed residence absent in About")
    if "Universiti Putra Malaysia (UPM)" not in out or "Production Economics and Farm Management" not in out:
        raise ValueError("Academic record unexpectedly missing")
    if "lecturer" in out.lower():
        raise ValueError("Unsupported lecturer role unexpectedly introduced")
    return out


def revise_contact(src: str) -> str:
    out = description(src, CONTACT_DESCRIPTION)
    out = strict_replace(
        out, "International &amp; remote collaboration",
        "Vancouver, British Columbia, Canada · International &amp; remote collaboration",
        "Contact residence",
    )
    if "name=\"csrfmiddlewaretoken\"" not in out and "{% csrf_token %}" not in out:
        raise ValueError("Expected existing contact CSRF form")
    return out

def revise_shared_meta(source: str) -> str:
    count = source.count(SEO_OLD)
    print("CONTACT_META_COPY_COUNT=" + str(count), flush=True)
    if count not in (2, 3, 4):
        raise ValueError("Unexpected number of shared Contact SEO references")
    return source.replace(SEO_OLD, SEO_NEW)


def targets() -> dict[str, Path]:
    if APP.is_symlink() or not (APP / "manage.py").is_file():
        raise ValueError("Independent personal Django application mismatch")
    result = {}
    for rel in RELATIVES:
        path = APP / rel
        if not path.is_file() or path.is_symlink() or path.resolve() != path:
            raise ValueError("Unsafe template: " + rel)
        result[rel] = path
    # The SEO configuration is a separate source from Contact's HTML template.
    # Restrict discovery to personal-app source files and require one exact match.
    roots = (APP / "personal_site", APP / "config", APP / "templates/personal_site")
    matches = []
    for root in roots:
        if not root.is_dir() or root.is_symlink():
            continue
        for path in root.rglob("*"):
            if path.suffix not in (".py", ".html", ".json", ".yml", ".yaml"):
                continue
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 1000000:
                continue
            raw = path.read_text(encoding="utf8")
            if SEO_OLD in raw or SEO_NEW in raw:
                matches.append(path)
    if len(matches) != 1:
        raise ValueError("Expected exactly one public Contact SEO text source; found " + str(len(matches)))
    seo_path = matches[0]
    if APP not in seo_path.parents or seo_path.resolve() != seo_path:
        raise ValueError("SEO source not within the independent personal application")
    rel = seo_path.relative_to(APP).as_posix()
    if rel in result:
        raise ValueError("SEO source must be separate from page templates")
    result[rel] = seo_path
    print("PROFILE_META_SOURCE=" + rel, flush=True)
    return result


def plan() -> dict[str, tuple[bytes, bytes]]:
    changed = {}
    for rel, path in targets().items():
        before = path.read_bytes()
        source = before.decode("utf8")
        if rel.endswith("/about.html"):
            revised = revise_about(source)
        elif rel.endswith("/contact.html"):
            revised = revise_contact(source)
        else:
            if rel != "templates/personal_site/base.html":
                raise ValueError("Unexpected Contact metadata source path: " + rel)
            revised = revise_shared_meta(source)
        after = revised.encode("utf8")
        if after == before:
            raise ValueError("No difference in " + rel)
        changed[rel] = (before, after)
    return changed


def django_preflight(candidates: dict[str, tuple[bytes, bytes]]) -> None:
    sys.path.insert(0, str(APP))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.template import engines
    for rel, (_, data) in candidates.items():
        if rel.endswith(".html"):
            engines["django"].engine.from_string(data.decode("utf8"))
        elif rel.endswith(".py"):
            compile(data.decode("utf8"), rel, "exec")
        elif rel.endswith(".json"):
            json.loads(data.decode("utf8"))
    from django.test import Client
    c = Client(HTTP_HOST="mojplaywin.com")
    for route in ("about/", "contact/", "resume/", "gallery/", "blog/"):
        r = c.get("/mojtaba.roozegar/" + route, secure=True)
        if r.status_code != 200:
            raise ValueError("Baseline personal route unhealthy: " + route)
    # File-based candidate templates are compiled before any production write.
    print("PERSONAL_PROFILE_DJANGO_PREFLIGHT=PASS", flush=True)


def backup_folder(run_id: str) -> Path:
    if not re.fullmatch(r"[0-9]{6,24}", run_id):
        raise ValueError("Invalid workflow run")
    return BACKUP_ROOT / run_id


def atomic_replace(path: Path, data: bytes) -> None:
    fd, temp = tempfile.mkstemp(prefix=".mr-public-copy-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            os.fchmod(out.fileno(), stat.S_IMODE(path.stat().st_mode))
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        if os.path.lexists(temp):
            os.unlink(temp)


def install(run_id: str, candidates: dict[str, tuple[bytes, bytes]]) -> None:
    folder = backup_folder(run_id)
    if folder.exists() or folder.is_symlink():
        raise ValueError("Backup location already exists")
    folder.mkdir(parents=True, mode=0o700)
    manifest = {"files": {}}
    paths = targets()
    for idx, (rel, (before, after)) in enumerate(candidates.items()):
        saved = folder / ("file" + str(idx) + ".before")
        with saved.open("xb") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(before)
            handle.flush()
            os.fsync(handle.fileno())
        manifest["files"][rel] = {
            "backup": saved.name,
            "before_sha256": digest(before),
            "after_sha256": digest(after),
            "before_bytes": len(before),
            "after_bytes": len(after),
        }
    mpath = folder / "manifest.json"
    mpath.write_text(json.dumps(manifest, sort_keys=True), encoding="utf8")
    mpath.chmod(0o600)
    for rel, (before, _) in candidates.items():
        entry = manifest["files"][rel]
        if digest(paths[rel].read_bytes()) != entry["before_sha256"]:
            raise ValueError("Concurrent source modification: " + rel)
        if digest((folder / entry["backup"]).read_bytes()) != digest(before):
            raise ValueError("Backup checksum invalid: " + rel)
    completed = []
    try:
        for rel, (_, after) in candidates.items():
            atomic_replace(paths[rel], after)
            completed.append(rel)
            if digest(paths[rel].read_bytes()) != digest(after):
                raise ValueError("Post-write checksum mismatch: " + rel)
    except BaseException:
        for rel in reversed(completed):
            old = candidates[rel][0]
            if digest(paths[rel].read_bytes()) == digest(candidates[rel][1]):
                atomic_replace(paths[rel], old)
        raise
    print("PERSONAL_PROFILE_COPY_INSTALLED=YES", flush=True)
    print("PERSONAL_PROFILE_BACKUP=" + str(folder), flush=True)


def rollback(run_id: str) -> None:
    folder = backup_folder(run_id)
    if folder.is_symlink() or not (folder / "manifest.json").is_file():
        raise ValueError("No valid backup")
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf8"))
    paths = targets()
    for rel, entry in manifest["files"].items():
        if rel not in paths:
            raise ValueError("Unexpected backup target")
        old = (folder / entry["backup"]).read_bytes()
        current = paths[rel].read_bytes()
        if digest(old) != entry["before_sha256"] or digest(current) not in (
            entry["before_sha256"], entry["after_sha256"]
        ):
            raise ValueError("Rollback refuses changed content: " + rel)
    for rel, entry in manifest["files"].items():
        if digest(paths[rel].read_bytes()) == entry["after_sha256"]:
            atomic_replace(paths[rel], (folder / entry["backup"]).read_bytes())
        if digest(paths[rel].read_bytes()) != entry["before_sha256"]:
            raise ValueError("Rollback verification failed: " + rel)
    print("PERSONAL_PROFILE_COPY_ROLLBACK=VERIFIED", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "install", "rollback"))
    parser.add_argument("--run-id")
    args = parser.parse_args()
    if args.action == "rollback":
        if not args.run_id:
            parser.error("--run-id required")
        rollback(args.run_id)
        return
    candidates = plan()
    django_preflight(candidates)
    print("PERSONAL_PROFILE_COPY_PREFLIGHT=PASS", flush=True)
    print("PERSONAL_PROFILE_TEMPLATES=" + str(len(candidates)), flush=True)
    if args.action == "install":
        if not args.run_id:
            parser.error("--run-id required")
        install(args.run_id, candidates)


if __name__ == "__main__":
    main()
