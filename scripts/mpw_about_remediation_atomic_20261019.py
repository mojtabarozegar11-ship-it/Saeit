#!/usr/bin/env python3
"""Fail-closed, reversible remediation of only MojPlayWin's priority-routed About HTML.

Old/new source fragments are pinned to a reviewed GitHub base and current commit.
Never edits a .htaccess, application, database, store, or child-site path.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path("/home/zomorod2/mojplaywin.com")
PAGE = ROOT / "design-preview-20261017/mpw-ten-editorials-20261018/pages/about.html"
RULES = ROOT / ".htaccess"
HOME = ROOT.parent
FILES = (
    "mojplaywin_about_team_section_20261018.html",
    "mpw_international_team_section_20261018.html",
    "mpw_senior_advisory_board_20261018.html",
    "mpw_seven_team_gallery_20261019.html",
    "mpw_founder_spotlight_20261019.html",
)
MARK = "MPW_ABOUT_REMEDIATION_20261019_V1"
OWNERSHIP = (
    "MojPlayWin (also written Moj Play Win) is a limited liability company "
    "owned and led by <strong>Mojtaba Roozegar</strong>, its founder "
    "and Chief Executive Officer."
)
ORIGINAL_IDENTITY = (
    "MojPlayWin (also written Moj Play Win) is an international-facing digital "
    "brand founded by <strong>Mojtaba Roozegar</strong>."
)
PRESERVE = (
    "MPW_ABOUT_RESEARCH_80_20_V1", "SPECIALISM 28",
    "COMPLEMENTARY SPECIALISM 30", "Original by Default",
    "mpw-meet-team-20261018", "mpw-senior-advisory-20261018",
    "mpw-international-team-20261018", "mpw-founder-spotlight-20261019",
    "mpw-seven-gallery-20261019",
)

def digest(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def fail(message: str):
    raise RuntimeError(message)

def run_paths(run_id: str):
    if not re.fullmatch(r"[0-9]{9,20}", run_id):
        fail("Unsafe run identifier")
    return (
        HOME / (".mpw-about-remediation-" + run_id),
        HOME / (".mpw-about-remediation-backup-" + run_id + ".html"),
        HOME / (".mpw-about-remediation-manifest-" + run_id + ".json"),
    )

def check_target():
    if ROOT.resolve() != ROOT or not ROOT.is_dir() or ROOT.is_symlink():
        fail("Document root was changed")
    if not PAGE.is_file() or PAGE.is_symlink() or not RULES.is_file() or RULES.is_symlink():
        fail("Expected original static file or rewrite rules are missing")
    if any(parent.is_symlink() for parent in (PAGE.parent, PAGE.parent.parent, PAGE.parent.parent.parent)):
        fail("Refuse symlinked parent")
    rules = RULES.read_text("utf-8", errors="replace")
    expected = "RewriteRule ^.*$ /design-preview-20261017/mpw-ten-editorials-20261018/pages/about.html [END,QSD]"
    if "RewriteCond %{REQUEST_URI} ^/about/$" not in rules or expected not in rules:
        fail("Priority route is no longer pinned to the About page")

def unique_replace(src: str, old: str, new: str, label: str):
    if old == new or src.count(old) != 1:
        fail("Ambiguous source or concurrent change: " + label + "; matches=" + str(src.count(old)))
    return src.replace(old, new, 1)

class Audit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.h1 = 0
        self.ids = set()
        self.local_refs = []
        self.card_counts = {x:0 for x in ("mpw-team-card","mpw-intl-card","mpw-advisory-card","mpw-seven-item")}
        self.indicators = 0
        self.images = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = set(a.get("class","").split())
        if tag == "h1": self.h1 += 1
        if a.get("id"): self.ids.add(a["id"])
        if tag == "a" and (a.get("href") or "").startswith("#"):
            self.local_refs.append(a["href"][1:])
        if tag == "img": self.images.append(a.get("src",""))
        for key in self.card_counts:
            if key in classes: self.card_counts[key] += 1
        if "mpw-profile-indicator" in classes: self.indicators += 1

def validate(document: str):
    if document.count(MARK) != 1:
        fail("Wrong patch marker count")
    for marker in PRESERVE:
        if marker not in document: fail("Lost original section: " + marker)
    if document.count(OWNERSHIP) != 1:
        fail("Incorrect owner/CEO company statement")
    parsed = Audit()
    parsed.feed(document)
    if parsed.h1 != 1: fail("Expected exactly one H1")
    if [parsed.card_counts[x] for x in ("mpw-team-card","mpw-intl-card","mpw-advisory-card","mpw-seven-item")] != [10,10,10,6]:
        fail("Profile count changed unexpectedly: " + str(parsed.card_counts))
    if parsed.indicators != 30: fail("All 30 virtual profiles must carry individual disclosures")
    if "data-gallery-image=\"06\"" in document or "mpw-team-gallery-seven-06-20261019.webp" in document:
        fail("Repeated image six was not removed")
    if "Senior Advisory Board</h2>" in document or ">Chief Executive Officer</p>" in document or ">CEO &amp; Business Development</p>" in document:
        fail("Misleading title remains")
    if not (document.index('id="mpw-founder-spotlight-20261019"') < document.index('id="our-story"')
            < document.index('id="mpw-meet-team-20261018"')):
        fail("Founder is not near top, before team")
    for ref in parsed.local_refs:
        if ref and ref not in parsed.ids: fail("Broken same-page fragment: #" + ref)
    if len(document.encode("utf-8")) < 60000 or len(document.encode("utf-8")) > 1400000:
        fail("Unexpected HTML size")
    if len(parsed.images) < 15:
        fail("Existing images may be missing")
    return {"h1":parsed.h1,"profiles":parsed.card_counts,
            "indicators":parsed.indicators,"images":len(parsed.images),
            "same_page_links":len(parsed.local_refs)}

def compose(html: str, sources: dict[str, tuple[str,str]]) -> str:
    if MARK in html: fail("Patch already installed")
    for key in PRESERVE: 
        if key not in html: fail("Source page missing prerequisite: " + key)
    if len(re.findall(r"<h1\b",html,re.I)) != 1:
        fail("Original H1 count changed")
    for filename in FILES:
        old,new=sources[filename]
        html=unique_replace(html,old,new,filename)
    html=unique_replace(html,ORIGINAL_IDENTITY,OWNERSHIP,"company type and CEO identity")
    # Move the complete existing founder portrait and description above the company
    # history, rather than duplicating either the image or the heading.
    founder = sources["mpw_founder_spotlight_20261019.html"][1]
    html=unique_replace(html,founder,"","relocate single founder section")
    hero=re.search(r'<header\b[^>]*\bid="about-top"[^>]*>[\s\S]*?</header>',html,re.I)
    if not hero: fail("Original About hero missing")
    pos=hero.end()
    html=html[:pos]+"\n"+founder+"\n"+html[pos:]
    # Make extensive original research chapters opt-in reading without losing any
    # research text, references, anchors, editorial images or source content.
    start_d=html.find('id="doctoral-dossier"')
    start_c=html.find('id="complementary-portfolio"')
    reference=html.find('id="complementary-reference-methods"')
    if not (0<start_d<start_c<reference): fail("Dossier/sector section order changed")
    begin_d=html.rfind("<section",0,start_d)
    begin_c=html.rfind("<section",0,start_c)
    end_ref=html.find("</section>",reference)
    if begin_d<0 or begin_c<0 or end_ref<0: fail("Cannot bound original dossiers")
    end_ref+=len("</section>")
    intro_d='<details id="mpw-advanced-research" class="mpw-about-advanced"><summary>Advanced research dossier · 28 specialisms (expand)</summary>\n'
    intro_c='<details id="mpw-complementary-details" class="mpw-about-advanced"><summary>Complementary sector dossier · 30 specialisms (expand)</summary>\n'
    html=(html[:begin_d]+intro_d+html[begin_d:begin_c]+"</details>\n"+
          intro_c+html[begin_c:end_ref]+"</details>\n"+html[end_ref:])
    # Make the top-level nav open visible sections, while deep linking remains
    # possible with the hash-open enhancement below.
    html=html.replace('href="#doctoral-dossier"','href="#mpw-advanced-research"')
    html=html.replace('href="#complementary-portfolio"','href="#mpw-complementary-details"')
    extra = '''
<style id="mpw-about-remediation-css-20261019">
#mpw-advanced-research,#mpw-complementary-details{margin:24px auto;padding:clamp(16px,2vw,28px);border:1px solid rgba(230,184,94,.5);border-radius:20px;background:#171712;color:#f7e7c7}
#mpw-advanced-research>summary,#mpw-complementary-details>summary{cursor:pointer;font-weight:800;line-height:1.65;color:#f3d397;outline-offset:5px;font-size:clamp(1rem,2vw,1.28rem)}
#mpw-advanced-research>summary:focus-visible,#mpw-complementary-details>summary:focus-visible{outline:3px solid #f3d397}
#mpw-advanced-research[open]>summary,#mpw-complementary-details[open]>summary{margin-bottom:20px}
#mpw-advanced-research .mw-section,#mpw-complementary-details .mw-section{max-width:100%;overflow-wrap:anywhere}
#mpw-advanced-research section[id],#mpw-complementary-details section[id],#mpw-founder-spotlight-20261019{scroll-margin-top:22px}
#mpw-founder-spotlight-20261019{margin-top:clamp(24px,4vw,42px)}
@media(max-width:600px){#mpw-advanced-research,#mpw-complementary-details{padding:14px;border-radius:16px}}
</style>
<script id="mpw-about-hash-open-20261019">
(function(){function reveal(){
 var id=decodeURIComponent(location.hash.slice(1));if(!id)return;
 var node=document.getElementById(id);if(!node)return;
 var p=node.closest('details.mpw-about-advanced');if(p&&!p.open)p.open=true;
}document.addEventListener('DOMContentLoaded',reveal);window.addEventListener('hashchange',reveal);})();
</script>
<!-- MPW_ABOUT_REMEDIATION_20261019_V1 -->
'''
    if html.lower().count("</body>")!=1: fail("Cannot safely insert About-only accessibility CSS")
    html=html.replace("</body>",extra+"</body>",1)
    validate(html)
    return html

def atomic(path: Path, raw: bytes, mode: int):
    if path.is_symlink(): fail("Write through symlink prohibited")
    fd,temp=tempfile.mkstemp(dir=path.parent,prefix=".mpw-about-remediation-")
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if os.path.lexists(temp):os.unlink(temp)

def source_pairs(stage: Path):
    src={}
    for file in FILES:
        before=stage/"old"/file
        after=stage/"new"/file
        if not before.is_file() or not after.is_file() or before.is_symlink() or after.is_symlink():
            fail("Missing pinned staged source pair: " + file)
        src[file]=(before.read_text("utf-8"),after.read_text("utf-8"))
    return src

def install(run_id: str):
    stage,backup,manifest=run_paths(run_id)
    check_target()
    if backup.exists() or manifest.exists():fail("Backup or manifest already exists")
    source=source_pairs(stage)
    before=PAGE.read_bytes()
    updated=compose(before.decode("utf-8"),source).encode("utf-8")
    mode=stat.S_IMODE(PAGE.stat().st_mode)
    # Persist the recovery source BEFORE replacing live HTML.
    with backup.open("xb") as f:
        os.fchmod(f.fileno(),0o600);f.write(before);f.flush();os.fsync(f.fileno())
    record={"run_id":run_id,"page":str(PAGE),"old_sha":digest(before),
            "new_sha":digest(updated),"backup":str(backup)}
    with manifest.open("x",encoding="utf-8") as f:
        os.fchmod(f.fileno(),0o600);json.dump(record,f);f.flush();os.fsync(f.fileno())
    if PAGE.read_bytes()!=before:fail("Concurrent page modification before atomic write")
    atomic(PAGE,updated,mode)
    if digest(PAGE.read_bytes())!=record["new_sha"]:
        fail("Live file digest mismatch after write")
    print("MPW_ABOUT_INSTALL="+json.dumps({**record,"qa":validate(updated.decode("utf-8"))}))

def rollback(run_id: str):
    stage,backup,manifest=run_paths(run_id)
    check_target()
    if not backup.is_file() or backup.is_symlink() or not manifest.is_file() or manifest.is_symlink():
        fail("No approved backup or manifest to roll back")
    record=json.loads(manifest.read_text("utf-8"))
    if record.get("page")!=str(PAGE) or record.get("run_id")!=run_id:fail("Manifest changed")
    before=backup.read_bytes()
    if digest(before)!=record["old_sha"]:fail("Backup integrity mismatch")
    if digest(PAGE.read_bytes())!=record["new_sha"]:
        fail("Refusing rollback over a newer concurrent page edit")
    atomic(PAGE,before,stat.S_IMODE(PAGE.stat().st_mode))
    if digest(PAGE.read_bytes())!=record["old_sha"]:fail("Rollback verification failed")
    print("MPW_ABOUT_ROLLED_BACK="+record["old_sha"])

def status(run_id: str):
    _,_,manifest=run_paths(run_id)
    data=json.loads(manifest.read_text("utf-8"))
    print("MPW_ABOUT_STATUS="+json.dumps({"current_sha":digest(PAGE.read_bytes()),
                                         "published_sha":data["new_sha"],
                                         "matches":digest(PAGE.read_bytes())==data["new_sha"]}))

if __name__=="__main__":
    if len(sys.argv)!=3 or sys.argv[1] not in ("install","rollback","status"):
        fail("Usage: script.py install|rollback|status RUN_ID")
    {"install":install,"rollback":rollback,"status":status}[sys.argv[1]](sys.argv[2])
