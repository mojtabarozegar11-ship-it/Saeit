#!/usr/bin/env python3
"""Isolated founder official-photo and Company About cross-link polish.
Only two pinned MojPlayWin static HTML assets can be changed.
"""
import hashlib,json,os,re,stat,sys,tempfile
from pathlib import Path

ROOT=Path("/home/zomorod2/mojplaywin.com")
BASE=ROOT/"design-preview-20261017/mpw-ten-editorials-20261018/pages"
ABOUT=BASE/"about.html"
COMPANY=BASE/"company.html"
RULES=ROOT/".htaccess"
MARK="MPW_COMPANY_FOUNDER_POLISH_20261019_V1"
OWNER_IMAGE="/mojtaba.roozegar/assets/personal_site/official_profile_20261016/portrait.2935ce8cb70d.webp"
OLD_IMAGE="/design-preview-20261017/mpw-ten-editorials-20261018/pages/mpw-founder-portrait-20261019.webp"
OWNER_ALT="Official portrait of Mojtaba Roozegar, owner and Chief Executive Officer of MojPlayWin"
OLD_ALT="Stylized MojPlayWin founder portrait of Mojtaba Roozegar in formal attire beside the black and gold MojPlayWin emblem"
BANNER='''<section id="mpw-company-owner-crosslink-20261019" aria-labelledby="mpw-company-owner-title" class="mpw-company-owner-banner">
<p class="mpw-company-owner-kicker">MOJPLAYWIN · COMPANY &amp; LEADERSHIP</p>
<h2 id="mpw-company-owner-title">A limited liability company owned and led by Mojtaba Roozegar</h2>
<p>Mojtaba Roozegar is the owner, founder and Chief Executive Officer of MojPlayWin. Discover our mission, research, original games, digital services and development standards on the complete About page.</p>
<p>Company registration number and jurisdiction are not stated here without documentary verification. Illustrative role portraits are not verified staff or board appointments.</p>
<a href="/about/" class="mpw-company-owner-link">Explore the complete company profile →</a>
</section>'''
STYLE='''<style id="mpw-company-owner-style-20261019">
.mpw-company-owner-banner{max-width:1240px;margin:20px auto 28px;padding:clamp(24px,4vw,44px);background:linear-gradient(135deg,#0d1211,#251e14 60%,#101718);border:1px solid #d6ad55;border-radius:20px;box-shadow:0 16px 44px #0005;color:#f5f0e4;box-sizing:border-box}
.mpw-company-owner-banner *{box-sizing:border-box}
.mpw-company-owner-banner h2{font-size:clamp(1.6rem,3.5vw,2.8rem);line-height:1.22;color:#f1d69a;margin:.3rem 0 .8rem}
.mpw-company-owner-banner p{font-size:clamp(.94rem,1.2vw,1.08rem);line-height:1.85;color:#f4ebda;max-width:82ch}
.mpw-company-owner-kicker{letter-spacing:.12em;color:#f0cc82!important;font-weight:800}
.mpw-company-owner-link{display:inline-block;padding:12px 18px;margin-top:8px;border-radius:12px;background:#cba35b;color:#15120c!important;text-decoration:none;font-weight:750}
.mpw-company-owner-link:focus-visible{outline:3px solid #f1d69a;outline-offset:5px}
@media(max-width:600px){.mpw-company-owner-banner{margin:14px 10px;padding:20px}}
@media(prefers-reduced-motion:reduce){.mpw-company-owner-banner *{scroll-behavior:auto}}
</style>'''
def sha(x):return hashlib.sha256(x).hexdigest()
def fail(x):raise RuntimeError(x)
def safe_run(run):
    if not re.fullmatch(r"[0-9]{9,20}",run):fail("Invalid run number")
    return run
def paths(run):
    safe_run(run)
    return (ROOT.parent/(".mpw-owner-polish-"+run+"-about.bak"),
            ROOT.parent/(".mpw-owner-polish-"+run+"-company.bak"),
            ROOT.parent/(".mpw-owner-polish-"+run+"-manifest.json"))
def guard():
    if ROOT.is_symlink() or ROOT.resolve()!=ROOT or not ROOT.is_dir():fail("Unexpected root")
    for page in (ABOUT,COMPANY):
        if not page.is_file() or page.is_symlink() or page.parent.is_symlink():fail("Unsafe target "+str(page))
    if not RULES.is_file() or RULES.is_symlink():fail("Unexpected rewrite file")
    routing=RULES.read_text("utf-8",errors="replace")
    if not ("company.html" in routing and "about.html" in routing):
        fail("Public route mapping cannot be verified")
