#!/usr/bin/env python3
"""Append a research-grade owner-authored CV and official photo to a live page snapshot.

This builder has NO production file/server write access. It reads a known public
page, then emits independent static HTML, which is eligible for a narrowly scoped
root rewrite only after a separate no-go preflight and health checks.
"""
from urllib.request import Request,urlopen
from pathlib import Path
import argparse,hashlib,html,json,re

URL="https://mojplaywin.com/about/mojtaba-rozegar/"
MARKER="MOJPLAYWIN_PROFESSOR_MOJTabA_ROOZEGAR_PROFILE_20261018"
OFFICIAL_IMAGE="https://mojplaywin.com/mojtaba.roozegar/assets/personal_site/official_profile_20261016/portrait.2935ce8cb70d.webp"
TITLE="Professor Mojtaba Roozegar | PhD, Research & MojPlayWin Leadership"
DESC=("Professor Mojtaba Roozegar: self-reported PhD in Agricultural Economics "
      "at Universiti Putra Malaysia, Production Economics and Farm Management; "
      "researcher, entrepreneur and founder of MojPlayWin.")

def replace_meta(text,field,new):
    tags=list(re.finditer(r"<meta\b[^>]*>",text,re.I))
    match=[]
    for tag in tags:
        if re.search(r'\b(?:property|name)\s*=\s*["\x27]'+re.escape(field)+r'["\x27]',tag.group(),re.I):
            match.append(tag)
    if len(match)!=1:
        raise RuntimeError(f"Expected exactly one meta tag named {field}; got {len(match)}")
    tag=match[0]; val=tag.group()
    val,n=re.subn(r'(\bcontent\s*=\s*)(["\x27]).*?\2',
                lambda m:m.group(1)+m.group(2)+html.escape(new,quote=True)+m.group(2),val,count=1,flags=re.S|re.I)
    if n!=1:raise RuntimeError("Missing meta content: "+field)
    return text[:tag.start()]+val+text[tag.end():]

def construct(old,content):
    if len(old)<3000 or len(old)>25000:
        raise RuntimeError("Unexpected old profile size")
    if old.count("<main")!=1 or old.count("</main>")!=1:
        raise RuntimeError("Profile must have one main container")
    if not re.search(r"<h1\b[^>]*>\s*Mojtaba Rozegar\s*</h1>",old,re.I):
        raise RuntimeError("Expected original leadership H1 mismatch")
    if MARKER in old:
        raise RuntimeError("Already published, refusing duplicate")
    if len(content)<9000 or len(content)>100000 or MARKER not in content:
        raise RuntimeError("Incomplete academic source")
    if "{%" in content or "{{" in content:
        raise RuntimeError("Unexpected Django syntax in static source")
    if OFFICIAL_IMAGE not in content:
        raise RuntimeError("Official original photo omitted")
    if "self-reported" not in content or "PhD" not in content or "UPM" not in content:
        raise RuntimeError("Credential provenance notes missing")

    css=re.search(r'<style\s+id="mpw-exec-professional-profile-20261018">.*?</style>',content,re.I|re.S)
    if css is None:raise RuntimeError("No scoped CV stylesheet")
    content_without_css=content[:css.start()]+content[css.end():]
    old=old.replace("Mojtaba Rozegar","Mojtaba Roozegar")
    old=re.sub(r"(<h1\b[^>]*>)\s*Mojtaba Roozegar\s*(</h1>)",
               r"\1Professor Mojtaba Roozegar\2",old,count=1,flags=re.I)
    start=re.search(r"<main\b[^>]*>",old,re.I)
    old=old[:start.end()]+"\n"+content_without_css+"\n"+old[start.end():]
    old=old.replace("</head>",css.group(0)+"\n</head>",1)
    old,n=re.subn(r"<title>[^<]+</title>","<title>"+html.escape(TITLE)+"</title>",old,count=1,flags=re.I)
    if n!=1:raise RuntimeError("Cannot replace leadership title")
    old=replace_meta(old,"description",DESC)
    for key,value in [
        ("og:title",TITLE),
        ("og:description",DESC),
        ("og:image",OFFICIAL_IMAGE),
    ]:old=replace_meta(old,key,value)
    schema=('<script id="mpw-leadership-person-schema-20261018" type="application/ld+json">'
            '{"@context":"https://schema.org","@type":"ProfilePage",'
            '"url":"https://mojplaywin.com/about/mojtaba-rozegar/",'
            '"mainEntity":{"@type":"Person","name":"Mojtaba Roozegar","honorificPrefix":"Dr.",'
            '"image":"'+OFFICIAL_IMAGE+'",'
            '"url":"https://mojplaywin.com/mojtaba.roozegar/",'
            '"jobTitle":"Founder, Researcher and CEO",'
            '"worksFor":[{"@type":"Organization","name":"MojPlayWin"},'
            '{"@type":"Organization","name":"Zomorod Melal"}],'
            '"alumniOf":{"@type":"CollegeOrUniversity","name":"Universiti Putra Malaysia"}}}'
            '</script>')
    old=old.replace("</head>",schema+"\n</head>",1)
    count_h1=len(re.findall(r"<h1\b",old,re.I))
    if count_h1!=1:raise RuntimeError("Expected exactly one page H1, found "+str(count_h1))
    if old.count('<main')!=1 or old.count('</main>')!=1:
        raise RuntimeError("Main landmarks changed")
    if "Mojtaba Rozegar" in old:
        raise RuntimeError("Spelling inconsistencies remain")
    if not all(x in old for x in ("Professor Mojtaba Roozegar","Universiti Putra Malaysia",
                                  "Production Economics and Farm Management",
                                  "Official profile portrait","Founder &amp; CEO")):
        raise RuntimeError("Academic source incomplete")
    return old

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    req=Request(URL+"?__mpw_professor_snapshot=20261018",headers={"Cache-Control":"no-cache","User-Agent":"MPWProfessorProfileBuilder/1.0"})
    with urlopen(req,timeout=20) as resp:
        if resp.status!=200 or "text/html" not in resp.headers.get("Content-Type",""):
            raise RuntimeError("Existing profile endpoint unhealthy")
        original=resp.read(25001).decode("utf-8","replace")
    final=construct(original,Path(a.source).read_text(encoding="utf-8"))
    out=Path(a.output);out.write_text(final,encoding="utf-8")
    print(json.dumps({"status":"PROFESSOR_EXECUTIVE_STATIC_READY","original_bytes":len(original.encode()),
        "new_bytes":out.stat().st_size,"sha256":hashlib.sha256(out.read_bytes()).hexdigest(),
        "has_official_personal_image":True,"preserved_original_profile":True,
        "academic_qualification_self_reported":True,"no_server_mutation":True}))
if __name__=="__main__":main()
