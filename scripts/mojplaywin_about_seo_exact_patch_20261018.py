#!/usr/bin/env python3
"""Atomic, fail-closed SEO patch to the already released static MojPlayWin /about/.

Only the known 109680-byte About HTML asset is modified. No .htaccess,
Django, Passenger, database, store, child site, or other HTML files are touched.
"""
import hashlib
import html
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path("/home/zomorod2/mojplaywin.com")
PAGE = ROOT / "design-preview-20261017/complete-about-20261018.html"
HTACCESS = ROOT / ".htaccess"
PREVIOUS_SHA = "88952bfbd749c6b6af40b85518e5071d20a909a6e3e5faeb5d84e7112f211036"
ROUTE_SHA = "723bb8ba5de87725bc6f1865d895a6407aae55dca4588a16bc8708a5154b6d6d"
TITLE = "About MojPlayWin | Research, Technology, Games & Business"
DESCRIPTION = ("An advanced introduction to MojPlayWin: scientific research, AI, "
               "software, original games, digital education and 10 complementary "
               "economic sectors, with founder Mojtaba Roozegar.")
SCHEMA = ('<script id="mpw-about-schema-20261018" type="application/ld+json">'
          '{"@context":"https://schema.org","@type":"AboutPage","url":"https://mojplaywin.com/about/",'
          '"name":"About MojPlayWin","inLanguage":"en","description":'
          '"Research, games, AI, software and complementary economic sectors.",'
          '"mainEntity":{"@type":"Organization","name":"MojPlayWin","url":"https://mojplaywin.com/",'
          '"founder":{"@type":"Person","name":"Mojtaba Roozegar","url":"https://mojplaywin.com/mojtaba.roozegar/"}}}'
          '</script>')
MARKERS = ("MPW_ABOUT_RESEARCH_80_20_V1", "SPECIALISM 28",
           "COMPLEMENTARY SPECIALISM 30", "Original by Default")

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def fail(reason):
    raise RuntimeError(reason)

def safeid(runid):
    if not re.fullmatch(r"[0-9]{9,20}", runid):
        fail("Invalid workflow run ID")
    return runid

