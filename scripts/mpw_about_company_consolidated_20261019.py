#!/usr/bin/env python3
"""Two-file, fail-closed About/Company semantic, SEO, visual and B2B repair.
Atomic writes with source-hash rollback. No .htaccess/Django/site-wide changes.
"""
from __future__ import annotations
import hashlib, html, json, os, re, stat, sys, tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request,urlopen

ROOT=Path("/home/zomorod2/mojplaywin.com")
PAGES=ROOT/"design-preview-20261017/mpw-ten-editorials-20261018/pages"
ABOUT=PAGES/"about.html"
COMPANY=PAGES/"company.html"
ROUTES=ROOT/".htaccess"
MARK="MPW_ABOUT_COMPANY_SEMANTIC_20261019_V2"
LOGO="/static/site/mojplaywin-coin-logo.420e0d1f954b.png"
HERO="/static/site/heroes/platform-home.4dd3ab6a401d.webp"
MAIL="support@mojplaywin.com"
BUSINESS='''<aside id="mpw-business-contact-20261019" class="mpw-business-contact" aria-label="Business and collaboration enquiries">
<h2>Business partnerships and collaboration</h2>
<p>For business proposals, licensing enquiries and professional collaboration, use our published contact channel. Include <strong>Business Partnership — MojPlayWin</strong> in the subject and describe your project and requested next step. Availability and response times are not guaranteed.</p>
<a href="mailto:support@mojplaywin.com?subject=Business%20Partnership%20-%20MojPlayWin">Email a business proposal →</a>
</aside>'''
GLOBAL_STYLES='''<style id="mpw-about-company-align-20261019">
.mpw-business-contact{box-sizing:border-box;margin:24px auto;padding:clamp(20px,3.5vw,38px);border:1px solid #d6ad55;border-radius:18px;max-width:1240px;background:linear-gradient(135deg,#12140f,#282011);color:#f5f0e4;box-shadow:0 16px 42px #0005}
.mpw-business-contact h2{font-size:clamp(1.45rem,2.8vw,2rem);line-height:1.3;color:#f5d794;margin:0 0 .8rem}
.mpw-business-contact p{line-height:1.8;color:#f0e7d6;max-width:90ch}
.mpw-business-contact a{display:inline-block;border:1px solid #e6bf69;border-radius:12px;padding:12px 16px;background:#d6ad55;color:#1a1308!important;text-decoration:none;font-weight:750}
.mpw-business-contact a:focus-visible{outline:3px solid #fff3ce;outline-offset:4px}
body.mpw-company-harmonized,body.mpw-company-harmonized main{background:#050608!important;color:#f5f0e4!important;color-scheme:dark}
body.mpw-company-harmonized .mw-site-nav{background:rgba(13,13,11,.96)!important;border:1px solid #826738!important;border-radius:18px;box-shadow:0 12px 40px #0005}
body.mpw-company-harmonized .mw-page-hero,body.mpw-company-harmonized .mw-section{background:linear-gradient(145deg,#16140e,#090b0c)!important;border:1px solid #77603a!important;color:#f5f0e4!important}
body.mpw-company-harmonized .mw-card{background:linear-gradient(155deg,#191914,#101211)!important;border-color:#7e663d!important}
body.mpw-company-harmonized .mw-page-hero h2{font-size:clamp(1.8rem,4vw,3.3rem);line-height:1.2;color:#f7e5c6}
body.mpw-company-harmonized .mw-site-nav a,body.mpw-company-harmonized .mw-section a{color:#f4d28c}
body.mpw-company-harmonized .mw-section p,body.mpw-company-harmonized .mw-page-hero p{color:#e7ded0}
body.mpw-company-harmonized .mw-brand img{width:48px;height:48px;object-fit:contain}
body.mpw-company-harmonized .mw-page-hero img{max-width:100%;height:auto;display:block;object-fit:cover}
#mpw-company-owner-crosslink-20261019>h1{font-size:clamp(2rem,4.2vw,3.3rem);line-height:1.2;color:#ffe3a5}
.mpw-company-about .mw-page-hero>h1{font-size:clamp(2rem,4.2vw,3.3rem);line-height:1.12;color:#f6e0aa;margin:.5em 0}
.mpw-page-hero>h2{font-size:clamp(1.8rem,3vw,2.7rem);line-height:1.25}
@media(max-width:640px){.mpw-business-contact{margin:18px 10px;padding:20px 16px}body.mpw-company-harmonized .mw-page-hero{padding:22px 18px}}
@media(prefers-reduced-motion:reduce){.mpw-business-contact *,body.mpw-company-harmonized *{scroll-behavior:auto!important;transition:none!important}}
</style>'''
COMPANY_TITLE="Company Overview | MojPlayWin — Leadership, Services & Governance"
COMPANY_DESC="MojPlayWin company overview: leadership by owner and CEO Mojtaba Roozegar, limited-liability structure, digital products, research, games, company standards and business contact."
ABOUT_DESC="Discover MojPlayWin: its owner and CEO Mojtaba Roozegar, limited-liability company identity, original games, responsible AI, research, software, and independent digital publishing."

