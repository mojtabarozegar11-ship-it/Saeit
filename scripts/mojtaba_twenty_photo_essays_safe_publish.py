#!/usr/bin/env python3
"""Additive publication of 20 additional distinct enterprise web articles and 20 editorial SVG diagrams.

Only independent Mojtaba V17 Django personal-site templates and native Post records.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import os
import re
import shutil
import sys
from pathlib import Path

APP = Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
TEMPLATES = {"home":"home.html","posts":"posts.html","detail":"detail.html"}
STATIC_FOLDER = "personal_site/mojtaba_personal_image_essays_20261016"
INDEX_MARK = 'id="mpw-mojtaba-twenty-image-essays-20261016"'
DETAIL_MARK = 'id="mpw-mojtaba-essay-cover-20261016"'
PROTECTED = (
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
)
OLD_FILES = (
  "mojtaba_seven_full_independent_journal_20261016.json",
  "mojtaba_six_advanced_journal_articles_20261016.json",
  "mojtaba_ten_advanced_website_engineering_20261016.json",
  "mojtaba_vancouver_collab_part_a_20261016.json",
  "mojtaba_vancouver_collab_part_b_20261016.json",
  "mojtaba_vancouver_enterprise_web_part_1_20261016.json",
  "mojtaba_vancouver_enterprise_web_part_2_20261016.json",
  "mojtaba_vancouver_enterprise_web_part_3_20261016.json",
  "mojtaba_vancouver_enterprise_web_part_4_20261016.json",
  "mojtaba_vancouver_enterprise_web_series2_part_1_20261016.json",
  "mojtaba_vancouver_enterprise_web_series2_part_2_20261016.json",
  "mojtaba_vancouver_enterprise_web_series2_part_3_20261016.json",
  "mojtaba_vancouver_enterprise_web_series2_part_4_20261016.json",
)

def hashbytes(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def image_name(slug:str)->str:
    return STATIC_FOLDER+"/"+slug+".webp"

def load_articles(folder:Path):
    results=[]
    for n in range(1,21,2):
        p=folder/("mojtaba_twenty_photo_essays_"+str(n).zfill(2)+"_"+str(n+1).zfill(2)+".json")
        if p.is_symlink() or not p.is_file():raise ValueError("Missing two-essay manuscript")
        d=json.loads(p.read_text(encoding="utf-8"))
        if d.get("version")!=1 or len(d.get("articles",[]))!=2:
            raise ValueError("Each manuscript must contain exactly two essays")
        results.extend(d["articles"])
    names=set();pictures=set()
    for item in results:
        if set(item)!={"slug","title","excerpt","content","photo_index","source_kind"}:
            raise ValueError("Incorrect essay fields")
        slug=item["slug"]
        if not isinstance(slug,str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)+",slug):
            raise ValueError("Invalid slug")
        if slug in names or item["photo_index"] in pictures:
            raise ValueError("Duplicate essay or photo index")
        names.add(slug);pictures.add(item["photo_index"])
        if not 1<=item["photo_index"]<=20:
            raise ValueError("Invalid photograph number")
        if item["source_kind"]!=("owner_supplied" if item["photo_index"]<=10 else "generated_illustration"):
            raise ValueError("Wrong photo attribution kind")
        if not 20<len(item["title"])<=180 or not 35<len(item["excerpt"])<=350 or len(item["content"].split())<265:
            raise ValueError("Essay lacks substantive content or exceeds model field constraints")
        if any("<script" in item[k].lower() or "<iframe" in item[k].lower() for k in ("title","excerpt","content")):
            raise ValueError("Unsafe markup")
    if len(results)!=20 or pictures!=set(range(1,21)):
        raise ValueError("Exactly 20 unique essays matched to 20 distinct images required")
    return results

def load_older(folder:Path):
    slugs=[]
    for name in OLD_FILES:
        file=folder/name
        if not file.is_file() or file.is_symlink():raise ValueError("Original post manifest missing: "+name)
        slugs.extend(x["slug"] for x in json.loads(file.read_text(encoding="utf-8"))["articles"])
    if len(slugs)!=73 or len(set(slugs))!=73:
        raise ValueError("Old 73 independent articles must be unique")
    return slugs

def photo_binary(row:dict,pictures:Path)->bytes:
    if pictures.is_symlink() or not pictures.is_dir():raise ValueError("Photo staging directory invalid")
    p=pictures/("photo_"+str(row["photo_index"]).zfill(2)+".webp")
    if p.is_symlink() or not p.is_file():raise ValueError("Exact matching photograph absent: "+str(row["photo_index"]))
    raw=p.read_bytes()
    if len(raw)<4000 or len(raw)>2000000 or raw[:4]!=b"RIFF" or raw[8:12]!=b"WEBP":
        raise ValueError("Corrupt or unexpected personal WebP image")
    recordfile=pictures/"manifest.json"
    if recordfile.is_symlink() or not recordfile.is_file():raise ValueError("Image provenance manifest missing")
    records=json.loads(recordfile.read_text(encoding="utf-8"))
    if len(records)!=20:raise ValueError("Unexpected photo manifest count")
    index=row["photo_index"]
    record=next((x for x in records if x.get("number")==index),None)
    expected_kind="owner_supplied" if index<=10 else "AI_generated_illustration"
    if record is None or record.get("name")!=p.name or record.get("source_type")!=expected_kind or record.get("sha256")!=hashbytes(raw):
        raise ValueError("Photograph source and content checksum mismatch")
    return raw

def index_block(rows):
    parts=['{% load static %}', '<section '+INDEX_MARK+' aria-label="Enterprise smart website collaboration in Vancouver" style="background:#161615;color:#f5ead8;border:4px solid #c6a36b;border-radius:16px;padding:clamp(20px,3vw,36px);margin:42px auto;max-width:1190px">',
           '<h2 style="font:700 clamp(26px,3vw,39px)/1.25 Georgia,serif;color:#e6c68b">20 Photo Essays: Professional Profile and Smart Website Collaboration</h2>',
           '<p style="font:16px/1.8 system-ui,sans-serif">Ten owner-supplied personal photographs and ten conceptual technology illustrations accompany twenty practical essays on evidence-led business websites, research, design, cybersecurity, AI and cooperation. Images are editorial, not documentation of completed Canadian contracts.</p>',
           '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:17px">']
    for row in rows:
        path=image_name(row["slug"])
        image="{% static '"+path+"' %}"
        url="/mojtaba.roozegar/blog/"+row["slug"]+"/"
        parts.append('<article style="border:2px solid #a8895d;border-radius:11px;background:#292622;overflow:hidden"><a href="'+html.escape(url,quote=True)+'" style="color:#f5deb0;text-decoration:none"><img src="'+image+'" width="640" height="360" loading="lazy" decoding="async" alt="'+html.escape("Editorial image accompanying: "+row["title"],quote=True)+'" style="width:100%;height:auto;aspect-ratio:16/9;display:block"><div style="padding:17px"><h3 style="font:600 21px/1.45 Georgia,serif">'+html.escape(row["title"])+'</h3><p style="color:#e6dccd;font:15px/1.7 system-ui,sans-serif">'+html.escape(row["excerpt"])+'</p></div></a></article>')
    parts.append('</div></section>')
    return "\n".join(parts)

def detail_block(rows):
    content=['{% load static %}','{% if kind == "Article" %}']
    for i,row in enumerate(rows):
        condition="{% if" if i==0 else "{% elif"
        content.append(condition+' item.slug == "'+row["slug"]+'" %}')
        file="{% static '"+image_name(row["slug"])+"' %}"
        content.append('<figure '+DETAIL_MARK+' style="border:3px solid #b9955c;background:#171717;padding:12px;max-width:1100px;margin:24px auto;border-radius:11px"><img src="'+file+'" alt="'+html.escape("Essay illustration: "+row["title"],quote=True)+'" width="640" height="360" loading="eager" decoding="async" style="width:100%;height:auto;display:block"><figcaption style="color:#e4cca1;font:14px/1.6 system-ui,sans-serif">Personal portrait or illustrative digital artwork supplied for this essay. The image is not proof of a Vancouver office, professional engagement or completed enterprise project.</figcaption></figure>')
    content.extend(['{% endif %}','{% endif %}'])
    return "\n".join(content)

def templates(app):
    if app.is_symlink() or not (app/"manage.py").is_file():raise ValueError("Unexpected personal app")
    root=app/"templates/personal_site/core"
    result={}
    for name,filename in TEMPLATES.items():
        p=root/filename
        if p.is_symlink() or not p.is_file():raise ValueError("Unexpected original template")
        result[name]=p.read_text(encoding="utf-8")
    return result

def patch(name,original,rows):
    block="{% block content %}"
    if original.count(block)!=1:raise ValueError("Missing or duplicate content block")
    if (INDEX_MARK if name!="detail" else DETAIL_MARK) in original:
        raise ValueError("Enterprise articles already inserted")
    if name in ("home","posts"):
        for marker in PROTECTED:
            if original.count(marker)!=1:raise ValueError("Preserved personal content marker missing: "+marker)
        start=original.index(block)+len(block)
        end=original.find("{% endblock %}",start)
        if end<0:raise ValueError("Unterminated original content block")
        output=original[:end]+"\n"+index_block(rows)+"\n"+original[end:]
        if output.count(INDEX_MARK)!=1:raise ValueError("Index insertion mismatch")
        return output
    if name=="detail":
        if "{{ item.title" not in original:raise ValueError("Unknown native detail template")
        i=original.index(block)+len(block)
        out=original[:i]+"\n"+detail_block(rows)+"\n"+original[i:]
        if out.count(DETAIL_MARK)!=20:raise ValueError("All twenty detail images required")
        return out
    raise ValueError("Disallowed template")

def prepare(app):
    sys.path.insert(0,str(app))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    import django;django.setup()
    from django.conf import settings
    from django.db import transaction
    from django.template import engines
    from core.models import Post
    if not str(settings.STATIC_URL).startswith("/mojtaba.roozegar/assets/"):
        raise ValueError("Expected live static delivery route unavailable")
    target=app/"static"/STATIC_FOLDER
    if not (app/"static").is_dir() or (app/"static").is_symlink():raise ValueError("Static source root invalid")
    return Post,transaction,engines,target

def safe_backup_write(file:Path,text:str):
    temp=file.with_name(file.name+".enterprise-new")
    if temp.exists() or temp.is_symlink():raise ValueError("Temporary template collision")
    temp.write_text(text,encoding="utf-8")
    temp.chmod(file.stat().st_mode & 0o777)
    os.replace(temp,file)

def install(app,folder,backup,pictures):
    rows=load_articles(folder)
    older=load_older(folder)
    before=templates(app)
    Post,transaction,engines,target=prepare(app)
    if target.exists() or target.is_symlink():raise ValueError("Dedicated portrait archive folder already exists")
    if backup.exists() or backup.is_symlink():raise ValueError("Backup collision")
    if Post.objects.filter(slug__in=[a["slug"] for a in rows]).exists():raise ValueError("New slug collides with existing post")
    if Post.objects.filter(slug__in=older,published=True).count()!=73:raise ValueError("Previous 73 posts must remain published")
    after={k:patch(k,v,rows) for k,v in before.items()}
    for key,proposal in after.items():
        engines["django"].engine.from_string(proposal)
        print("PERSONAL_PHOTO20_TEMPLATE_PREFLIGHT="+key,flush=True)
    graphics={a["slug"]:photo_binary(a,pictures) for a in rows}
    backup.mkdir(parents=True,mode=0o700)
    template_meta={}
    for key,filename in TEMPLATES.items():
        (backup/filename).write_text(before[key],encoding="utf-8")
        (backup/filename).chmod(0o600)
        template_meta[key]={"before":hashbytes(before[key].encode()),"after":hashbytes(after[key].encode())}
    manifest={"schema":1,"templates":template_meta,"new_posts":{a["slug"]:{"title":a["title"],"body_sha":hashbytes(a["content"].encode()),"image_sha":hashbytes(graphics[a["slug"]])} for a in rows}}
    (backup/"state.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    changed=[]
    try:
        target.mkdir(parents=True,mode=0o755)
        for slug,data in graphics.items():
            p=target/(slug+".webp")
            p.write_bytes(data);p.chmod(0o644)
            if hashbytes(p.read_bytes())!=hashbytes(data):raise ValueError("Photo media copy failed")
        with transaction.atomic():
            if Post.objects.filter(slug__in=[a["slug"] for a in rows]).exists():raise ValueError("Race inserting new articles")
            for row in rows:
                Post.objects.create(title=row["title"],slug=row["slug"],excerpt=row["excerpt"],content=row["content"],published=True)
            for key,filename in TEMPLATES.items():
                if before[key]==after[key]:continue
                file=app/"templates/personal_site/core"/filename
                if hashbytes(file.read_bytes())!=template_meta[key]["before"]:
                    raise ValueError("Template changed concurrently")
                safe_backup_write(file,after[key])
                changed.append(key)
    except BaseException:
        for key in changed:
            filename=TEMPLATES[key]
            original=app/"templates/personal_site/core"/filename
            if hashbytes(original.read_bytes())==template_meta[key]["after"]:
                shutil.copy2(backup/filename,original)
        for slug,b in graphics.items():
            p=target/(slug+".webp")
            if p.is_file() and hashbytes(p.read_bytes())==hashbytes(b):p.unlink()
        if target.is_dir():
            try:target.rmdir()
            except OSError:pass
        raise
    if (app/"tmp").is_dir():(app/"tmp/restart.txt").touch()
    print("PERSONAL_PHOTO20_ARTICLES_INSERTED=yes",flush=True)
    print("PERSONAL_PHOTO20_MATCHED_WEBP_IMAGES_INSTALLED=yes",flush=True)
    print("PERSONAL_PHOTO20_OLD_73_ARTICLES_PRESERVED=yes",flush=True)
    print("PERSONAL_PHOTO20_BACKUP="+str(backup),flush=True)

def rollback(app,backup):
    Post,transaction,engines,target=prepare(app)
    state=json.loads((backup/"state.json").read_text(encoding="utf-8"))
    now=templates(app)
    for key in TEMPLATES:
        ref=state["templates"][key]
        if hashbytes(now[key].encode())!=ref["after"] or hashbytes((backup/TEMPLATES[key]).read_bytes())!=ref["before"]:
            raise ValueError("Template changed since install: do not overwrite")
    posts={p.slug:p for p in Post.objects.filter(slug__in=state["new_posts"])}
    if len(posts)!=20:raise ValueError("Some new posts changed since deployment")
    for slug,record in state["new_posts"].items():
        obj=posts[slug];file=target/(slug+".webp")
        if obj.title!=record["title"] or hashbytes(obj.content.encode())!=record["body_sha"] or obj.cover.name:
            raise ValueError("New article changed since install")
        if not file.is_file() or hashbytes(file.read_bytes())!=record["image_sha"]:
            raise ValueError("New photograph changed since install")
    with transaction.atomic():
        Post.objects.filter(slug__in=state["new_posts"]).delete()
        for key,filename in TEMPLATES.items():
            dest=app/"templates/personal_site/core"/filename
            temp=dest.with_name(filename+".enterprise-revert")
            if temp.exists():raise ValueError("Restore staging collision")
            shutil.copy2(backup/filename,temp)
            os.replace(temp,dest)
    for slug in state["new_posts"]:
        (target/(slug+".webp")).unlink()
    try:target.rmdir()
    except OSError:pass
    if (app/"tmp").is_dir():(app/"tmp/restart.txt").touch()
    print("PERSONAL_PHOTO20_SAFE_ROLLBACK_SUCCESS=yes",flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("check","install","rollback"))
    p.add_argument("--app",type=Path,default=APP)
    p.add_argument("--content",type=Path)
    p.add_argument("--backup",type=Path)
    p.add_argument("--pictures",type=Path)
    args=p.parse_args()
    if args.action=="rollback":
        if not args.backup:p.error("Need backup")
        rollback(args.app,args.backup);return
    if not args.content:p.error("Need content")
    rows=load_articles(args.content)
    if args.action=="check":
        print("PERSONAL_PHOTO20_MANUSCRIPTS_READY="+str(len(rows)),flush=True);return
    if not args.backup:p.error("Need backup")
    if not args.pictures:p.error("Need photos")
    install(args.app,args.content,args.backup,args.pictures)

if __name__=="__main__":main()
