#!/usr/bin/env python3
"""Conservative professional-copy cleanup of the separate Mojtaba personal site.

Replace self-disclaimers next to owner portrait and remove redundant editorial
self-disclaimer sentences from native journal articles. Does not add factual
accomplishments, update routes/media/commerce, or delete an article. Every
affected file and row has SHA-backed, guarded rollback.
"""
from __future__ import annotations
import argparse,hashlib,html,importlib.util,json,os,re,shutil,sys
from pathlib import Path

APP=Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
PROFILE='id="mpw-primary-personal-profile-20261016"'
PHOTO_FIG='id="mpw-mojtaba-essay-cover-20261016"'
CONTACT='/mojtaba.roozegar/contact/'
PROFILE_COPY=("My work combines research, applied economics and the design of intelligent industrial and commercial websites. "
              "I welcome collaboration on enterprise platforms, data-driven services, practical AI systems and digital learning.")
CAPTION="Mojtaba Roozegar · Research and Intelligent Web Development"
TOPIC_CAPTION="Research, professional website development and digital technology"
PHOTO_CAPTION="Research, applied economics and intelligent website development"
IMAGE_CAPTION="Intelligent Enterprise Website Design"

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def posts_from_manifests(root:Path):
    src=root.parent/"scripts/mojtaba_twenty_photo_essays_safe_publish.py"
    if src.is_symlink() or not src.is_file():raise ValueError("Protected article manifest reader unavailable")
    spec=importlib.util.spec_from_file_location("personal_essays",src)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    photos=mod.load_articles(root)
    older=mod.load_older(root)
    slugs=older+[row["slug"] for row in photos]
    if len(slugs)!=93 or len(set(slugs))!=93:raise ValueError("Expected exactly 93 independent journal slugs")
    return slugs

def template_paths(app:Path):
    if app.is_symlink() or not (app/"manage.py").is_file():raise ValueError("Independent personal V17 missing")
    folder=app/"templates/personal_site/core"
    if folder.is_symlink() or not folder.is_dir():raise ValueError("Independent personal templates missing")
    paths={}
    for p in sorted(folder.glob("*.html")):
        if p.is_symlink() or not p.is_file():raise ValueError("Unexpected template symlink")
        paths[p.name]=p
    if not {"home.html","about.html","posts.html","detail.html"}<=set(paths):
        raise ValueError("Personal Home, About, Journal or Detail template missing")
    if len(paths)>30:raise ValueError("Unexpected large template scope")
    return paths

def is_editorial_disclaimer(sentence:str)->bool:
    s=sentence.lower().strip()
    if not s:return False
    photo=bool(re.search(r'\b(photo|photograph|portrait|picture|image|illustration|artwork|visual|collage|screenshot)\b',s))
    identity=bool(re.search(r'\b(vancouver|canadian|canada|residen|office|customer|client|contract|partner|commercial|project|business|location|credential|certificate|company|meeting|engagement|deployment|installation|employment|work authorization|claim)\b',s))
    negative=bool(re.search(r'\b(not|never|no|cannot|does not|do not|without|avoid|rather than|should not|isn.t|aren.t|unverified|unsupported)\b',s))
    # Disclaimers about photograph identity and project history; not normal scientific caveats.
    if photo and negative and (identity or re.search(r'\b(proof|evidence|record|document|demonstrat|verified|actual|real|assert)\b',s)):
        return True
    if identity and negative and re.search(r'\b(claim|implied|asserted|guaranteed|promis|evidence of|proof of)\b',s):
        return True
    if s.startswith(("editorial note:","author note:")) and negative and identity:
        return True
    return False

def trim_sentence(paragraph:str):
    chunks=re.split(r'(?<=[.!?])\s+(?=[A-Z0-9“"\'(])',paragraph)
    kept=[]
    for chunk in chunks:
        chunk=chunk.strip()
        if not chunk:continue
        if is_editorial_disclaimer(chunk):continue
        # Remove a self-referential trailing phrase, preserving educational content.
        chunk=re.sub(r',?\s+(?:without|rather than)\s+(?:claiming|asserting|implying|presenting)[^.!?]+(?=[.!?])','',chunk,flags=re.I)
        kept.append(chunk)
    return " ".join(kept).strip()

def clean_article_body(source:str):
    paragraphs=re.split(r'(\n\s*\n)',source)
    out=[]
    removed=0
    for block in paragraphs:
        if not block.strip() or block.startswith("\n"):out.append(block);continue
        updated=trim_sentence(block)
        if updated!=block.strip():removed+=1
        out.append(updated)
    result="".join(out)
    result=re.sub(r'\n{3,}',"\n\n",result).strip()
    # Keep instructional substance intact.
    if len(result.split())<max(170,int(len(source.split())*.77)):
        raise ValueError("Article cleanup would remove too much educational content")
    # Only visible prose, not CSS.
    if "۱۰۰٪" in result or re.search(r'(?<![\w])100\s*%',result):
        raise ValueError("Disallowed absolute-percentage wording remains in article")
    return result,removed

