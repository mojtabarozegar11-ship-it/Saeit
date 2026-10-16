#!/usr/bin/env python3
"""Scoped, reversible, image-backed Vancouver articles on Mojtaba's independent Django V17 personal site."""
from __future__ import annotations
import argparse,hashlib,html,json,os,shutil,sys
from pathlib import Path
from urllib.parse import urljoin

APP=Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
TEMPLATES={"home":"home.html","posts":"posts.html","detail":"detail.html"}
MARKER='id="mpw-vancouver-collab-photo-ten-20261016"'
DETAIL_MARKER='id="mpw-vancouver-post-photo-20261016"'
PREVIOUS=('id="mpw-new-originals-20261015-b"','id="mpw-fifty-editorials-20261015"','id="mpw-academic-profile-20261016"','id="mpw-personal-expanded-20261016"','id="mpw-journal-longform-index-20261016"','id="mpw-journal-advanced-index-20261016"','id="mpw-website-ten-index-20261016"')
IMAGE_FOLDER="personal_site/vancouver_collab_20261016"
OLD_MANIFESTS=("mojtaba_seven_full_independent_journal_20261016.json","mojtaba_six_advanced_journal_articles_20261016.json","mojtaba_ten_advanced_website_engineering_20261016.json")

def digest(data):return hashlib.sha256(data).hexdigest()
def file_sha(p):return digest(p.read_bytes())
def expected_path(slug):return IMAGE_FOLDER+"/"+slug+".jpg"
def load_bundle(paths):
    if len(paths)!=2:raise ValueError("Two separate content manifests required")
    all_rows=[]
    for path in paths:
        path=Path(path)
        if not path.is_file() or path.is_symlink():raise ValueError("Missing safe content part")
        d=json.loads(path.read_text(encoding="utf-8"))
        if d.get("version")!=1 or d.get("language")!="en" or len(d.get("articles",[]))!=5:raise ValueError("Each part needs five English articles")
        all_rows+=d["articles"]
    names=set()
    for row in all_rows:
        if set(row)!={"slug","title","excerpt","content","photo_id","photo_credit","photo_url"}:raise ValueError("Unexpected article fields")
        if any(not isinstance(v,str) or not v.strip() for v in row.values()):raise ValueError("Empty text or photo metadata")
        slug=row["slug"]
        if not 16<=len(slug)<=160 or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in slug):raise ValueError("Unsafe slug")
        if slug in names:raise ValueError("Duplicate slug")
        if not row["photo_id"].replace("-","").replace("_","").isalnum() or not row["photo_url"].startswith("https://unsplash.com/photos/"):
            raise ValueError("Invalid photo source")
        if len(row["title"])>180 or len(row["excerpt"])>350 or len(row["content"].split())<300:raise ValueError("Article too short or Django max length exceeded")
        if "<script" in row["content"].lower() or "<iframe" in row["content"].lower():raise ValueError("Unapproved HTML in article")
        names.add(slug)
    if len(all_rows)!=10:raise ValueError("Exactly ten articles required")
    return all_rows

def protected_templates(app):
    base=app/"templates/personal_site/core"
    if app.is_symlink() or base.is_symlink() or not (app/"manage.py").is_file():raise ValueError("Unexpected independent personal app")
    out={}
    for page,filename in TEMPLATES.items():
        p=base/filename
        if p.is_symlink() or not p.is_file():raise ValueError("Unexpected site template "+filename)
        out[page]=p.read_text(encoding="utf-8")
    return out

