#!/usr/bin/env python3
"""Guarded change of the prominent personal profile picture (home + about).

Only the owner's separate /mojtaba.roozegar/ Django V17 app is eligible.
Never edit existing gallery images, site roots, Post records, or payment flows.
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil
from pathlib import Path

APP=Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
STATIC_FOLDER="personal_site/official_profile_20261016"
MARK="id=\"mpw-primary-personal-profile-20261016\""
TEMPLATES={"home":"home.html","about":"about.html"}
IMAGES={
"portrait.webp":"482cad022c1739a464d17f0e023c69fcd6971d72bc67881f8ec24218bd2d8e41",
"avatar.webp":"16969b7fb6b2d5dd7288b53a1000006abd521b05deb350a1cfcec2eed346ebf1",
}
ORIGINAL_SHA="fa1923539c59fa55578787407169ad2dee4aaad2883dac0360eda19eb095a675"
def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def targets(app:Path):
    if app.is_symlink() or not (app/"manage.py").is_file():raise ValueError("Independent personal V17 app missing")
    root=app/"templates/personal_site/core"
    result={name:root/file for name,file in TEMPLATES.items()}
    for p in result.values():
        if p.is_symlink() or not p.is_file():raise ValueError("Unexpected or linked personal template")
    return result
def image_bytes(pics:Path):
    if pics.is_symlink() or not pics.is_dir():raise ValueError("Photo source staging is missing")
    manifest=pics/"manifest.json"
    if manifest.is_symlink() or not manifest.is_file():raise ValueError("Photo manifest missing")
    m=json.loads(manifest.read_text(encoding="utf-8"))
    if m.get("source_uploaded_photo_sha256")!="50493b0e83f475b7f54405570e0cbce210bf6eb9e2520f024e316e999779e04a":
        raise ValueError("Unexpected original uploaded photo")
    if {x.get("name") for x in m.get("files",[])}!=set(IMAGES):
        raise ValueError("Wrong photo manifest contents")
    if sorted(x.name for x in pics.iterdir())!=["avatar.webp","manifest.json","portrait.webp"]:
        raise ValueError("Extra or missing images")
    assets={}
    for name,digest in IMAGES.items():
        path=pics/name
        if path.is_symlink() or not path.is_file():raise ValueError("Unexpected photo symlink")
        b=path.read_bytes()
        if not 8000<len(b)<300000 or b[:4]!=b"RIFF" or b[8:12]!=b"WEBP" or sha(b)!=digest:
            raise ValueError("Uploaded photo SHA or encoding mismatch")
        record=next((x for x in m["files"] if x["name"]==name),None)
        if not record or record["sha256"]!=digest or record["bytes"]!=len(b):
            raise ValueError("Photo manifest checksum mismatch")
        assets[name]=b
    return assets
def profile_section(which):
    if which=="home":
        file="portrait.webp"
        width,height=850,1131
        circular="border-radius:18px;max-height:520px;object-fit:cover;object-position:center 20%;"
    elif which=="about":
        file="avatar.webp"
        width,height=600,600
        circular="border-radius:50%;max-height:300px;object-fit:cover;object-position:center;"
    else:raise ValueError("Unknown personal page")
    return (
      '<section '+MARK+' aria-label="Mojtaba Roozegar primary professional profile photograph" '
      'style="max-width:1050px;margin:24px auto 34px;padding:clamp(18px,3vw,30px);background:#181715;'
      'border:2px solid #c8a36a;border-radius:16px;display:flex;flex-wrap:wrap;align-items:center;'
      'justify-content:center;gap:clamp(18px,3vw,36px);color:#f4e6d3">'
      '<figure style="margin:0;flex:0 1 345px;min-width:min(100%,235px);">'
      '<img src="{% static '+"'"+STATIC_FOLDER+"/"+file+"'"+' %}"'
      ' alt="Mojtaba Roozegar – primary professional profile portrait, owner-selected photograph"'
      ' width="'+str(width)+'" height="'+str(height)+'" decoding="async" loading="eager"'
      ' fetchpriority="high" style="display:block;width:100%;height:auto;'+circular
      'border:2px solid #d6ae79"/>'
      '<figcaption style="margin-top:10px;text-align:center;color:#e8d0a7;font:13px/1.5 system-ui,sans-serif">'
      'Official owner-selected profile photograph</figcaption>'
      '</figure>'
      '<div style="flex:1 1 320px;max-width:570px">'
      '<p style="font:700 13px/1.6 system-ui,sans-serif;color:#dcbb85;letter-spacing:.1em">PROFESSIONAL PROFILE</p>'
      '<p style="font:700 clamp(26px,3vw,38px)/1.15 Georgia,serif;margin:6px 0 18px;color:#f6d59a">Mojtaba Roozegar</p>'
      '<p style="font:16px/1.8 system-ui,sans-serif">Research, applied economics, and intelligent industrial and commercial website collaboration.</p>'
      '<p style="font:14px/1.8 system-ui,sans-serif">This is a personal photograph selected by the profile owner. '
      'It is not presented as evidence of a Vancouver office or a completed client project.</p>'
      '<p><a href="/mojtaba.roozegar/contact/" style="color:#f5d39c;text-decoration:underline;'
      'font:700 16px system-ui,sans-serif">Discuss a professional collaboration →</a></p>'
      '</div></section>'
    )
def patch(which,source):
    token="{% block content %}"
    if source.count(token)!=1:raise ValueError("Personal content block not unique")
    if MARK in source:raise ValueError("Primary photograph already installed")
    if which=="home" and ('id="mpw-new-originals-20261015-b"' not in source or 'id="mpw-mojtaba-twenty-image-essays-20261016"' not in source):
        raise ValueError("Original personal home content markers changed")
    if which=="about" and ('id="mpw-academic-profile-20261016"' not in source and 'mpw-academic-profile-20261016' not in source):
        raise ValueError("Original professional about profile marker absent")
    if "{% load static %}" not in source:
        source=source.replace(token,"{% load static %}\n"+token,1)
    return source.replace(token,token+"\n"+profile_section(which)+"\n",1)
def check_django(app:Path):
    import sys
    sys.path.insert(0,str(app))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    import django;django.setup()
    from django.template import engines
    from core.models import Post
    if Post.objects.filter(published=True).count()<93:raise ValueError("Personal site articles fewer than 93")
    return engines
def install(app:Path,pics:Path,backup:Path):
    images=image_bytes(pics)
    paths=targets(app)
    before={key:path.read_text(encoding="utf-8") for key,path in paths.items()}
    after={key:patch(key,value) for key,value in before.items()}
    engines=check_django(app)
    for key,value in after.items():
        engines["django"].engine.from_string(value)
        print("PROFILE_PHOTO_VALID_TEMPLATE="+key,flush=True)
    dest=app/"static"/STATIC_FOLDER
    if dest.exists() or dest.is_symlink():raise ValueError("Profile media folder collision")
    if backup.exists() or backup.is_symlink():raise ValueError("Backup folder collision")
    backup.mkdir(parents=True,mode=0o700)
    checks={}
    for key,p in paths.items():
        (backup/p.name).write_text(before[key],encoding="utf-8")
        (backup/p.name).chmod(0o600)
        checks[key]={"before":sha(before[key].encode()),"after":sha(after[key].encode())}
    (backup/"state.json").write_text(json.dumps({"templates":checks,"assets":IMAGES},indent=2),encoding="utf-8")
    (backup/"state.json").chmod(0o600)
    changed=[]
    try:
        dest.mkdir(parents=True,mode=0o755)
        for name,data in images.items():
            f=dest/name
            f.write_bytes(data);f.chmod(0o644)
        for key,p in paths.items():
            if sha(p.read_bytes())!=checks[key]["before"]:raise ValueError("Concurrent template changes")
            tmp=p.with_name(p.name+".photo-profile-new")
            if tmp.exists() or tmp.is_symlink():raise ValueError("Temporary file collision")
            tmp.write_text(after[key],encoding="utf-8")
            tmp.chmod(p.stat().st_mode&0o777)
            os.replace(tmp,p);changed.append(key)
    except BaseException:
        for key in changed:
            p=paths[key]
            if sha(p.read_bytes())==checks[key]["after"]:shutil.copy2(backup/p.name,p)
        if dest.is_dir() and sorted(x.name for x in dest.iterdir())==sorted(images) and all(sha((dest/n).read_bytes())==sha(b) for n,b in images.items()):
            shutil.rmtree(dest)
        raise
    if (app/"tmp").is_dir():(app/"tmp/restart.txt").touch()
    print("PROFILE_PHOTO_OWNER_SELECTED_INSTALLED=yes",flush=True)
    print("PROFILE_PHOTO_ORIGINAL_GALLERY_AND_ARTICLES_UNCHANGED=yes",flush=True)
    print("PROFILE_PHOTO_BACKUP="+str(backup),flush=True)
def rollback(app:Path,backup:Path):
    if backup.is_symlink() or not backup.is_dir():raise ValueError("Backup missing")
    state=json.loads((backup/"state.json").read_text(encoding="utf-8"))
    paths=targets(app)
    for key,p in paths.items():
        if sha((backup/p.name).read_bytes())!=state["templates"][key]["before"] or sha(p.read_bytes())!=state["templates"][key]["after"]:
            raise ValueError("Page changed since profile edit; refuse overwrite")
    dest=app/"static"/STATIC_FOLDER
    if dest.is_symlink() or not dest.is_dir() or sorted(x.name for x in dest.iterdir())!=sorted(IMAGES):
        raise ValueError("Profile media folder not safe to restore")
    for n,digest in IMAGES.items():
        if sha((dest/n).read_bytes())!=digest:raise ValueError("New photo modified; refuse deletion")
    for key,p in paths.items():
        tmp=p.with_name(p.name+".photo-profile-restore")
        if tmp.exists() or tmp.is_symlink():raise ValueError("Temporary restore collision")
        shutil.copy2(backup/p.name,tmp);os.replace(tmp,p)
    shutil.rmtree(dest)
    if (app/"tmp").is_dir():(app/"tmp/restart.txt").touch()
    print("PROFILE_PHOTO_SAFE_ROLLBACK=yes",flush=True)
def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("action",choices=("check","install","rollback"))
    cli.add_argument("--app",type=Path,default=APP)
    cli.add_argument("--pictures",type=Path)
    cli.add_argument("--backup",type=Path)
    args=cli.parse_args()
    if args.action=="rollback":
        if not args.backup:cli.error("Backup required")
        rollback(args.app,args.backup);return
    if not args.pictures:cli.error("Pictures required")
    image_bytes(args.pictures)
    if args.action=="check":
        print("PROFILE_PHOTO_UPLOAD_SHA_VERIFIED=yes",flush=True);return
    if not args.backup:cli.error("Backup required")
    install(args.app,args.pictures,args.backup)
if __name__=="__main__":main()
