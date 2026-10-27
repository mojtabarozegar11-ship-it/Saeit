#!/usr/bin/env python3
"""Safely consolidate repeated editorial evidence notices on the public MojPlayWin site."""
from pathlib import Path
import hashlib
import html
import json
import os
import re
import stat
import sys
import tempfile

ROOT=Path("/home/zomorod2/mojplaywin.com")
BASE=ROOT/"mpw-editorial"
GUIDES=BASE/"field-guides/20261023/guides"
COLLECTIONS=BASE/"collections"
SERVICES=BASE/"revenue"
POLICY=BASE/"editorial-standards/index.html"
POLICY_URL="/mpw-editorial/editorial-standards/index.html"
BACKUPS=Path("/home/zomorod2/.mpw-architecture-backups")
MARKER="MPW_EDITORIAL_EVIDENCE_REFACTORED_20261027"
OLD_GUIDE=("These original implementation recommendations are informed by the following authoritative documentation and standards. "
"Any numbers in worked scenarios are illustrative calculations, not measured performance results for MojPlayWin or the cited sources. "
"Validate them on the intended product and hardware.")
OLD_VISUAL=("Ten independent educational notes, each with a practical method and a lightweight image. "
"Described capabilities are not automatically evidence of live products or licensed operations.")
OLD_RESEARCH=("Independent technical analyses with explicit research questions, proposed methods, measurable outcomes, limitations and sources. "
"These are educational proposals, not peer-reviewed original experiments, accredited findings, or evidence that any described facility is operating.")
OLD_NOTICE=("<strong>Evidence notice:</strong> Methodology guides cite external benchmarks but do not claim peer review, "
"professional licensing, regulatory approval, guaranteed results or that examples describe an active MojPlayWin product. "
"Verify applicability, local law and newer editions before real-world decisions.")
OLD_CTA=("Tell us what you need using the existing MojPlayWin contact route. "
"We will only accept payment after an agreed quotation or a verified product checkout becomes available.")

def sha(data):return hashlib.sha256(data).hexdigest()

def safe_title(s):
    m=re.search(r"<h1\b[^>]*>(.*?)</h1>",s,re.I|re.S)
    if not m:raise ValueError("Missing H1")
    t=re.sub(r"<[^>]+>","",m.group(1))
    return re.sub(r"\s+"," ",html.unescape(t)).strip()

def replace_one(s,old,new,where):
    if s.count(old)!=1:raise ValueError(f"Expected one shared paragraph in {where}, got {s.count(old)}")
    updated=s.replace(old,new,1)
    if MARKER in s:raise ValueError("Already patched "+where)
    return updated