def fail(msg): raise RuntimeError(msg)
def sha(b):return hashlib.sha256(b).hexdigest()
def unique(s,a,b,label):
    n=s.count(a)
    if n!=1:fail(label+" expected exactly one target, found "+str(n))
    return s.replace(a,b,1)
def edit_tag(s,pat,replacer,label):
    matches=list(re.finditer(pat,s,re.I|re.S))
    if len(matches)!=1:fail(label+" unique tag check failed: "+str(len(matches)))
    m=matches[0]
    return s[:m.start()]+replacer(m)+s[m.end():]
def set_description(doc,description):
    pattern=r'<meta\b(?=[^>]*\bname=["\x27]description["\x27])[^>]*>'
    def repl(m):
        tag=m.group()
        new,n=re.subn(r'(\bcontent\s*=\s*)(["\x27])[\s\S]*?\2',
          lambda a:a.group(1)+a.group(2)+html.escape(description,quote=True)+a.group(2),
          tag,count=1,flags=re.I)
        if n!=1:fail("Description lacks a content attribute")
        return new
    return edit_tag(doc,pattern,repl,"description")
def metadata_company(doc):
    doc=edit_tag(doc,r'<title\b[^>]*>[\s\S]*?</title>',
         lambda m:"<title>"+html.escape(COMPANY_TITLE)+"</title>","Company title")
    doc=set_description(doc,COMPANY_DESC)
    # One canonical of its own; no index-collapsing redirect or duplicate page.
    if not re.search(r'rel=["\x27]canonical["\x27][^>]*href=["\x27]https://mojplaywin.com/company/["\x27]',doc,re.I):
        fail("Company canonical unexpectedly changed")
    if "mpw-company-og-20261019" in doc or "application/ld+json" in doc:
        fail("Unexpected preexisting company metadata, review manually")
    injected=(
        '<meta id="mpw-company-og-20261019" property="og:type" content="website">\n'
        '<meta property="og:site_name" content="MojPlayWin">\n'
        '<meta property="og:title" content="'+html.escape(COMPANY_TITLE,quote=True)+'">\n'
        '<meta property="og:description" content="'+html.escape(COMPANY_DESC,quote=True)+'">\n'
        '<meta property="og:url" content="https://mojplaywin.com/company/">\n'
        '<meta property="og:image" content="https://mojplaywin.com'+LOGO+'">\n'
        '<meta name="twitter:card" content="summary">\n'
        '<meta name="twitter:title" content="'+html.escape(COMPANY_TITLE,quote=True)+'">\n'
        '<meta name="twitter:description" content="'+html.escape(COMPANY_DESC,quote=True)+'">\n'
        '<meta name="twitter:image" content="https://mojplaywin.com'+LOGO+'">\n'
        '<script type="application/ld+json" id="mpw-company-schema-20261019">'+
        json.dumps({"@context":"https://schema.org","@type":"AboutPage",
        "name":"MojPlayWin company overview",
        "url":"https://mojplaywin.com/company/","inLanguage":"en",
        "mainEntity":{"@type":"Organization","name":"MojPlayWin",
        "url":"https://mojplaywin.com/","legalForm":"Limited liability company",
        "founder":{"@type":"Person","name":"Mojtaba Roozegar"},
        "contactPoint":{"@type":"ContactPoint","contactType":"Business enquiries (via published support channel)","email":MAIL}}},ensure_ascii=False,separators=(',',':'))+
        '</script>\n')
    if doc.lower().count("</head>")!=1:fail("No single head end")
    doc=unique(doc,"</head>",injected+"</head>","company SEO injection")
    doc=edit_tag(doc,r'<meta\b(?=[^>]*\bname=["\x27]theme-color["\x27])[^>]*>',
       lambda m:re.sub(r'(content=["\x27])[^"\x27]*',r'\g<1>#050608',m.group(),count=1),
       "theme color")
    return doc
