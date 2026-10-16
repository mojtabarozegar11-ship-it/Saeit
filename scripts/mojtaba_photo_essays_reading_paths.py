#!/usr/bin/env python3
"""Additive navigation-only follow-up for the twenty original illustrated personal essays.

Does not modify native Post rows, static files, head/meta tags, canonical,
payments, unrelated sites or the previous photo gallery. Only 3 personal V17
Django templates are eligible, with byte-hash guarded rollback.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

APP=Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
TEMPLATES={"home":"home.html","posts":"posts.html","detail":"detail.html"}
HOMEBLOCK='id="mpw-photoessay-reading-guides-20261016"'
DETAILBLOCK='id="mpw-photoessay-related-20261016"'
GROUPS=(
 ("Applied research and reliable evidence", (2,9,10,14,19),
  "Economics, evidence provenance, operational measurement and analytical decisions."),
 ("Designing useful enterprise websites", (1,4,15,16,18),
  "Real user tasks, accessible design, trustworthy transactions and robust releases."),
 ("Professional trust, secure AI and portfolios", (3,5,12,13,17),
  "Demonstrable expertise, responsible AI assistance and enterprise security."),
 ("Vancouver-oriented collaboration", (6,7,8,11,20),
  "Scoping, communication, responsible location claims and remote project delivery."),
)
PROTECTED=(
 'id="mpw-new-originals-20261015-b"',
 'id="mpw-fifty-editorials-20261015"',
 'id="mpw-academic-profile-20261016"',
 'id="mpw-personal-expanded-20261016"',
 'id="mpw-journal-longform-index-20261016"',
 'id="mpw-journal-advanced-index-20261016"',
 'id="mpw-website-ten-index-20261016"',
 'id="mpw-vancouver-collab-photo-ten-20261016"',
 'id="mpw-vancouver-enterprise-20-index-20261016"',
 'id="mpw-vancouver-enterprise-20-series2-index-20261016"',
 'id="mpw-mojtaba-twenty-image-essays-20261016"',
)
def sha(data:bytes):return hashlib.sha256(data).hexdigest()

def base_module(content:Path):
    f=content.parent/"scripts/mojtaba_twenty_photo_essays_safe_publish.py"
    if not f.is_file() or f.is_symlink():raise ValueError("Required original publication module missing")
    spec=importlib.util.spec_from_file_location("existing_photo20",f)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m

def rows_and_older(content:Path):
    m=base_module(content)
    new=m.load_articles(content)
    older=m.load_older(content)
    if len(new)!=20 or len(older)!=73 or len(set(older))!=73:
        raise ValueError("Expected 73 older and 20 new journal articles")
    if set(older)&{x["slug"] for x in new}:raise ValueError("Article slug overlap")
    if {x["photo_index"] for x in new}!=set(range(1,21)):
        raise ValueError("Invalid photo index")
    flat=[i for name,ixs,_ in GROUPS for i in ixs]
    if sorted(flat)!=list(range(1,21)):
        raise ValueError("Reading paths must cover every image exactly once")
    return {x["photo_index"]:x for x in new},older

def article_url(x):
    return "/mojtaba.roozegar/blog/"+x["slug"]+"/"

def reading_section(by_number):
    out=[
    '<section '+HOMEBLOCK+' aria-label="Photo essay reading guide" style="max-width:1180px;margin:36px auto;background:#141414;color:#f6ead3;border:3px solid #c39b5e;border-radius:16px;padding:clamp(18px,3vw,36px);clear:both">',
    '<h2 style="font:700 clamp(26px,3vw,36px)/1.2 Georgia,serif;color:#ebca92">Explore the 20 photo essays by professional interest</h2>',
    '<p style="font:16px/1.8 system-ui,sans-serif">Each article has its own accompanying portrait or original conceptual illustration. Choose a research, website-engineering, trust or Vancouver-oriented collaboration pathway below. Images document editorial themes, not client contracts.</p>',
    '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,250px),1fr));gap:16px">']
    for group,nums,explainer in GROUPS:
        out.append('<section style="background:#29251f;border:1px solid #a78450;padding:18px;border-radius:12px">'
                   '<h3 style="font:600 21px/1.4 Georgia,serif;color:#f2d3a1">'+html.escape(group)+'</h3>'
                   '<p style="font:14px/1.7 system-ui,sans-serif">'+html.escape(explainer)+'</p>'
                   '<ol style="padding-left:22px;display:grid;gap:10px">')
        for num in nums:
            row=by_number[num]
            out.append('<li><a href="'+html.escape(article_url(row),quote=True)+'" style="color:#f6d49d;line-height:1.55;text-decoration:underline;text-underline-offset:3px">'+html.escape(row["title"])+'</a></li>')
        out.append('</ol></section>')
    out.extend(['</div>',
     '<p style="font:15px/1.8 system-ui,sans-serif;margin-top:18px">Interested in an enterprise website or applied-research discussion? <a href="/mojtaba.roozegar/" style="color:#f7d69b;text-decoration:underline">Explore the professional profile and collaboration information</a>. A discussion would start with project scope, not an assumption of an existing Vancouver engagement.</p>',
     '</section>'])
    return "\n".join(out)

def detail_section(by_number):
    groups={n:(name,nums) for name,nums,_ in GROUPS for n in nums}
    out=['{% if kind == "Article" %}']
    for num in range(1,21):
        row=by_number[num]
        _,nums=groups[num]
        related=[n for n in nums if n!=num][:3]
        # One cross-category entry: deterministic next image index
        other=(num%20)+1
        if other not in related:related.append(other)
        start="{% if" if num==1 else "{% elif"
        out.append(start+' item.slug == "'+row["slug"]+'" %}')
        out.append('<aside '+DETAILBLOCK+' aria-label="Related illustrated journal articles" style="clear:both;max-width:1080px;margin:34px auto;padding:24px;border:2px solid #c39e66;border-radius:12px;background:#1b1916;color:#f7ead5">'
            '<h2 style="font:600 24px/1.4 Georgia,serif;color:#f2d098">Continue with related illustrated articles</h2><nav aria-label="Recommended next articles"><ul style="display:grid;gap:12px;padding-left:24px">')
        for j in related:
            dest=by_number[j]
            out.append('<li><a href="'+html.escape(article_url(dest),quote=True)+'" style="color:#f2d29b;text-decoration:underline;text-underline-offset:3px">'+html.escape(dest["title"])+'</a></li>')
        out.append('</ul><p style="margin-top:16px"><a href="/mojtaba.roozegar/blog/" style="color:#f8d89e">See all articles</a>'
            ' &nbsp;•&nbsp; <a href="/mojtaba.roozegar/" style="color:#f8d89e">Professional profile and collaboration</a></p></nav></aside>')
    out.extend(['{% endif %}','{% endif %}'])
    return "\n".join(out)

def target_paths(app:Path):
    if app.is_symlink() or not (app/"manage.py").is_file():
        raise ValueError("Expected separate personal V17 project missing")
    folder=app/"templates/personal_site/core"
    result={}
    for key,f in TEMPLATES.items():
        p=folder/f
        if p.is_symlink() or not p.is_file():raise ValueError("Unexpected template file")
        result[key]=p
    return result

def patch(key,source,rows):
    block="{% block content %}"
    if source.count(block)!=1:raise ValueError("Content template block missing or ambiguous")
    start=source.index(block)+len(block)
    end=source.find("{% endblock %}",start)
    if end<0:raise ValueError("Missing content block termination")
    if HOMEBLOCK in source or DETAILBLOCK in source:
        raise ValueError("Reading paths already published")
    if key in ("home","posts"):
        for marker in PROTECTED:
            if source.count(marker)!=1:
                raise ValueError("Original personal page marker missing: "+marker)
        addition=reading_section(rows)
        if addition.count('href="/mojtaba.roozegar/blog/')!=20:
            raise ValueError("All twenty links required")
    elif key=="detail":
        if source.count('id="mpw-mojtaba-essay-cover-20261016"')!=20:
            raise ValueError("All twenty original photo figures must be present")
        if 'id="mpw-journal-related-20261016"' not in source or "{{ item.title" not in source:
            raise ValueError("Original article related links or detail view missing")
        addition=detail_section(rows)
        if addition.count(DETAILBLOCK)!=20 or addition.count("item.slug ==")!=20:
            raise ValueError("Twenty related sets expected")
    else:raise ValueError("Unallowlisted template")
    return source[:end]+"\n"+addition+"\n"+source[end:]

def django_post_checks(app:Path,by_number,old):
    sys.path.insert(0,str(app))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    import django;django.setup()
    from django.template import engines
    from core.models import Post
    from django.db import connection
    if Post.objects.filter(slug__in=old,published=True).count()!=73:
        raise ValueError("73 previously published articles missing")
    for row in by_number.values():
        if not Post.objects.filter(slug=row["slug"],title=row["title"],published=True).exists():
            raise ValueError("One of the 20 original photo essays is missing")
    return engines

def install(app:Path,content:Path,backup:Path):
    rows,old=rows_and_older(content)
    paths=target_paths(app)
    original={k:p.read_text(encoding="utf-8") for k,p in paths.items()}
    proposed={k:patch(k,v,rows) for k,v in original.items()}
    engines=django_post_checks(app,rows,old)
    for k,v in proposed.items():
        engines["django"].engine.from_string(v)
        print("PHOTO_READING_PATHS_TEMPLATE_VALID="+k,flush=True)
    if backup.is_symlink() or backup.exists():raise ValueError("Existing backup collision")
    backup.mkdir(parents=True,mode=0o700)
    hashes={}
    for k,name in TEMPLATES.items():
        (backup/name).write_text(original[k],encoding="utf-8")
        (backup/name).chmod(0o600)
        hashes[k]={"before":sha(original[k].encode()),"after":sha(proposed[k].encode())}
    (backup/"manifest.json").write_text(json.dumps({"templates":hashes,"slugs":sorted(x["slug"] for x in rows.values())},indent=2),encoding="utf-8")
    (backup/"manifest.json").chmod(0o600)
    changed=[]
    try:
        for k,p in paths.items():
            if sha(p.read_bytes())!=hashes[k]["before"]:
                raise ValueError("Personal template changed since preflight")
            tmp=p.with_name(p.name+".reading-guides")
            if tmp.exists() or tmp.is_symlink():raise ValueError("Temporary file collision")
            tmp.write_text(proposed[k],encoding="utf-8")
            tmp.chmod(p.stat().st_mode & 0o777)
            os.replace(tmp,p)
            changed.append(k)
    except BaseException:
        for k in changed:
            p=paths[k]
            if sha(p.read_bytes())==hashes[k]["after"]:
                shutil.copy2(backup/TEMPLATES[k],p)
        raise
    if (app/"tmp").is_dir():(app/"tmp/restart.txt").touch()
    print("PHOTO_READING_PATHS_INSTALLED=yes",flush=True)
    print("PHOTO_READING_PATHS_DATABASE_UNCHANGED=yes",flush=True)
    print("PHOTO_READING_PATHS_BACKUP="+str(backup),flush=True)

def rollback(app:Path,backup:Path):
    if backup.is_symlink() or not backup.is_dir():raise ValueError("Backup absent")
    d=json.loads((backup/"manifest.json").read_text())
    paths=target_paths(app)
    for k,p in paths.items():
        before=(backup/TEMPLATES[k]).read_bytes()
        if sha(before)!=d["templates"][k]["before"] or sha(p.read_bytes())!=d["templates"][k]["after"]:
            raise ValueError("Template edited since this release; refuse overwrite")
    for k,p in paths.items():
        tmp=p.with_name(p.name+".reading-revert")
        if tmp.exists() or tmp.is_symlink():raise ValueError("Temporary restore collision")
        shutil.copy2(backup/TEMPLATES[k],tmp)
        os.replace(tmp,p)
    if (app/"tmp").is_dir():(app/"tmp/restart.txt").touch()
    print("PHOTO_READING_PATHS_SAFE_ROLLBACK=yes",flush=True)

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("action",choices=("check","install","rollback"))
    cli.add_argument("--app",type=Path,default=APP)
    cli.add_argument("--content",type=Path)
    cli.add_argument("--backup",type=Path)
    a=cli.parse_args()
    if a.action=="rollback":
        if not a.backup:cli.error("--backup required")
        rollback(a.app,a.backup);return
    if not a.content:cli.error("--content required")
    rows,old=rows_and_older(a.content)
    if a.action=="check":
        print("PHOTO_READING_PATHS_ARTICLE_COUNT="+str(len(rows)),flush=True)
        print("PHOTO_READING_PATHS_PRIOR_ARTICLES="+str(len(old)),flush=True)
        return
    if not a.backup:cli.error("--backup required")
    install(a.app,a.content,a.backup)

if __name__=="__main__":main()
