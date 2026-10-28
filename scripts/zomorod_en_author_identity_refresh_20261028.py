#!/usr/bin/env python3
"""Update only the existing English Zomorod author HTML, with exact rollback.

Owner-confirmed Vancouver residence and roles; no unsupported publication,
degree date, journal acceptance, or researcher identifier is invented.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

HOME = Path("/home/zomorod2")
TARGET = HOME / "public_html/en/authors/mojtaba-rozegar/index.html"
BACKUP = HOME / ".private-zm-author-route/en-profile-seo-20261028"
ORIGINAL = BACKUP / "index.html.before"
MANIFEST = BACKUP / "manifest.json"
EXPECTED_SOURCE = "b766b419f506fc9f32dbb84681eba9793a9027dfeb57990730b0db069fef006d"
PROFILE_ID = 'id="mojtaba-roozegar-official-profile-20261021"'
PERSON_URL = "https://zomorodmelal.ir/en/authors/mojtaba-rozegar/"
PERSIAN_URL = "https://zomorodmelal.ir/authors/mojtaba-rozegar/"
RESUME_URL = "https://mojplaywin.com/mojtaba.roozegar/resume/"
HEAD_TITLE = "Mojtaba Roozegar | Researcher & CEO of MojPlayWin and Zomorod Melal"
DESCRIPTION = (
    "Mojtaba Roozegar (مجتبی روزگار), Vancouver-based scientific researcher "
    "and CEO of MojPlayWin, remotely leading Zomorod Melal Agro-Industry. "
    "Agricultural economics, smart farming, teaching and web systems."
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def one(source: str, before: str, after: str) -> str:
    if source.count(before) != 1:
        raise ValueError("VERIFIED_EN_AUTHOR_SOURCE_DRIFT")
    return source.replace(before, after, 1)


def revise(source: bytes) -> bytes:
    if digest(source) != EXPECTED_SOURCE:
        raise ValueError("ENGLISH_AUTHOR_SOURCE_HASH_CHANGED")
    text = source.decode("utf-8")
    if text.count(PROFILE_ID) != 1:
        raise ValueError("PROFILE_PHOTO_SECTION_MISSING")
    original_title = "Mojtaba Roozegar (Mojtaba Rozegar) | Zomorod Melal"
    original_desc = (
        "Official profile of Mojtaba Roozegar (Mojtaba Rozegar), "
        "researcher and CEO of Zomorod Melal; also known as مجتبی روزگار, "
        "Roozegar and Rozegar."
    )
    text = one(text, '<title>'+original_title+'</title>',
               '<title>'+HEAD_TITLE+'</title>')
    text = one(text, '<meta property="og:title" content="'+original_title+'">',
               '<meta property="og:title" content="'+HEAD_TITLE+'">')
    text = one(text, '<meta name="description" content="'+original_desc+'">',
               '<meta name="description" content="'+DESCRIPTION+'">')
    text = one(text,
        '<meta property="og:description" content="Official profile of Mojtaba Roozegar (Mojtaba Rozegar), researcher and CEO of Zomorod Melal.">',
        '<meta property="og:description" content="'+DESCRIPTION+'">')
    text = one(text,
        '<link rel="canonical" href="'+PERSON_URL+'">',
        '<link rel="canonical" href="'+PERSON_URL+'">'
        '<link rel="alternate" hreflang="en" href="'+PERSON_URL+'">'
        '<link rel="alternate" hreflang="fa-IR" href="'+PERSIAN_URL+'">')
    text = one(text, '<h1>Mojtaba Rozegar</h1>',
               '<h1>Mojtaba Roozegar</h1>')
    text = one(text,
        '<p class="lead">Mojtaba Rozegar (مجتبی روزگار) is a researcher and CEO of Zomorod Melal Agriculture &amp; Industry Company.</p>',
        '<p class="lead">Mojtaba Roozegar (مجتبی روزگار) is a scientific researcher based in Vancouver, Canada, CEO of MojPlayWin and continuing CEO and remote executive of Zomorod Melal Agro-Industry Company.</p>')
    text = one(text, '<h1 id="mr-profile-title">Mojtaba Roozegar</h1>',
               '<h2 id="mr-profile-title">Mojtaba Roozegar</h2>')
    text = one(text, '.mr-profile h1{margin:0 0 8px}',
        '.mr-profile h2{font-size:clamp(34px,5vw,62px);line-height:1.2;letter-spacing:-.025em;margin:0 0 8px;color:var(--gold)}')
    text = one(text,
        'مجتبی روزگار؛ محقق، پژوهشگر و مدیرعامل شرکت کشت و صنعت زمرد ملل.',
        'مجتبی روزگار؛ پژوهشگر علمی ساکن ونکوور کانادا، مدیرعامل مج‌پلی‌وین و مدیرعامل و راهبر از راه دور شرکت کشت و صنعت زمرد ملل.')
    text = one(text,
        'Mojtaba Roozegar (also spelled Mojtaba Rozegar, Roozegar or Rozegar) is a researcher and the chief executive of Zomorod Melal Agricultural and Industrial Company. His professional profile connects research and agricultural development with the company’s work.',
        'Mojtaba Roozegar (also spelled Mojtaba Rozegar, Roozegar or Rozegar) is a Vancouver-based researcher and writer whose primary work spans scientific investigation, agricultural economics, farm management and evidence-based decision support. He is CEO of MojPlayWin and continues to direct Zomorod Melal Agro-Industry and selected businesses remotely after earlier executive work in Iran. He works on organizational intelligence, smart agriculture, practical AI and professional web development, and organizes courses and workshops in business, agriculture and economics. Books and articles are owner-reported; publisher-confirmed and peer-reviewed records must be verified individually.')
    text = one(text,
        '<nav aria-label="Official profile links"><a href="https://zomorodmelal.ir/about/">About Zomorod Melal</a><a href="https://mojplaywin.com/mojtaba.roozegar/">Personal website</a></nav>',
        '<nav aria-label="Official profile links"><a href="https://zomorodmelal.ir/about/">About Zomorod Melal</a><a href="https://mojplaywin.com/mojtaba.roozegar/">Personal website</a><a href="'+RESUME_URL+'">Scientific and executive CV</a><a href="'+PERSIAN_URL+'">بیوگرافی فارسی</a></nav>')
    expression = re.compile(r'(<script type="application/ld\+json">)(.*?)(</script>)',re.S)
    matches = list(expression.finditer(text))
    if len(matches) != 1:
        raise ValueError("JSONLD_BLOCK_NOT_UNIQUE")
    m = matches[0]
    graph = json.loads(m.group(2))
    if graph.get("@type") != "ProfilePage" or graph.get("mainEntity",{}).get("@type") != "Person":
        raise ValueError("PERSON_SCHEMA_DRIFT")
    graph["name"] = HEAD_TITLE
    graph["inLanguage"] = "en"
    graph["@id"] = PERSON_URL + "#profile"
    person = graph["mainEntity"]
    person["name"] = "Mojtaba Roozegar"
    person["description"] = DESCRIPTION
    person["jobTitle"] = [
        "Scientific Researcher",
        "Chief Executive Officer of MojPlayWin",
        "Chief Executive Officer of Zomorod Melal Agro-Industry Company",
        "Business and Agricultural Economics Educator"
    ]
    person["knowsAbout"] = [
        "Scientific Research", "Agricultural Economics", "Farm Management",
        "Smart Agriculture", "Organizational Intelligence",
        "Web Systems Development", "Business Education"
    ]
    person["worksFor"] = [
        {"@type":"Organization","name":"MojPlayWin","url":"https://mojplaywin.com/"},
        {"@type":"Organization","name":"Zomorod Melal Agro-Industry Company","url":"https://zomorodmelal.ir/"}
    ]
    person["sameAs"] = [
        "https://mojplaywin.com/mojtaba.roozegar/",
        RESUME_URL, PERSIAN_URL, "https://zomorodmelal.ir/about/"
    ]
    person["homeLocation"] = {
        "@type":"Place","name":"Vancouver, British Columbia, Canada"
    }
    encoded = json.dumps(graph,ensure_ascii=False,separators=(",",":")).replace("<","\\u003c")
    text = text[:m.start()] + m.group(1) + encoded + m.group(3) + text[m.end():]
    if text.lower().count("<h1") != 1:
        raise ValueError("SINGLE_H1_REQUIREMENT_FAILED")
    if "Vancouver" not in text or RESUME_URL not in text:
        raise ValueError("IDENTITY_CV_LINK_MISSING")
    if text.count('ceo-mojtaba-rozegar.webp') < 3:
        raise ValueError("OFFICIAL_PORTRAIT_REFERENCE_REMOVED")
    if PROFILE_ID not in text or '<link rel="canonical" href="'+PERSON_URL+'">' not in text:
        raise ValueError("PROFILE_MARKER_OR_CANONICAL_REMOVED")
    return text.encode("utf-8")


def atomic(path: Path, data: bytes, mode: int) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".en-author-safe-",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as stream:
            os.fchmod(stream.fileno(),mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.lexists(tmp):os.unlink(tmp)


def execute(mode: str) -> None:
    if Path.home() != HOME:
        raise RuntimeError("CPANEL_ACCOUNT_MISMATCH")
    for path in (HOME, TARGET.parent, TARGET, BACKUP.parent, BACKUP):
        if path.is_symlink():
            raise RuntimeError("SYMLINK_BLOCKED")
    if not TARGET.is_file():
        raise RuntimeError("STATIC_EN_AUTHOR_MISSING")
    current = TARGET.read_bytes()
    if mode == "plan":
        after = revise(current)
        print("EN_AUTHOR_PLAN=validated")
        print("EN_AUTHOR_BEFORE_SHA="+digest(current))
        print("EN_AUTHOR_AFTER_SHA="+digest(after))
        return
    if mode == "apply":
        after=revise(current)
        if not BACKUP.parent.is_dir() or BACKUP.exists():
            raise RuntimeError("BACKUP_SCOPE_CONFLICT")
        BACKUP.mkdir(mode=0o700)
        atomic(ORIGINAL,current,0o600)
        info={"before":digest(current),"after":digest(after),"scope":str(TARGET)}
        atomic(MANIFEST,(json.dumps(info)+"\n").encode(),0o600)
        if TARGET.read_bytes()!=current:
            raise RuntimeError("CONCURRENT_SOURCE_EDIT")
        atomic(TARGET,after,stat.S_IMODE(TARGET.stat().st_mode))
        if TARGET.read_bytes()!=after:
            raise RuntimeError("DEPLOY_VERIFY_FAILED")
        print("EN_AUTHOR_PATCH=applied")
        return
    if mode not in ("rollback","status"):
        raise RuntimeError("INVALID_MODE")
    if not ORIGINAL.is_file() or not MANIFEST.is_file():
        raise RuntimeError("BACKUP_MISSING")
    info=json.loads(MANIFEST.read_text())
    if digest(ORIGINAL.read_bytes())!=info["before"]:
        raise RuntimeError("BACKUP_CORRUPT")
    if mode == "status":
        print("EN_AUTHOR_PATCH_STATUS="+("applied" if digest(current)==info["after"]
              else "rolled_back" if digest(current)==info["before"] else "drifted"))
        return
    if digest(current)!=info["after"]:
        raise RuntimeError("CONCURRENT_CHANGE_BLOCKS_ROLLBACK")
    atomic(TARGET,ORIGINAL.read_bytes(),stat.S_IMODE(TARGET.stat().st_mode))
    print("EN_AUTHOR_PATCH=rolled_back")


if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("usage: plan|apply|rollback|status")
    execute(sys.argv[1])
