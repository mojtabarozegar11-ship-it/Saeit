#!/usr/bin/env python3
"""Image-only enhancement for six personal-site enterprise collaboration offer cards.

Creates six unique AI-generated conceptual WebP assets; modifies only home.html
and posts.html of isolated personal V17, plus a new dedicated static folder.
No post, contact, navigation, SEO, payments, or other app modification.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, os, re, shutil, sys
from pathlib import Path

APP=Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
STATIC_FOLDER="personal_site/mojtaba_six_diverse_collaboration_photos_20261016"
CARD_MARK='id="mpw-enterprise-collaboration-brief-20261016"'
NEW_MARK='data-mpw-diverse-collab-photo="20261016"'
CARD_HEAD='<article style="padding:21px;background:#29251f;border:1px solid #ab895a;border-radius:12px">'
PROTECTED=(
'id="mpw-mojtaba-twenty-image-essays-20261016"',
'id="mpw-photoessay-reading-guides-20261016"',
'id="mpw-fifty-editorials-20261015"',
'id="mpw-vancouver-enterprise-20-index-20261016"',
'id="mpw-vancouver-enterprise-20-series2-index-20261016"',
)
FILES=(
"01-architecture-discovery.webp",
"02-b2b-logistics.webp",
"03-industrial-monitoring.webp",
"04-ai-knowledge-research.webp",
"05-ux-accessibility.webp",
"06-cloud-reliability.webp",
)
ALT=(
"Conceptual illustration of professionals reviewing an enterprise systems architecture",
"Conceptual illustration of an industrial warehouse supporting B2B trade",
"Conceptual illustration of engineers reading industrial monitoring dashboards",
"Conceptual illustration of a research team exploring AI knowledge systems",
"Conceptual illustration of a user-experience designer preparing interface layouts",
"Conceptual illustration of an engineer operating a data center",
)
def sha(b:bytes):return hashlib.sha256(b).hexdigest()
def safe_source(app:Path):
    if app.is_symlink() or not (app/"manage.py").is_file():raise ValueError("Separate personal V17 missing")
    root=app/"templates/personal_site/core"
    paths={k:root/(k+".html") for k in ("home","posts")}
    for path in paths.values():
        if not path.is_file() or path.is_symlink():raise ValueError("Unexpected personal template")
    return paths

def old_articles(app:Path,folder:Path):
    module=folder.parent/"scripts/mojtaba_twenty_photo_essays_safe_publish.py"
    if not module.is_file() or module.is_symlink():raise ValueError("Original protected articles module missing")
    spec=importlib.util.spec_from_file_location("originals",module)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    new=m.load_articles(folder);old=m.load_older(folder)
    if len(new)!=20 or len(old)!=73:raise ValueError("Original 93 articles not available")
    sys.path.insert(0,str(app))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    import django;django.setup()
    from django.db import connection
    from django.template import engines
    from core.models import Post
    if Post.objects.filter(slug__in=old,published=True).count()!=73:
        raise ValueError("73 earlier original articles missing")
    if Post.objects.filter(slug__in=[x["slug"] for x in new],published=True).count()!=20:
        raise ValueError("20 illustrated articles missing")
    return engines

def validate_images(pictures:Path):
    if pictures.is_symlink() or not pictures.is_dir():raise ValueError("Image payload unavailable")
    manifest=pictures/"manifest.json"
    if manifest.is_symlink() or not manifest.is_file():raise ValueError("Image attribution missing")
    data=json.loads(manifest.read_text(encoding="utf-8"))
    if len(data)!=6:raise ValueError("Exactly six image records required")
    images=[]
    hashes=set()
    for i,entry in enumerate(data):
        p=pictures/FILES[i]
        if p.is_symlink() or not p.is_file() or entry["number"]!=i+1 or entry["filename"]!=FILES[i] or entry["topic"] not in FILES[i]:
            raise ValueError("Wrong or missing unique image")
        if entry["origin"]!="AI-generated conceptual photography; not a documented client site or office":
            raise ValueError("Image-origin disclosure incorrect")
        b=p.read_bytes()
        if not 15000<len(b)<300000 or b[:4]!=b"RIFF" or b[8:12]!=b"WEBP":
            raise ValueError("Unexpected photo file format")
        if entry["sha256"]!=sha(b) or sha(b) in hashes:
            raise ValueError("Duplicate or modified image payload")
        hashes.add(sha(b));images.append((p,b))
    if sorted(p.name for p in pictures.iterdir())!=sorted(list(FILES)+["manifest.json"]):
        raise ValueError("Unlisted images in release payload")
    return images

def image_figure(i):
    name=FILES[i]
    src="{% static '"+STATIC_FOLDER+"/"+name+"' %}"
    return ('<figure '+NEW_MARK+' style="margin:0 0 15px;overflow:hidden;border-radius:9px;background:#161514">'
            '<img src="'+src+'" width="960" height="540" loading="lazy" decoding="async"'
            ' style="display:block;width:100%;height:auto;aspect-ratio:16/9;object-fit:cover"'
            ' alt="'+ALT[i]+'"/>'
            '<figcaption style="font:12px/1.55 system-ui,sans-serif;color:#d9bd93;padding:9px 6px 0">Technology and engineering illustration</figcaption>'
            '</figure>')

def patch(original):
    if NEW_MARK in original:raise ValueError("Diversified photos already present")
    for mark in PROTECTED:
        if original.count(mark)!=1:raise ValueError("Previous site section missing: "+mark)
    if original.count(CARD_MARK)!=1:raise ValueError("Six-offer block missing")
    section_start=original.index(CARD_MARK)
    section_end=original.find("</section>",section_start)
    if section_end<0:raise ValueError("Cannot bound the existing offer section")
    end=section_end+len("</section>")
    section=original[section_start:end]
    if section.count(CARD_HEAD)!=6:raise ValueError("Expected six distinct offer cards")
    for i in range(6):
        if section.count("PROPOSAL "+str(i+1).zfill(2))!=1:raise ValueError("Offer order or content changed")
    if "{% load static %}" not in original:
        # only add the template tag library, without changing any existing code or page content
        token="{% block content %}"
        if original.count(token)!=1:raise ValueError("Template content block ambiguous")
        original=original.replace(token,"{% load static %}\n"+token,1)
        section_start=original.index(CARD_MARK)
        section_end=original.find("</section>",section_start)
        end=section_end+len("</section>")
        section=original[section_start:end]
    modified=section
    for i in range(6):
        key=CARD_HEAD
        proposal="PROPOSAL "+str(i+1).zfill(2)
        needle=key+'<p style="color:#d5ad75;font:700 14px system-ui,sans-serif">'+proposal+'</p>'
        if modified.count(needle)!=1:raise ValueError("Card structure mismatch: "+proposal)
        replacement=key+image_figure(i)+'<p style="color:#d5ad75;font:700 14px system-ui,sans-serif">'+proposal+'</p>'
        modified=modified.replace(needle,replacement,1)
    if modified.count(NEW_MARK)!=6:raise ValueError("Wrong photo-card count")
    result=original[:section_start]+modified+original[end:]
    if result.count(NEW_MARK)!=6 or result.count(CARD_MARK)!=1:raise ValueError("Unexpected article modifications")
    return result

def install(app:Path,contents:Path,pictures:Path,backup:Path):
    images=validate_images(pictures)
    paths=safe_source(app)
    original={name:p.read_text(encoding="utf-8") for name,p in paths.items()}
    revised={name:patch(text) for name,text in original.items()}
    engines=old_articles(app,contents)
    for name,text in revised.items():
        engines["django"].engine.from_string(text)
        print("DIVERSE_PHOTOS_DJANGO_TEMPLATE_VALID="+name,flush=True)
    target=app/"static"/STATIC_FOLDER
    if target.exists() or target.is_symlink() or not (app/"static").is_dir():
        raise ValueError("Dedicated static folder conflict")
    if backup.exists() or backup.is_symlink():raise ValueError("Backup path conflict")
    backup.mkdir(parents=True,mode=0o700)
    checks={}
    for name,p in paths.items():
        (backup/p.name).write_text(original[name],encoding="utf-8")
        (backup/p.name).chmod(0o600)
        checks[name]={"before":sha(original[name].encode()),"after":sha(revised[name].encode())}
    meta={"templates":checks,"files":[{"name":p.name,"sha256":sha(data)} for p,data in images]}
    (backup/"manifest.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    (backup/"manifest.json").chmod(0o600)
    changed=[]
    try:
        target.mkdir(parents=True,mode=0o755)
        for photo,data in images:
            path=target/photo.name
            path.write_bytes(data)
            path.chmod(0o644)
        for name,p in paths.items():
            if sha(p.read_bytes())!=checks[name]["before"]:raise ValueError("Template changed in race")
            tmp=p.with_name(p.name+".diverse-webp-tmp")
            if tmp.exists() or tmp.is_symlink():raise ValueError("Staging template conflict")
            tmp.write_text(revised[name],encoding="utf-8")
            tmp.chmod(p.stat().st_mode&0o777)
            os.replace(tmp,p);changed.append(name)
    except BaseException:
        for name in changed:
            p=paths[name]
            if sha(p.read_bytes())==checks[name]["after"]:
                shutil.copy2(backup/p.name,p)
        if target.is_dir() and not target.is_symlink():
            if all((target/filename).is_file() and sha((target/filename).read_bytes())==sha(data) for (photo,data),filename in zip(images,FILES)):
                shutil.rmtree(target)
        raise
    if (app/"tmp").is_dir():(app/"tmp/restart.txt").touch()
    print("DIVERSE_PHOTOS_SIX_UNIQUE_SOURCE_IMAGES_INSTALLED=yes",flush=True)
    print("DIVERSE_PHOTOS_DATABASE_AND_ORIGINAL_GALLERY_UNMODIFIED=yes",flush=True)
    print("DIVERSE_PHOTOS_BACKUP="+str(backup),flush=True)

def rollback(app:Path,backup:Path):
    if backup.is_symlink() or not backup.is_dir():raise ValueError("Backup absent")
    meta=json.loads((backup/"manifest.json").read_text(encoding="utf-8"))
    paths=safe_source(app)
    for name,p in paths.items():
        original=(backup/p.name).read_bytes()
        if sha(original)!=meta["templates"][name]["before"] or sha(p.read_bytes())!=meta["templates"][name]["after"]:
            raise ValueError("Post-release template changes detected; refuse unsafe rollback")
    target=app/"static"/STATIC_FOLDER
    if target.is_symlink() or not target.is_dir():raise ValueError("Release photos missing")
    if sorted(x.name for x in target.iterdir())!=sorted(FILES):
        raise ValueError("Image directory contains additional content; refuse removal")
    for pic in meta["files"]:
        path=target/pic["name"]
        if not path.is_file() or sha(path.read_bytes())!=pic["sha256"]:
            raise ValueError("Release image changed, refuse unsafe deletion")
    for name,p in paths.items():
        tmp=p.with_name(p.name+".diverse-webp-revert")
        if tmp.exists() or tmp.is_symlink():raise ValueError("Backup restore conflict")
        shutil.copy2(backup/p.name,tmp)
        os.replace(tmp,p)
    shutil.rmtree(target)
    if (app/"tmp").is_dir():(app/"tmp/restart.txt").touch()
    print("DIVERSE_PHOTOS_SAFE_ROLLBACK_COMPLETE=yes",flush=True)

def main():
    a=argparse.ArgumentParser()
    a.add_argument("action",choices=("check","install","rollback"))
    a.add_argument("--app",type=Path,default=APP)
    a.add_argument("--content",type=Path)
    a.add_argument("--pictures",type=Path)
    a.add_argument("--backup",type=Path)
    x=a.parse_args()
    if x.action=="rollback":
        if not x.backup:a.error("Missing backup")
        rollback(x.app,x.backup);return
    if not x.content or not x.pictures:a.error("Need article manifests and six pictures")
    validate_images(x.pictures)
    if x.action=="check":
        print("DIVERSE_PHOTOS_SIX_VERIFIED_SOURCE_WEBP=yes",flush=True);return
    if not x.backup:a.error("Missing backup")
    install(x.app,x.content,x.pictures,x.backup)
if __name__=="__main__":main()
