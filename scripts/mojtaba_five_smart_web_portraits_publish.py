#!/usr/bin/env python3
"""Publish five original AI editorial portraits alongside five existing technical articles.

Independent personal V17 application only. No native Post or contact mutations.
Requires full original 93 articles, all protected reading/portfolio sections,
five hash-verified unique WebP photographs and exactly three template backups.
"""
from __future__ import annotations
import argparse, hashlib, html, importlib.util, json, os, re, shutil, sys, zipfile
from pathlib import Path

APP=Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
ASSET="personal_site/mojtaba_five_smart_web_portraits_20261016"
ARCHIVE="mojtaba_five_smart_web_portraits_20261016.zip"
ARCHIVE_HASH="d3e5bc59b017550046e9f77d9dbc844671d572e350bc315c35933340ded9389a"
SOURCE_CONTENT="mojtaba_five_smart_web_portrait_editorials_20261016.json"
MARK='id="mpw-five-smart-web-portraits-20261016"'
DETAIL_MARK='id="mpw-five-smart-web-portrait-article-20261016"'
TEMPLATES={"home":"home.html","posts":"posts.html","detail":"detail.html"}
KEEP=(
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
 'id="mpw-photoessay-reading-guides-20261016"',
 'id="mpw-enterprise-collaboration-brief-20261016"',
)
ALT=(
 "Professional portrait introducing research-led intelligent website strategy",
 "Technical presenter explaining modular enterprise website architecture",
 "Professional working through web design and enterprise data analytics",
 "Professional in a server environment introducing reliable cloud engineering",
 "Technology presenter exploring intelligent website project collaboration",
)
def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def source_module(staging:Path):
    p=staging/"scripts/mojtaba_twenty_photo_essays_safe_publish.py"
    if p.is_symlink() or not p.is_file():raise ValueError("Original essay publisher missing")
    spec=importlib.util.spec_from_file_location("originals93",p)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod
def article_data(staging:Path):
    p=staging/"content"/SOURCE_CONTENT
    if p.is_symlink() or not p.is_file():raise ValueError("Five matching editorial articles missing")
    d=json.loads(p.read_text(encoding="utf-8"))
    if d.get("version")!=1 or len(d.get("articles",[]))!=5:raise ValueError("Expected five essays")
    rows=d["articles"]
    seen=set()
    for n,row in enumerate(rows,1):
        if row.get("number")!=n or row.get("image")!=f"vancouver-smart-web-portrait-{n:02d}.webp":
            raise ValueError("Photo-to-article map changed")
        if not isinstance(row.get("slug"),str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)+",row["slug"]):
            raise ValueError("Invalid original article URL")
        if row["slug"] in seen:raise ValueError("Repeated linked article")
        seen.add(row["slug"])
        if len(row.get("paragraphs",[]))!=3 or len(" ".join(row["paragraphs"]).split())<160:
            raise ValueError("Need substantive scientific content")
        if len(row.get("title",""))<25 or len(row.get("excerpt",""))<45:
            raise ValueError("Incomplete distinct caption and introduction")
        for key in ("title","excerpt","label"):
            if "<" in row[key] or ">" in row[key]:raise ValueError("Unsafe author text")
        for para in row["paragraphs"]:
            if "<" in para or ">" in para:raise ValueError("Unsafe paragraph markup")
    return rows
def verify_zip(staging:Path):
    p=staging/"assets"/ARCHIVE
    if p.is_symlink() or not p.is_file() or sha(p.read_bytes())!=ARCHIVE_HASH:
        raise ValueError("Incorrect original five-photo archive digest")
    rows=article_data(staging)
    with zipfile.ZipFile(p) as z:
        desired={x["image"] for x in rows}|{"manifest.json"}
        if set(z.namelist())!=desired:raise ValueError("Unexpected files in archive")
        info=json.loads(z.read("manifest.json"))
        if len(info)!=5:raise ValueError("Five image records expected")
        hashes=set();out=[]
        for n,row in enumerate(rows):
            meta=info[n]
            if meta.get("number")!=n+1 or meta.get("filename")!=row["image"] or meta.get("slug")!=row["slug"]:
                raise ValueError("Image provenance or topic mismatch")
            data=z.read(row["image"])
            if not 25000<len(data)<500000 or data[:4]!=b"RIFF" or data[8:12]!=b"WEBP":
                raise ValueError("Invalid compressed visual file")
            digest=sha(data)
            if digest!=meta.get("sha256") or digest in hashes:
                raise ValueError("Repeated or corrupted visual")
            hashes.add(digest);out.append((row["image"],data,digest))
    return out
