#!/usr/bin/env python3
"""Additive service briefing and contact-form path for Mojtaba personal V17.

No Django model writes, routes, contact form edits, payment, assets, or changes
outside the three personal-site template files. SHA-guarded restore.
"""
from __future__ import annotations
import argparse, hashlib, html, importlib.util, json, os, re, shutil, sys
from pathlib import Path

APP=Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
TEMPLATES={"home":"home.html","posts":"posts.html","detail":"detail.html"}
MARK='id="mpw-enterprise-collaboration-brief-20261016"'
DETAIL_MARK='id="mpw-enterprise-collaboration-contact-20261016"'
CONTACT="/mojtaba.roozegar/contact/"
PROTECTED=(
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
)
OFFERS=(
 ("Enterprise Web Discovery and Systems Architecture",
  "For organizations considering a new customer, procurement or internal business portal.",
  "Stakeholder map, user-role and data-flow diagrams, risk register, prioritized backlog and a tested task prototype.",
  "https://mojplaywin.com/mojtaba.roozegar/blog/listen-before-code-professional-enterprise-website-discovery/"),
 ("Secure Multi-Organization B2B Portal",
  "For suppliers, distributors and commercial teams with separate customers, prices or approvals.",
  "Tenant permission matrix, quotation or approval pilot, idempotent workflow tests and source-of-truth integration plan.",
  "https://mojplaywin.com/mojtaba.roozegar/blog/enterprise-b2b-commerce-web-trust-and-order-integrity/"),
 ("Read-Only Industrial Information Dashboard",
  "For manufacturers or facilities seeking understandable, authorized telemetry visibility.",
  "Measurement and freshness schema, synthetic dashboard, read-only integration boundary and disconnected-source tests.",
  "https://mojplaywin.com/mojtaba.roozegar/blog/industrial-data-dashboards-operational-truth-and-refresh/"),
 ("Source-Grounded Enterprise AI Knowledge Assistant",
  "For teams exploring document search and evidence-backed internal answers.",
  "Approved-source retrieval pilot, passage citations, permission abuse cases and an evaluated question set.",
  "https://mojplaywin.com/mojtaba.roozegar/blog/ai-powered-enterprise-websites-source-grounded-automation/"),
 ("Accessible User Experience and Website Assurance",
  "For enterprises needing clearer critical workflows, appropriate WCAG practices and permission checks.",
  "One redesigned accessible journey, testable components, keyboard review, risk cases and a correction backlog.",
  "https://mojplaywin.com/mojtaba.roozegar/blog/professional-ui-ux-workshops-for-enterprise-portals/"),
 ("Website Modernization, CI/CD and Resilience",
  "For organizations improving existing websites while avoiding risky broad replacements.",
  "Dependency inventory, guarded release process, route-level checks, rollback rehearsal and phased migration proposal.",
  "https://mojplaywin.com/mojtaba.roozegar/blog/cloud-hosting-continuous-delivery-enterprise-web-reliability/"),
)
def sha(x:bytes):return hashlib.sha256(x).hexdigest()
def photo_rows(content:Path):
    src=content.parent/"scripts/mojtaba_twenty_photo_essays_safe_publish.py"
    if not src.is_file() or src.is_symlink():raise ValueError("Original publishing script missing")
    spec=importlib.util.spec_from_file_location("existing_photo20",src)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    rows=m.load_articles(content);older=m.load_older(content)
    if len(rows)!=20 or len(older)!=73 or len(set(older))!=73:
        raise ValueError("Expected all 93 independent articles")
    return rows,older

def site_templates(app:Path):
    if app.is_symlink() or not (app/"manage.py").is_file():
        raise ValueError("Independent personal V17 app not found")
    root=app/"templates/personal_site/core"
    out={}
    for k,name in TEMPLATES.items():
        p=root/name
        if p.is_symlink() or not p.is_file():raise ValueError("Unsafe template file")
        out[k]=p
    return out