def add_business(doc,where):
    if doc.count('id="mpw-business-contact-20261019"'):fail("Business CTA already installed")
    if where=="about":
        # Insert directly before the original company research dossier rather than
        # inside the two nested disclosure sections, preserving all original research.
        needle='<details id="mpw-advanced-research"'
        pos=doc.find(needle)
        if pos<0:fail("About advanced dossier start changed")
        return doc[:pos]+BUSINESS+"\n"+doc[pos:]
    needle='<section id="mpw-company-owner-crosslink-20261019"'
    # Public live source normally serializes attributes differently; use bounded ID.
    hit=re.search(r'<section\b[^>]*\bid=["\x27]mpw-company-owner-crosslink-20261019["\x27][^>]*>',doc,re.I)
    if not hit:fail("Company owner section not found")
    close=doc.find("</section>",hit.end())
    if close<0:fail("Company owner section not closed")
    at=close+len("</section>")
    return doc[:at]+"\n"+BUSINESS+doc[at:]
def fix_about(doc):
    if doc.count("MPW_ABOUT_REMEDIATION_20261019_V1")!=1 or doc.count("MPW_COMPANY_FOUNDER_POLISH_20261019_V1")!=1:
        fail("Pinned live About editions missing")
    doc=unique(doc,"<h2>Our complete company profile</h2>","<h1>About MojPlayWin</h1>","About main H1")
    doc=unique(doc,"<h1>About MojPlayWin</h1>","<h2>MojPlayWin gaming and creative direction</h2>","Legacy gaming H1")
    # The replace above would match the newly introduced H1 first: correct order with
    # positional confirmation is enforced in unit tests; fix explicitly below instead.
    return doc
def patch_about(doc):
    if doc.count("MPW_ABOUT_REMEDIATION_20261019_V1")!=1 or doc.count("MPW_COMPANY_FOUNDER_POLISH_20261019_V1")!=1:
        fail("Known approved About editions missing")
    a="<h2>Our complete company profile</h2>"
    b="<h1>About MojPlayWin</h1>"
    if doc.count(a)!=1 or doc.count(b)!=1:fail("Unexpected H1/hero source shape")
    # Replace both at once, before injecting any other markup with the same text.
    doc=doc.replace(b,"<h2>MojPlayWin gaming and creative direction</h2>",1)
    doc=doc.replace(a,"<h1>About MojPlayWin</h1>",1)
    doc=set_description(doc,ABOUT_DESC)
    doc=add_business(doc,"about")
    return doc
