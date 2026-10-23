"""MojPlayWin MAIN-only standalone static publisher, completely outside Django.

Publishes ONLY byte/field-matched, previously authored, source-annotated, safe
English teaching guides to an owned new docroot folder. Never touches .htaccess,
Passenger, template routes, sites, product database, finance, other publishers.
This does NOT make factual source claims independently verified by Gen65.
"""
from __future__ import annotations
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from datetime import datetime, timezone

try:
    from .page_content_factory import BRIEFS, SOURCES, TENANT, build, _private
except ImportError:
    from page_content_factory import BRIEFS, SOURCES, TENANT, build, _private

DOCROOT = Path("/home/zomorod2/mojplaywin.com")
PRIVATE_ROOT = Path("/home/zomorod2/.private_mojplaywin_main_agents/evolution_runtime_20261018")
TARGET = DOCROOT / "mpw-standalone-guides"
OWNER = ".mpw-standalone-guides-owner.json"
MAX_PUBLISHED = 8
MAX_FILES = 35
SECTIONS = {"agents": ("AI & Agent Systems", "/agents/"),
            "knowledge": ("Knowledge & Learning", "/knowledge/"),
            "studio": ("Creative Studio", "/studio/"),
            "research": ("Research Methods", "/research/")}

CSS = """*{box-sizing:border-box}body{margin:0;background:#0d141b;color:#eaf0f5;font:17px/1.75 system-ui,-apple-system,sans-serif}
header,footer{background:#111e29;border-bottom:1px solid #b59b63;padding:18px 5%}
header a{color:#eacb89;margin-right:20px;text-decoration:none}footer{border-top:1px solid #b59b63;border-bottom:0}
main{max-width:940px;padding:45px 24px;margin:auto}h1{font-size:clamp(2rem,4vw,3.4rem);line-height:1.2}
h1,h2{color:#f6dda0}h2{margin-top:38px}a{color:#f1cd88}p,li{max-width:77ch}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:18px}
article{border:1px solid #554c3b;border-radius:16px;padding:24px;background:#172430}
.label{color:#e0bf7b;font-size:.82rem;letter-spacing:.12em;text-transform:uppercase}
.note{border-left:3px solid #c49e54;padding:13px 19px;background:#16212c}
@media(prefers-reduced-motion:reduce){*{animation:none!important;scroll-behavior:auto!important}}
"""

def _read_file(path: Path, limit: int) -> dict:
    if (path.is_symlink() or not path.is_file()
        or path.stat().st_size > limit):
        raise RuntimeError("unsafe_editorial_input")
    obj = json.loads(path.read_text("utf-8"))
    if not isinstance(obj,dict) or obj.get("tenant") != TENANT:
        raise RuntimeError("cross_tenant_editorial_input")
    return obj

def _proof_rows(private_root: Path):
    if not _private(private_root):
        raise RuntimeError("private_editorial_root_invalid")
    folder = private_root / "page_content_20261018" / "drafts"
    if not _private(folder):
        raise RuntimeError("private_draft_storage_invalid")
    report = _read_file(private_root / "gen65_operational_report.json",9000)
    if (report.get("status") != "gen65_operational_private"
        or report.get("active_private_generation") != 65
        or report.get("existing_public_master_generation") != 64):
        raise RuntimeError("gen65_operational_proof_missing")
    originals = {x["slug"]:x for x in BRIEFS}
    files = list(folder.iterdir())
    if len(files) > MAX_PUBLISHED:
        raise RuntimeError("editorial_content_count_exceeded")
    records = []
    for path in sorted(files):
        if (path.suffix != ".json" or path.name not in
            {key+".json" for key in originals}):
            raise RuntimeError("foreign_editorial_file")
        record = _read_file(path,19000)
        brief = originals[path.stem]
        # Compare all fields, down to exact authored body and source annotations.
        expected = build(brief, record.get("drafted_utc",""))
        if any(record.get(key) != val for key,val in expected.items()):
            raise RuntimeError("editorial_unverified_text_or_source")
        if (set(record) != set(expected) |
              {"gen65_private_review_recommendation",
               "gen65_factual_verification_completed"}
            or record["gen65_private_review_recommendation"] !=
               "candidate_ready_for_human_review"
            or record["gen65_factual_verification_completed"] is not False
            or record["published"] is not False
            or record["approved_for_publication"] is not False):
            raise RuntimeError("editorial_review_or_provenance_invalid")
        records.append(record)
    return records

