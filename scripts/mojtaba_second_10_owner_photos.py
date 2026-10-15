#!/usr/bin/env python3
"""Add SECOND set of 10 unmodified owner-supplied PNGs to personal V17 site only.
Requires exact SHA-256 verified owner archive. Safe, additive, idempotence-guarded.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
from zipfile import ZipFile

APP = Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
REL_TEMPLATE = Path("templates/personal_site/core")
PHOTO_SUBDIR = "personal_site/owner_gallery_20261015_b"
PHOTO_DIR = APP / "static" / PHOTO_SUBDIR
MARKER = 'id="mpw-new-originals-20261015-b"'
SHA = (
"9dad226ae5ade5d12338217e8297acd695b9967acbe90045f38934d1a4a4012a",
"003cda81df35dce91ffa40a8266b539a543dad284310e173e001fe1393146fb9",
"c8032a19c2dba60ba16b941873b15eb00b53a105be3063e8633e277e70f5fec1",
"e8487a4d2439932558b98962308aac9a6cfc25ae22b0d6bdd798314263347293",
"b1805dd62928103e00d5ce03a13ec51b62b5a987e9a0832ee0d5b93661ad360f",
"fd3b5e5b7dd23c5fcde840d81d2c59e54213741bfa8eb2ed536c94ed2368dff3",
"d016b84ad48852d58a3d1af0c21aff9b486f522be43cf2a3e53d7c72bbdbb435",
"f8b90e437420f0a4df3ff6d05468ff489680889a00797532c5e39f1777809313",
"44b6a033b63568e748ed8464343c2feabd587471013aa3104f68ab44747bcfb8",
"238a2f07653ead1afb7d650fa4e7c81ec3bc6c30dd486ce82bca16d8fe928f3b",
)
SIZES=(241506,320092,262496,280290,297394,301107,308946,276859,290610,270389)
TITLES=(
"Personal executive portrait",
"Agricultural research and fieldwork",
"Architecture and development portrait",
"Personal moments and perspectives",
"Four editorial lifestyle perspectives",
"Work and outdoor perspectives",
"Business and outdoor portraits",
"Lifestyle and travel moments",
"Four professional portrait views",
"Executive close-up portrait",
)
ROUTES={
    "home": ("home.html",[1,10,9]),
    "about": ("about.html",[1,10]),
    "projects": ("projects.html",[2,3]),
    "posts": ("posts.html",[2,3]),
    "gallery": ("gallery.html",list(range(1,11))),
    "resume": ("resume.html",[1,3,10]),
    "activities": ("activities.html",[2,3,6]),
    "memories": ("memories.html",[4,5,7,8]),
    "stories": ("stories.html",[4,9]),
}
CSS = """<style>
.mpw-batch-b{width:100%;clear:both;margin:36px auto;padding:26px;max-width:1180px;background:#172839;border:1px solid #a78c59;border-radius:8px;color:#f1e9dc;box-sizing:border-box}
.mpw-batch-b *{box-sizing:border-box}
.mpw-batch-b h2{color:#f8e7c8;font:400 clamp(24px,3.2vw,36px)/1.2 Georgia,'Times New Roman',serif;margin:0 0 8px}
.mpw-batch-b p{color:#d3dce1;font-size:15px;line-height:1.7;margin:0 0 20px}
.mpw-batch-b .mpw-photo-grid-b{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.mpw-batch-b figure{margin:0;min-width:0;border:1px solid #564c41;background:#101e2e;border-radius:5px;overflow:hidden}
.mpw-batch-b figure a{display:block}
.mpw-batch-b figure a:focus-visible{outline:3px solid #eac78c;outline-offset:-3px}
.mpw-batch-b img{display:block;width:100%;height:310px;object-fit:contain;background:#101e2e}
.mpw-batch-b figcaption{font-size:14px;line-height:1.5;color:#f0e6d6;padding:12px 14px}
@media(max-width:640px){.mpw-batch-b{padding:13px;margin:20px auto}.mpw-batch-b .mpw-photo-grid-b{grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.mpw-batch-b img{height:215px}.mpw-batch-b figcaption{font-size:12px;padding:9px}}
</style>"""

def image_tag(number: int) -> str:
    return "{% static '"+PHOTO_SUBDIR+"/photo-"+f"{number:02d}"+".jpg' %}"

def addition(page: str) -> str:
    labels=ROUTES[page][1]
    cards=[]
    for n in labels:
        img=image_tag(n)
        title=html.escape(TITLES[n-1],quote=True)
        caption=title+" · Owner-supplied editorial photograph"
        cards.append(
            '<figure><a href="'+img+'" target="_blank" rel="noopener noreferrer" aria-label="Open supplied original '+str(n)+'">'
            '<img src="'+img+'" loading="lazy" decoding="async" alt="'+title+'" width="480" height="640"></a>'
            '<figcaption>'+caption+'</figcaption></figure>'
        )
    explanatory=(
       "Ten new images supplied by the founder, shown individually and without changing their original files."
       if page=="gallery" else
       "Selected photographs from the founder’s second original collection. Composite images are preserved intact."
    )
    return ('<section id="mpw-new-originals-20261015-b" class="mpw-batch-b" aria-label="Original photo collection">'
            +CSS+'<h2>Original photo collection · New perspectives</h2><p>'
            +explanatory+'</p><div class="mpw-photo-grid-b">'
            +''.join(cards)+'</div></section>')

def patch(page: str, content: str) -> str:
    if page not in ROUTES: raise ValueError("Page not allowed")
    if MARKER in content: raise ValueError("Already installed: "+page)
    opening="{% block content %}"
    if content.count(opening)!=1: raise ValueError("Unexpected content block: "+page)
    pos=content.index(opening)+len(opening)
    closing="{% endblock %}"
    end=content.find(closing,pos)
    if end<0: raise ValueError("Missing content block end: "+page)
    if "{% load static %}" not in content:
        if "{% extends" not in content: raise ValueError("Unsafe template, no extends")
        extender=content.index("%}")+2
        content=content[:extender]+"\n{% load static %}"+content[extender:]
        end+=len("\n{% load static %}") if extender<=end else 0
    result=content[:end]+"\n"+addition(page)+"\n"+content[end:]
    if result.count(MARKER)!=1: raise ValueError("Missing new block")
    for n in ROUTES[page][1]:
        if result.count(PHOTO_SUBDIR+"/photo-"+f"{n:02d}"+".jpg")!=2:
            raise ValueError("Expected exactly two new references per photograph")
    return result

def verify_archive(zip_path: Path) -> None:
    if not zip_path.is_file() or zip_path.is_symlink(): raise ValueError("Missing source archive")
    expected={"owner-new-gallery/photo-"+f"{i:02d}"+".png" for i in range(1,11)}
    allowed=expected|{"manifest.json","README.txt"}
    total=0
    with ZipFile(zip_path) as z:
        names=z.namelist()
        if len(names)!=len(set(names)) or set(names)!=allowed: raise ValueError("Unexpected ZIP members")
        for i in range(1,11):
            name="owner-new-gallery/photo-"+f"{i:02d}"+".png"
            info=z.getinfo(name)
            if info.file_size!=SIZES[i-1]: raise ValueError("Image size mismatch "+name)
            if info.compress_size<1: raise ValueError("Invalid compression")
            if (info.external_attr>>16)&0o170000 == 0o120000: raise ValueError("Symlink refused")
            raw=z.read(info)
            if hashlib.sha256(raw).hexdigest()!=SHA[i-1] or not raw.startswith(b"\xff\xd8\xff"):
                raise ValueError("Owner image bytes mismatch "+name)
            total+=len(raw)
    print("SECOND_GALLERY_ORIGINALS_SHA256_VERIFIED=10 bytes="+str(total),flush=True)

def templates(app:Path)->dict[str,str]:
    root=app/REL_TEMPLATE
    allfiles={}
    for page,(filename,_) in ROUTES.items():
        dest=root/filename
        if not dest.is_file() or dest.is_symlink():raise ValueError("Unexpected template file "+filename)
        allfiles[page]=dest.read_text(encoding="utf-8")
    return allfiles

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=("verify","preflight","assets","install","rollback"))
    parser.add_argument("--archive",type=Path)
    parser.add_argument("--backup",type=Path)
    parser.add_argument("--app",type=Path,default=APP)
    args=parser.parse_args()
    if args.mode=="verify":
        if not args.archive:raise SystemExit("--archive required")
        verify_archive(args.archive)
        return
    app=args.app
    if not args.backup:raise SystemExit("--backup required")
    if not (app/"manage.py").is_file() or app.is_symlink():raise ValueError("Not the independent personal V17 app")
    backup=args.backup
    photo_dir=app/"static"/PHOTO_SUBDIR
    if args.mode=="rollback":
        for page,(filename,_) in ROUTES.items():
            orig=backup/filename
            if not orig.is_file() or orig.is_symlink():raise ValueError("Missing backup: "+filename)
        for page,(filename,_) in ROUTES.items():
            dst=app/REL_TEMPLATE/filename
            tmp=dst.with_suffix(".photo-restore")
            shutil.copy2(backup/filename,tmp)
            os.replace(tmp,dst)
        # Existing photo bytes in this dedicated subfolder are never edited.
        if (app/"tmp").is_dir():(app/"tmp/restart.txt").touch()
        print("SECOND_GALLERY_ROLLBACK=all_nine_templates",flush=True)
        return
    if args.mode=="assets":
        if not args.archive: raise SystemExit("--archive required")
        verify_archive(args.archive)
        if photo_dir.exists():
            if photo_dir.is_symlink() or not photo_dir.is_dir():
                raise ValueError("Unsafe second gallery directory")
            for i in range(1,11):
                existing=photo_dir/("photo-"+f"{i:02d}"+".jpg")
                if not existing.is_file() or existing.is_symlink() or hashlib.sha256(existing.read_bytes()).hexdigest()!=SHA[i-1]:
                    raise ValueError("Existing original image mismatch "+str(i))
            print("SECOND_GALLERY_STATIC_ALREADY_VERIFIED=10",flush=True)
            return
        photo_dir.mkdir(parents=True,mode=0o755)
        with ZipFile(args.archive) as z:
            for i in range(1,11):
                p=photo_dir/("photo-"+f"{i:02d}"+".jpg")
                with p.open("xb") as handle:
                    handle.write(z.read("owner-new-gallery/photo-"+f"{i:02d}"+".png"))
                p.chmod(0o644)
        print("SECOND_GALLERY_STATIC_STAGED=10",flush=True)
        return
    if args.mode=="install":
        if not photo_dir.is_dir() or photo_dir.is_symlink():raise ValueError("Originals not staged")
        for i in range(1,11):
            p=photo_dir/("photo-"+f"{i:02d}"+".jpg")
            if not p.is_file() or p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=SHA[i-1]:
                raise ValueError("Staged photo mismatch "+str(i))
    existing=templates(app)
    new={page:patch(page,data) for page,data in existing.items()}
    if args.mode=="preflight":
        print("NINE_TEMPLATES_READY=yes",flush=True)
        return
    if backup.exists():raise ValueError("Refuse overwriting backup")
    backup.mkdir(parents=True,mode=0o700)
    for page,(filename,_) in ROUTES.items():
        p=backup/filename
        p.write_text(existing[page],encoding="utf-8")
        p.chmod(0o600)
    print("SECOND_GALLERY_STATIC_ALREADY_COLLECTED=yes",flush=True)
    print("SECOND_GALLERY_BACKUP_READY=yes",flush=True)
    changed=[]
    try:
        for page,(filename,_) in ROUTES.items():
            p=app/REL_TEMPLATE/filename
            tmp=p.with_suffix(".gallery-20261015-b.tmp")
            if tmp.exists():raise ValueError("Unsafe existing temporary file")
            tmp.write_text(new[page],encoding="utf-8")
            os.chmod(tmp,p.stat().st_mode & 0o777)
            os.replace(tmp,p)
            changed.append(page)
    except BaseException:
        for page in changed:
            shutil.copy2(backup/ROUTES[page][0],app/REL_TEMPLATE/ROUTES[page][0])
        raise
    if (app/"tmp").is_dir(): (app/"tmp/restart.txt").touch()
    print("SECOND_GALLERY_NINE_PAGES_INSTALLED=yes",flush=True)

if __name__=="__main__":main()