def patch_company(doc):
    if doc.count("MPW_COMPANY_FOUNDER_POLISH_20261019_V1")!=1:fail("Company owner banner missing")
    if doc.count('class="mpw-ten-card"')!=10:fail("Original Company guides changed")
    old='<h2 id="mpw-company-owner-title">A limited liability company owned and led by Mojtaba Roozegar</h2>'
    new='<h1 id="mpw-company-owner-title">MojPlayWin — Company Overview</h1>'
    doc=unique(doc,old,new,"Company first heading")
    doc=unique(doc,"<h1>About MojPlayWin</h1>",
      "<h2>Digital business, research and development</h2>","Company legacy hero")
    # Replace only About-labeled nav link, not the new direct About CTA.
    doc=unique(doc,'<a href="/company/">About</a>',
      '<a href="/company/">Company</a><a href="/about/">About Us</a>',"Company navigation")
    doc=metadata_company(doc)
    # Recognized verified business brand icon path; preserve decorative alt text.
    logo='<img src="/design-preview-20261017/static/site/mojplaywin-atelier/official-coin-80.3ea52711f49d.webp" alt="">'
    # Support attribute-order drift using exact src+alt source in either order.
    def replace_logo(m):
        tag=m.group()
        if "/design-preview-20261017/static/site/mojplaywin-atelier/official-coin-80.3ea52711f49d.webp" not in tag:
            fail("Company logo changed")
        tag=tag.replace('/design-preview-20261017/static/site/mojplaywin-atelier/official-coin-80.3ea52711f49d.webp',LOGO)
        tag=tag[:-1]+' width="80" height="80" loading="eager" decoding="async">'
        return tag
    doc=edit_tag(doc,r'<img\b[^>]*official-coin-80\.3ea52711f49d\.webp[^>]*>',replace_logo,"company brand image")
    doc=edit_tag(doc,r'<img\b[^>]*platform-home\.4dd3ab6a401d\.webp[^>]*>',
         lambda m:m.group()[:-1]+' loading="lazy" decoding="async" width="1200" height="675">',
         "Company banner image")
    doc=add_business(doc,"company")
    doc=edit_tag(doc,r'<body\b[^>]*>',lambda m:m.group()[:-1]+' class="mpw-company-harmonized">',"Company body")
    return doc
class BodyAudit(HTMLParser):
    def __init__(self):
        super().__init__();self.main=0;self.h=[];self.ids=[];self.images=[];self.in_main=False;self.d=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="main":self.in_main=True;self.main+=1
        if tag=="details":self.d+=1
        if self.in_main and tag in ("h1","h2","h3","h4","h5","h6"):
            self.h.append(tag)
        if a.get("id"):self.ids.append(a["id"])
        if tag=="img" and self.in_main:self.images.append(a)
    def handle_endtag(self,tag):
        if tag=="main":self.in_main=False
def validate_pair(about,company):
    if about.count(MARK)!=1 or company.count(MARK)!=1:fail("Wrong repair marker")
    for name,doc in (("about",about),("company",company)):
        parsed=BodyAudit();parsed.feed(doc)
        if parsed.main!=1:fail("Main landmark duplication "+name)
        if parsed.h.count("h1")!=1:fail("Wrong heading count "+name)
        if parsed.h[0]!="h1":fail("H1 not first in main "+name)
        if len(parsed.ids)!=len(set(parsed.ids)):fail("Duplicate ID "+name)
        if not re.search(r'<meta\b[^>]*\bname=["\x27]viewport["\x27]',doc,re.I):fail("Missing mobile viewport")
        if MAIL not in doc or BUSINESS not in doc:fail("Business contact missing "+name)
    if about.count('class="mpw-profile-indicator"')!=30:fail("Disclosures changed")
    if about.count('class="mpw-seven-item"')!=6 or 'data-gallery-image="06"' in about:
        fail("Duplicate gallery image resurfaced")
    for key in ("SPECIALISM 28","COMPLEMENTARY SPECIALISM 30","mpw-founder-spotlight-20261019",
                "mpw-advanced-research","mpw-complementary-details","official_profile_20261016"):
        if key not in about:fail("Preserved About evidence missing "+key)
    if company.count('class="mpw-ten-card"')!=10:fail("Company article count changed")
    if html.escape(COMPANY_TITLE) not in company or 'og:description' not in company:fail("Company SEO missing")
    if 'theme-color" content="#050608"' not in company:fail("Theme color drifted")
    if len(about.encode())<90000 or len(company.encode())<19000:fail("Content was truncated")
    return {"about_headings_before_h1":0,"company_headings_before_h1":0,
            "company_cards":10,"illustrative_profiles":30,"gallery_cards":6}
def compose(a,b):
    if MARK in a or MARK in b:fail("Already patched")
    about=patch_about(a)
    company=patch_company(b)
    for page,content in (("about",about),("company",company)):
        if content.count("</head>")!=1:fail("Invalid head "+page)
    about=about.replace("</head>",GLOBAL_STYLES+"\n</head>",1)
    company=company.replace("</head>",GLOBAL_STYLES+"\n</head>",1)
    about=about.replace("</body>","<!-- "+MARK+" -->\n</body>",1)
    company=company.replace("</body>","<!-- "+MARK+" -->\n</body>",1)
    return about,company
