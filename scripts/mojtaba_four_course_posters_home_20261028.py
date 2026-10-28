#!/usr/bin/env python3
"""Add four no-fake-portrait course posters to existing personal Django homepage.

One exact template only. NO modifications to main MojPlayWin, Zomorod Melal,
Django DBs, social credentials, unrelated templates, pictures or webserver config.
Backup original bytes and refuse blind rollbacks after concurrent owner changes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

LIVE_APP=Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
BACKUPS=Path("/home/zomorod2/.backups/mojtaba-personal-education-posters-20261028")
TEMPLATE=Path("templates/personal_site/core/home.html")
MARKER='id="mpw-four-course-posters-20261028"'
POSTERS=(
    ("business","دوره کسب‌وکار","برنامه‌ریزی، مدیریت، بازاریابی و فروش"),
    ("agriculture","دوره افزایش درآمد کشاورزی","بهره‌وری، مدیریت منابع و بازار محصول"),
    ("online-income","دوره آموزش کسب درآمد از اینترنت","مهارت‌های دیجیتال و تجارت آنلاین"),
    ("chatgpt","دوره تخصصی آموزش چت‌جی‌پی‌تی","پرامپت‌نویسی و کاربرد حرفه‌ای ChatGPT"),
)
SITE="/mojtaba.roozegar/"
HUB=SITE+"social-command/"

def sha(data):
    return hashlib.sha256(data).hexdigest()

def _safe_target(app):
    if app != LIVE_APP and os.environ.get("MPW_COURSE_POSTERS_TEST")!="1":
        raise RuntimeError("Only isolated personal site may be modified")
    if app.is_symlink() or not app.is_dir() or not (app/"manage.py").is_file():
        raise RuntimeError("Standalone personal Django app missing")
    target=app/TEMPLATE
    if target.is_symlink() or not target.is_file():
        raise RuntimeError("Approved personal homepage template missing")
    return target

def _run_id(value):
    if not re.fullmatch(r"[0-9]{8,25}",str(value)):
        raise RuntimeError("Invalid Actions release ID")
    return value

def section_html():
    posters=[]
    for slug,title,desc in POSTERS:
        svg=HUB+"posters/"+slug+".svg"
        detail=HUB+"courses/#"+slug
        posters.append(
            '<article class="mpw-course-home-card">'
            '<a href="'+detail+'" aria-label="آشنایی با '+title+'">'
            '<img src="'+svg+'" loading="lazy" decoding="async" width="900" height="1200" alt="'+
            title+'؛ پوستر طراحی گرافیکی بدون تصویر مدرس"></a>'
            '<div class="mpw-course-home-copy"><h3>'+title+'</h3>'
            '<p>'+desc+'</p>'
            '<a class="mpw-course-home-more" href="'+detail+'">جزئیات و سرفصل‌ها</a></div></article>'
        )
    css=r"""
