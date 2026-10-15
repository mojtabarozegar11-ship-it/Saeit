#!/usr/bin/env python3
"""Safely publish self-reported education and career biography on 5 personal V17 pages.
Additive templates only. All existing 50 articles, 20 owner photos and routes preserved.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import shutil

APP=Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
PAGES={"home":"home.html","about":"about.html","resume":"resume.html","activities":"activities.html","posts":"posts.html"}
MARKER='id="mpw-academic-profile-20261016"'
PREVIOUS_EDITORIAL='id="mpw-fifty-editorials-20261015"'
PREVIOUS_PHOTOS='id="mpw-new-originals-20261015-b"'
CSS="""<style>
.mpw-academic{max-width:1180px;width:100%;box-sizing:border-box;clear:both;margin:36px auto;padding:32px;border:1px solid #c2aa7d;border-radius:10px;background:linear-gradient(130deg,#f8f4eb,#fffdf9);color:#1e3040}
.mpw-academic *{box-sizing:border-box}
.mpw-academic .mpw-kicker{font:700 12px/1.4 system-ui,sans-serif;letter-spacing:.16em;color:#876938;text-transform:uppercase}
.mpw-academic h2{font:400 clamp(28px,3.5vw,42px)/1.24 Georgia,'Times New Roman',serif;color:#16283a;margin:11px 0 16px}
.mpw-academic p{font:400 16px/1.85 system-ui,sans-serif;color:#465665;margin:0 0 16px;max-width:910px}
.mpw-academic .mpw-intro{font-size:clamp(17px,1.7vw,21px);line-height:1.75;color:#253a4e}
.mpw-academic .mpw-facts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:22px 0}
.mpw-academic .mpw-fact{border:1px solid #e5d8c1;border-left:3px solid #bd9560;padding:15px;background:#fff;border-radius:4px;min-width:0}
.mpw-academic .mpw-fact dt{color:#80653f;font:700 12px/1.5 system-ui,sans-serif;text-transform:uppercase;letter-spacing:.065em;margin:0 0 6px}
.mpw-academic .mpw-fact dd{margin:0;color:#233647;font:600 15px/1.6 system-ui,sans-serif;overflow-wrap:anywhere}
.mpw-academic .mpw-note{font:400 12px/1.7 system-ui,sans-serif;color:#5e6973;margin:19px 0 0}
.mpw-academic a{color:#425b84;text-decoration:underline}
@media(max-width:760px){.mpw-academic{padding:20px 14px;margin:24px auto}.mpw-academic .mpw-facts{grid-template-columns:1fr}.mpw-academic p{font-size:15px}}
</style>"""

def read_content(path:Path)->dict:
    if not path.is_file() or path.is_symlink():raise ValueError("Education content source missing")
    data=json.loads(path.read_text(encoding="utf-8"))
    if data.get("version")!=1 or data.get("marker")!="mpw-academic-profile-20261016" or data.get("language")!="en":
        raise ValueError("Wrong education content version")
    if set(data.get("pages",{}))!=set(PAGES):raise ValueError("Incorrect allowlisted page set")
    identity=data.get("identity",{})
    for label,expect in {"degree":"PhD in Agricultural Economics","university":"Universiti Putra Malaysia (UPM)","specialization":"Production Economics and Farm Management"}.items():
        if identity.get(label)!=expect:raise ValueError("Essential academic fact missing: "+label)
    for page,record in data["pages"].items():
        if set(record)!={"kicker","title","intro","paragraphs","facts","note"}:raise ValueError("Unexpected section fields")
        if len(record["paragraphs"]) not in range(2,7):raise ValueError("Incorrect amount of prose: "+page)
        if len(record["facts"]) not in range(3,8):raise ValueError("Missing academic facts: "+page)
        for key in ("kicker","title","intro","note"):
            if not isinstance(record[key],str) or not record[key].strip():raise ValueError("Empty field")
        for p in record["paragraphs"]:
            if not isinstance(p,str) or len(p)<110:raise ValueError("Biography paragraph too short")
        for fact in record["facts"]:
            if not isinstance(fact,list) or len(fact)!=2 or not all(isinstance(x,str) and x.strip() for x in fact):
                raise ValueError("Malformed credential card")
    return data

def render_section(page:str,data:dict)->str:
    if page not in PAGES:raise ValueError("Not allowed")
    part=data["pages"][page]
    out=['<section id="mpw-academic-profile-20261016" class="mpw-academic" aria-label="Education and professional biography">',
         CSS,
         '<span class="mpw-kicker">'+html.escape(part["kicker"])+'</span>',
         '<h2>'+html.escape(part["title"])+'</h2>',
         '<p class="mpw-intro">'+html.escape(part["intro"])+'</p>',
         '<dl class="mpw-facts">']
    for name,val in part["facts"]:
        out.append('<div class="mpw-fact"><dt>'+html.escape(name)+'</dt><dd>'+html.escape(val)+'</dd></div>')
    out.append('</dl>')
    for p in part["paragraphs"]:
        out.append('<p>'+html.escape(p)+'</p>')
    out.append('<p class="mpw-note">'+html.escape(part["note"])+'</p>')
    out.append('</section>')
    return "\n".join(out)

def patch(page:str,original:str,data:dict)->str:
    if page not in PAGES:raise ValueError("Page not allowed")
    if MARKER in original:raise ValueError("Academic biography already exists")
    if original.count(PREVIOUS_EDITORIAL)!=1 or original.count(PREVIOUS_PHOTOS)!=1:
        raise ValueError("Previously published 50 articles and owner photos must remain intact")
    start="{% block content %}"
    if original.count(start)!=1:raise ValueError("Cannot unambiguously locate Django content")
    startidx=original.index(start)+len(start)
    end=original.find("{% endblock %}",startidx)
    if end<0:raise ValueError("Missing Django block end")
    out=original[:end]+"\n"+render_section(page,data)+"\n"+original[end:]
    if out.count(MARKER)!=1 or out.count(PREVIOUS_EDITORIAL)!=1 or out.count(PREVIOUS_PHOTOS)!=1:
        raise ValueError("Nonadditive operation refused")
    return out

def get_templates(app:Path)->dict[str,str]:
    if app.is_symlink() or not (app/"manage.py").is_file():
        raise ValueError("Personal Django V17 not found")
    base=app/"templates/personal_site/core"
    result={}
    for page,name in PAGES.items():
        f=base/name
        if not f.is_file() or f.is_symlink() or f.resolve()!=f:
            raise ValueError("Template path not safe: "+name)
        result[page]=f.read_text(encoding="utf-8")
    return result

def main(args)->None:
    app=args.app
    backup=args.backup
    if args.mode=="rollback":
        if not backup or not backup.is_dir() or backup.is_symlink():raise ValueError("Missing backup directory")
        if app.is_symlink() or not (app/"manage.py").is_file():raise ValueError("Invalid personal Django directory")
        for name in PAGES.values():
            if not (backup/name).is_file() or (backup/name).is_symlink():raise ValueError("Backup incomplete")
        for name in PAGES.values():
            dest=app/"templates/personal_site/core"/name
            tmp=dest.with_name(dest.name+".academic-restore")
            shutil.copy2(backup/name,tmp)
            os.replace(tmp,dest)
        if (app/"tmp").is_dir():(app/"tmp/restart.txt").touch()
        print("ACADEMIC_PROFILE_ROLLBACK_5_PAGES_SUCCESS=yes",flush=True)
        return
    data=read_content(args.content)
    old=get_templates(app)
    new={p:patch(p,html,data) for p,html in old.items()}
    print("ACADEMIC_PROFILE_PRECHECK_5_PAGES=yes",flush=True)
    if args.mode=="check":return
    if not backup:raise ValueError("Backup required")
    if backup.exists():raise ValueError("Cannot overwrite previous backup")
    backup.mkdir(parents=True,mode=0o700)
    for page,name in PAGES.items():
        f=backup/name
        f.write_text(old[page],encoding="utf-8")
        f.chmod(0o600)
        print("BACKUP_PAGE="+name+" SHA256="+hashlib.sha256(old[page].encode()).hexdigest(),flush=True)
    if len(list(backup.glob("*.html")))!=5:raise ValueError("Incomplete protected backup")
    changed=[]
    try:
        for page,name in PAGES.items():
            path=app/"templates/personal_site/core"/name
            tmp=path.with_name(path.name+".academic-update")
            if tmp.exists():raise ValueError("Temporary path already exists")
            tmp.write_text(new[page],encoding="utf-8")
            os.chmod(tmp,path.stat().st_mode & 0o777)
            os.replace(tmp,path)
            changed.append(page)
    except BaseException:
        for page in changed:
            shutil.copy2(backup/PAGES[page],app/"templates/personal_site/core"/PAGES[page])
        raise
    if (app/"tmp").is_dir():(app/"tmp/restart.txt").touch()
    print("ACADEMIC_PROFILE_5_PAGES_INSTALLED=yes",flush=True)
    print("ACADEMIC_PROFILE_BACKUP="+str(backup),flush=True)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=["check","install","rollback"])
    parser.add_argument("--content",type=Path)
    parser.add_argument("--app",type=Path,default=APP)
    parser.add_argument("--backup",type=Path)
    args=parser.parse_args()
    if args.mode!="rollback" and args.content is None:parser.error("--content required")
    main(args)