def atom(path, raw, mode):
    if path.is_symlink():
        fail("Symlink rejected")
    fd, temporary = tempfile.mkstemp(prefix=".mpw-about-seo-",dir=path.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def patch_meta(document, key, value):
    tags = list(re.finditer(r"<meta\b[^>]*>", document, flags=re.I))
    matching = [m for m in tags if re.search(r'\bproperty\s*=\s*["\x27]'+re.escape(key)+r'["\x27]',m.group(),flags=re.I)]
    if len(matching)!=1:
        fail("Expected exactly one existing meta property: "+key)
    m=matching[0]
    tag=m.group()
    updated,n=re.subn(r'(\bcontent\s*=\s*)(["\x27]).*?\2',
        lambda match: match.group(1)+match.group(2)+html.escape(value,quote=True)+match.group(2),
        tag,count=1,flags=re.I|re.S)
    if n!=1:
        fail("Missing content for meta property "+key)
    return document[:m.start()]+updated+document[m.end():]

def patch(document):
    if "MPW_ABOUT_RESEARCH_80_20_V1" not in document:
        fail("Expected live editorial release marker missing")
    h1=list(re.finditer(r"(<h1\b[^>]*>)(.*?)(</h1\s*>)",document,flags=re.I|re.S))
    if len(h1)!=1:
        fail("Expected exactly one current H1; found "+str(len(h1)))
    m=h1[0]
    plain=re.sub(r"<[^>]+>"," ",m.group(2))
    plain=re.sub(r"\s+"," ",html.unescape(plain)).strip()
    if plain!="Original games. Measured evolution.":
        fail("Unexpected H1 text; refusing speculative changes: "+plain[:100])
    replacement=m.group(1)+"About MojPlayWin"+m.group(3)
    replacement+='<p class="mpw-about-original-tagline">Original games. Measured evolution.</p>'
    document=document[:m.start()]+replacement+document[m.end():]
    document=patch_meta(document,"og:title",TITLE)
    document=patch_meta(document,"og:description",DESCRIPTION)
    # Keep existing OpenGraph image and canonical unchanged.
    if 'id="mpw-about-schema-20261018"' in document:
        fail("Schema already installed")
    additions=(
        '<meta name="twitter:title" content="'+html.escape(TITLE,quote=True)+'">\n'
        '<meta name="twitter:description" content="'+html.escape(DESCRIPTION,quote=True)+'">\n'
        +SCHEMA+'\n'
        '<style id="mpw-about-tagline-style">.mpw-about-original-tagline{font-size:1.1rem;line-height:1.7;opacity:.84;margin:.5rem 0 1.2rem}</style>\n')
    if document.lower().count("</head>")!=1:
        fail("Invalid document head")
    document=document.replace("</head>",additions+"</head>",1)
    for marker in MARKERS:
        if marker not in document:fail("Existing company dossier lost "+marker)
    if len(re.findall(r"<h1\b",document,flags=re.I))!=1:
        fail("Invalid H1 count")
    if "<title>"+html.escape("About MojPlayWin | Scientific, Digital & Complementary Business Profile")+"</title>" not in document:
        fail("Existing title unexpectedly differs; protect against mismatch")
    document=document.replace(
       "<title>About MojPlayWin | Scientific, Digital &amp; Complementary Business Profile</title>",
       "<title>"+html.escape(TITLE)+"</title>",1)
    if "Our complete company profile" not in document:
        fail("Expected company profile heading missing")
    if len(document.encode("utf-8"))>200_000:
        fail("Unexpected expansion")
    return document

def guard():
    if not ROOT.is_dir() or ROOT.is_symlink() or not PAGE.is_file() or PAGE.is_symlink():
        fail("Incorrect target")
    if not HTACCESS.is_file() or HTACCESS.is_symlink() or sha(HTACCESS.read_bytes())!=ROUTE_SHA:
        fail("About rewrite changed; refuse patch")
    if sha(PAGE.read_bytes())!=PREVIOUS_SHA:
        fail("Previous version changed; refuse patch")

def backup_path(runid):
    return ROOT.parent / (".mpw-about-seo-"+safeid(runid)+".backup")

def install(runid):
    guard()
    before=PAGE.read_bytes()
    after=patch(before.decode("utf-8")).encode("utf-8")
    if before==after:fail("No change")
    backup=backup_path(runid)
    if backup.exists() or backup.is_symlink():fail("Backup path already exists")
    with open(backup,"xb") as f:
        os.chmod(backup,0o600)
        f.write(before)
        f.flush()
        os.fsync(f.fileno())
    mode=stat.S_IMODE(PAGE.stat().st_mode)
    try:
        atom(PAGE,after,mode)
        if sha(PAGE.read_bytes())!=sha(after):
            fail("Post-write SHA failure")
    except BaseException:
        if PAGE.is_file() and sha(PAGE.read_bytes())==sha(after):
            atom(PAGE,before,mode)
        raise
    print(json.dumps({"status":"SEO_PUBLISHED","sha_before":sha(before),
                      "sha_after":sha(after),"bytes":len(after),
                      "single_page_only":True,"passenger_restart":False,
                      "rollback_backup_created":True}))
def rollback(runid):
    backup=backup_path(runid)
    if not backup.is_file() or backup.is_symlink():fail("Missing backup")
    before=backup.read_bytes()
    if sha(before)!=PREVIOUS_SHA:fail("Corrupt rollback source")
    current=PAGE.read_bytes()
    if "mpw-about-schema-20261018" not in current.decode("utf-8"):
        fail("SEO edition not present; refuse to overwrite unrelated edits")
    atom(PAGE,before,stat.S_IMODE(PAGE.stat().st_mode))
    if sha(PAGE.read_bytes())!=PREVIOUS_SHA:fail("Rollback verification failed")
    print(json.dumps({"status":"SEO_ROLLED_BACK","sha":PREVIOUS_SHA}))
if __name__=="__main__":
    if len(sys.argv)!=3:fail("Use install|rollback RUNID")
    if sys.argv[1]=="install":install(sys.argv[2])
    elif sys.argv[1]=="rollback":rollback(sys.argv[2])
    else:fail("Invalid mode")