def new_policy():
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Research and evidence standards | MojPlayWin</title>
<meta name="description" content="Editorial methodology, evidence boundaries and source verification for MojPlayWin guides, research briefs and professional service descriptions.">
<link rel="canonical" href="https://mojplaywin.com{POLICY_URL}">
<style>
:root{{color-scheme:dark}}
body{{margin:0;background:#0b1117;color:#f1e8db;font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif;line-height:1.72}}
a{{color:#eac782;text-underline-offset:4px}}a:focus-visible{{outline:3px solid #ffe2a4;outline-offset:4px}}
header,main,footer{{max-width:1040px;margin:0 auto;padding:22px clamp(18px,5vw,58px)}}
nav{{display:flex;gap:18px;flex-wrap:wrap;padding:15px 0;border-bottom:1px solid #695534}}
h1{{font-size:clamp(2rem,4.6vw,3.7rem);line-height:1.12;color:#ffe2a4}}h2{{color:#e9c480;margin-top:0}}
section{{margin:22px 0;padding:20px 25px;background:#172029;border:1px solid #645331;border-radius:16px}}
.lead{{font-size:1.13rem;max-width:70ch}}footer{{border-top:1px solid #645331;color:#c8bba5}}
</style></head>
<body data-mpw-evidence-policy="20261027"><header>
<nav aria-label="Main"><a href="/">MojPlayWin</a><a href="/knowledge/">Knowledge</a><a href="/research/">Research</a><a href="/mpw-editorial/field-guides/20261023/index.html">Field guides</a><a href="/services/">Services</a></nav>
<h1>Research and evidence standards</h1>
<p class="lead">How to interpret our illustrative methods, external references, research proposals, and commercial service descriptions.</p>
</header><main id="main-content">
<section><h2>Practical implementation guidance</h2><p>Field guides contain original recommendations informed by the specific external documentation cited on each guide. Those references are not proof that a listed capability is already deployed in MojPlayWin. Reproduce the steps on the relevant product and device before operational reliance.</p></section>
<section><h2>Numbers and worked scenarios</h2><p>Unless a page explicitly identifies a reproducible measurement and its provenance, values in worked examples illustrate possible calculations. They are not observed performance results, verified customer outcomes or independent benchmarks for MojPlayWin.</p></section>
<section><h2>Research status and limitations</h2><p>Research briefs describe questions, possible methods, measurement frameworks, limitations and cited material. They are educational proposals, not peer-reviewed original experiments, independently accredited findings or evidence that a described facility is operating.</p></section>
<section><h2>Compliance, licensing and applicability</h2><p>No example establishes professional licensure, regulatory approval, legal compliance, investment return or a guaranteed result. Verify local law, the newest source editions and the facts of the actual case before implementing a proposal.</p></section>
<section><h2>Source integrity</h2><p>Specific guide citations stay with their topics. Readers should inspect the original source, its publication date and any later revisions. Marketing claims and user-facing service descriptions are kept separate from independently verified operating claims.</p></section>
<section><h2>Quotes, orders and payment</h2><p>Service inquiries are nonbinding. Pricing, delivery scope, authorization and any payment are determined only through a confirmed quotation or a verified product checkout. Do not email passwords or payment credentials as part of an inquiry.</p></section>
</main><footer>MojPlayWin editorial policy · <a href="/contact/">Contact</a> · <a href="/mpw-editorial/field-guides/20261023/index.html">Browse field guides</a></footer></body></html>
""".encode("utf-8")

def transform(path,kind):
    orig=path.read_bytes()
    s=orig.decode("utf-8")
    title=safe_title(s)
    label=html.escape(title,quote=True)
    link=f'<a href="{POLICY_URL}">evidence standards</a>'
    if kind=="guide":
        new=f"For the topic <em>{label}</em>, use the sources listed below to check relevant methods. Any worked figures illustrate a scenario, not measured MojPlayWin performance. Consult the shared {link} before applying the method."
        s=replace_one(s,OLD_GUIDE,new+"<!-- "+MARKER+" -->",str(path))
    elif kind=="collection":
        a=f"Explore ten illustrated approaches to {label}. The notes are educational examples and do not establish that a described commercial service is operating."
        b=f"This {label} research collection presents proposed questions, methods and limits; it does not represent peer-reviewed original results or independent accreditation. See the {link}."
        c=f'<strong>Evidence notice for {label}:</strong> Referenced methods are not professional certification, regulatory approval or guaranteed outcomes. Check current sources and the {link}.'
        s=replace_one(s,OLD_VISUAL,a+"<!-- "+MARKER+" -->",str(path))
        if s.count(OLD_RESEARCH)!=1 or s.count(OLD_NOTICE)!=1:raise ValueError("Incomplete collection research notices "+str(path))
        s=s.replace(OLD_RESEARCH,b,1).replace(OLD_NOTICE,c,1)
    elif kind=="service":
        new=f"For <strong>{label}</strong>, send your requirements through the quote request below. Payment is requested only after an agreed scope and quotation or a verified checkout. Review our {link}."
        s=replace_one(s,OLD_CTA,new+"<!-- "+MARKER+" -->",str(path))
    else:raise ValueError("Unknown section kind")
    return orig,s.encode("utf-8")

def manifest_targets():
    sets={
        "guide":sorted(GUIDES.glob("*/index.html")),
        "collection":sorted(COLLECTIONS.glob("*/index.html")),
        "service":sorted(SERVICES.glob("*/index.html")),
    }
    expected={"guide":50,"collection":18,"service":12}
    for kind,paths in sets.items():
        if len(paths)!=expected[kind]:raise ValueError(f"Unexpected {kind} count {len(paths)} expected {expected[kind]}")
    if POLICY.exists() or POLICY.is_symlink():raise ValueError("Policy page already exists")
    result={}
    for kind,paths in sets.items():
        for p in paths:
            if p.is_symlink() or not p.is_file() or not str(p.resolve()).startswith(str(BASE.resolve())+"/"):
                raise ValueError("Invalid site file "+str(p))
            before,after=transform(p,kind)
            if before==after:raise ValueError("No change "+str(p))
            result[str(p.relative_to(ROOT))]=dict(path=p,kind=kind,before=before,after=after,mode=stat.S_IMODE(p.stat().st_mode))
    return result

def atomic(path,content,mode=0o644):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=".mpw-editorial-",dir=path.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as f:
            f.write(content);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def backup_dir(run_id):
    if not re.fullmatch(r"\d{6,20}",run_id):raise ValueError("Bad run ID")
    return BACKUPS/("editorial-standards-"+run_id)

def rollback(run_id):
    backup=backup_dir(run_id)
    mf=backup/"manifest.json"
    if not mf.exists():raise ValueError("Missing release manifest")
    manifest=json.loads(mf.read_text())
    restored=0
    for key,rec in manifest.items():
        if key=="_policy":continue
        p=ROOT/key
        before=backup/key
        if p.exists() and sha(p.read_bytes())==rec["after"] and before.is_file() and sha(before.read_bytes())==rec["before"]:
            atomic(p,before.read_bytes(),rec["mode"]);restored+=1
    if POLICY.is_file() and sha(POLICY.read_bytes())==manifest["_policy"]["sha"]:
        POLICY.unlink()
    print("MPW_EDITORIAL_ROLLBACK",restored,flush=True)

def publish(run_id):
    targets=manifest_targets()
    policy=new_policy()
    backup=backup_dir(run_id)
    if backup.exists():raise ValueError("Backup collision")
    backup.mkdir(parents=True,mode=0o700)
    backup.chmod(0o700)
    manifest={}
    try:
        for key,rec in targets.items():
            dest=backup/key
            atomic(dest,rec["before"],0o600)
            manifest[key]=dict(before=sha(rec["before"]),after=sha(rec["after"]),mode=rec["mode"],kind=rec["kind"])
        manifest["_policy"]=dict(sha=sha(policy))
        atomic(backup/"manifest.json",json.dumps(manifest,indent=2,sort_keys=True).encode(),0o600)
        for key,rec in targets.items():
            if sha(rec["path"].read_bytes())!=sha(rec["before"]):raise ValueError("Source drift "+key)
        for key,rec in targets.items():
            atomic(rec["path"],rec["after"],rec["mode"])
        atomic(POLICY,policy)
    except Exception:
        if (backup/"manifest.json").exists():rollback(run_id)
        raise
    print("MPW_EDITORIAL_POLICY_PUBLISHED",len(targets),sha(policy)[:20],flush=True)

def main():
    mode=sys.argv[1] if len(sys.argv)>1 else "preflight"
    if mode=="selftest":
        assert len(OLD_GUIDE)>200 and len(OLD_RESEARCH)>220
        assert "Research and evidence standards" in new_policy().decode()
        print("MPW_EDITORIAL_SELFTEST_OK")
    elif mode=="preflight":
        result=manifest_targets()
        print("MPW_EDITORIAL_PREFLIGHT_OK",len(result),{kind:sum(r["kind"]==kind for r in result.values()) for kind in ("guide","collection","service")},flush=True)
    elif mode=="publish":publish(sys.argv[2])
    elif mode=="rollback":rollback(sys.argv[2])
    else:raise ValueError("Unknown action")
if __name__=="__main__":main()