def original_slugs(staging:Path,rows):
    m=source_module(staging)
    last=m.load_articles(staging/"content")
    older=m.load_older(staging/"content")
    if len(last)!=20 or len(older)!=73 or len(set(older))!=73:
        raise ValueError("Old 93-post manifests incomplete")
    inventory=set(older)|{x["slug"] for x in last}
    if len(inventory)!=93 or not {x["slug"] for x in rows}<=inventory:
        raise ValueError("One matching original website article missing")
    return older,last
def templates(app:Path):
    if app.is_symlink() or not (app/"manage.py").is_file():
        raise ValueError("Only the independent personal V17 website is allowed")
    folder=app/"templates/personal_site/core"
    result={}
    for name,file in TEMPLATES.items():
        p=folder/file
        if p.is_symlink() or not p.is_file():raise ValueError("Protected template missing")
        result[name]=p
    return result
def image_source(row):
    return "{% static '"+ASSET+"/"+row["image"]+"' %}"
def figure(row):
    alt=ALT[row["number"]-1]
    return ('<figure style="margin:0;background:#171615;border-radius:12px;overflow:hidden;border:1px solid #987648">'
            '<img src="'+image_source(row)+'" width="900" height="1125" loading="lazy" decoding="async" '
            'alt="'+html.escape(alt,quote=True)+'" style="display:block;width:100%;height:auto;aspect-ratio:4/5;object-fit:cover"/>'
            '<figcaption style="padding:10px 14px;color:#ddc59d;font:13px/1.65 system-ui,sans-serif">'
            +html.escape(row["label"])+' · Original digital portrait illustration</figcaption></figure>')
def home_block(rows):
    lines=['<section '+MARK+' aria-labelledby="mpw-five-portraits-title" style="max-width:1200px;margin:44px auto;padding:clamp(20px,3vw,36px);background:#151413;color:#f3e6d3;border:2px solid #c7a16b;border-radius:16px">',
    '<h2 id="mpw-five-portraits-title" style="font:700 clamp(27px,3vw,37px)/1.3 Georgia,serif;color:#eecb92">Five Perspectives on Intelligent Website Engineering</h2>',
    '<p style="font:16px/1.8 system-ui,sans-serif">Explore five complementary technical ideas for intelligent commercial and industrial websites: discovery, modular architecture, analytical accuracy, resilient infrastructure and professional collaboration.</p>',
    '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,198px),1fr));gap:17px">']
    for row in rows:
        url="/mojtaba.roozegar/blog/"+row["slug"]+"/"
        lines.append('<article style="background:#2a2620;padding:11px;border-radius:11px;display:flex;flex-direction:column;gap:11px">'+figure(row)+
          '<h3 style="font:600 19px/1.4 Georgia,serif;color:#f5d49d;margin:0">'+html.escape(row["title"])+'</h3>'+
          '<p style="font:14px/1.7 system-ui,sans-serif;margin:0">'+html.escape(row["excerpt"])+'</p>'+
          '<a href="'+url+'" style="margin-top:auto;color:#f6d6a1;text-decoration:underline;text-underline-offset:3px">Read the illustrated technical analysis →</a></article>')
    lines.extend(['</div>','<p style="margin-top:25px;font:15px/1.8 system-ui,sans-serif">For project discussions, the <a style="color:#f4d5a2" href="/mojtaba.roozegar/contact/">existing contact page</a> is available. Each proposal is scoped to requirements and acceptance criteria.</p>','</section>'])
    return "\n".join(lines)