def index_html(rows,media_url):
    esc=lambda s:html.escape(s,quote=True)
    parts=['{% load static %}\n<section '+MARKER+' class="mpw-vancouver-photo-series" aria-label="Open to professional collaboration in Vancouver">',
    '<style>.mpw-vancouver-photo-series{background:#161513;color:#f5e7d2;border:4px solid #c69b55;border-radius:14px;padding:clamp(18px,3vw,34px);margin:36px auto;max-width:1180px}.mpw-vancouver-photo-series h2{font:600 clamp(24px,3vw,36px)/1.3 Georgia,serif;color:#ebc785}.mpw-vancouver-photo-series .intro{font:400 16px/1.8 system-ui,sans-serif}.mpw-vancouver-photo-series .grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.mpw-vancouver-photo-series article{background:#26221e;border:1px solid #a8864d;border-radius:10px;overflow:hidden}.mpw-vancouver-photo-series img{width:100%;aspect-ratio:16/9;object-fit:cover;display:block}.mpw-vancouver-photo-series a{color:#f5db9f;text-decoration:none}.mpw-vancouver-photo-series a:hover{text-decoration:underline}.mpw-vancouver-photo-series .copy{padding:16px}.mpw-vancouver-photo-series h3{font:600 21px/1.38 Georgia,serif;margin:4px 0 12px}.mpw-vancouver-photo-series p{line-height:1.65}.mpw-vancouver-photo-series small{color:#ded0b7}@media(max-width:750px){.mpw-vancouver-photo-series .grid{grid-template-columns:1fr}}</style>',
    '<h2>Open to Collaboration in Vancouver — Ten Illustrated Articles</h2>',
    '<p class="intro">Mojtaba Roozegar welcomes appropriate discussions about research, education, original games, artificial intelligence and professional website projects. I welcome thoughtful professional conversations about research, digital services and relevant projects.</p>',
    '<div class="grid">']
    for a in rows:
        slug,title,excerpt=a["slug"],a["title"],a["excerpt"]
        src="{% static '"+expected_path(slug)+"' %}"
        parts+=['<article><a href="/mojtaba.roozegar/blog/'+esc(slug)+'/"><img loading="lazy" decoding="async" width="1200" height="675" src="'+src+'" alt="'+esc("Illustrative Vancouver photograph: "+title)+'"><div class="copy"><h3>'+esc(title)+'</h3><p>'+esc(excerpt)+'</p></div></a><div class="copy"><small>Photograph: '+esc(a["photo_credit"])+' / Unsplash. Illustrative scene, not a verified business meeting.</small></div></article>']
    parts+=['</div></section>']
    return "\n".join(parts)

def patch(page,original,rows,media_url):
    if page in ("home","posts"):
        if MARKER in original:raise ValueError("Already published")
        for m in PREVIOUS:
            if original.count(m)!=1:raise ValueError("Earlier content missing "+m)
        block="{% block content %}"
        if original.count(block)!=1:raise ValueError("Ambiguous content block")
        stop=original.find("{% endblock %}",original.index(block)+len(block))
        if stop<0:raise ValueError("Django endblock absent")
        new=original[:stop]+"\n"+index_html(rows,media_url)+"\n"+original[stop:]
        if new.count(MARKER)!=1:raise ValueError("New image-backed index missing")
        return new
    if page!="detail":raise ValueError("Forbidden page")
    if DETAIL_MARKER in original:raise ValueError("Image already inserted")
    block="{% block content %}"
    if original.count(block)!=1 or "{{ item.title" not in original:raise ValueError("Unexpected article detail template")
    where=original.index(block)+len(block)
    detail_bits=['{% load static %}','{% if kind == "Article" %}']
    for k,entry in enumerate(rows):
        branch="{% if" if k==0 else "{% elif"
        detail_bits.append(branch+' item.slug == "'+entry["slug"]+'" %}')
        photo="{% static '"+expected_path(entry["slug"])+"' %}"
        detail_bits.append('<figure '+DETAIL_MARKER+' style="border:3px solid #bb9652;background:#161513;padding:12px;border-radius:10px;margin:24px auto;max-width:1050px"><img src="'+photo+'" alt="'+html.escape("Illustrative Vancouver photograph for "+entry["title"],quote=True)+'" width="1200" height="675" decoding="async" style="width:100%;height:auto;object-fit:cover;display:block"><figcaption style="color:#e1c896;font:14px/1.5 system-ui,sans-serif">Editorial illustration. The photograph does not depict a confirmed partnership or office.</figcaption></figure>')
    detail_bits.extend(['{% endif %}','{% endif %}'])
    markup="\n"+"\n".join(detail_bits)+"\n"
    return original[:where]+markup+original[where:]

