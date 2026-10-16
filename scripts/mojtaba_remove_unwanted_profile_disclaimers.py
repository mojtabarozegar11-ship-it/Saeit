#!/usr/bin/env python3
"""Delete unhelpful self-defensive promotional disclaimers from Mojtaba personal site.

Not a truth-claim rewrite: no fictitious address, clients, success figures or
qualifications added. Only recognized personal template prose and native content
for the exactly 93 previously published articles. Preserve photos, markup,
published URLs, metadata and all other Django apps; SHA-guarded backups/rollback.
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
import sys
from pathlib import Path

APP = Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
ROOT = "templates/personal_site/core"
PRIMARY = 'id="mpw-primary-personal-profile-20261016"'
OLD_GALLERY = 'id="mpw-new-originals-20261015-b"'
OLD_ARTICLES = 'id="mpw-mojtaba-twenty-image-essays-20261016"'
NO_TOKENS = (
    "It is not presented as evidence of a Vancouver office",
    "not an existing Vancouver project or guaranteed service",
    "not completed client contracts, a claimed Canadian office",
    "not an actual client installation",
    "Images document editorial themes, not client contracts",
    "The image is not proof of a Vancouver office",
    "not evidence of a business partnership",
    "not a claim of a Canadian office",
)

def digest(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def trim_spaces(s:str)->str:
    return re.sub(r" {2,}", " ", s).strip()

def cleanup_template(text:str)->str:
    """Change only conspicuous editorial boilerplate; do not touch site facts."""
    s=text
    # Owner photo profile: remove the full duplicated disclaimer paragraph.
    s, n = re.subn(
        r'<p\b[^>]*>\s*This is a personal photograph selected by the profile owner\.\s*'
        r'It is not presented as\s*evidence of a Vancouver office or a completed client project\.\s*</p>',
        "", s, flags=re.I|re.S
    )
    # Owner's photo already describes the person; neutralize unnatural caption.
    s=s.replace("Official owner-selected profile photograph", "Mojtaba Roozegar")
    # Professional proposals must explain possible outputs, not repeat defenses.
    s=s.replace(
        "The following are proposed pilot formats, not completed client contracts, a claimed Canadian office, fixed offers or guaranteed results.",
        "The following are possible starting points for a clearly scoped technical pilot."
    )
    s=s.replace(
        "This is an invitation, not an existing Vancouver project or guaranteed service.",
        "A practical collaboration starts with the organization's requirements and a defined pilot."
    )
    s=s.replace(
        "Images document editorial themes, not client contracts.",
        "Explore the methods and practical applications described in each article."
    )
    s=s.replace(
        "Conceptual visualization · not an actual client installation",
        "Technology and engineering illustration"
    )
    s=s.replace(
        "Conceptual illustration · not an actual client installation",
        "Technology and engineering illustration"
    )
    s=s.replace(
        "Personal portrait or illustrative digital artwork supplied for this essay. The image is not proof of a Vancouver office, professional engagement or completed enterprise project.",
        "Portrait or technology illustration accompanying this article."
    )
    s=s.replace(
        "Personal gallery photograph used as an editorial illustration, not evidence of a business partnership.",
        "Personal gallery photograph."
    )
    s=s.replace(
        "This is an invitation to explore possibilities—not a claim of a Canadian office, completed partnership or work authorization.",
        "I welcome discussions about research, digital services and practical project opportunities."
    )
    s=s.replace(
        "not a record of a completed client deployment.",
        "created to illustrate a technical topic."
    )
    # Avoid a repeated meta-disclaimer on all personal photo cards.
    s=s.replace(
        "This is a personal photograph selected by the profile owner.",
        ""
    )
    if n>2:raise ValueError("Unusually many profile paragraphs")
    if s.count(PRIMARY)!=text.count(PRIMARY):raise ValueError("Profile image section changed")
    if s.count(OLD_GALLERY)!=text.count(OLD_GALLERY):
        raise ValueError("Owner gallery marker changed")
    if s.count(OLD_ARTICLES)!=text.count(OLD_ARTICLES):
        raise ValueError("Existing illustrated articles marker changed")
    return s

# These expressions are deliberately limited to self-referential editorial
# disclaimers, not scientific uncertainty or necessary safety information.
EDITORIAL_NEGATIVE = re.compile(
    r"(?:\bnot\s+(?:proof|evidence|a\s+(?:record|claim|photograph|representation|statement|screenshot|verified|documented|real|completed|Canadian|Vancouver)|an?\s+(?:existing|established|actual|authorized|independently|assertion))\b"
    r"|\bdoes\s+not\s+(?:prove|establish|document|represent|verify)\b"
    r"|\bwithout\s+(?:claiming|asserting|implying|inventing)\b"
    r"|\bno\s+(?:existing|signed|confirmed|actual|established)\b"
    r"|\bnot\s+(?:a\s+|an\s+)?claim\s+of\b)",
    re.I
)
SELF_PROMO_CONTEXT = re.compile(
    r"(?:\bphoto(?:graph)?\b|\bportrait\b|\bpicture\b|\billustrat(?:ion|e|ed)\b|\bartwork\b|"
    r"\bimage\b|\bprofile\b|\bclient\b|\bcustomer\b|\bcontract\b|\bVancouver\b|\bCanada\b|\bCanadian\b|"
    r"\boffice\b|\bresiden(?:ce|cy|t)\b|\bproject\b|\bcommercial\s+(?:engagement|relationship)\b|"
    r"\bdeployment\b|\bcertificat(?:ion|e)\b)",
    re.I
)
def objectionable(sentence:str)->bool:
    t=sentence.strip()
    if t.startswith(("Editorial note:", "Editorial Note:")):
        return True
    if ("Author: Mojtaba Roozegar." in t and
        re.search(r"(?:not proof|not verification|not evidence|not a|not an|does not|not claim)",t,re.I)):
        return True
    if EDITORIAL_NEGATIVE.search(t) and SELF_PROMO_CONTEXT.search(t):
        # Retain technical, scientific, legal or access-control safeguards:
        # e.g., dashboards do not prove an actual profit, missing data, safety.
        if re.search(r"(?:a\s+dashboard|a\s+scenario|input|metric|accuracy|"
                     r"payment|privacy|consent|legal advice|authorized data|"
                     r"regulated|sensor|audit|result|method|test|calculation)",t,re.I) and not re.search(
                         r"(?:portrait|picture|photograph|artwork|illustration|"
                         r"Vancouver\s+office|Canadian\s+office|client\s+relationship|"
                         r"customer\s+contract|finished\s+(?:corporate|client)|"
                         r"completed\s+(?:client|customer|enterprise)\s+(?:project|deployment))",t,re.I):
            return False
        return True
    if re.search(r"\b(?:photograph|portrait|illustration|image|picture|artwork)\b",t,re.I) and re.search(
        r"\b(?:no|not|never)\b.{0,130}\b(?:client|contract|office|residen|Canadian|Vancouver|"
        r"meeting|completed\s+(?:project|software|service)|customer|installed|certified)\b",t,re.I
    ):
        return True
    return False

def cleanup_article(text:str)->str:
    out=[]
    for para in text.split("\n\n"):
        strip=para.strip()
        if not strip:
            continue
        if re.match(r"^(?:Editorial note|Editorial Note):",strip):
            continue
        # Preserve byline when it is paired with disallowed editorial commentary.
        if strip.startswith("Author: Mojtaba Roozegar.") and objectionable(strip):
            out.append("Author: Mojtaba Roozegar.")
            continue
        # Each native article is plain text; paragraphs may start with a heading.
        lines=para.splitlines()
        if len(lines)>1 and len(lines[0])<110:
            heading=lines[0]
            copy="\n".join(lines[1:])
        else:
            heading=""
            copy=para
        # Split only at full stop/question mark preceding an English sentence.
        pieces=re.split(r"(?<=[.!?])\s+(?=[A-Z])",copy)
        kept=[p for p in pieces if not objectionable(p)]
        if not kept:
            # Keep informative heading and text structure where possible.
            continue
        body=" ".join(kept).strip()
        if heading:body=heading+"\n"+body
        out.append(body)
    revised="\n\n".join(out)
    if len(revised)<len(text)*.68 or len(revised.split())<160:
        raise ValueError("Refusing oversized or overly aggressive editorial removal")
    return revised

def article_rows(content_dir:Path):
    mpath=content_dir.parent/"scripts/mojtaba_twenty_photo_essays_safe_publish.py"
    if not mpath.is_file() or mpath.is_symlink():
        raise ValueError("Expected native article catalog absent")
    spec=importlib.util.spec_from_file_location("original_photo_catalog",mpath)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    rows=module.load_articles(content_dir)
    older=module.load_older(content_dir)
    if len(rows)!=20 or len(older)!=73 or len(set(older))!=73:
        raise ValueError("Expected all original 93 articles")
    newest=[r["slug"] for r in rows]
    if set(older)&set(newest):raise ValueError("Duplicate article slug across generations")
    return list(older)+newest

def paths(app:Path):
    if app.is_symlink() or not (app/"manage.py").is_file():
        raise ValueError("Independent personal Django V17 app not found")
    folder=app/ROOT
    if not folder.is_dir() or folder.is_symlink():raise ValueError("Unexpected template folder")
    files={}
    for p in folder.glob("*.html"):
        if p.is_symlink() or not p.is_file():raise ValueError("Unexpected template symlink")
        files[p.name]=p
    if not all(n in files for n in ("home.html","about.html","detail.html","posts.html")):
        raise ValueError("Core personal templates missing")
    return files

def prepare(app:Path,content:Path):
    sys.path.insert(0,str(app))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    import django;django.setup()
    from django.template import engines
    from core.models import Post
    all_slugs=article_rows(content)
    db={p.slug:p for p in Post.objects.filter(slug__in=all_slugs)}
    if len(db)!=93 or not all(p.published for p in db.values()):
        raise ValueError("93 native published personal articles must be present")
    before_posts={slug:db[slug].content for slug in all_slugs}
    after_posts={slug:cleanup_article(s) for slug,s in before_posts.items()}
    before_tpl={n:p.read_text(encoding="utf-8") for n,p in paths(app).items()}
    after_tpl={n:cleanup_template(s) for n,s in before_tpl.items()}
    if sum(before_tpl[n]!=after_tpl[n] for n in before_tpl)>11:
        raise ValueError("Unexpectedly broad template edit scope")
    if not (before_tpl["home.html"]!=after_tpl["home.html"] and
            before_tpl["about.html"]!=after_tpl["about.html"]):
        raise ValueError("The reported profile disclaimer is not present in both expected profile pages")
    for n,v in after_tpl.items():
        if before_tpl[n]!=v:
            engines["django"].engine.from_string(v)
    # Require removal of key photographed-profile phrase everywhere in allowlisted templates/posts.
    joined="\n".join(list(after_tpl.values())+list(after_posts.values()))
    for prohibited in NO_TOKENS:
        if prohibited.casefold() in joined.casefold():
            raise ValueError("An explicitly rejected phrase remained: "+prohibited)
    return db,before_posts,after_posts,before_tpl,after_tpl

def install(app:Path,content:Path,backup:Path):
    from django.db import transaction
    db,bp,ap,bt,at=prepare(app,content)
    if backup.exists() or backup.is_symlink():raise ValueError("Backup path collision")
    changed_posts={slug:{"before":bp[slug],"after":ap[slug]} for slug in bp if bp[slug]!=ap[slug]}
    changed_templates={name:{"before":bt[name],"after":at[name]} for name in bt if bt[name]!=at[name]}
    if not changed_posts and not changed_templates:raise ValueError("No editorial changes found")
    backup.mkdir(parents=True,mode=0o700)
    state={"posts":changed_posts,"templates":changed_templates,"article_count":93}
    (backup/"state.json").write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")
    (backup/"state.json").chmod(0o600)
    written=[]
    files=paths(app)
    try:
        with transaction.atomic():
            for slug,values in changed_posts.items():
                obj=db[slug]
                if obj.content!=values["before"]:raise ValueError("Article edited by another process")
                obj.content=values["after"]
                obj.save(update_fields=["content"])
            for name,values in changed_templates.items():
                p=files[name]
                if digest(p.read_bytes())!=digest(values["before"].encode()):
                    raise ValueError("Template modified by another process")
                tmp=p.with_name(p.name+".editorial-revision")
                if tmp.exists() or tmp.is_symlink():raise ValueError("Unowned temp file")
                tmp.write_text(values["after"],encoding="utf-8")
                tmp.chmod(p.stat().st_mode&0o777)
                os.replace(tmp,p);written.append(name)
    except BaseException:
        for name in written:
            p=files[name]
            if digest(p.read_bytes())==digest(changed_templates[name]["after"].encode()):
                tmp=p.with_name(p.name+".editorial-auto-restore")
                tmp.write_text(changed_templates[name]["before"],encoding="utf-8")
                tmp.chmod(p.stat().st_mode&0o777);os.replace(tmp,p)
        raise
    if (app/"tmp").is_dir():(app/"tmp/restart.txt").touch()
    print("EDITORIAL_CLEANUP_PROFILE_NOTICE_REMOVED=yes",flush=True)
    print("EDITORIAL_CLEANUP_TEMPLATES_CHANGED="+str(len(changed_templates)),flush=True)
    print("EDITORIAL_CLEANUP_NATIVE_ARTICLE_BODIES_CHANGED="+str(len(changed_posts)),flush=True)
    print("EDITORIAL_CLEANUP_PHOTOS_LINKS_TITLES_UNCHANGED=yes",flush=True)
    print("EDITORIAL_CLEANUP_BACKUP="+str(backup),flush=True)

def rollback(app:Path,backup:Path):
    if backup.is_symlink() or not backup.is_dir():raise ValueError("Backup missing")
    state=json.loads((backup/"state.json").read_text(encoding="utf-8"))
    filemap=paths(app)
    for name,val in state["templates"].items():
        if digest(filemap[name].read_bytes())!=digest(val["after"].encode()):
            raise ValueError("New template changes since release; manual review required")
    sys.path.insert(0,str(app))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    import django;django.setup()
    from core.models import Post
    from django.db import transaction
    posts={p.slug:p for p in Post.objects.filter(slug__in=state["posts"])}
    if len(posts)!=len(state["posts"]):raise ValueError("Post rows removed since release")
    for slug,values in state["posts"].items():
        if posts[slug].content!=values["after"]:
            raise ValueError("Article edited after release; refuse loss of newer work")
    with transaction.atomic():
        for slug,values in state["posts"].items():
            p=posts[slug];p.content=values["before"];p.save(update_fields=["content"])
        for name,val in state["templates"].items():
            f=filemap[name]
            tmp=f.with_name(f.name+".editorial-rollback")
            if tmp.exists() or tmp.is_symlink():raise ValueError("Rollback staging collision")
            tmp.write_text(val["before"],encoding="utf-8")
            tmp.chmod(f.stat().st_mode&0o777);os.replace(tmp,f)
    if (app/"tmp").is_dir():(app/"tmp/restart.txt").touch()
    print("EDITORIAL_CLEANUP_SAFE_ROLLBACK=yes",flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("check","install","rollback"))
    p.add_argument("--app",type=Path,default=APP)
    p.add_argument("--content",type=Path)
    p.add_argument("--backup",type=Path)
    a=p.parse_args()
    if a.action=="rollback":
        if not a.backup:p.error("Need --backup")
        rollback(a.app,a.backup);return
    if not a.content:p.error("Need --content")
    if a.action=="check":
        db,bp,ap,bt,at=prepare(a.app,a.content)
        print("EDITORIAL_CLEANUP_PREFLIGHT_93_ARTICLES=yes",flush=True)
        print("EDITORIAL_CLEANUP_PREFLIGHT_TEMPLATES_TO_CHANGE="+str(sum(bt[n]!=at[n] for n in bt)),flush=True)
        print("EDITORIAL_CLEANUP_PREFLIGHT_POSTS_TO_CHANGE="+str(sum(bp[n]!=ap[n] for n in bp)),flush=True)
    else:
        if not a.backup:p.error("Need --backup")
        install(a.app,a.content,a.backup)
if __name__=="__main__":main()
