#!/usr/bin/env python3
"""Clean visible production/structure notes on independent Mojtaba personal V17.

Only exact, reviewed website-production sentences and badges are removed.
Preserves articles, routes, photos, professional facts, citations and legal essentials.
Writes require a verified immutable backup and refuse concurrent changes.
"""
from __future__ import annotations
import argparse, hashlib, html, json, os, re, shutil, sys
from pathlib import Path

APP=Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
BLOCKS=(
    "The views and concepts here are educational or editorial, not claims of completed projects, regulated advice, or independently validated results.",
    "Editorial material and self-reported biography. Educational scenarios are illustrative, not professional or financial advice; academic credentials and specific accomplishments are not independently verified here.",
    "Biography supplied by the site owner; academic credentials are not independently verified on this page.",
    "Personal and academic information provided by the website owner. Graduation year, thesis title and external institutional verification are not claimed.",
    "This is a self-reported public résumé. It does not represent an independently credential-verified academic record.",
    "This is a personal introduction to the experience and subjects behind the website. Qualifications are presented from the biographical details I have provided, without inventing graduation dates or independently verified honors.",
    "Selected photographs from the founder’s second original collection. Composite images are preserved intact.",
    "Every image below is one of the ten original photographs supplied by the founder. The photographs remain unaltered, and no scene is used as documentary proof of an event.",
    "Ten new images supplied by the founder, shown individually and without changing their original files.",
    "These are editorial and branded images supplied for this website; depicted scenes are not independent documentary proof of specific meetings or locations. Planned percentages are goals, not audited business results.",
    "Browse the complete supplied collection individually. Each image remains unaltered and can be opened separately; the scenes are illustrative and are not independent evidence of specific meetings or office locations.",
    "Explore my professional interests through ten individual branded visual portraits. Select any image to open it independently, in its original supplied composition.",
    "An original fictional sample, clearly separated from personal biography and professional reporting.",
    "This short story is fictional editorial writing created for this page. Its people and events should not be interpreted as the founder's personal memories or verified biography.",
    "These are clearly fictional pieces, not verified personal events.",
    "The personal editorial collection · 5 entries",
    "The personal editorial collection · 12 entries",
    "The personal editorial collection · 3 entries",
    "The personal editorial collection · 4 entries",
    "The personal editorial collection · 6 entries",
    "The personal editorial collection · 7 entries",
    "A transparent collection of potential projects, not a claim of completed launches",
    "Three editorial perspectives on truthful visual presentation",
    "Four personal reflections without invented dated experiences",
    "Fictional vignettes about curiosity, evidence, and craft; not biographical accounts",
    "Seven original, in-depth educational articles about production economics, farm planning, digital research, original game design, and product quality. Each article has its own permanent link.",
    "Six additional, in-depth educational articles about production economics, farm planning, digital research, original game design, and product quality. Each article has its own permanent link.",
)
# These are visual metadata, not the actual image, alt text or attribution.
FRAGMENTS=(
    " · Owner-supplied editorial photograph",
    " · Owner-supplied branded editorial image",
    " · Original digital portrait illustration",
    "Owner-supplied editorial photograph",
    "Owner-supplied branded editorial image",
    "Owner-provided editorial portrait, not a documentary image of a location or event",
    "Owner-provided branded editorial portrait, not a photograph of Persepolis",
    "Owner-provided editorial portrait; not an illustration of a fictional scene",
    "Owner-provided editorial portrait; fictional characters are not depicted",
    "Professional portrait or illustrative digital artwork supplied for this essay.",
    "Personal portrait or illustrative digital artwork supplied for this essay.",
    "Original digital portrait illustration",
    "The personal editorial collection · 10 entries",
)
ARTICLE_PRODUCTION_NOTES=(
    "Editorial note: This original educational article is published on Mojtaba Roozegar's personal website.",
    "Editorial note: This original educational article appears in the research journal of Mojtaba Roozegar.",
)
PHOTO_CREDIT_RE=re.compile(r"(Photograph:\s*[^<\n]{1,130}?\s*/\s*Unsplash\.)\s*Illustrative scene, not a verified business meeting\.",re.I)
COLLECTION_RE=re.compile(r"<span\b([^>]*\bclass=[\"'][^\"']*mpw-overline[^\"']*[\"'][^>]*)>\s*The personal editorial collection\s*·\s*\d+\s*entries\s*</span>",re.I)
IDENTIFIER_RE=re.compile(r"(?<=\w)\s*·\s*MPW-\d{3}\b")
PARAGRAPH_WRAPPERS=("p","small","span","figcaption")
MIN_POSTS=93
MIN_IMAGES=300