def replace_profile_block(source:str):
    if PROFILE not in source:return source,0
    if source.count(PROFILE)!=1:raise ValueError("Multiple owner profile sections")
    start=source.index(PROFILE)
    finish=source.find("</section>",start)
    if finish<0:raise ValueError("Profile section end missing")
    end=finish+len("</section>")
    section=source[start:end]
    original=section
    # The exact introductory paragraph shown below the chosen professional photograph.
    pat=r'<p\b[^>]*>\s*This is a personal photograph selected by the profile owner\.\s*It is not presented as\s*evidence of a Vancouver office or a completed client project\.\s*</p>'
    section,n=re.subn(pat,'<p style="font:15px/1.8 system-ui,sans-serif">'+PROFILE_COPY+'</p>',section,flags=re.I|re.S)
    if n!=1:raise ValueError("Owner profile unwanted paragraph changed from expected source")
    section=section.replace("Official owner-selected profile photograph",CAPTION)
    if section==original:raise ValueError("Owner portrait copy not changed")
    return source[:start]+section+source[end:],1

def template_copy(source:str):
    out,num=replace_profile_block(source) if PROFILE in source else (source,0)
    known_replacements=(
        ("The image is not proof of a Vancouver office, professional engagement or completed enterprise project.",PHOTO_CAPTION+"."),
        ("Conceptual visualization · not an actual client installation",IMAGE_CAPTION),
        ("Conceptual visualization · not an actual client project",IMAGE_CAPTION),
        ("These articles propose possible pilot projects; they do not claim existing clients, a Canadian office or work authorization.", "Explore practical project ideas and potential collaboration paths."),
        ("The following are proposed pilot formats, not completed client contracts, a claimed Canadian office, fixed offers or guaranteed results.", "Each proposal begins with project discovery, technical planning and measurable deliverables."),
        ("This is an invitation, not an existing Vancouver project or guaranteed service.", "Explore a practical collaboration based on a clearly defined project scope."),
        ("Images document editorial themes, not client contracts.", "Images accompany the research and professional topics."),
        ("A discussion would start with project scope, not an assumption of an existing Vancouver engagement.", "A conversation can begin with the project scope and business needs."),
        ("The illustration communicates a collaborative design method; it does not claim an existing customer agreement or a completed redesign project.",TOPIC_CAPTION+"."),
    )
    for old,new in known_replacements:
        if old in out:
            n=out.count(old);out=out.replace(old,new);num+=n
    # Some source photo captions use a distinct second wording.
    out=out.replace("Personal portrait or illustrative digital artwork supplied for this essay. The image is not proof of a Vancouver office, professional engagement or completed enterprise project.",
        "Professional portrait and creative illustration for an article on research and intelligent website development.")
    # Purposely avoid touching any CSS percentage declarations or route/schema code.
    return out,num

def get_rows(app:Path,slugs:list[str]):
    sys.path.insert(0,str(app))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    import django;django.setup()
    from core.models import Post
    from django.template import engines
    records=list(Post.objects.filter(slug__in=slugs,published=True).order_by("slug"))
    if len(records)!=93 or {x.slug for x in records}!=set(slugs):
        raise ValueError("Some of the 93 original published articles are missing")
    return records,engines

def plan(app:Path,content:Path):
    slugs=posts_from_manifests(content)
    paths=template_paths(app)
    records,engines=get_rows(app,slugs)
    existing={k:p.read_text(encoding="utf-8") for k,p in paths.items()}
    edited={}
    for name,src in existing.items():
        after,n=template_copy(src)
        if after!=src:
            engines["django"].engine.from_string(after)
            edited[name]=(src,after,n)
    if "home.html" not in edited or "about.html" not in edited:
        raise ValueError("Profile copy already changed or not present; do not overwrite")
    updated=[]
    for row in records:
        after,n=clean_article_body(row.content)
        if after!=row.content:
            updated.append((row,after,n))
    if not updated:raise ValueError("No original editorial body changes identified")
    print("EDITORIAL_COPY_TARGET_TEMPLATES="+str(len(edited)),flush=True)
    print("EDITORIAL_COPY_UPDATED_ARTICLES="+str(len(updated)),flush=True)
    print("EDITORIAL_COPY_ORIGINAL_POSTS=93",flush=True)
    return paths,edited,updated