def detail_block(rows):
    lines=['{% if kind == "Article" %}']
    for n,row in enumerate(rows):
        lines.append(("{% if" if n==0 else "{% elif")+' item.slug == "'+row["slug"]+'" %}')
        lines.append('<section '+DETAIL_MARK+' aria-label="Related professional web research" style="max-width:1030px;margin:32px auto;padding:clamp(18px,3vw,28px);background:#1a1917;border:2px solid #bd9866;border-radius:14px;color:#f4e7d4"><div style="display:grid;grid-template-columns:minmax(190px,310px) minmax(0,1fr);gap:clamp(16px,3vw,32px);align-items:start">')
        lines.append('<div>'+figure(row)+'</div><div><h2 style="font:700 clamp(23px,2.8vw,32px)/1.3 Georgia,serif;color:#eecb92">'+html.escape(row["title"])+'</h2>')
        lines.append('<p style="font:16px/1.8 system-ui,sans-serif">'+html.escape(row["excerpt"])+'</p>')
        for para in row["paragraphs"]:
            lines.append('<p style="font:15px/1.8 system-ui,sans-serif">'+html.escape(para)+'</p>')
        lines.append('<p><a style="color:#f1d19a;text-decoration:underline" href="/mojtaba.roozegar/contact/">Discuss a scoped intelligent website project →</a></p></div></div></section>')
    lines.extend(['{% endif %}','{% endif %}'])
    return "\n".join(lines)
def patch(name,source,rows):
    if MARK in source or DETAIL_MARK in source:raise ValueError("Five images already installed")
    opening="{% block content %}"
    if source.count(opening)!=1:raise ValueError("Personal site's content block changed")
    start=source.index(opening)+len(opening);ending=source.find("{% endblock %}",start)
    if ending<0:raise ValueError("Expected end of content block missing")
    if name in ("home","posts"):
        for mark in KEEP:
            if source.count(mark)!=1:raise ValueError("Existing library section missing: "+mark)
        if source.count('data-mpw-diverse-collab-photo="20261016"')!=6:
            raise ValueError("Existing six nonduplicate enterprise visuals missing")
        if name=="home" and source.count('id="mpw-primary-personal-profile-20261016"')!=1:
            raise ValueError("Owner-selected profile photo not protected")
        extra=home_block(rows)
        if extra.count("Read the illustrated technical analysis")!=5:raise ValueError("Five links needed")
    elif name=="detail":
        if source.count('id="mpw-mojtaba-essay-cover-20261016"')!=20:
            raise ValueError("Existing twenty original personal portraits absent")
        if source.count('id="mpw-photoessay-related-20261016"')!=20:
            raise ValueError("Prior topic links missing")
        if source.count('id="mpw-enterprise-collaboration-contact-20261016"')!=20:
            raise ValueError("Prior collaboration links missing")
        extra=detail_block(rows)
        if extra.count(DETAIL_MARK)!=5:raise ValueError("Five detail images required")
    else:raise ValueError("Outside personal site scope")
    if "{% load static %}" not in source:
        source=source.replace(opening,"{% load static %}\n"+opening,1)
        start=source.index(opening)+len(opening);ending=source.find("{% endblock %}",start)
    return source[:ending]+"\n"+extra+"\n"+source[ending:]
def django_guards(app:Path,staging:Path,rows):
    older,illustrated=original_slugs(staging,rows)
    sys.path.insert(0,str(app))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    import django;django.setup()
    from django.template import engines
    from core.models import Post
    if Post.objects.filter(slug__in=older,published=True).count()!=73:
        raise ValueError("73 original articles missing")
    if Post.objects.filter(slug__in=[x["slug"] for x in illustrated],published=True).count()!=20:
        raise ValueError("20 earlier portrait articles missing")
    if Post.objects.filter(slug__in=[x["slug"] for x in rows],published=True).count()!=5:
        raise ValueError("Five selected technical articles missing")
    return engines
