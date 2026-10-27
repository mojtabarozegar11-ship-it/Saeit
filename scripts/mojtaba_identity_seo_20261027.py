#!/usr/bin/env python3
"""Canonical person SEO, name variants and evidence-safe scholarly author profile.

Enhance a single existing Person JSON-LD node plus home and about copy.
Preserve verified profile content and avoid unverified journal publication claims.
Exact file backup, hash checks, Django preflight and rollback are required.
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
    "templates/personal_site/base.html",
    "templates/personal_site/core/home.html",
    "templates/personal_site/core/about.html",
)
BACKUP_ROOT = Path("/home/zomorod2/.backups/mojtaba-person-identity-seo-20261027")
ABOUT_DESCRIPTION = (
    "Mojtaba Roozegar (مجتبی روزگار) is a Vancouver-based researcher and "
    "scientific author, PhD Agricultural Economics (UPM), CEO of Zomorod "
    "Melal and founder of MojPlayWin. Research, books and articles."
)
HOME_DESCRIPTION = (
    "Mojtaba Roozegar (مجتبی روزگار): Vancouver-based agricultural economics "
    "researcher, scientific author, Zomorod Melal CEO and MojPlayWin founder."
)
HOME_OG_DESCRIPTION = (
    "Discover Mojtaba Roozegar's scientific research, authored articles, "
    "specialist book projects, management experience and digital ventures."
)
ALIAS_REQUIRED = (
    "مجتبی روزگار", "روزگار", "Mojtaba Roozegar", "Roozegar",
    "Mojtaba Rozegar", "Rozegar", "Mojtaba Rouzegar", "Rouzegar",
)
JSONLD_TAG = re.compile(
    r'(<script\s+type="application/ld\+json"\s*>)(.*?)(</script>)', re.S
)
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
        ("I am Mojtaba Roozegar, also written مجتبی روزگار in Persian.",
         "I am Mojtaba Roozegar (مجتبی روزگار), also romanized "
         "Mojtaba Rozegar or Mojtaba Rouzegar."),
        ("I have described my scientific work as researcher and author, including "
         "the development of specialized books, educational materials and "
         "encyclopedic projects. These are areas of work and research interest; "
         "a specific publication or credential should only be described as "
         "completed when its details are individually documented.",
         "I work as a researcher and author on several scientific articles, "
         "specialized books, educational texts and encyclopedic writing "
         "projects. The public research journal documents articles and ongoing "
         "research; journal-reviewed publications are only listed as such "
         "when independent publisher records can be checked."),
    )
    for old, new in edits:
        out = strict_replace(out, old, new, "About scientific author profile")
    for name in ("Mojtaba Rouzegar", "Mojtaba Rozegar", "مجتبی روزگار"):
        if name not in out:
            raise ValueError("Missing canonical personal name variant")
    if "Vancouver, British Columbia, Canada" not in out:
        raise ValueError("Confirmed current residence missing")
    if "Universiti Putra Malaysia (UPM)" not in out:
        raise ValueError("Existing academic section missing")
    if "No independently verified peer-reviewed" in out:
        raise ValueError("Scientific CV copy unexpectedly embedded in About")
    return out


def revise_home(src: str) -> str:
    out = description(src, HOME_DESCRIPTION)
    old_og = ("{% block og_description %}Mojtaba Roozegar is an "
              "entrepreneur, business executive and researcher. Read about "
              "his work, ideas and writing.{% endblock %}")
    new_og = "{% block og_description %}" + HOME_OG_DESCRIPTION + "{% endblock %}"
    out = strict_replace(out, old_og, new_og, "Home Open Graph")
    out = strict_replace(
        out,
        "Mojtaba Roozegar is an entrepreneur, business executive and "
        "researcher. This independent website brings together his work, "
        "ideas and writing.",
        "Mojtaba Roozegar (مجتبی روزگار) is an agricultural economics "
        "researcher, scientific author and agribusiness executive based in "
        "Vancouver, Canada. Explore his research writing, specialist books "
        "in development, professional experience and digital ventures.",
        "Home main introduction",
    )
    return out

def revise_shared_meta(source: str) -> str:
    matches = list(JSONLD_TAG.finditer(source))
    if len(matches) != 1:
        raise ValueError("Expected exactly one existing JSON-LD script in personal base")
    m = matches[0]
    try:
        graph = json.loads(m.group(2))
    except json.JSONDecodeError as exc:
        raise ValueError("Existing Person structured data is not literal JSON") from exc
    if graph.get("@type") != "ProfilePage":
        raise ValueError("Existing structured data is not a ProfilePage")
    person = graph.get("mainEntity")
    if not isinstance(person, dict) or person.get("@type") != "Person":
        raise ValueError("Existing structured person not found")
    if person.get("@id") != "https://mojplaywin.com/mojtaba.roozegar/#person":
        raise ValueError("Person ID must remain stable")
    aliases = person.get("alternateName")
    if not isinstance(aliases, list) or "Mojtaba Rouzegar" in aliases or "Rouzegar" in aliases:
        raise ValueError("Unexpected aliases or duplicate targeted release")
    if "Mojtaba Rozegar" not in aliases or "روزگار" not in aliases:
        raise ValueError("Existing owner name identity mismatch")
    aliases += ["Mojtaba Rouzegar", "Rouzegar"]
    if len(aliases) != len(set(aliases)):
        raise ValueError("Duplicate alternateName values")
    if not all(x in aliases for x in ALIAS_REQUIRED):
        raise ValueError("Not all required name spellings are present")
    titles = person.get("jobTitle")
    if not isinstance(titles, list) or "Researcher" not in titles or "Author" in titles:
        raise ValueError("Existing professional role list mismatch")
    titles.append("Author")
    person["description"] = (
        "Iranian researcher, scientific author and business executive "
        "based in Vancouver, Canada. Reported PhD Agricultural Economics "
        "(UPM), specialization in Production Economics and Farm Management; "
        "CEO Zomorod Melal and founder MojPlayWin. Scientific articles, "
        "specialized writing and ongoing scholarly book projects."
    )
    person["alumniOf"] = {
        "@type": "CollegeOrUniversity",
        "name": "Universiti Putra Malaysia (UPM)",
    }
    person["homeLocation"] = {
        "@type": "Place", "name": "Vancouver, British Columbia, Canada",
    }
    person["knowsAbout"] = [
        "Agricultural Economics", "Production Economics",
        "Farm Management", "Scientific Research", "Scientific Writing",
        "Agribusiness Leadership",
    ]
    payload = json.dumps(graph, ensure_ascii=False, separators=(",", ":"))
    out = source[:m.start(2)] + payload + source[m.end(2):]
    if len(list(JSONLD_TAG.finditer(out))) != 1:
        raise ValueError("Structured data duplicated")
    return out

def targets() -> dict[str, Path]:
    if APP.is_symlink() or not (APP / "manage.py").is_file():
        raise ValueError("Independent personal Django application mismatch")
    result = {}
    for rel in RELATIVES:
        path = APP / rel
        if not path.is_file() or path.is_symlink() or path.resolve() != path:
            raise ValueError("Unsafe personal template: " + rel)
        result[rel] = path
    return result

def plan() -> dict[str, tuple[bytes, bytes]]:
    changed = {}
    for rel, path in targets().items():
        before = path.read_bytes()
        source = before.decode("utf8")
        if rel.endswith("/about.html"):
            revised = revise_about(source)
        elif rel.endswith("/home.html"):
            revised = revise_home(source)
        elif rel == "templates/personal_site/base.html":
            revised = revise_shared_meta(source)
        else:
            raise ValueError("Unexpected profile SEO target")
        after = revised.encode("utf8")
        if after == before:
            raise ValueError("No SEO improvement in " + rel)
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