def card_section():
    parts=[
    '<section '+MARK+' aria-labelledby="mpw-collab-brief-title" style="max-width:1200px;margin:36px auto;padding:clamp(19px,3vw,36px);background:#141413;color:#f8e9d2;border:3px solid #c9a369;border-radius:16px;clear:both">',
    '<p style="font:700 13px/1.6 system-ui,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:#e5be82">Open to technical discussion • Vancouver / international teams</p>',
    '<h2 id="mpw-collab-brief-title" style="font:700 clamp(27px,3.3vw,42px)/1.22 Georgia,serif;color:#f1d09a">Intelligent Enterprise Website Collaboration</h2>',
    '<p style="font:17px/1.8 system-ui,sans-serif;max-width:1020px">I am open to discussing research-led, professional web development for industrial and commercial organizations, including teams based in Vancouver. These proposed pilot formats provide practical ways to explore a specific technical challenge. Each engagement would require verified scope, technical ownership and applicable contracting arrangements.</p>',
    '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,335px),1fr));gap:15px;margin:23px 0">'
    ]
    for n,(title,fit,deliverable,link) in enumerate(OFFERS,1):
        parts.append('<article style="padding:21px;background:#29251f;border:1px solid #ab895a;border-radius:12px">'
            '<p style="color:#d5ad75;font:700 14px system-ui,sans-serif">PROPOSAL '+str(n).zfill(2)+'</p>'
            '<h3 style="font:600 23px/1.4 Georgia,serif;color:#f2d19b">'+html.escape(title)+'</h3>'
            '<p style="font:15px/1.75 system-ui,sans-serif">'+html.escape(fit)+'</p>'
            '<p style="font:15px/1.75 system-ui,sans-serif"><strong>Possible first deliverable:</strong> '+html.escape(deliverable)+'</p>'
            '<a href="'+html.escape(link,quote=True)+'" style="color:#f3d3a0;text-decoration:underline;text-underline-offset:3px">Read the relevant technical article</a>'
            '</article>')
    parts.extend([
        '</div>',
        '<h3 style="font:600 23px Georgia,serif;color:#f2d19b">A careful four-step engagement path</h3>',
        '<ol style="display:grid;gap:9px;padding-left:26px;font:16px/1.7 system-ui,sans-serif">'
        '<li><strong>Initial inquiry:</strong> explain the organization, problem and preferred virtual contact.</li>'
        '<li><strong>Discovery:</strong> review users, current systems, risk, delivery boundaries and available evidence.</li>'
        '<li><strong>Scoped pilot:</strong> agree on deliverables, acceptance tests, cost and legal/technical prerequisites.</li>'
        '<li><strong>Evaluation:</strong> review prototype evidence and decide whether to revise, stop or expand.</li></ol>',
        '<p style="font:15px/1.8 system-ui,sans-serif">Do not send credentials, confidential records or personal documents in an introductory message. Availability, legal eligibility, paid terms and any on-site activity must be confirmed separately.</p>',
        '<p style="margin-top:24px"><a href="'+CONTACT+'" style="display:inline-block;background:#dfb975;color:#191716;border-radius:9px;padding:15px 22px;font:700 17px system-ui,sans-serif;text-decoration:none">Send a collaboration inquiry through the existing contact form →</a></p>',
        '</section>'
    ])
    return "\n".join(parts)

def detail_section(rows):
    out=['{% if kind == "Article" %}']
    for i,r in enumerate(rows):
        out.append(("{% if" if i==0 else "{% elif")+' item.slug == "'+r["slug"]+'" %}')
        out.append('<aside '+DETAIL_MARK+' aria-label="Discuss a professional collaboration" style="clear:both;background:#211e1a;border:2px solid #c19c63;border-radius:12px;margin:30px auto;max-width:1100px;padding:24px;color:#f7e6ce">'
                   '<h2 style="color:#efd09f;font:600 25px/1.4 Georgia,serif">Discuss a related enterprise website pilot</h2>'
                   '<p style="font:16px/1.8 system-ui,sans-serif">Interested in exploring the ideas in this article for an industrial, commercial or research website? An introductory discussion can identify a specific problem, the responsible technical team and a limited pilot. A useful introductory discussion begins with a business problem, the responsible team and a realistic pilot.</p>'
                   '<a href="'+CONTACT+'" style="display:inline-block;background:#dbb57b;color:#21190e;padding:12px 19px;border-radius:8px;font:700 16px system-ui,sans-serif;text-decoration:none">Open the existing contact form →</a>'
                   '</aside>')
    out.extend(['{% endif %}','{% endif %}'])
    return "\n".join(out)

def patch(key,old,rows):
    if MARK in old or DETAIL_MARK in old:raise ValueError("Collaboration brief already installed")
    token="{% block content %}"
    if old.count(token)!=1:raise ValueError("Unrecognized personal template")
    start=old.index(token)+len(token);end=old.find("{% endblock %}",start)
    if end<0:raise ValueError("Content block end absent")
    if key in ("home","posts"):
        for mark in PROTECTED:
            if old.count(mark)!=1:raise ValueError("Existing page content not preserved: "+mark)
        added=card_section()
        if added.count("Read the relevant technical article")!=6:
            raise ValueError("Six unique documented offers expected")
    elif key=="detail":
        if old.count('id="mpw-mojtaba-essay-cover-20261016"')!=20 or old.count('id="mpw-photoessay-related-20261016"')!=20:
            raise ValueError("Prior twenty images/related article recommendations must exist")
        if "{{ item.title" not in old or 'id="mpw-journal-related-20261016"' not in old:
            raise ValueError("Original detail article content altered")
        added=detail_section(rows)
        if added.count(DETAIL_MARK)!=20:raise ValueError("Twenty contextual contact links expected")
    else:raise ValueError("Non-allowlisted template")
    return old[:end]+"\n"+added+"\n"+old[end:]

