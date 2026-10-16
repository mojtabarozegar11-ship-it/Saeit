#!/usr/bin/env python3
"""Safely publish exactly ten advanced website engineering articles through existing independent personal Django Post model.

Does not modify Django code, migrations, existing database rows, media, or the main sites.
Changes only 2 allowlisted personal V17 templates, and INSERTs 10 new Post records.
Use separate check/install/rollback commands. Existing records are never overwritten.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
import sys

APP = Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
TEMPLATES = {"home": "home.html", "posts": "posts.html"}
MARKER = 'id="mpw-website-ten-index-20261016"'
PROTECTED = (
    'id="mpw-new-originals-20261015-b"',
    'id="mpw-fifty-editorials-20261015"',
    'id="mpw-academic-profile-20261016"',
    'id="mpw-personal-expanded-20261016"',
    'id="mpw-journal-longform-index-20261016"',
    'id="mpw-journal-advanced-index-20261016"',
)
CSS = """
<style>
.mpw-web-expert{box-sizing:border-box;clear:both;max-width:1160px;width:100%;margin:34px auto;padding:clamp(20px,3vw,34px);background:#161615;border:4px solid #c8a05a;border-radius:14px;color:#f0e5d4;box-shadow:0 13px 36px rgba(0,0,0,.2)}
.mpw-web-expert *{box-sizing:border-box}
.mpw-web-expert h2{font:600 clamp(25px,3vw,38px)/1.25 Georgia,serif;color:#f3d49b;margin:0 0 15px}
.mpw-web-expert .intro{font:400 16px/1.8 system-ui,sans-serif;color:#e5ded4;max-width:950px;margin:0 0 20px}
.mpw-web-expert .link-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.mpw-web-expert .link-grid a{display:block;padding:17px;border:1px solid #9f7a3b;background:#24211c;border-radius:9px;text-decoration:none;color:#f6dab0;overflow-wrap:anywhere}
.mpw-web-expert .link-grid a:hover,.mpw-web-expert .link-grid a:focus{background:#3d3020;text-decoration:underline}
.mpw-web-expert .link-grid strong{font:600 20px/1.34 Georgia,serif;display:block;margin:0 0 9px}
.mpw-web-expert .link-grid span{color:#e5ded4;font:400 13px/1.65 system-ui,sans-serif;display:block}
@media(max-width:760px){.mpw-web-expert .link-grid{grid-template-columns:1fr}}
</style>"""

def load_manifest(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Manifest file missing or symlink")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1 or data.get("language") != "en":
        raise ValueError("Incorrect content manifest version")
    posts = data.get("articles")
    if not isinstance(posts, list) or len(posts) != 10:
        raise ValueError("Exactly 10 unique articles required")
    slugs = set()
    titles = set()
    for row in posts:
        if not isinstance(row, dict) or set(row) != {"slug","title","excerpt","content"}:
            raise ValueError("Unexpected article record")
        if any(not isinstance(v, str) or not v.strip() for v in row.values()):
            raise ValueError("Empty article field")
        slug = row["slug"]
        if not 16 <= len(slug) <= 160 or not all(c in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in slug):
            raise ValueError("Unsafe slug")
        if len(row["title"]) > 180 or len(row["excerpt"]) > 350:
            raise ValueError("Django Post field size exceeded")
        if len(row["content"].split()) < 600:
            raise ValueError("Not a full-length article: "+slug)
        if slug in slugs or row["title"] in titles:
            raise ValueError("Duplicate article")
        if "<script" in row["content"].lower() or "<iframe" in row["content"].lower():
            raise ValueError("Raw executable markup prohibited")
        slugs.add(slug)
        titles.add(row["title"])
    return data

def index_block(data: dict) -> str:
    esc = lambda s: html.escape(s, quote=True)
    bits = [
        '<section id="mpw-website-ten-index-20261016" class="mpw-web-expert" aria-label="Long-form research articles">',
        CSS,
        "<h2>Professional Website Engineering: Ten Expert Articles</h2>",
        '<p class="intro">Ten advanced technical studies on website architecture, Django engineering, APIs, SQL, performance, security, accessible design, SEO, deployment and observability. Each chapter has a separate permanent article URL.</p>',
        '<nav class="link-grid" aria-label="Ten specialist website engineering articles">'
    ]
    for entry in data["articles"]:
        slug, title, excerpt = (entry[x] for x in ("slug", "title", "excerpt"))
        bits.append(
            '<a href="/mojtaba.roozegar/blog/'+esc(slug)+'/">'
            + "<strong>"+esc(title)+"</strong><span>"+esc(excerpt)+"</span></a>"
        )
    bits.append("</nav></section>")
    return "\n".join(bits)

def check_app(app: Path) -> Path:
    if app.is_symlink() or not (app / "manage.py").is_file():
        raise ValueError("Unexpected personal Django V17 app path")
    base = app / "templates/personal_site/core"
    if base.is_symlink() or not base.is_dir():
        raise ValueError("Unsafe template directory")
    return base

def read_templates(app: Path) -> dict:
    base = check_app(app)
    result = {}
    for page, filename in TEMPLATES.items():
        path = base / filename
        if path.is_symlink() or not path.is_file() or path.resolve() != path:
            raise ValueError("Unsafe template file: "+filename)
        result[page] = path.read_text(encoding="utf-8")
    return result

def patch_template(original: str, data: dict) -> str:
    if MARKER in original:
        raise ValueError("Journal index already published")
    for protect in PROTECTED:
        if original.count(protect) != 1:
            raise ValueError("Previous material absent or duplicated: "+protect)
    block = "{% block content %}"
    if original.count(block) != 1:
        raise ValueError("Ambiguous Django content insertion")
    start = original.index(block) + len(block)
    stop = original.find("{% endblock %}", start)
    if stop < 0:
        raise ValueError("Django template lacks ending block")
    proposed = original[:stop] + "\n" + index_block(data) + "\n" + original[stop:]
    if proposed.count(MARKER) != 1:
        raise ValueError("Article index insertion failed")
    for protect in PROTECTED:
        if proposed.count(protect) != 1:
            raise ValueError("Protected content changed")
    return proposed

def sha(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def prepare_django(app: Path):
    check_app(app)
    sys.path.insert(0, str(app))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from core.models import Post
    from django.db import transaction
    return Post, transaction

def health_check(Post, posts):
    if not all(hasattr(Post, field) for field in ("slug","title","excerpt","content","published","cover")):
        raise ValueError("Native Django Post schema mismatch")
    existing = Post.objects.filter(slug__in=[x["slug"] for x in posts])
    if existing.exists():
        raise ValueError("Refusing to overwrite existing article slug(s)")

def stage_backup(backup: Path, before: dict, after: dict, posts: list) -> dict:
    if backup.exists() or backup.is_symlink():
        raise ValueError("Backup target must not exist")
    backup.mkdir(parents=True, mode=0o700)
    for page, name in TEMPLATES.items():
        f = backup / name
        f.write_text(before[page], encoding="utf-8")
        f.chmod(0o600)
    manifest = {
        "version":1,
        "templates":{page:{"before_sha256":sha(before[page]),"after_sha256":sha(after[page])} for page in TEMPLATES},
        "articles":{x["slug"]:{"title":x["title"],"content_sha256":sha(x["content"])} for x in posts}
    }
    # Deliberately do not add database IDs; records are selected by slug plus exact content.
    f = backup / "manifest.json"
    f.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    f.chmod(0o600)
    return manifest

def install(app: Path, content: Path, backup: Path) -> None:
    data = load_manifest(content)
    originals = read_templates(app)
    updated = {p:patch_template(text, data) for p,text in originals.items()}
    Post, transaction = prepare_django(app)
    health_check(Post, data["articles"])
    manifest = stage_backup(backup, originals, updated, data["articles"])
    changed = []
    try:
        with transaction.atomic():
            health_check(Post, data["articles"])
            for row in data["articles"]:
                Post.objects.create(
                    title=row["title"], slug=row["slug"],
                    excerpt=row["excerpt"], content=row["content"],
                    published=True
                )
            for page, name in TEMPLATES.items():
                path = app / "templates/personal_site/core" / name
                tmp = path.with_name(name+".journal-install")
                if tmp.exists() or tmp.is_symlink():
                    raise ValueError("Temporary file already exists")
                tmp.write_text(updated[page], encoding="utf-8")
                os.chmod(tmp, path.stat().st_mode & 0o777)
                os.replace(tmp, path)
                changed.append(page)
    except BaseException:
        for page in changed:
            shutil.copy2(backup / TEMPLATES[page], app / "templates/personal_site/core" / TEMPLATES[page])
        raise
    if (app / "tmp").is_dir():
        (app / "tmp/restart.txt").touch()
    print("WEBSITE_TEN_ARTICLES_DB_INSERTED=yes", flush=True)
    print("WEBSITE_TEN_NAV_INSTALLED_HOME_BLOG=yes", flush=True)
    print("ARTICLE_BACKUP_DIR="+str(backup), flush=True)

def rollback(app: Path, backup: Path) -> None:
    current = read_templates(app)
    if not backup.is_dir() or backup.is_symlink():
        raise ValueError("Missing backup")
    manifest_path = backup / "manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValueError("Backup manifest missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for page,name in TEMPLATES.items():
        before = backup / name
        if before.is_symlink() or not before.is_file():
            raise ValueError("Incomplete rollback templates")
        if sha(before.read_text(encoding="utf-8")) != manifest["templates"][page]["before_sha256"]:
            raise ValueError("Backup checksum mismatch")
        if sha(current[page]) != manifest["templates"][page]["after_sha256"]:
            raise ValueError("Template changed after installation; manual attention required")
    Post,transaction = prepare_django(app)
    slugdata = manifest["articles"]
    records = list(Post.objects.filter(slug__in=slugdata))
    if len(records) != len(slugdata):
        raise ValueError("Cannot safely rollback: article count differs")
    for record in records:
        expected = slugdata[record.slug]
        if record.title != expected["title"] or sha(record.content) != expected["content_sha256"]:
            raise ValueError("Cannot delete a modified article")
    with transaction.atomic():
        for page,name in TEMPLATES.items():
            path = app / "templates/personal_site/core" / name
            tmp = path.with_name(name+".journal-restore")
            shutil.copy2(backup / name, tmp)
            os.replace(tmp, path)
        Post.objects.filter(slug__in=slugdata).delete()
    if (app / "tmp").is_dir():
        (app / "tmp/restart.txt").touch()
    print("WEBSITE_TEN_ARTICLES_SAFE_ROLLBACK_COMPLETE=yes",flush=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode",choices=["check","install","rollback"])
    ap.add_argument("--app",type=Path,default=APP)
    ap.add_argument("--content",type=Path)
    ap.add_argument("--backup",type=Path)
    a = ap.parse_args()
    if a.mode=="rollback":
        if not a.backup:ap.error("--backup required")
        rollback(a.app,a.backup)
        return
    if not a.content:ap.error("--content required")
    data=load_manifest(a.content)
    current=read_templates(a.app)
    proposed={p:patch_template(s,data) for p,s in current.items()}
    print("WEBSITE_TEN_ARTICLES_CONTENT_TEMPLATES_VALID=yes",flush=True)
    if a.mode=="check":
        # Only check model if we are running within the expected live site.
        if a.app == APP and (a.app/"core/models.py").is_file():
            Post,_=prepare_django(a.app)
            health_check(Post,data["articles"])
            print("WEBSITE_TEN_ARTICLE_SLUGS_AVAILABLE=yes",flush=True)
        return
    if not a.backup:ap.error("--backup required")
    install(a.app,a.content,a.backup)

if __name__=="__main__":
    main()