def compose(about,company):
    if MARK in about or MARK in company:fail("Owner polish already installed")
    if about.count("MPW_ABOUT_REMEDIATION_20261019_V1")!=1:
        fail("Original approved About repair is not live")
    if about.count(OLD_IMAGE)!=1 or about.count(OLD_ALT)!=1:
        fail("Founder portrait or alt changed; refusing overwrite")
    if about.count('id="mpw-founder-spotlight-20261019"')!=1:fail("Founder section changed")
    about=about.replace(OLD_IMAGE,OWNER_IMAGE,1).replace(OLD_ALT,OWNER_ALT,1)
    about=about.replace("</body>","<!-- "+MARK+" -->\n</body>",1)
    if company.count('id="mpw-ten-illustrated-20261018"')!=1:fail("Company 10-image collection changed")
    if company.count('class="mpw-ten-card"')!=10:fail("Company existing cards changed")
    main=re.search(r'<main\b[^>]*>',company,re.I)
    if not main:fail("Company main landmark missing")
    if company.lower().count("</head>")!=1:fail("Company HTML head missing")
    company=company.replace("</head>",STYLE+"\n</head>",1)
    main=re.search(r'<main\b[^>]*>',company,re.I)
    company=company[:main.end()]+"\n<!-- "+MARK+" -->\n"+BANNER+"\n"+company[main.end():]
    if about.count(OWNER_IMAGE)!=1 or company.count(BANNER)!=1:
        fail("Postpatch identity/image count inconsistent")
    if company.count('class="mpw-ten-card"')!=10:
        fail("Company cards lost after patch")
    if "</body>" not in company or "</body>" not in about:fail("Broken HTML")
    return about,company
def atomic(path,blob,mode):
    if path.is_symlink():fail("Symlink write rejected")
    fd,tmp=tempfile.mkstemp(prefix=".mpw-owner-polish-",dir=path.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as f:f.write(blob);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.lexists(tmp):os.unlink(tmp)
def install(run):
    guard()
    ab,co,manifest=paths(run)
    if ab.exists() or co.exists() or manifest.exists():fail("Backup run already exists")
    old=(ABOUT.read_bytes(),COMPANY.read_bytes())
    new=tuple(z.encode("utf-8") for z in compose(*(z.decode("utf-8") for z in old)))
    mode=(stat.S_IMODE(ABOUT.stat().st_mode),stat.S_IMODE(COMPANY.stat().st_mode))
    rec={"run":run,"before":[sha(x) for x in old],"after":[sha(x) for x in new]}
    for file,blob in ((ab,old[0]),(co,old[1])):
        with file.open("xb") as f:
            os.fchmod(f.fileno(),0o600);f.write(blob);f.flush();os.fsync(f.fileno())
    with manifest.open("x") as f:
        os.fchmod(f.fileno(),0o600);json.dump(rec,f);f.flush();os.fsync(f.fileno())
    if (ABOUT.read_bytes(),COMPANY.read_bytes())!=old:fail("Concurrent edit before write")
    try:
        atomic(ABOUT,new[0],mode[0])
        atomic(COMPANY,new[1],mode[1])
    except BaseException:
        for path,blob,before,after,m in zip((ABOUT,COMPANY),old,rec["before"],rec["after"],mode):
            actual=sha(path.read_bytes())
            if actual==after:atomic(path,blob,m)
            elif actual!=before:fail("Concurrent edit during two-page commit; manual recovery required")
        raise
    if [sha(ABOUT.read_bytes()),sha(COMPANY.read_bytes())]!=rec["after"]:fail("Postwrite hash mismatch")
    print("MPW_OWNER_COMPANY_POLISH="+json.dumps(rec))
def rollback(run):
    guard()
    ab,co,mf=paths(run)
    rec=json.loads(mf.read_text("utf-8"))
    if rec["run"]!=run:fail("Wrong restore run")
    pages=(ABOUT,COMPANY)
    old=(ab.read_bytes(),co.read_bytes())
    if [sha(x) for x in old]!=rec["before"]:fail("Backup changed")
    if [sha(x.read_bytes()) for x in pages]!=rec["after"]:fail("Refusing rollback over later edits")
    for page,blob in zip(pages,old):atomic(page,blob,stat.S_IMODE(page.stat().st_mode))
    if [sha(x.read_bytes()) for x in pages]!=rec["before"]:fail("Rollback not verified")
    print("MPW_POLISH_ROLLBACK=VERIFIED")
if __name__=="__main__":
    if len(sys.argv)!=3:fail("Usage: install|rollback RUN_ID")
    {"install":install,"rollback":rollback}[sys.argv[1]](safe_run(sys.argv[2]))