def _render_markdown(text: str):
    fragments = []
    for line in text.splitlines():
        line=line.strip()
        if not line:continue
        if line.startswith("# "):
            fragments.append("<h1>"+html.escape(line[2:])+"</h1>")
        elif line.startswith("## "):
            fragments.append("<h2>"+html.escape(line[3:])+"</h2>")
        elif line.startswith("- https://"):
            url=line[2:]
            if url not in SOURCES.values():
                raise RuntimeError("unrecognized_reference_url")
            fragments.append('<p><a rel="noopener noreferrer" href="'+html.escape(url,quote=True)+'">'+html.escape(url)+'</a></p>')
        elif line.startswith("#") or "<script" in line.lower():
            raise RuntimeError("unexpected_content_markup")
        else:
            fragments.append("<p>"+html.escape(line)+"</p>")
    return "\n".join(fragments)

def _frame(title: str, body: str, canonical: str, description: str):
    esc=lambda x:html.escape(x,quote=True)
    if not canonical.startswith("https://mojplaywin.com/mpw-standalone-guides/"):
        raise RuntimeError("untrusted_public_canonical_url")
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="index,follow">'
            '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; '
            'style-src &#39;self&#39;; img-src &#39;self&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;">'
            '<title>'+esc(title)+' | MojPlayWin</title><meta name="description" content="'+esc(description[:155])+'">'
            '<link rel="canonical" href="'+esc(canonical)+'"><link rel="stylesheet" href="/mpw-standalone-guides/style.css">'
            '</head><body><header><nav aria-label="MojPlayWin">'
            '<a href="/">MojPlayWin</a><a href="/mpw-standalone-guides/index.html">Knowledge & Insights</a>'
            '<a href="/agents/">AI</a><a href="/knowledge/">Knowledge</a>'
            '<a href="/studio/">Studio</a><a href="/research/">Research</a></nav></header>'
            '<main>'+body+'</main><footer><p>MojPlayWin · Independent educational guides.'
            ' Source references do not imply official endorsement or certification.</p>'
            '<a href="/">Back to MojPlayWin</a></footer></body></html>')

def make_files(records: list[dict]):
    if len(records)>MAX_PUBLISHED:
        raise RuntimeError("public_editorial_article_limit")
    files = {"style.css": CSS.encode("utf-8")}
    all_cards=[]
    for section, (label, original) in SECTIONS.items():
        subset = [r for r in records if r["page_path"] == original]
        cards=[]
        for row in subset:
            slug=row["slug"]
            relative=f"{section}/{slug}/index.html"
            public_url=f"https://mojplaywin.com/mpw-standalone-guides/{section}/{slug}/index.html"
            article=(_render_markdown(row["body_markdown"])
                     + '<p class="note">Educational material: this is a guide, not '
                     'a verified claim that MojPlayWin has deployed these controls. '
                     'Check linked primary sources before applying the advice.</p>')
            files[relative]=_frame(row["title"],article,public_url,row["summary"]).encode("utf8")
            link=f'<article><span class="label">{html.escape(label)}</span><h2><a href="/mpw-standalone-guides/{section}/{slug}/index.html">{html.escape(row["title"])}</a></h2><p>{html.escape(row["summary"][:195])}</p></article>'
            cards.append(link);all_cards.append(link)
        body=(f'<span class="label">MojPlayWin / {html.escape(label)}</span>'
              f'<h1>{html.escape(label)} — Learning Guides</h1>'
              f'<p>Original educational resources and practical steps. '
              f'These articles are independent content, not product claims.</p>'
              '<div class="grid">'+"".join(cards or ['<p>New guides are being prepared.</p>'])+'</div>')
        files[f"{section}/index.html"]=_frame(label,body,
             f"https://mojplaywin.com/mpw-standalone-guides/{section}/index.html",
             f"Educational guides about {label.lower()} from MojPlayWin.").encode("utf8")
    body=('<span class="label">MOJPLAYWIN / FREE EDUCATIONAL RESOURCES</span>'
          '<h1>Knowledge & Insights</h1><p>Independent guides for understanding '
          'AI evaluation, accessible learning, creative technology and research methods.</p>'
          '<div class="grid">'+"".join(all_cards or ['<p>Guides are being prepared.</p>'])+'</div>')
    files["index.html"]=_frame("Knowledge & Insights",body,
             "https://mojplaywin.com/mpw-standalone-guides/index.html",
             "Free practical educational guides on AI, learning, studio and research.").encode("utf8")
    files[OWNER]=json.dumps({"tenant":TENANT,"published_articles":len(records),
              "scope":"mojplaywin-main-static-standalone-guides-only",
              "content_fingerprints":{r["slug"]:r["content_sha256"] for r in records}},
              sort_keys=True).encode("utf8")
    if len(files)>MAX_FILES:
        raise RuntimeError("public_editorial_file_limit")
    return files