def atomic(path,raw,mode):
    if path.is_symlink():fail("Target symlink")
    fd,tmp=tempfile.mkstemp(prefix=".mpw-final-",dir=path.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.lexists(tmp):os.unlink(tmp)
def run_files(run):
    if not re.fullmatch(r"[0-9]{9,20}",run):fail("Run id")
    base=ROOT.parent
    return base/(".mpw-final-about-"+run+".bak"),base/(".mpw-final-company-"+run+".bak"),base/(".mpw-final-"+run+".json")
def guard():
    if ROOT.resolve()!=ROOT or not ROOT.is_dir() or ROOT.is_symlink():fail("Site root drift")
    for p in (ABOUT,COMPANY):
        if not p.is_file() or p.is_symlink():fail("Unexpected static target "+str(p))
    if not ROUTES.is_file() or ROUTES.is_symlink():fail("No safe route mapping")
    rule=ROUTES.read_text("utf-8",errors="replace")
    if "mpw-ten-editorials-20261018/pages/about.html" not in rule or "mpw-ten-editorials-20261018/pages/company.html" not in rule:
        fail("Static route mappings do not match protected filenames")
def install(run):
    guard()
    f1,f2,mf=run_files(run)
    if f1.exists() or f2.exists() or mf.exists():fail("This run already exists")
    old=(ABOUT.read_bytes(),COMPANY.read_bytes())
    new=tuple(x.encode("utf-8") for x in compose(*(x.decode("utf-8") for x in old)))
    validate_pair(*(x.decode("utf-8") for x in new))
    rec={"run":run,"old":[sha(x) for x in old],"new":[sha(x) for x in new]}
    for p,content in ((f1,old[0]),(f2,old[1])):
        with p.open("xb") as f:
            os.fchmod(f.fileno(),0o600);f.write(content);f.flush();os.fsync(f.fileno())
    with mf.open("x") as f:
        os.fchmod(f.fileno(),0o600);json.dump(rec,f);f.flush();os.fsync(f.fileno())
    if old!=(ABOUT.read_bytes(),COMPANY.read_bytes()):fail("Concurrent edit")
    modes=[stat.S_IMODE(p.stat().st_mode) for p in (ABOUT,COMPANY)]
    try:
        atomic(ABOUT,new[0],modes[0])
        atomic(COMPANY,new[1],modes[1])
    except BaseException:
        for p,prior,old_sha,new_sha,mode in zip((ABOUT,COMPANY),old,rec["old"],rec["new"],modes):
            current=sha(p.read_bytes())
            if current==new_sha:atomic(p,prior,mode)
            elif current!=old_sha:fail("Concurrent production modification: human recovery required")
        raise
    if [sha(p.read_bytes()) for p in (ABOUT,COMPANY)]!=rec["new"]:
        fail("Postwrite hash mismatch; use rollback")
    print("MPW_CONSOLIDATED_INSTALL="+json.dumps(rec))
def rollback(run):
    guard()
    f1,f2,mf=run_files(run)
    rec=json.loads(mf.read_text("utf-8"))
    if rec["run"]!=run:fail("Wrong run")
    old=(f1.read_bytes(),f2.read_bytes())
    if [sha(x) for x in old]!=rec["old"]:fail("Recovery backups corrupted")
    if [sha(p.read_bytes()) for p in (ABOUT,COMPANY)]!=rec["new"]:
        fail("Reject rollback over newer unrelated edits")
    for p,prior in zip((ABOUT,COMPANY),old):
        atomic(p,prior,stat.S_IMODE(p.stat().st_mode))
    if [sha(p.read_bytes()) for p in (ABOUT,COMPANY)]!=rec["old"]:fail("Failed recovery")
    print("MPW_CONSOLIDATED_ROLLBACK=VERIFIED")
if __name__=="__main__":
    if len(sys.argv)!=3 or sys.argv[1] not in ("install","rollback"):fail("install|rollback RUN_ID")
    {"install":install,"rollback":rollback}[sys.argv[1]](sys.argv[2])