def install(app:Path,content:Path,backup:Path):
    paths,edited,updated=plan(app,content)
    if backup.exists() or backup.is_symlink():raise ValueError("Backup folder collision")
    backup.mkdir(parents=True,mode=0o700)
    state={"templates":{},"articles":[]}
    for name,(old,new,n) in edited.items():
        file=backup/name
        file.write_text(old,encoding="utf-8");file.chmod(0o600)
        state["templates"][name]={"before":sha(old.encode()),"after":sha(new.encode()),"changes":n}
    for row,new,n in updated:
        state["articles"].append({"slug":row.slug,"before":sha(row.content.encode()),"after":sha(new.encode()),"original":row.content,"changes":n})
    (backup/"manifest.json").write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")
    (backup/"manifest.json").chmod(0o600)
    changed=[]
    try:
        from django.db import transaction
        from core.models import Post
        with transaction.atomic():
            for row,new,_ in updated:
                n=Post.objects.filter(pk=row.pk,content=row.content).update(content=new)
                if n!=1:raise ValueError("Concurrent article edit; refuse write")
            for name,(old,new,_) in edited.items():
                path=paths[name]
                if sha(path.read_bytes())!=state["templates"][name]["before"]:
                    raise ValueError("Concurrent template edit; refuse write")
                tmp=path.with_name(path.name+".copy-cleanup-new")
                if tmp.exists() or tmp.is_symlink():raise ValueError("Temporary template collision")
                tmp.write_text(new,encoding="utf-8")
                tmp.chmod(path.stat().st_mode&0o777)
                os.replace(tmp,path)
                changed.append(name)
    except BaseException:
        for name in changed:
            path=paths[name]
            if sha(path.read_bytes())==state["templates"][name]["after"]:
                shutil.copy2(backup/name,path)
        raise
    if (app/"tmp").is_dir():(app/"tmp/restart.txt").touch()
    print("EDITORIAL_COPY_UPDATED_POSTS="+str(len(updated)),flush=True)
    print("EDITORIAL_COPY_UPDATED_TEMPLATES="+str(len(edited)),flush=True)
    print("EDITORIAL_COPY_PROFILE_DESCRIPTION_REPLACED=yes",flush=True)
    print("EDITORIAL_COPY_BACKUP="+str(backup),flush=True)

def rollback(app:Path,backup:Path):
    if backup.is_symlink() or not (backup/"manifest.json").is_file():raise ValueError("Backup missing")
    state=json.loads((backup/"manifest.json").read_text(encoding="utf-8"))
    paths=template_paths(app)
    slugs=[x["slug"] for x in state["articles"]]
    rows,_=get_rows(app,slugs + []) if len(slugs)==93 else (None,None)
    # In a bounded release some of the 93 unchanged posts were deliberately omitted:
    from core.models import Post
    records={x.slug:x for x in Post.objects.filter(slug__in=slugs,published=True)}
    if len(records)!=len(slugs):raise ValueError("One cleaned article no longer present")
    for r in state["articles"]:
        row=records[r["slug"]]
        if sha(row.content.encode())!=r["after"]:
            raise ValueError("Article changed since this release; refuse overwrite")
    for name,meta in state["templates"].items():
        if sha(paths[name].read_bytes())!=meta["after"] or sha((backup/name).read_bytes())!=meta["before"]:
            raise ValueError("Template changed since release; refuse overwrite")
    from django.db import transaction
    with transaction.atomic():
        for r in state["articles"]:
            if Post.objects.filter(pk=records[r["slug"]].pk,content=records[r["slug"]].content).update(content=r["original"])!=1:
                raise ValueError("Article rollback race")
        for name in state["templates"]:
            file=paths[name];tmp=file.with_name(file.name+".copy-cleanup-back")
            if tmp.exists() or tmp.is_symlink():raise ValueError("Restore staging conflict")
            shutil.copy2(backup/name,tmp);os.replace(tmp,file)
    if (app/"tmp").is_dir():(app/"tmp/restart.txt").touch()
    print("EDITORIAL_COPY_SAFE_ROLLBACK=yes",flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("check","install","rollback"))
    p.add_argument("--app",type=Path,default=APP)
    p.add_argument("--content",type=Path)
    p.add_argument("--backup",type=Path)
    a=p.parse_args()
    if a.action=="rollback":
        if not a.backup:p.error("Backup required")
        rollback(a.app,a.backup);return
    if not a.content:p.error("Manifests required")
    if a.action=="check":plan(a.app,a.content);return
    if not a.backup:p.error("Backup required")
    install(a.app,a.content,a.backup)
if __name__=="__main__":main()