def sha(v:bytes)->str: return hashlib.sha256(v).hexdigest()

def remove_exact_html(txt:str, phrase:str)->tuple[str,int]:
    changes=0
    # Remove a wrapper only if it consists exclusively of the approved production note.
    for tag in PARAGRAPH_WRAPPERS:
        pattern=r"<"+tag+r"\b[^>]*>\s*"+re.escape(phrase)+r"\s*</"+tag+r">"
        txt,n=re.subn(pattern,"",txt,flags=re.I)
        changes+=n
    # For composite captions and embedded sentences, remove only the text.
    n=txt.count(phrase)
    if n:
        txt=txt.replace(phrase,"")
        changes+=n
    return txt,changes

def clean_template(txt:str)->tuple[str,dict]:
    original=txt
    changes={}
    for phrase in BLOCKS+FRAGMENTS:
        txt,n=remove_exact_html(txt,phrase)
        if n:changes[phrase[:75]]=changes.get(phrase[:75],0)+n
    txt,n=PHOTO_CREDIT_RE.subn(r"\1",txt)
    if n:changes["photo credits retained; illustrative production note removed"]=n
    txt,n=COLLECTION_RE.subn("",txt)
    if n:changes["internal collection counter"]=n
    # Keep item titles and types, strip implementation IDs only from visible label spans.
    def no_id(m):
        before=m.group()
        return IDENTIFIER_RE.sub("",before)
    txt,n=re.subn(r'<span\b[^>]*class=["\'][^"\']*mpw-article-id[^"\']*["\'][^>]*>[^<]*</span>',no_id,txt,flags=re.I)
    if n and txt!=original:changes["internal editorial IDs in visible badges"]=n
    if txt!=original and not changes:changes["metadata text trimmed"]=1
    return txt,changes

def clean_post_content(txt:str)->tuple[str,int]:
    out=txt
    n_total=0
    for phrase in ARTICLE_PRODUCTION_NOTES:
        n=out.count(phrase)
        if n:
            out=out.replace(phrase,"").strip()
            n_total+=n
    # Do NOT remove scientific caveats, citations, case studies or numerical examples.
    if n_total and len(out.split()) < 0.95*len(txt.split()):
        raise ValueError("Unreasonable article body reduction")
    return out,n_total

def target_templates(app:Path)->dict[str,Path]:
    if app != APP or app.is_symlink() or not (app/"manage.py").is_file():
        raise ValueError("Not the authorized personal Django V17 root")
    base=app/"templates"/"personal_site"
    if base.is_symlink() or not base.is_dir():raise ValueError("Personal templates missing")
    paths={}
    for p in sorted(base.rglob("*.html")):
        if p.is_symlink() or not p.is_file():raise ValueError("Symlink in personal template tree")
        key=str(p.relative_to(app))
        paths[key]=p
    if not 10<=len(paths)<=70:raise ValueError("Unexpected personal template inventory size")
    for name in ("base.html","core/home.html","core/posts.html","core/detail.html","core/about.html"):
        if "templates/personal_site/"+name not in paths:raise ValueError("Protected original template absent")
    return paths

def media_inventory(app:Path):
    roots=[app/"static"/"personal_site",app/"media",app/"staticfiles"/"personal_site"]
    ret={}
    for root in roots:
        if not root.is_dir() or root.is_symlink():continue
        for p in root.rglob("*"):
            if p.is_symlink():raise ValueError("Unexpected image symlink")
            if p.is_file() and p.suffix.lower() in (".jpg",".jpeg",".png",".webp",".svg",".avif"):
                ret[str(p.relative_to(app))]=sha(p.read_bytes())
    if len(ret)<MIN_IMAGES:raise ValueError("Photo inventory lower than verified baseline")
    return ret

def django_init(app):
    sys.path.insert(0,str(app))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    import django;django.setup()
    from django.template import engines
    from core.models import Post
    return engines,Post

