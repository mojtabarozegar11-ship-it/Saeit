#!/usr/bin/env python3
"""Additive publication of 20 original enterprise web articles and 20 editorial SVG diagrams.

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
STATIC_FOLDER = "personal_site/enterprise_web_diagrams_20261016"
INDEX_MARK = 'id="mpw-vancouver-enterprise-20-index-20261016"'
DETAIL_MARK = 'id="mpw-vancouver-enterprise-illustration-20261016"'
PROTECTED = (
  'id="mpw-new-originals-20261015-b"',
  'id="mpw-fifty-editorials-20261015"',
  'id="mpw-academic-profile-20261016"',
  'id="mpw-personal-expanded-20261016"',
  'id="mpw-journal-longform-index-20261016"',
  'id="mpw-journal-advanced-index-20261016"',
  'id="mpw-website-ten-index-20261016"',
  'id="mpw-vancouver-collab-photo-ten-20261016"',
)
OLD_FILES = (
  "mojtaba_seven_full_independent_journal_20261016.json",
  "mojtaba_six_advanced_journal_articles_20261016.json",
  "mojtaba_ten_advanced_website_engineering_20261016.json",
  "mojtaba_vancouver_collab_part_a_20261016.json",
  "mojtaba_vancouver_collab_part_b_20261016.json",
)

def hashbytes(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def image_name(slug:str)->str:
    return STATIC_FOLDER+"/"+slug+".svg"

def load_articles(folder:Path):
    out=[]
    for k in (1,2,3,4):
        p=folder/("mojtaba_vancouver_enterprise_web_part_"+str(k)+"_20261016.json")
        if p.is_symlink() or not p.is_file():
            raise ValueError("Required content manifest unavailable")
        data=json.loads(p.read_text(encoding="utf-8"))
        if data.get("version")!=1 or data.get("language")!="en" or len(data.get("articles",[]))!=5:
            raise ValueError("Each part must provide five English articles")
        out+=data["articles"]
    slugs=set();titles=set()
    for x in out:
        if set(x)!={"slug","title","excerpt","content","diagram"}:
            raise ValueError("Article schema unexpected")
        slug=x["slug"]
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)+",slug):
            raise ValueError("Unsafe article slug")
        if slug in slugs or x["title"] in titles:
            raise ValueError("Duplicate article")
        slugs.add(slug);titles.add(x["title"])
        if len(slug)>175 or not 20<len(x["title"])<=180 or not 40<len(x["excerpt"])<=350:
            raise ValueError("Django field constraints violated")
        if len(x["content"].split())<330 or len(x["diagram"])!=4 or any(not isinstance(t,str) or not 3<=len(t)<=22 for t in x["diagram"]):
            raise ValueError("Article must contain substantive content and four visual labels")
        if any("<script" in x[k].lower() or "<iframe" in x[k].lower() for k in ("content","title","excerpt")):
            raise ValueError("HTML not approved inside article")
    if len(out)!=20:
        raise ValueError("Exactly twenty distinct articles required")
    return out

def load_older(folder:Path):
    slugs=[]
    for name in OLD_FILES:
        file=folder/name
        if not file.is_file() or file.is_symlink():raise ValueError("Original post manifest missing: "+name)
        slugs.extend(x["slug"] for x in json.loads(file.read_text(encoding="utf-8"))["articles"])
    if len(slugs)!=33 or len(set(slugs))!=33:
        raise ValueError("Old 33 independent articles must be unique")
    return slugs

def svg_diagram(row:dict,position:int)->bytes:
    esc=html.escape
    title=row["title"]
    words=title.split()
    lines=[];current=[]
    for word in words:
        if len(" ".join(current+[word]))>43 and current:
            lines.append(" ".join(current));current=[word]
        else: current.append(word)
    if current:lines.append(" ".join(current))
    if len(lines)>3:
        raise ValueError("Cannot fit title in vector cover")
    coords=[64,351,638,925]
    tiles=[]
    for i,(x,label) in enumerate(zip(coords,row["diagram"])):
        tiles.append('<rect x="'+str(x)+'" y="421" width="210" height="112" rx="16" fill="#292821" stroke="#c3a068" stroke-width="2"/>')
        tiles.append('<text x="'+str(x+20)+'" y="458" fill="#d2b482" font-size="20" font-family="sans-serif">0'+str(i+1)+'</text>')
        tiles.append('<text x="'+str(x+105)+'" y="499" fill="#fff1db" text-anchor="middle" font-size="20" font-family="sans-serif">'+esc(label)+'</text>')
        if i<3:
            tiles.append('<path d="M '+str(x+217)+' 476 l 61 0 m -14 -13 l 14 13 -14 13" stroke="#ad965c" stroke-width="3" fill="none"/>')
    headers="".join('<text x="68" y="'+str(252+j*57)+'" fill="#f9e5b8" font-size="37" font-weight="700" font-family="sans-serif">'+esc(line)+'</text>' for j,line in enumerate(lines))
    data='''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 675" role="img" aria-labelledby="title desc">
<title id="title">'''+esc(title)+'''</title>
<desc id="desc">An original four-stage conceptual diagram for a possible industrial and commercial website collaboration; not evidence of an existing client project.</desc>
<defs><linearGradient id="gold" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#b6904c"/><stop offset="1" stop-color="#e4cf99"/></linearGradient><linearGradient id="dark" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#10171a"/><stop offset="1" stop-color="#23201b"/></linearGradient></defs>
<rect width="1200" height="675" fill="url(#dark)"/>
<rect x="16" y="16" width="1168" height="643" rx="18" fill="none" stroke="url(#gold)" stroke-width="8"/>
<rect x="44" y="43" width="1112" height="71" fill="#272821" rx="12"/>
<text x="66" y="87" fill="#e3c188" font-size="23" font-family="sans-serif" font-weight="700">VANCOUVER | ENTERPRISE SMART WEB</text>
<text x="1139" y="87" text-anchor="end" fill="#c8b58e" font-size="22" font-family="sans-serif">RESEARCH &amp; DESIGN / '''+str(position).zfill(2)+'''</text>
<text x="68" y="171" fill="#bcaa85" font-size="19" font-family="sans-serif">A proposed architecture and collaboration pathway</text>
'''+headers+'''
<line x1="63" y1="382" x2="1137" y2="382" stroke="#8b754e" stroke-width="2"/>
'''+''.join(tiles)+'''
<text x="64" y="585" fill="#a99b80" font-size="18" font-family="sans-serif">Original educational illustration • No claimed Vancouver office or completed contract</text>
<text x="64" y="617" fill="#e5c98e" font-size="19" font-family="sans-serif">Mojtaba Roozegar • Available to discuss scoped enterprise collaboration</text>
</svg>'''
    if "<script" in data or "<foreignObject" in data or "http:" in data.replace("http://www.w3.org/2000/svg",""):
        raise ValueError("SVG safety constraints")
    return data.encode("utf-8")

def index_block(rows):
    parts=['{% load static %}', '<section '+INDEX_MARK+' aria-label="Enterprise smart website collaboration in Vancouver" style="background:#161615;color:#f5ead8;border:4px solid #c6a36b;border-radius:16px;padding:clamp(20px,3vw,36px);margin:42px auto;max-width:1190px">',
           '<h2 style="font:700 clamp(26px,3vw,39px)/1.25 Georgia,serif;color:#e6c68b">Vancouver Enterprise Smart Web — 20 Collaboration Articles</h2>',
           '<p style="font:16px/1.8 system-ui,sans-serif">I am open to discussing smart industrial and commercial websites, enterprise portals, secure integration, AI and digital transformation with Vancouver organizations. These articles propose possible pilot projects; they do not claim existing clients, a Canadian office or work authorization.</p>',
           '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:17px">']
    for row in rows:
        path=image_name(row["slug"])
        image="{% static '"+path+"' %}"
        url="/mojtaba.roozegar/blog/"+row["slug"]+"/"
        parts.append('<article style="border:2px solid #a8895d;border-radius:11px;background:#292622;overflow:hidden"><a href="'+html.escape(url,quote=True)+'" style="color:#f5deb0;text-decoration:none"><img src="'+image+'" width="1200" height="675" loading="lazy" decoding="async" alt="'+html.escape("Original four-stage engineering diagram: "+row["title"],quote=True)+'" style="width:100%;height:auto;aspect-ratio:16/9;display:block"><div style="padding:17px"><h3 style="font:600 21px/1.45 Georgia,serif">'+html.escape(row["title"])+'</h3><p style="color:#e6dccd;font:15px/1.7 system-ui,sans-serif">'+html.escape(row["excerpt"])+'</p></div></a></article>')
    parts.append('</div></section>')
    return "\n".join(parts)

def detail_block(rows):
    content=['{% load static %}','{% if kind == "Article" %}']
    for i,row in enumerate(rows):
        condition="{% if" if i==0 else "{% elif"
        content.append(condition+' item.slug == "'+row["slug"]+'" %}')
        file="{% static '"+image_name(row["slug"])+"' %}"
        content.append('<figure '+DETAIL_MARK+' style="border:3px solid #b9955c;background:#171717;padding:12px;max-width:1100px;margin:24px auto;border-radius:11px"><img src="'+file+'" alt="'+html.escape("Technical editorial diagram: "+row["title"],quote=True)+'" width="1200" height="675" loading="eager" decoding="async" style="width:100%;height:auto;display:block"><figcaption style="color:#e4cca1;font:14px/1.6 system-ui,sans-serif">Original conceptual diagram for a possible Vancouver enterprise project, not a record of a completed client deployment.</figcaption></figure>')
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

def install(app,folder,backup):
    rows=load_articles(folder)
    older=load_older(folder)
    before=templates(app)
    Post,transaction,engines,target=prepare(app)
    if target.exists() or target.is_symlink():raise ValueError("Reserved diagram folder exists")
    if backup.exists() or backup.is_symlink():raise ValueError("Backup collision")
    if Post.objects.filter(slug__in=[a["slug"] for a in rows]).exists():raise ValueError("New slug collides with existing post")
    if Post.objects.filter(slug__in=older,published=True).count()!=33:raise ValueError("Previous 33 posts must remain published")
    after={k:patch(k,v,rows) for k,v in before.items()}
    for key,proposal in after.items():
        engines["django"].engine.from_string(proposal)
        print("ENTERPRISE_20_TEMPLATE_PREFLIGHT="+key,flush=True)
    graphics={a["slug"]:svg_diagram(a,i+1) for i,a in enumerate(rows)}
    backup.mkdir(parents=True,mode=0o700)
    template_meta={}
    for key,filename in TEMPLATES.items():
        (backup/filename).write_text(before[key],encoding="utf-8")
        (backup/filename).chmod(0o600)
        template_meta[key]={"before":hashbytes(before[key].encode()),"after":hashbytes(after[key].encode())}
    manifest={"schema":1,"templates":template_meta,"new_posts":{a["slug"]:{"title":a["title"],"body_sha":hashbytes(a["content"].encode()),"svg_sha":hashbytes(graphics[a["slug"]])} for a in rows}}
    (backup/"state.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    changed=[]
    try:
        target.mkdir(parents=True,mode=0o755)
        for slug,data in graphics.items():
            p=target/(slug+".svg")
            p.write_bytes(data);p.chmod(0o644)
            if hashbytes(p.read_bytes())!=hashbytes(data):raise ValueError("Diagram write failed")
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
            p=target/(slug+".svg")
            if p.is_file() and hashbytes(p.read_bytes())==hashbytes(b):p.unlink()
        if target.is_dir():
            try:target.rmdir()
            except OSError:pass
        raise
    if (app/"tmp").is_dir():(app/"tmp/restart.txt").touch()
    print("ENTERPRISE_20_NATIVE_ARTICLES_INSERTED=yes",flush=True)
    print("ENTERPRISE_20_ORIGINAL_SVG_IMAGES_INSTALLED=yes",flush=True)
    print("ENTERPRISE_OLD_33_ARTICLES_PRESERVED=yes",flush=True)
    print("ENTERPRISE_20_BACKUP="+str(backup),flush=True)

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
        obj=posts[slug];file=target/(slug+".svg")
        if obj.title!=record["title"] or hashbytes(obj.content.encode())!=record["body_sha"] or obj.cover.name:
            raise ValueError("New article changed since install")
        if not file.is_file() or hashbytes(file.read_bytes())!=record["svg_sha"]:
            raise ValueError("New diagram changed since install")
    with transaction.atomic():
        Post.objects.filter(slug__in=state["new_posts"]).delete()
        for key,filename in TEMPLATES.items():
            dest=app/"templates/personal_site/core"/filename
            temp=dest.with_name(filename+".enterprise-revert")
            if temp.exists():raise ValueError("Restore staging collision")
            shutil.copy2(backup/filename,temp)
            os.replace(temp,dest)
    for slug in state["new_posts"]:
        (target/(slug+".svg")).unlink()
    try:target.rmdir()
    except OSError:pass
    if (app/"tmp").is_dir():(app/"tmp/restart.txt").touch()
    print("ENTERPRISE_20_SAFE_ROLLBACK_SUCCESS=yes",flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("check","install","rollback"))
    p.add_argument("--app",type=Path,default=APP)
    p.add_argument("--content",type=Path)
    p.add_argument("--backup",type=Path)
    args=p.parse_args()
    if args.action=="rollback":
        if not args.backup:p.error("Need backup")
        rollback(args.app,args.backup);return
    if not args.content:p.error("Need content")
    rows=load_articles(args.content)
    if args.action=="check":
        print("ENTERPRISE_20_MANUSCRIPTS_READY="+str(len(rows)),flush=True);return
    if not args.backup:p.error("Need backup")
    install(args.app,args.content,args.backup)

if __name__=="__main__":main()