def prepare(app):
    sys.path.insert(0,str(app))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    import django
    django.setup()
    from django.conf import settings
    from django.db import transaction
    from core.models import Post,GalleryItem
    media=Path(settings.MEDIA_ROOT)
    if not media.is_absolute() or media.is_symlink() or not media.is_dir():raise ValueError("Unexpected media root")
    return Post,GalleryItem,transaction,media,settings.MEDIA_URL

def old_slugs(contents):
    names=[]
    for source in OLD_MANIFESTS:
        p=Path(contents)/source
        if not p.is_file() or p.is_symlink():raise ValueError("Older evidence manifest missing")
        names += [x["slug"] for x in json.loads(p.read_text(encoding="utf-8"))["articles"]]
    if len(names)!=23 or len(set(names))!=23:raise ValueError("Previous 23 unique article names required")
    return names

def safe_photos(rows,folder):
    folder=Path(folder)
    out={}
    for row in rows:
        p=folder/(row["slug"]+".jpg")
        if p.is_symlink() or not p.is_file() or not 35000<=p.stat().st_size<=7000000 or p.read_bytes()[:3]!=b"\xff\xd8\xff":
            raise ValueError("Missing or invalid JPEG "+row["slug"])
        out[row["slug"]]={"filename":p,"sha256":file_sha(p),"bytes":p.stat().st_size}
    return out


def public_owner_gallery_photos():
    """Read the twenty images actually exposed by the personal gallery, not presumed ORM rows."""
    from html.parser import HTMLParser
    from urllib.request import Request,urlopen
    from urllib.parse import urljoin,urlparse
    base="https://mojplaywin.com/mojtaba.roozegar/gallery/"
    class Photos(HTMLParser):
        def __init__(self):
            super().__init__()
            self.one=[];self.two=[]
        def handle_starttag(self,tag,attrs):
            if tag!="img":return
            raw=dict(attrs).get("src","")
            if not raw:return
            uri=urljoin(base,raw)
            parsed=urlparse(uri)
            if parsed.scheme!="https" or parsed.netloc!="mojplaywin.com":return
            if "owner_gallery_20261015_b/" in parsed.path:self.two.append(uri)
            elif "owner_gallery_20261015/" in parsed.path:self.one.append(uri)
    with urlopen(Request(base,headers={"User-Agent":"MojtabaGalleryImageReuser/1"}),timeout=25) as response:
        if response.status!=200:raise ValueError("Existing gallery unavailable")
        page=response.read(4000000).decode("utf-8","replace")
    parser=Photos();parser.feed(page)
    if len(parser.one)!=10 or len(parser.two)!=10:raise ValueError("Twenty existing owner-gallery images not visible")
    photos=parser.one+parser.two
    if len(set(photos))!=20:raise ValueError("Original owner gallery images are duplicated")
    return photos

def legacy_photo_fallback(source,missing_to_image):
    """Render owner's existing photo URLs only for older Post records with a blank cover.

    No legacy Post rows are modified.
    """
    if not missing_to_image:return source
    mark='id="mpw-vancouver-older-article-photo-20261016"'
    if mark in source:raise ValueError("Legacy photo fallback already present")
    block="{% block content %}"
    if source.count(block)!=1:raise ValueError("Missing article detail insertion point")
    snippets=['{% if kind == "Article" and not item.cover %}']
    for i,(slug,url) in enumerate(sorted(missing_to_image.items())):
        if any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in slug):raise ValueError("Unsafe old slug")
        test="{% if" if i==0 else "{% elif"
        snippets.append(test+' item.slug == "'+slug+'" %}')
        snippets.append('<figure '+mark+' style="border:3px solid #c19a51;background:#161513;padding:10px;margin:20px auto;max-width:1050px"><img src="'+html.escape(url,quote=True)+'" alt="Photograph from Mojtaba Roozegar’s original personal gallery" width="1200" height="675" loading="lazy" decoding="async" style="width:100%;height:auto;object-fit:cover"><figcaption style="color:#ddc6a0;font:14px/1.5 system-ui,sans-serif">Personal gallery photograph.</figcaption></figure>')
    snippets.extend(['{% endif %}','{% endif %}'])
    where=source.index(block)+len(block)
    return source[:where]+"\n"+"\n".join(snippets)+"\n"+source[where:]

