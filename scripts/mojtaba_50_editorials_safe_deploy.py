#!/usr/bin/env python3
"""Safe, additive 50-piece owner-personal-site content installer.

Only touches 9 allowlisted Django templates in the existing independent V17
personal application; no changes to database, media, payments, URLs or sites.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import html
import json
import os
from pathlib import Path
import shutil

APP=Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
PAGE_FILES={
  "home":"home.html",
  "about":"about.html",
  "projects":"projects.html",
  "posts":"posts.html",
  "gallery":"gallery.html",
  "resume":"resume.html",
  "activities":"activities.html",
  "memories":"memories.html",
  "stories":"stories.html",
}
COUNTS={"home":5,"about":5,"projects":7,"posts":12,"gallery":3,"resume":5,"activities":6,"memories":4,"stories":3}
PAGE_LABELS={
  "home":("From experience to ideas","Five guiding perspectives on useful research, technology, and collaboration"),
  "about":("Five more ways to know the person","Personal perspective, work values, and professional directions"),
  "projects":("Seven initiatives and working concepts","A transparent collection of potential projects, not a claim of completed launches"),
  "posts":("Twelve new research-minded notes","Original educational essays with practical reasoning and explicit limitations"),
  "gallery":("Understanding the photographs","Three editorial perspectives on truthful visual presentation"),
  "resume":("Five professional approaches","Methods and skills that connect management, research, trade, hospitality, and technology"),
  "activities":("Six areas of ongoing interest","How meaningful work can be structured, tested, and improved"),
  "memories":("Reflections on continuity","Four personal reflections without invented dated experiences"),
  "stories":("Three original short stories","Fictional vignettes about curiosity, evidence, and craft; not biographical accounts"),
}
MARKER='id="mpw-fifty-editorials-20261015"'
PHOTO_MARKER='id="mpw-new-originals-20261015-b"'
CSS="""<style>
.mpw-fifty{box-sizing:border-box;margin:38px auto;max-width:1180px;width:100%;clear:both;padding:32px 26px;background:#f8f4ed;border:1px solid #d8cbb4;border-radius:10px;color:#263342}
.mpw-fifty *{box-sizing:border-box}
.mpw-fifty .mpw-overline{display:block;font:700 12px/1.5 system-ui,sans-serif;letter-spacing:.15em;text-transform:uppercase;color:#806335;margin:0 0 12px}
.mpw-fifty h2{color:#1a2938;font:400 clamp(28px,4vw,40px)/1.22 Georgia,'Times New Roman',serif;margin:0 0 12px}
.mpw-fifty .mpw-fifty-intro{font:400 clamp(15px,1.55vw,18px)/1.75 system-ui,sans-serif;color:#505c67;max-width:850px;margin:0 0 24px}
.mpw-fifty .mpw-article-index{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 22px}
.mpw-fifty .mpw-article-index a{display:inline-block;padding:7px 11px;border:1px solid #c7ad83;border-radius:4px;background:#fff9ee;color:#4c402e;text-decoration:none;font-size:13px}
.mpw-fifty .mpw-article-index a:focus-visible,.mpw-fifty a:focus-visible{outline:3px solid #a17b40;outline-offset:2px}
.mpw-fifty .mpw-article-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}
.mpw-fifty article{padding:23px;background:#fff;border:1px solid #e2d8c8;border-top:3px solid #ad8c58;border-radius:6px;min-width:0;box-shadow:0 7px 16px rgba(33,45,57,.035)}
.mpw-fifty .mpw-article-id{display:block;color:#906d35;text-transform:uppercase;font:700 11px/1.3 system-ui,sans-serif;letter-spacing:.1em;margin:0 0 10px}
.mpw-fifty h3{font:400 clamp(21px,2.5vw,27px)/1.28 Georgia,'Times New Roman',serif;color:#223447;margin:0 0 14px}
.mpw-fifty article p{font:400 15px/1.86 system-ui,sans-serif;color:#495667;margin:0 0 12px}
.mpw-fifty article p:last-child{margin-bottom:0}
.mpw-fifty .mpw-disclaimer{font:400 13px/1.7 system-ui,sans-serif;color:#5c625f;margin:23px 0 0}
@media(max-width:720px){.mpw-fifty{padding:18px 13px;margin:24px auto}.mpw-fifty .mpw-article-grid{grid-template-columns:minmax(0,1fr);gap:14px}.mpw-fifty article{padding:18px}}
</style>"""

def load_content(path:Path)->dict:
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing vetted editorial source JSON")
    data=json.loads(path.read_text(encoding="utf-8"))
    if data.get("version")!=1 or data.get("total")!=50 or data.get("language")!="en":
        raise ValueError("Unexpected editorial source metadata")
    rows=data.get("entries")
    if not isinstance(rows,list) or len(rows)!=50:
        raise ValueError("Expected exactly fifty editorial content records")
    keys=set()
    titles=set()
    counts=Counter()
    for i,row in enumerate(rows,1):
        if not isinstance(row,dict) or set(row)!={"id","page","type","title","lead","body"}:
            raise ValueError("Unexpected editorial entry shape "+str(i))
        if row["id"]!="MPW-"+f"{i:03d}":
            raise ValueError("Unexpected editorial numbering")
        if row["page"] not in PAGE_FILES:
            raise ValueError("Editorial page outside allowlist")
        if row["type"] not in {"Perspective","Personal reflection","Professional outlook","Project concept","Research note","Visual editorial","Professional method","Current focus","Original fiction"}:
            raise ValueError("Unknown editorial category")
        if any(not isinstance(row[k],str) or not row[k].strip() for k in ("id","page","type","title","lead","body")):
            raise ValueError("Empty or malformed editorial field")
        if len((row["lead"]+" "+row["body"]).split())<65:
            raise ValueError("Editorial piece too short "+row["id"])
        if len(row["title"])>115 or len(row["lead"])>1100 or len(row["body"])>1800:
            raise ValueError("Unreasonable editorial content length")
        if row["title"] in titles or row["id"] in keys:
            raise ValueError("Repeated title or ID")
        if row["page"]=="stories" and row["type"]!="Original fiction":
            raise ValueError("Unlabelled fiction prohibited")
        titles.add(row["title"]);keys.add(row["id"]);counts[row["page"]]+=1
    if dict(counts)!=COUNTS:
        raise ValueError("Incorrect nine-page editorial distribution "+str(counts))
    return data

def section(page:str,source:dict)->str:
    if page not in PAGE_FILES:raise ValueError("Page not allowlisted")
    title,intro=PAGE_LABELS[page]
    pieces=[e for e in source["entries"] if e["page"]==page]
    if len(pieces)!=COUNTS[page]:raise ValueError("Page count differs from manifest")
    out=['<section id="mpw-fifty-editorials-20261015" class="mpw-fifty" aria-label="Additional original editorial content">',
         CSS,
         '<span class="mpw-overline">The personal editorial collection · '+str(len(pieces))+' entries</span>',
         '<h2>'+html.escape(title)+'</h2><p class="mpw-fifty-intro">'+html.escape(intro)+'</p>']
    if page=="posts":
        out.append('<nav aria-label="Jump to research note" class="mpw-article-index">')
        for row in pieces:
            out.append('<a href="#'+row["id"]+'">'+html.escape(row["title"])+'</a>')
        out.append('</nav>')
    out.append('<div class="mpw-article-grid">')
    for row in pieces:
        out.append('<article id="'+row["id"]+'" aria-labelledby="heading-'+row["id"]+'">'
                   '<span class="mpw-article-id">'+html.escape(row["type"])+' · '+row["id"]+'</span>'
                   '<h3 id="heading-'+row["id"]+'">'+html.escape(row["title"])+'</h3>'
                   '<p>'+html.escape(row["lead"])+'</p>'
                   '<p>'+html.escape(row["body"])+'</p></article>')
    out.append('</div>')
    out.append('<p class="mpw-disclaimer">'
               +("These are clearly fictional pieces, not verified personal events." if page=="stories"
                 else "The views and concepts here are educational or editorial, not claims of completed projects, regulated advice, or independently validated results.")
               +'</p></section>')
    return "\n".join(out)

def patch_template(page:str,original:str,source:dict)->str:
    if page not in PAGE_FILES:raise ValueError("Page not allowed")
    if MARKER in original:raise ValueError("Fifty-piece section already published: "+page)
    if original.count(PHOTO_MARKER)!=1:
        raise ValueError("Previously verified ten-photo gallery must remain intact: "+page)
    anchor="{% block content %}"
    if original.count(anchor)!=1:raise ValueError("Cannot safely identify Django content block")
    # Insert just before the first endblock after the unique content block, exactly
    # as the previously successful, owner-approved image deployment did.
    start=original.index(anchor)+len(anchor)
    end=original.find("{% endblock %}",start)
    if end<0:raise ValueError("Missing Django content block end")
    new=original[:end]+"\n"+section(page,source)+"\n"+original[end:]
    if new.count(MARKER)!=1 or new.count(PHOTO_MARKER)!=1:
        raise ValueError("Non-additive installation refused")
    if new.count("<article id=\"MPW-")!=COUNTS[page]:
        raise ValueError("Missing individual editorial content blocks")
    return new

def template_sources(app:Path)->dict[str,str]:
    if app.is_symlink() or not (app/"manage.py").is_file():
        raise ValueError("Independent personal V17 installation not verified")
    base=app/"templates/personal_site/core"
    result={}
    for page,filename in PAGE_FILES.items():
        f=base/filename
        if not f.is_file() or f.is_symlink() or f.resolve()!=f:
            raise ValueError("Unsafe or missing template "+filename)
        result[page]=f.read_text(encoding="utf-8")
    return result

def run(args)->None:
    app=args.app
    backup=args.backup
    if args.mode=="rollback":
        if not backup or not backup.is_dir() or backup.is_symlink():
            raise ValueError("Missing protected backup directory")
        if app.is_symlink() or not (app/"manage.py").is_file():
            raise ValueError("Unsafe personal app path")
        for name in PAGE_FILES.values():
            src=backup/name
            if not src.is_file() or src.is_symlink():
                raise ValueError("Incomplete backup; refusing partial rollback "+name)
        for name in PAGE_FILES.values():
            dest=app/"templates/personal_site/core"/name
            temporary=dest.with_name(dest.name+".fifty-restore")
            shutil.copy2(backup/name,temporary)
            os.replace(temporary,dest)
        if (app/"tmp").is_dir(): (app/"tmp/restart.txt").touch()
        print("EDITORIAL_50_ROLLBACK_ALL_NINE_SUCCESS=yes",flush=True)
        return
    content=load_content(args.content)
    originals=template_sources(app)
    proposals={p:patch_template(p,src,content) for p,src in originals.items()}
    print("EDITORIAL_50_VALIDATED=yes",flush=True)
    print("EDITORIAL_50_ALL_NINE_PROPOSED=yes",flush=True)
    if args.mode=="check":return
    if not backup:raise ValueError("Backup path required")
    if backup.exists():raise ValueError("Refusing to overwrite prior backup")
    backup.mkdir(parents=True,mode=0o700)
    for page,filename in PAGE_FILES.items():
        file=backup/filename
        file.write_text(originals[page],encoding="utf-8")
        file.chmod(0o600)
        print("BACKUP_50="+filename+" sha256="+hashlib.sha256(originals[page].encode()).hexdigest(),flush=True)
    if len(list(backup.glob("*.html")))!=9:
        raise ValueError("Backup must contain nine complete templates")
    updated=[]
    try:
        for page,filename in PAGE_FILES.items():
            dest=app/"templates/personal_site/core"/filename
            temporary=dest.with_name(dest.name+".fifty-install")
            if temporary.exists():raise ValueError("Unexpected temporary template file")
            temporary.write_text(proposals[page],encoding="utf-8")
            os.chmod(temporary,dest.stat().st_mode & 0o777)
            os.replace(temporary,dest)
            updated.append(page)
    except BaseException:
        for page in updated:
            shutil.copy2(backup/PAGE_FILES[page],app/"templates/personal_site/core"/PAGE_FILES[page])
        raise
    if (app/"tmp").is_dir(): (app/"tmp/restart.txt").touch()
    print("EDITORIAL_50_NINE_PAGES_INSTALLED=yes",flush=True)
    print("BACKUP_PATH="+str(backup),flush=True)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=["check","install","rollback"])
    parser.add_argument("--content",type=Path)
    parser.add_argument("--app",type=Path,default=APP)
    parser.add_argument("--backup",type=Path)
    opts=parser.parse_args()
    if opts.mode!="rollback" and not opts.content:
        parser.error("--content required")
    run(opts)