def install(app:Path,staging:Path,backup:Path):
    rows=article_data(staging);pics=verify_zip(staging)
    paths=templates(app)
    original={k:p.read_text(encoding="utf-8") for k,p in paths.items()}
    proposed={k:patch(k,v,rows) for k,v in original.items()}
    engines=django_guards(app,staging,rows)
    for k,text in proposed.items():
        engines["django"].engine.from_string(text)
        print("FIVE_PORTRAITS_TEMPLATE_COMPILES="+k,flush=True)
    target=app/"static"/ASSET
    if target.exists() or target.is_symlink() or not (app/"static").is_dir():
        raise ValueError("New static photo folder collides")
    if backup.is_symlink() or backup.exists():raise ValueError("Backup location already used")
    backup.mkdir(parents=True,mode=0o700)
    audit={"templates":{},"images":[{"name":name,"sha256":digest} for name,raw,digest in pics]}
    for k,p in paths.items():
        (backup/p.name).write_text(original[k],encoding="utf-8")
        (backup/p.name).chmod(0o600)
        audit["templates"][k]={"before":sha(original[k].encode()),"after":sha(proposed[k].encode())}
    (backup/"manifest.json").write_text(json.dumps(audit,indent=2),encoding="utf-8")
    (backup/"manifest.json").chmod(0o600)
    written=[]
    try:
        target.mkdir(parents=True,mode=0o755)
        for name,raw,digest in pics:
            p=target/name
            p.write_bytes(raw);p.chmod(0o644)
        for k,p in paths.items():
            if sha(p.read_bytes())!=audit["templates"][k]["before"]:
                raise ValueError("Original template modified during update")
            tmp=p.with_name(p.name+".five-web-portrait")
            if tmp.exists() or tmp.is_symlink():raise ValueError("Temp file collision")
            tmp.write_text(proposed[k],encoding="utf-8")
            tmp.chmod(p.stat().st_mode & 0o777)
            os.replace(tmp,p);written.append(k)
    except BaseException:
        for k in written:
            p=paths[k]
            if sha(p.read_bytes())==audit["templates"][k]["after"]:
                shutil.copy2(backup/p.name,p)
        if target.is_dir() and not target.is_symlink() and sorted(p.name for p in target.iterdir())==sorted(x[0] for x in pics):
            if all(sha((target/name).read_bytes())==digest for name,raw,digest in pics):
                shutil.rmtree(target)
        raise
    if (app/"tmp").is_dir():(app/"tmp/restart.txt").touch()
    print("FIVE_PORTRAITS_SOURCE_WEBP_AND_EDITORIALS_INSTALLED=yes",flush=True)
    print("FIVE_PORTRAITS_93_NATIVE_POSTS_UNMODIFIED=yes",flush=True)
    print("FIVE_PORTRAITS_BACKUP="+str(backup),flush=True)
def rollback(app:Path,backup:Path):
    if backup.is_symlink() or not backup.is_dir():raise ValueError("Backup unavailable")
    d=json.loads((backup/"manifest.json").read_text())
    paths=templates(app);target=app/"static"/ASSET
    for k,p in paths.items():
        original=(backup/p.name).read_bytes()
        if sha(original)!=d["templates"][k]["before"] or sha(p.read_bytes())!=d["templates"][k]["after"]:
            raise ValueError("Template edited by another operation; refuse overwrite")
    if target.is_symlink() or not target.is_dir() or sorted(p.name for p in target.iterdir())!=sorted(x["name"] for x in d["images"]):
        raise ValueError("New visual directory modified; refuse removal")
    for item in d["images"]:
        if sha((target/item["name"]).read_bytes())!=item["sha256"]:
            raise ValueError("Generated image changed after release")
    for k,p in paths.items():
        tmp=p.with_name(p.name+".five-web-rollback")
        if tmp.exists() or tmp.is_symlink():raise ValueError("Restore file collision")
        shutil.copy2(backup/p.name,tmp)
        os.replace(tmp,p)
    shutil.rmtree(target)
    if (app/"tmp").is_dir():(app/"tmp/restart.txt").touch()
    print("FIVE_PORTRAITS_SAFE_ROLLBACK_SUCCESS=yes",flush=True)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("check","install","rollback"))
    p.add_argument("--app",type=Path,default=APP)
    p.add_argument("--staging",type=Path)
    p.add_argument("--backup",type=Path)
    args=p.parse_args()
    if args.action=="rollback":
        if not args.backup:p.error("--backup required")
        rollback(args.app,args.backup);return
    if not args.staging:p.error("--staging required")
    rows=article_data(args.staging)
    pics=verify_zip(args.staging)
    original_slugs(args.staging,rows)
    if args.action=="check":
        print("FIVE_PORTRAITS_ZIP_DIGEST_AND_FIVE_UNIQUE_WEBP_VERIFIED=yes",flush=True)
        print("FIVE_PORTRAITS_93_OLD_ARTICLE_MANIFESTS_VERIFIED=yes",flush=True)
        return
    if not args.backup:p.error("--backup required")
    install(args.app,args.staging,args.backup)
if __name__=="__main__":main()
