#!/usr/bin/env python3
"""Read-only, bounded production census for EXISTING zomorodmelal.ir, no content changes.

Only anonymous GETs to allowed public paths; never submit, edit, delete, pay, login,
or treat HTTP 200 as sufficient proof of usable content.
"""
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit, unquote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

HOST="zomorodmelal.ir"
BASE="https://"+HOST
MAX_SCAN=200
MAX_SITEMAP_BYTES=4_000_000
STATIC=[
"/", "/company/", "/company/executive/", "/about/", "/company-gallery/",
"/company/department-1/", "/company/department-2/",
"/company/unit-1/", "/company/unit-2/", "/company/genetics-1/",
"/company/product-1/", "/company/product-2/",
"/company/statutory-1/", "/company/statutory-2/",
"/company/project-1/", "/company/project-2/",
"/services/", "/contact/", "/ask-master/index.php?service=1",
"/agriculture/", "/agriculture/genetics/", "/agriculture/horticulture/",
"/agriculture/greenhouse/", "/agriculture/livestock/",
"/agriculture/free-tools/20261025/",
"/agriculture/water-soil/irrigation-planner/",
"/agriculture/greenhouse/ventilation-estimator/",
"/industry/", "/research/", "/research/projects/",
"/research/directory/centers/bioinformatics/",
"/research/directory/laboratories/microbiology/",
"/knowledge/", "/newsletter/", "/newsletter/archive/", "/news/", "/blog/",
"/topics/", "/topics/zm-r01/wheat/", "/agents/", "/economy/", "/market/",
"/business/", "/studio/", "/games/", "/games/water-path/",
"/apps/", "/store/", "/auctions/", "/tala/", "/ghanadi/",
"/ghanadi/cafe-shiraz/", "/faremah/", "/farnaz/", "/amozeshgah/",
"/education/", "/academy/", "/weather/", "/search/?q=%DA%A9%D8%B4%D8%A7%D9%88%D8%B1%D8%B2%DB%8C",
"/en/", "/assets/zm-ar-v1.html", "/authors/mojtaba-rozegar/",
"/en/authors/mojtaba-rozegar/", "/site-heritage/home-before-nexus-20261112/index.html",
"/staff/", "/staff/command-center/", "/api/health/", "/api/bridge/health/",
]
DENY=re.compile(r"(?i)(?:logout|delete|remove|wipe|flush|reset|checkout|purchase|payment|pay/|subscribe/|unsubscribe/|enroll/|complete/|submit/|vote/|withdraw|transfer|start-trade|login/|admin/|__zm|private|\.bak(?:$|/)|\.env|wp-admin)")
class Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.titles=[];self.h1=[];self.meta={};self.links=[];self.images=[];self.canonical=[]
        self.rootattrs={};self.current=None;self.body=[];self.in_skip=0;self.seen_main=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="html":self.rootattrs=a
        if tag in ("title","h1"):self.current=tag
        if tag=="main":self.seen_main=True;self.in_skip+=1
        if tag=="meta" and a.get("name"):self.meta[a["name"].lower()]=a.get("content","")
        if tag=="link" and a.get("rel")=="canonical":self.canonical.append(a.get("href",""))
        if tag=="a" and a.get("href"):self.links.append(a["href"])
        if tag=="img":self.images.append(a)
    def handle_endtag(self,tag):
        if tag in ("title","h1"):self.current=None
        if tag=="main" and self.in_skip:self.in_skip-=1
    def handle_data(self,data):
        txt=" ".join(data.split())
        if not txt:return
        if self.current=="title":self.titles.append(txt)
        if self.current=="h1":self.h1.append(txt)
        if self.in_skip:self.body.append(txt)

def allowed(path):
    u=urlsplit(path)
    if u.scheme or u.netloc or not u.path.startswith("/") or not u.path or len(path)>320:
        return False
    if DENY.search(u.path):return False
    if u.query and not(u.path=="/ask-master/index.php" and u.query=="service=1"
       or u.path=="/search/" and u.query.startswith("q=")):return False
    if re.search(r"(?i)\.(?:png|gif|jpg|jpeg|webp|svg|css|js|woff2?|pdf|zip|tar|gz|mp4)(?:$|/)",u.path):
        return False
    return True
def get(path,limit=1_250_000):
    start=time.monotonic()
    req=Request(BASE+path,headers={"User-Agent":"ZomorodSitewidePublicAudit/1.0 (limited read only)",
        "Accept":"text/html,application/xml,text/xml,text/plain;q=0.9,*/*;q=0.3",
        "Cache-Control":"no-cache"},method="GET")
    try:
        with urlopen(req,timeout=18) as res:
            data=res.read(limit+1)
            status=res.status; dest=res.url;h=dict(res.headers)
    except HTTPError as e:
        data=e.read(min(limit,64_000));status=e.code;dest=e.url;h=dict(e.headers)
    except (URLError,TimeoutError,ConnectionError,OSError) as e:
        return {"path":path,"code":0,"error":str(e)[:130],"ms":round(1000*(time.monotonic()-start)),"bytes":0,"host_ok":False}
    u=urlsplit(dest)
    return {"path":path,"code":status,"bytes":len(data),"ms":round(1000*(time.monotonic()-start)),
        "host_ok":u.scheme=="https" and u.hostname in (HOST,"www."+HOST),
        "content_type":h.get("Content-Type",""),"headers":h,
        "oversize":len(data)>limit,"body":data[:limit],"final":dest}