def db_inventory(Post):
    rows=list(Post.objects.all().order_by("pk").values("pk","slug","content","published"))
    published=sum(bool(r["published"]) for r in rows)
    if published<MIN_POSTS:raise ValueError("Published article inventory reduced")
    return rows,published

def plan(app):
    paths=target_templates(app)
    engines,Post=django_init(app)
    old={p:path.read_text(encoding="utf-8") for p,path in paths.items()}
    changed={}
    for name,before in old.items():
        after,report=clean_template(before)
        if after==before:continue
        engines["django"].engine.from_string(after)
        if len(after)<len(before)*0.86:raise ValueError("Excessive template removal: "+name)
        # Protection of article indexes, original photographs and enterprise sections.
        for marker in ("mpw-primary-personal-profile-20261016",
          "mpw-fifty-editorials-20261015",
          "mpw-academic-profile-20261016",
          "mpw-five-smart-web-portraits-20261016",
          "mpw-enterprise-v18-20261016"):
            if before.count(marker)!=after.count(marker):raise ValueError("Protected section lost: "+marker)
        changed[name]={"before":before,"after":after,"report":report}
    rows,published=db_inventory(Post)
    db_changes={}
    for row in rows:
        if not row["published"]:continue
        after,n=clean_post_content(row["content"] or "")
        if n:db_changes[str(row["pk"])]={"pk":row["pk"],"slug":row["slug"],"before":row["content"],"after":after,"count":n}
    if not changed and not db_changes:raise ValueError("No approved editorial scaffolding found")
    photos=media_inventory(app)
    report={"templates_scanned":len(paths),"templates_to_clean":len(changed),
      "published_posts":published,"article_bodies_to_clean":len(db_changes),
      "assets_protected":len(photos),
      "template_hits":{k:v["report"] for k,v in changed.items()},
      "article_slugs":[v["slug"] for v in db_changes.values()]}
    return paths,changed,db_changes,rows,photos,report,Post

def audit(app):
    _,_,_,_,_,report,_=plan(app)
    print("PERSONAL_VISIBLE_PRODUCTION_NOTES_AUDIT="+json.dumps(report,ensure_ascii=False),flush=True)

def install(app:Path,backup:Path):
    paths,changed,db_changes,rows,photos,report,Post=plan(app)
    if backup.is_symlink() or backup.exists():raise ValueError("Backup target occupied")
    backup.mkdir(parents=True,mode=0o700)
    save=backup/"templates";save.mkdir(mode=0o700)
    state={"templates":{},"posts":{},"all_posts_sha256":sha(json.dumps(rows,sort_keys=True,default=str).encode()),
           "protected_images":photos,"published_posts":report["published_posts"],"audit":report}
    for i,(name,v) in enumerate(changed.items()):
        dest=save/(str(i)+".html")
        dest.write_text(v["before"],encoding="utf-8")
        dest.chmod(0o600)
        if dest.read_bytes()!=v["before"].encode():raise ValueError("Unverified template backup")
        state["templates"][name]={"backup_file":dest.name,"before":sha(v["before"].encode()),"after":sha(v["after"].encode())}
    for pk,v in db_changes.items():
        state["posts"][pk]={"slug":v["slug"],"original":v["before"],"before":sha(v["before"].encode()),"after":sha(v["after"].encode())}
    (backup/"manifest.json").write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")
    (backup/"manifest.json").chmod(0o600)
    print("PERSONAL_CLEANUP_BACKUP_VERIFIED=yes",flush=True)
    from django.db import transaction
    done=[]
    try:
        with transaction.atomic():
            for name,v in changed.items():
                if sha(paths[name].read_bytes())!=state["templates"][name]["before"]:
                    raise ValueError("Concurrent template modifications")
            for pk,v in db_changes.items():
                if Post.objects.filter(pk=int(pk),slug=v["slug"],content=v["before"]).count()!=1:
                    raise ValueError("Concurrent article content modifications")
            for name,v in changed.items():
                p=paths[name];tmp=p.with_name(p.name+".clean-production-staging")
                if tmp.exists() or tmp.is_symlink():raise ValueError("Temporary file collision")
                tmp.write_text(v["after"],encoding="utf-8")
                os.chmod(tmp,p.stat().st_mode&0o777)
                if sha(tmp.read_bytes())!=state["templates"][name]["after"]:raise ValueError("Staging mismatch")
                os.replace(tmp,p);done.append(name)
            for pk,v in db_changes.items():
                if Post.objects.filter(pk=int(pk),content=v["before"]).update(content=v["after"])!=1:
                    raise ValueError("Article update race")
            if photos!=media_inventory(app):raise ValueError("Photographic inventory changed")
            if db_inventory(Post)[1]!=report["published_posts"]:raise ValueError("Article count changed")
    except BaseException:
        for name in done:
            p=paths[name]
            m=state["templates"][name]
            if sha(p.read_bytes())==m["after"]:
                shutil.copy2(save/m["backup_file"],p)
        raise
    print("PERSONAL_CLEANUP_INSTALLED=yes",flush=True)
    print("PERSONAL_CLEANUP_TEMPLATE_COUNT="+str(len(changed)),flush=True)
    print("PERSONAL_CLEANUP_POST_BODIES="+str(len(db_changes)),flush=True)
    print("PERSONAL_CLEANUP_BACKUP_PATH="+str(backup),flush=True)