def stage_install(app,rows,photo_dir,contents,backup):
    current=protected_templates(app)
    Post,GalleryItem,transaction,media,media_url=prepare(app)
    if not media_url.startswith("/") or not media_url.endswith("/"):raise ValueError("Unexpected MEDIA_URL")
    photos=safe_photos(rows,photo_dir)
    older=old_slugs(contents)
    if Post.objects.filter(slug__in=[r["slug"] for r in rows]).exists():raise ValueError("New slug collision")
    if Post.objects.filter(slug__in=older,published=True).count()!=23:raise ValueError("23 older posts not published")
    gallery=public_owner_gallery_photos()
    if backup.exists() or backup.is_symlink():raise ValueError("Backup destination exists")
    prior=list(Post.objects.filter(slug__in=older))
    # The old public gallery is template-backed, not necessarily twenty GalleryItem rows.
    # Preserve all old DB rows and render the already-public original images as fallback.
    fallback={p.slug:gallery[j%len(gallery)] for j,p in enumerate(sorted(prior,key=lambda v:v.slug)) if not p.cover}
    changes={}
    proposed={page:(legacy_photo_fallback(patch(page,text,rows,media_url),fallback) if page=="detail" else patch(page,text,rows,media_url)) for page,text in current.items()}
    media_target=app/"static"/IMAGE_FOLDER
    if media_target.is_symlink() or media_target.exists():raise ValueError("Dedicated image destination must be new")
    backup.mkdir(parents=True,mode=0o700)
    meta={"schema":1,"new":{r["slug"]:{"title":r["title"],"body_sha256":digest(r["content"].encode()),"cover":"","file_sha256":photos[r["slug"]]["sha256"]} for r in rows},
          "previous_covers":changes,"templates":{p:{"old":digest(current[p].encode()),"new":digest(proposed[p].encode())} for p in TEMPLATES}}
    for p,filename in TEMPLATES.items():
        out=backup/filename
        out.write_text(current[p],encoding="utf-8")
        out.chmod(0o600)
    (backup/"state.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    (backup/"state.json").chmod(0o600)
    changed=[]
    try:
        media_target.mkdir(parents=True,mode=0o755)
        for r in rows:
            target=app/"static"/expected_path(r["slug"])
            with target.open("xb") as out:
                with photos[r["slug"]]["filename"].open("rb") as input_file:shutil.copyfileobj(input_file,out)
            target.chmod(0o644)
            if file_sha(target)!=photos[r["slug"]]["sha256"]:raise ValueError("Photo corruption")
        with transaction.atomic():
            if Post.objects.filter(slug__in=[r["slug"] for r in rows]).exists():raise ValueError("Concurrent slug collision")
            for r in rows:
                Post.objects.create(title=r["title"],slug=r["slug"],excerpt=r["excerpt"],content=r["content"],published=True)
            for page,filename in TEMPLATES.items():
                path=app/"templates/personal_site/core"/filename
                if proposed[page]==current[page]:continue
                tmp=path.with_name(filename+".vancouver-publish")
                if tmp.exists() or tmp.is_symlink():raise ValueError("Temporary file exists")
                tmp.write_text(proposed[page],encoding="utf-8")
                tmp.chmod(path.stat().st_mode & 0o777)
                os.replace(tmp,path)
                changed.append(page)
    except BaseException:
        for page in changed:
            shutil.copy2(backup/TEMPLATES[page],app/"templates/personal_site/core"/TEMPLATES[page])
        for row in rows:
            target=app/"static"/expected_path(row["slug"])
            if target.exists() and file_sha(target)==photos[row["slug"]]["sha256"]:target.unlink()
        try:media_target.rmdir()
        except OSError:pass
        raise
    if (app/"tmp").is_dir():(app/"tmp/restart.txt").touch()
    print("VANCOUVER_NEW_TEN_NATIVE_ARTICLES_INSTALLED=yes",flush=True)
    print("VANCOUVER_LEGACY_POST_IMAGES_INSERTED_IN_DETAIL="+str(len(fallback)),flush=True)
    print("VANCOUVER_TEN_STATIC_JPEG_FILES_SAVED=yes",flush=True)
    print("VANCOUVER_BACKUP="+str(backup),flush=True)

def rollback(app,backup):
    Post,GalleryItem,transaction,media,media_url=prepare(app)
    meta=json.loads((backup/"state.json").read_text(encoding="utf-8"))
    current=protected_templates(app)
    for page,filename in TEMPLATES.items():
        ref=meta["templates"][page]
        if digest((backup/filename).read_bytes())!=ref["old"] or digest(current[page].encode())!=ref["new"]:
            raise ValueError("Template diverged; refuse destructive rollback")
    rows=list(Post.objects.filter(slug__in=meta["new"]))
    if len(rows)!=10:raise ValueError("Article set changed; cannot safely roll back")
    for obj in rows:
        ref=meta["new"][obj.slug]
        if obj.title!=ref["title"] or digest(obj.content.encode())!=ref["body_sha256"] or obj.cover.name!=ref["cover"]:
            raise ValueError("Article edited after release; refuse rollback")
        p=app/"static"/expected_path(obj.slug)
        if not p.is_file() or file_sha(p)!=ref["file_sha256"]:raise ValueError("Media changed; refuse cleanup")
    previous={p.slug:p for p in Post.objects.filter(slug__in=meta["previous_covers"])}
    if len(previous)!=len(meta["previous_covers"]):raise ValueError("Prior posts changed")
    for slug,change in meta["previous_covers"].items():
        if previous[slug].cover.name!=change["after"]:raise ValueError("Existing photo subsequently changed")
    with transaction.atomic():
        for slug,p in previous.items():
            p.cover=meta["previous_covers"][slug]["before"]
            p.save(update_fields=["cover"])
        Post.objects.filter(slug__in=meta["new"]).delete()
        for page,filename in TEMPLATES.items():
            target=app/"templates/personal_site/core"/filename
            tmp=target.with_name(filename+".vancouver-restore")
            if tmp.exists():raise ValueError("Restore temporary file exists")
            shutil.copy2(backup/filename,tmp)
            os.replace(tmp,target)
    for slug,ref in meta["new"].items():
        (app/"static"/expected_path(slug)).unlink()
    try:(app/"static"/IMAGE_FOLDER).rmdir()
    except OSError:pass
    if (app/"tmp").is_dir():(app/"tmp/restart.txt").touch()
    print("VANCOUVER_NEW_TEN_SAFE_FULL_ROLLBACK=yes",flush=True)

def main():
    a=argparse.ArgumentParser()
    a.add_argument("mode",choices=("check","install","rollback"))
    a.add_argument("--app",type=Path,default=APP)
    a.add_argument("--part-a",type=Path)
    a.add_argument("--part-b",type=Path)
    a.add_argument("--photos",type=Path)
    a.add_argument("--old-content",type=Path)
    a.add_argument("--backup",type=Path)
    args=a.parse_args()
    if args.mode=="rollback":
        if not args.backup:a.error("backup required")
        rollback(args.app,args.backup);return
    if not args.part_a or not args.part_b:a.error("Two content parts required")
    rows=load_bundle([args.part_a,args.part_b])
    templates=protected_templates(args.app)
    if args.mode=="check":
        print("VANCOUVER_TEN_ARTICLE_MANIFEST_AND_TEMPLATES_READY=yes",flush=True);return
    if not args.photos or not args.old_content or not args.backup:a.error("photos, old-content and backup required")
    stage_install(args.app,rows,args.photos,args.old_content,args.backup)

if __name__=="__main__":main()