def normalize_text(s):return re.sub(r"\s+"," ",html.unescape(s)).strip()
def uniq(seq):return list(dict.fromkeys(seq))
def main():
    started=time.time()
    report_dir=Path(os.environ.get("RUNNER_TEMP","/tmp"))/"zm-sitewide-audit"
    report_dir.mkdir(parents=True,exist_ok=True)
    notes=[];sitemap={}
    for path in ("/robots.txt","/sitemap.xml","/topics/sitemap.xml","/ghanadi/sitemap.xml"):
        r=get(path,MAX_SITEMAP_BYTES)
        entry={"path":path,"code":r["code"],"bytes":r["bytes"],"ms":r["ms"],
               "oversize":r.get("oversize",False),"host_ok":r["host_ok"]}
        if "sitemap" in path and r["code"]==200 and r["host_ok"]:
            try:
                xml=ET.fromstring(r["body"])
                urls=[]
                for el in xml.iter():
                    if el.tag.endswith("}loc") or el.tag=="loc":
                        loc=(el.text or "").strip()
                        u=urlsplit(loc)
                        if u.scheme=="https" and u.hostname in (HOST,"www."+HOST):
                            raw=u.path or "/"
                            if allowed(raw):urls.append(raw)
                entry["listed_urls"]=len(urls)
                sitemap[path]=uniq(urls)
            except (ET.ParseError, UnicodeError) as e:entry["parse_error"]=str(e)[:200]
        if path=="/robots.txt" and r["code"]==200:
            lines=r["body"].decode("utf8","replace").splitlines()
            entry["sitemap_directives"]=[x.strip() for x in lines if x.lower().startswith("sitemap:")]
            entry["disallows"]=[x.strip() for x in lines if x.lower().startswith("disallow:")]
        notes.append(entry)
        print("ZM_SITEWIDE_META "+json.dumps(entry,ensure_ascii=False),flush=True)
    sitemap_all=uniq(u for urls in sitemap.values() for u in urls)
    selected=[p for p in STATIC if allowed(p)]
    # Stratified sitemap sampling: one representative from every 1st path segment,
    # then take remainder in deterministic sitemap order up to hard cap.
    bucket={}
    for path in sitemap_all:
        key=path.strip("/").split("/")[0] or "home"
        bucket.setdefault(key,[]).append(path)
    for paths in bucket.values():
        selected.extend(paths[:min(5,len(paths))])
    selected=uniq(selected)
    selected.extend(p for p in sitemap_all if p not in selected)
    selected=uniq(selected)[:MAX_SCAN]
    records=[];link_targets=set();groups={};canonical_groups={};header=None
    for i,path in enumerate(selected,1):
        r=get(path)
        data=r.pop("body",b"")
        hdr=r.pop("headers",{})
        if path=="/":header={k.lower():v for k,v in hdr.items() if k.lower() in
            ("strict-transport-security","content-security-policy","x-frame-options",
            "x-content-type-options","referrer-policy","permissions-policy","cache-control",
            "content-type","server","set-cookie")}
        kind="html" if b"<html" in data[:1500].lower() and b"</html" in data[-3500:].lower() else "not_html"
        issues=[];warnings=[]
        if r["code"]>=500 or r["code"]==0:issues.append("server_or_network_failure")
        elif r["code"]>=400:issues.append("http_"+str(r["code"]))
        elif r["code"] in (301,302,303,307,308):warnings.append("redirect")
        if not r["host_ok"]:issues.append("unexpected_final_host")
        if r.get("oversize"):warnings.append("body_too_large_for_audit")
        if r["code"]==200 and kind!="html" and path not in ("/api/health/","/api/bridge/health/"):
            issues.append("http_200_non_html")
        row={**r,"kind":kind,"issues":issues,"warnings":warnings}
        if kind=="html":
            p=Parser()
            try:p.feed(data.decode("utf8","replace"))
            except Exception:issues.append("html_parse_error")
            title=normalize_text(" ".join(p.titles))
            visible=normalize_text(" ".join(p.body))
            row.update({"title":title[:180],"description":p.meta.get("description","")[:210],
              "canonical":p.canonical[0] if p.canonical else "",
              "robots":p.meta.get("robots",""),
              "lang":p.rootattrs.get("lang",""),
              "h1":p.h1[:4],
              "main_chars":len(visible),
              "images":len(p.images),"images_missing_alt":sum("alt" not in x for x in p.images),
              "link_count":len(p.links)})
            if r["code"]==200 and len(data)<700:issues.append("suspicious_short_html")
            if r["code"]==200 and path not in ("/search/",) and len(visible)<95:
                warnings.append("little_main_text")
            if not title:warnings.append("no_title")
            if not p.canonical:warnings.append("no_canonical")
            if len(p.h1)==0:warnings.append("no_h1")
            if len(p.h1)>1:warnings.append("multi_h1")
            if len(p.images) and any("alt" not in x for x in p.images):warnings.append("images_missing_alt")
            if (re.search(r"(?i)(django debug|traceback \(most recent call last\)|internal server error)",data.decode("utf8","replace"))):
                issues.append("possible_error_detail_exposure")
            for link in p.links:
                u=urlsplit(link)
                if link.startswith("/") and allowed(u.path or "/"):
                    link_targets.add(u.path)
                elif u.scheme=="https" and u.hostname in (HOST,"www."+HOST) and allowed(u.path or "/"):
                    link_targets.add(u.path)
            # Only compare meaningful main text; many static pages share header/footer.
            if len(visible)>180 and r["code"]==200:
                finger=hashlib.sha256(visible[:12000].encode()).hexdigest()[:16]
                groups.setdefault(finger,[]).append(path)
            if row.get("canonical") and r["code"]==200:
                canonical_groups.setdefault(row["canonical"],[]).append(path)
        records.append(row)
        important=issues or (warnings and path in STATIC)
        if important:
            print("ZM_SITEWIDE_FINDING "+json.dumps({
                "path":path,"code":r["code"],"issues":issues,"warnings":warnings,
                "title":row.get("title","")[:100]},ensure_ascii=False),flush=True)
        if i%25==0:
            print("ZM_SITEWIDE_PROGRESS "+json.dumps({"probed":i,"limit":MAX_SCAN,
               "hard_failures":sum(bool(x["issues"]) for x in records)},ensure_ascii=False),flush=True)
        time.sleep(.09)
    duplicates=[{"fingerprint":k,"paths":v[:35],"count":len(v)}
        for k,v in groups.items() if len(v)>1]
    duplicates.sort(key=lambda x:x["count"],reverse=True)
    shared_canonical=[{"canonical":k,"paths":v[:30],"count":len(v)}
        for k,v in canonical_groups.items() if len(v)>1]
    shared_canonical.sort(key=lambda x:x["count"],reverse=True)
    covered={r["path"] for r in records}
    missing_targets=sorted(p for p in link_targets if p not in covered)
    errors=[{"path":r["path"],"code":r["code"],"issues":r["issues"]}
        for r in records if r["issues"]]
    warnings=[{"path":r["path"],"warnings":r["warnings"]}
        for r in records if r["warnings"]]
    summary={"scope":"EXISTING_SITE_READONLY","total_sitemap_urls":len(sitemap_all),
        "requested_limit":MAX_SCAN,"pages_checked":len(records),
        "http_200":sum(r["code"]==200 for r in records),
        "http_3xx":sum(300<=r["code"]<400 for r in records),
        "http_4xx":sum(400<=r["code"]<500 for r in records),
        "http_5xx_or_network":sum(r["code"]>=500 or r["code"]==0 for r in records),
        "error_pages":len(errors),"warning_pages":len(warnings),
        "duplicate_content_groups":len(duplicates),
        "duplicate_canonical_groups":len(shared_canonical),
        "sitemap_coverage_pct":round(100*len(set(sitemap_all)&covered)/len(sitemap_all),1) if sitemap_all else None,
        "unprobed_link_targets":len(missing_targets),
        "site_writes":0,"forms_submitted":0,"payments":0,
        "elapsed_s":round(time.time()-started,1)}
    report={"summary":summary,"sitemaps":notes,"security_headers":header,
        "records":records,"errors":errors,"warnings":warnings,
        "exact_duplicate_main_text":duplicates[:40],
        "shared_canonical":shared_canonical[:40],
        "not_checked_discovered_links":missing_targets[:150]}
    (report_dir/"sitewide-http.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
    print("ZM_SITEWIDE_DUPLICATES "+json.dumps(duplicates[:12],ensure_ascii=False),flush=True)
    print("ZM_SITEWIDE_CANONICALS "+json.dumps(shared_canonical[:12],ensure_ascii=False),flush=True)
    print("ZM_SITEWIDE_SECURITY_HEADERS "+json.dumps(header,ensure_ascii=False),flush=True)
    print("ZM_SITEWIDE_HTTP_SUMMARY "+json.dumps(summary,ensure_ascii=False),flush=True)
    summary_file=os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file,"a",encoding="utf8") as f:
            f.write("## Existing Zomorod site — public GET audit only\n\n")
            f.write("Site write count: 0. Probed "+str(len(records))+" URLs; sitemap listed "+
                    str(len(sitemap_all))+" distinct eligible URLs.\n\n")
            f.write("| Metric | Evidence |\n|---|---|\n")
            for k,v in summary.items():f.write("| "+str(k)+" | "+str(v)+" |\n")
            f.write("\n### First 40 hard issues\n\n")
            for issue in errors[:40]:f.write("- "+str(issue)+"\n")
            f.write("\n### Duplicate content groups\n\n")
            for item in duplicates[:20]:f.write("- "+str(item)+"\n")
            f.write("\nGET only, no forms, logins, payments, mutations, or template changes.\n")
if __name__=="__main__":main()