<style id="mpw-four-course-posters-style-20261028">
#mpw-four-course-posters-20261028{max-width:1230px;margin:clamp(26px,4vw,52px) auto;
padding:clamp(15px,3vw,35px);background:linear-gradient(145deg,#121b19,#10191e);
border:1px solid #ab8b50;border-radius:18px;box-shadow:0 16px 48px #0006;box-sizing:border-box}
#mpw-four-course-posters-20261028 *{box-sizing:border-box}
#mpw-four-course-posters-20261028 .mpw-course-home-header{text-align:center;max-width:750px;margin:0 auto 25px}
#mpw-four-course-posters-20261028 .mpw-course-home-eyebrow{color:#d8bd82;
font-size:12px;letter-spacing:.15em;text-transform:uppercase}
#mpw-four-course-posters-20261028 h2{color:#f7dbad;font-size:clamp(25px,3.3vw,40px);margin:10px 0}
#mpw-four-course-posters-20261028 .mpw-course-home-header p{color:#e6dccd;font-size:15px;line-height:1.85}
#mpw-four-course-posters-20261028 .mpw-course-home-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:15px}
#mpw-four-course-posters-20261028 .mpw-course-home-card{min-width:0;border:1px solid #725d3f;
border-radius:13px;overflow:hidden;background:#1d2925}
#mpw-four-course-posters-20261028 .mpw-course-home-card img{width:100%;height:auto;aspect-ratio:3/4;
object-fit:cover;display:block}
#mpw-four-course-posters-20261028 .mpw-course-home-copy{padding:14px;line-height:1.7}
#mpw-four-course-posters-20261028 h3{font-size:clamp(16px,1.6vw,21px);margin:0 0 7px;color:#f5d79e}
#mpw-four-course-posters-20261028 .mpw-course-home-copy p{color:#ebe4d8;font-size:13px;margin:0 0 11px}
#mpw-four-course-posters-20261028 a.mpw-course-home-more{display:inline-block;background:#e3c17d;
padding:7px 11px;border-radius:8px;color:#1d251d!important;text-decoration:none;font-weight:700}
#mpw-four-course-posters-20261028 a:focus-visible{outline:3px solid white;outline-offset:3px}
#mpw-four-course-posters-20261028 .mpw-course-home-note{font-size:12px;color:#d6c7b0;text-align:center;margin:23px 0 0}
@media(max-width:990px){#mpw-four-course-posters-20261028 .mpw-course-home-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:540px){#mpw-four-course-posters-20261028{margin:17px 10px;padding:12px}
#mpw-four-course-posters-20261028 .mpw-course-home-grid{gap:10px}
#mpw-four-course-posters-20261028 .mpw-course-home-copy{padding:10px}
#mpw-four-course-posters-20261028 h3{font-size:15px}
#mpw-four-course-posters-20261028 .mpw-course-home-copy p{font-size:12px}}
</style>"""
    return (
        '\n<section '+MARKER+' dir="rtl" lang="fa" aria-labelledby="mpw-four-courses-title">'
        +css+
        '<div class="mpw-course-home-header"><div class="mpw-course-home-eyebrow">'
        'MOJTABA ROOZEGAR · EDUCATION</div>'
        '<h2 id="mpw-four-courses-title">چهار دوره برای توسعه مهارت و کسب‌وکار</h2>'
        '<p>با چهار مسیر یادگیری در کسب‌وکار، اقتصاد کشاورزی، درآمد اینترنتی و استفاده حرفه‌ای '
        'از ChatGPT آشنا شوید.</p></div>'
        '<div class="mpw-course-home-grid">'+''.join(posters)+'</div>'
        '<p class="mpw-course-home-note">این بخش معرفی دوره‌هاست؛ تاریخ شروع، شهریه و '
        'ثبت‌نام هنوز اعلام نشده‌اند. هیچ تضمین درآمدی ارائه نمی‌شود.</p></section>\n'
    )

def patch(current):
    if current.count(MARKER):
        raise RuntimeError("Four-course section already installed; abort duplicate")
    start="{% block content %}"
    end="{% endblock %}"
    if current.count(start)!=1:
        raise RuntimeError("Personal content template insert landmark missing/ambiguous")
    begin=current.index(start)+len(start)
    index=current.find(end,begin)
    if index<0:
        raise RuntimeError("Cannot locate end of personal homepage content")
    out=current[:index]+section_html()+current[index:]
    if out.count(MARKER)!=1 or any(out.count('src="'+HUB+"posters/"+slug+".svg")!=1
                                      for slug,_,_ in POSTERS):
        raise RuntimeError("Four-poster injection shape invalid")
    if out[:begin]!=current[:begin] or out[index+len(section_html()):]!=current[index:]:
        raise RuntimeError("Non-additive template edit detected")
    return out

def _write_atomic(path,data, *, mode=None):
    fd,tmp=tempfile.mkstemp(prefix=".mpw-courses-",dir=path.parent)
    try:
        os.fchmod(fd,stat.S_IMODE(path.stat().st_mode) if mode is None else mode)
        with os.fdopen(fd,"wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def check(app):
    target=_safe_target(app)
    raw=target.read_bytes()
    updated=patch(raw.decode("utf-8")).encode("utf-8")
    return {"status":"ready","before_sha":sha(raw),"after_sha":sha(updated),
            "posters":len(POSTERS),"target":"isolated_personal_home_only"}

def install(app,backup,run_id):
    target=_safe_target(app)
    run_id=_run_id(run_id)
    old=target.read_bytes()
    updated=patch(old.decode("utf-8")).encode("utf-8")
    if not backup.is_absolute() or not backup.parent.is_dir() or backup.parent.is_symlink():
        raise RuntimeError("Private backup root untrusted")
    if backup.exists() and (backup.is_symlink() or backup.stat().st_mode & 0o077):
        raise RuntimeError("Private backup permissions unsafe")
    if not backup.exists():
        backup.mkdir(mode=0o700)
    folder=backup/run_id
    if folder.exists() or folder.is_symlink():
        raise RuntimeError("Duplicate poster deployment ID")
    folder.mkdir(mode=0o700)
    orig=folder/"original_home.html"
    orig.write_bytes(old)
    os.chmod(orig,0o600)
    meta={"kind":"four_course_home_only","target":str(target),
          "before_sha":sha(old),"after_sha":sha(updated)}
    path=folder/"manifest.json"
    path.write_text(json.dumps(meta,sort_keys=True),encoding="utf-8")
    os.chmod(path,0o600)
    if sha(target.read_bytes())!=meta["before_sha"]:
        raise RuntimeError("Concurrent home-template modification")
    _write_atomic(target,updated)
    if sha(target.read_bytes())!=meta["after_sha"]:
        raise RuntimeError("Poster home template hash mismatch")
    return {"status":"installed","posters":4,"backup":str(folder),
            "other_site_files_touched":False,"database_preserved":True}

def rollback(app,backup,run_id):
    target=_safe_target(app)
    folder=backup/_run_id(run_id)
    m=folder/"manifest.json"
    o=folder/"original_home.html"
    if folder.is_symlink() or m.is_symlink() or o.is_symlink() or not o.is_file():
        raise RuntimeError("Verified poster rollback unavailable")
    meta=json.loads(m.read_text(encoding="utf-8"))
    old=o.read_bytes()
    if meta.get("kind")!="four_course_home_only" or meta.get("target")!=str(target):
        raise RuntimeError("Poster rollback target mismatch")
    if sha(old)!=meta["before_sha"] or sha(target.read_bytes())!=meta["after_sha"]:
        raise RuntimeError("Homepage changed; refuse unsafe rollback")
    _write_atomic(target,old)
    if sha(target.read_bytes())!=meta["before_sha"]:
        raise RuntimeError("Poster homepage rollback failed")
    return {"status":"restored","database_preserved":True,"only_personal_home":True}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=("check","install","rollback"))
    parser.add_argument("--run-id",default="")
    parser.add_argument("--test-app-root",default="")
    parser.add_argument("--backup-root",default=str(BACKUPS))
    args=parser.parse_args()
    if args.test_app_root and os.environ.get("MPW_COURSE_POSTERS_TEST")!="1":
        parser.error("Non-production app roots forbidden")
    app=Path(args.test_app_root) if args.test_app_root else LIVE_APP
    backup=Path(args.backup_root)
    try:
        if args.action=="check": result=check(app)
        elif args.action=="install": result=install(app,backup,args.run_id)
        else: result=rollback(app,backup,args.run_id)
        print(json.dumps(result,sort_keys=True,ensure_ascii=False))
    except (OSError,RuntimeError,UnicodeError,ValueError) as exc:
        print(json.dumps({"status":"blocked","reason":str(exc)},ensure_ascii=False))
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