def render_to_staging(private_root: Path, stage_root: Path):
    """Pure build + staging, no modification of the public document root."""
    if not _private(stage_root):
        raise RuntimeError("editorial_staging_not_private")
    rows=_proof_rows(private_root)
    if len(rows)<2:
        raise RuntimeError("no_verified_private_guides")
    artifacts=make_files(rows)
    for rel,raw in artifacts.items():
        dest=stage_root/rel
        if dest.exists() or dest.is_symlink():
            raise RuntimeError("staging_not_empty")
        dest.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        dest.write_bytes(raw)
        dest.chmod(0o600)
    return {"tenant":TENANT,"generated_articles":len(rows),
            "generated_files":len(artifacts),"article_slugs":[r["slug"] for r in rows]}

def verify_public_target(docroot: Path, target: Path):
    if (docroot != DOCROOT or not docroot.is_dir() or docroot.is_symlink()
        or target != docroot/"mpw-standalone-guides"
        or (docroot/"passenger_wsgi.py").is_symlink()
        or not (docroot/"passenger_wsgi.py").is_file()
        or (docroot/".htaccess").is_symlink()
        or not (docroot/".htaccess").is_file()):
        raise RuntimeError("public_main_documentroot_attestation_failed")
    if target.exists():
        if target.is_symlink() or not target.is_dir():
            raise RuntimeError("public_editorial_target_not_owned")
        mark=_read_file(target/OWNER,6000)
        if mark.get("scope")!="mojplaywin-main-static-standalone-guides-only":
            raise RuntimeError("public_editorial_owner_invalid")
        allowed_top={OWNER,"index.html","style.css",*SECTIONS}
        children=list(target.iterdir())
        if (len(children)>len(allowed_top)
            or any(child.name not in allowed_top or child.is_symlink()
                   for child in children)):
            raise RuntimeError("public_editorial_unexpected_top_level")
        for section in SECTIONS:
            folder=target/section
            if folder.exists() and (folder.is_symlink() or not folder.is_dir()):
                raise RuntimeError("public_editorial_section_not_owned")
        for name in ("index.html","style.css"):
            file=target/name
            if file.exists() and (file.is_symlink() or not file.is_file()):
                raise RuntimeError("public_editorial_owned_file_not_regular")
        fingerprints=mark.get("content_fingerprints")
        if (not isinstance(fingerprints,dict)
            or len(fingerprints)>MAX_PUBLISHED
            or any(not isinstance(k,str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,80}",k)
                   for k in fingerprints)):
            raise RuntimeError("public_editorial_owned_fingerprints_invalid")
        for section in SECTIONS:
            folder=target/section
            if folder.exists():
                for entry in folder.iterdir():
                    if entry.is_symlink() or (entry.name=="index.html" and not entry.is_file()):
                        raise RuntimeError("public_editorial_unowned_section_entry")
                    if entry.name!="index.html":
                        if entry.name not in fingerprints or not entry.is_dir():
                            raise RuntimeError("public_editorial_unowned_section_entry")
                        contents=list(entry.iterdir())
                        if len(contents)!=1 or contents[0].name!="index.html" or not contents[0].is_file() or contents[0].is_symlink():
                            raise RuntimeError("public_editorial_unowned_article_entry")