def check_django(app:Path,rows,older):
    sys.path.insert(0,str(app));os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    import django;django.setup()
    from django.template import engines
    from core.models import Post
    if Post.objects.filter(slug__in=older,published=True).count()!=73:raise ValueError("Older articles missing")
    if Post.objects.filter(slug__in=[a["slug"] for a in rows],published=True).count()!=20:raise ValueError("Illustrated articles missing")
    return engines

def install(app:Path,content:Path,backup:Path):
    rows,older=photo_rows(content);paths=site_templates(app)
    original={k:p.read_text(encoding="utf-8") for k,p in paths.items()}
    edited={k:patch(k,v,rows) for k,v in original.items()}
    engines=check_django(app,rows,older)
    for k,v in edited.items():
        engines["django"].engine.from_string(v)
        print("COLLAB_INQUIRY_DJANGO_TEMPLATE_VALID="+k,flush=True)
    if backup.exists() or backup.is_symlink():raise ValueError("Backup path collision")
    backup.mkdir(parents=True,mode=0o700)
    hashes={}
    for k,n in TEMPLATES.items():
        (backup/n).write_text(original[k],encoding="utf-8")
        (backup/n).chmod(0o600)
        hashes[k]={"before":sha(original[k].encode()),"after":sha(edited[k].encode())}
    (backup/"manifest.json").write_text(json.dumps({"template_hashes":hashes,"post_count":93},indent=2),encoding="utf-8")
    (backup/"manifest.json").chmod(0o600)
    done=[]
    try:
        for k,p in paths.items():
            if sha(p.read_bytes())!=hashes[k]["before"]:raise ValueError("Template changed during publication")
            tmp=p.with_name(p.name+".collab-inquiry")
            if tmp.exists() or tmp.is_symlink():raise ValueError("Staging collision")
            tmp.write_text(edited[k],encoding="utf-8")
            tmp.chmod(p.stat().st_mode&0o777)
            os.replace(tmp,p)
            done.append(k)
    except BaseException:
        for k in done:
            p=paths[k]
            if sha(p.read_bytes())==hashes[k]["after"]:
                shutil.copy2(backup/TEMPLATES[k],p)
        raise
    if (app/"tmp").is_dir():(app/"tmp/restart.txt").touch()
    print("COLLAB_INQUIRY_SECTION_ADDED=yes",flush=True)
    print("COLLAB_INQUIRY_DATABASE_AND_PHOTOS_UNCHANGED=yes",flush=True)
    print("COLLAB_INQUIRY_BACKUP="+str(backup),flush=True)

def rollback(app:Path,backup:Path):
    if backup.is_symlink() or not backup.is_dir():raise ValueError("Backup absent")
    state=json.loads((backup/"manifest.json").read_text())
    paths=site_templates(app)
    for k,p in paths.items():
        original=(backup/TEMPLATES[k]).read_bytes()
        if sha(original)!=state["template_hashes"][k]["before"] or sha(p.read_bytes())!=state["template_hashes"][k]["after"]:
            raise ValueError("Template modified since installation; refuse overwrite")
    for k,p in paths.items():
        tmp=p.with_name(p.name+".collab-revert")
        if tmp.exists() or tmp.is_symlink():raise ValueError("Restore staging conflict")
        shutil.copy2(backup/TEMPLATES[k],tmp)
        os.replace(tmp,p)
    if (app/"tmp").is_dir():(app/"tmp/restart.txt").touch()
    print("COLLAB_INQUIRY_GUARDED_ROLLBACK=yes",flush=True)

def main():
    a=argparse.ArgumentParser()
    a.add_argument("action",choices=("check","install","rollback"))
    a.add_argument("--app",type=Path,default=APP)
    a.add_argument("--content",type=Path)
    a.add_argument("--backup",type=Path)
    x=a.parse_args()
    if x.action=="rollback":
        if not x.backup:a.error("Backup required")
        rollback(x.app,x.backup);return
    if not x.content:a.error("Content folder required")
    rows,old=photo_rows(x.content)
    if x.action=="check":
        print("COLLAB_INQUIRY_ARTICLES_CONFIRMED="+str(len(rows)+len(old)),flush=True);return
    if not x.backup:a.error("Backup required")
    install(x.app,x.content,x.backup)
if __name__=="__main__":main()