def verify(app:Path,backup:Path):
    paths=target_templates(app);_,Post=django_init(app)
    state=json.loads((backup/"manifest.json").read_text(encoding="utf-8"))
    for name,m in state["templates"].items():
        if sha(paths[name].read_bytes())!=m["after"]:raise ValueError("Template verification mismatch: "+name)
    for pk,m in state["posts"].items():
        s=Post.objects.get(pk=int(pk))
        if s.slug!=m["slug"] or sha(s.content.encode())!=m["after"]:
            raise ValueError("Post content check failed")
    if state["protected_images"]!=media_inventory(app):raise ValueError("Image hash changed")
    if db_inventory(Post)[1]!=state["published_posts"]:raise ValueError("Post count changed")
    print("PERSONAL_CLEANUP_VERIFIED=yes",flush=True)
    print("PERSONAL_PROTECTED_POST_COUNT="+str(state["published_posts"]),flush=True)
    print("PERSONAL_PROTECTED_IMAGE_COUNT="+str(len(state["protected_images"])),flush=True)
    print("PERSONAL_CLEANUP_CHANGED_TEMPLATES="+str(len(state["templates"])),flush=True)

def rollback(app:Path,backup:Path):
    paths=target_templates(app);_,Post=django_init(app)
    state=json.loads((backup/"manifest.json").read_text(encoding="utf-8"))
    for name,m in state["templates"].items():
        old=(backup/"templates"/m["backup_file"]).read_bytes()
        if sha(old)!=m["before"] or sha(paths[name].read_bytes()) not in (m["after"],m["before"]):
            raise ValueError("Unsafe concurrent edit or invalid backup; refuse rollback")
    for pk,m in state["posts"].items():
        row=Post.objects.get(pk=int(pk))
        if row.slug!=m["slug"] or sha(row.content.encode()) not in (m["after"],m["before"]):
            raise ValueError("Article changed after installation")
    from django.db import transaction
    with transaction.atomic():
        for pk,m in state["posts"].items():
            row=Post.objects.get(pk=int(pk))
            if Post.objects.filter(pk=row.pk,slug=m["slug"],content=row.content).update(content=m["original"])!=1:
                raise ValueError("Cannot safely recover article")
        for name,m in state["templates"].items():
            p=paths[name];tmp=p.with_name(p.name+".clean-production-rollback")
            if tmp.exists() or tmp.is_symlink():raise ValueError("Rollback collision")
            shutil.copy2(backup/"templates"/m["backup_file"],tmp)
            os.replace(tmp,p)
    if (app/"tmp").is_dir():(app/"tmp"/"restart.txt").touch()
    print("PERSONAL_CLEANUP_ROLLBACK_VERIFIED=yes",flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("audit","install","verify","rollback"))
    p.add_argument("--app",type=Path,default=APP)
    p.add_argument("--backup",type=Path)
    a=p.parse_args()
    if a.action=="audit":audit(a.app)
    else:
        if a.backup is None:p.error("backup required")
        if a.action=="install":install(a.app,a.backup)
        elif a.action=="verify":verify(a.app,a.backup)
        else:rollback(a.app,a.backup)
if __name__=="__main__":main()
