#!/usr/bin/env python3
"""Read-only public inventory of two sitemap files, lightly rate-limited."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from collections import Counter, defaultdict
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
import csv,json,os,re,sys,threading,time,xml.etree.ElementTree as ET
from pathlib import Path
HOST="zomorodmelal.ir"
BASE="https://"+HOST
PATHS=["/","/store/","/search/","/about/","/company/","/contact/","/agriculture/","/research/","/knowledge/","/news/","/agents/","/business/","/tala/","/industry/","/services/","/studio/","/amozeshgah/","/economy/","/market/","/blog/"]
HEADERS={"User-Agent":"ZomorodMelalReadOnlyQualityAudit/2026-10","Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.5"}
lock=threading.Lock(); last=[0.0]
def throttle():
    with lock:
        now=time.monotonic()
        delay=max(0,0.26-(now-last[0]))
        if delay:time.sleep(delay)
        last[0]=time.monotonic()
def fetch(url,cap=210000,timeout=22):
    throttle()
    started=time.monotonic()
    try:
        with urlopen(Request(url,headers=HEADERS),timeout=timeout) as r:
            data=r.read(cap)
            return {"status":r.status,"final":r.url,"content_type":r.headers.get("Content-Type",""),"headers":{k.lower():v for k,v in r.headers.items()},"data":data,"ms":round((time.monotonic()-started)*1000)}
    except HTTPError as e:
        return {"status":e.code,"final":url,"content_type":e.headers.get("Content-Type",""),"headers":{k.lower():v for k,v in e.headers.items()},"data":e.read(2500),"ms":round((time.monotonic()-started)*1000)}
    except Exception as e:
        return {"status":0,"final":url,"content_type":"","headers":{},"data":b"","ms":round((time.monotonic()-started)*1000),"error":str(e)[:160]}
class Inspect(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title=[];self.active_title=False;self.meta={};self.canonical=[];self.h1=[];self.in_h1=False
        self.img=0;self.images_missing_alt=0;self.images_empty_alt=0;self.scripts=0;self.styles=0;self.css=[];self.links=[];self.form_count=0
        self.h2=0;self.lang="";self.dir=""
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="html":self.lang=a.get("lang","");self.dir=a.get("dir","")
        elif tag=="title":self.active_title=True
        elif tag=="h1":self.in_h1=True;self.h1.append("")
        elif tag=="h2":self.h2+=1
        elif tag=="meta":
            key=a.get("name",a.get("property","")).lower()
            if key:self.meta[key]=a.get("content","")
        elif tag=="link":
            if a.get("rel","").lower()=="canonical":self.canonical.append(a.get("href",""))
            if "stylesheet" in a.get("rel","").lower():self.css.append(a.get("href",""))
        elif tag=="img":
            self.img+=1
            if "alt" not in a:self.images_missing_alt+=1
            elif not a["alt"]:self.images_empty_alt+=1
        elif tag=="a" and a.get("href"):self.links.append(a["href"])
        elif tag=="script":self.scripts+=1
        elif tag=="style":self.styles+=1
        elif tag=="form":self.form_count+=1
    def handle_endtag(self,tag):
        if tag=="title":self.active_title=False
        elif tag=="h1":self.in_h1=False
    def handle_data(self,data):
        if self.active_title:self.title.append(data)
        if self.in_h1 and self.h1:self.h1[-1]+=data
def canonicalize(u):
    x=urlsplit(u)
    return urlunsplit((x.scheme.lower(),x.netloc.lower(),x.path.rstrip("/") or "/",x.query,""))
def inspect(url):
    x=fetch(url)
    status=x["status"];html="html" in x["content_type"].lower()
    row={"url":url,"status":status,"ms":x["ms"],"final":x["final"],"bytes_sample":len(x["data"]),"mime":x["content_type"],"error":x.get("error","")}
    if status!=200 or not html:
        return row
    p=Inspect()
    try:p.feed(x["data"].decode("utf-8",errors="replace"))
    except Exception as e:row["parse_error"]=str(e)[:130]
    title=" ".join("".join(p.title).split())
    desc=p.meta.get("description","")
    hs=[" ".join(y.split()) for y in p.h1]
    c=p.canonical[0] if p.canonical else ""
    row.update(title=title,description=desc[:220],h1=hs[:8],h1_count=len(hs),nonempty_h1=sum(bool(y) for y in hs),
      canonical=c,canonical_match=(canonicalize(c)==canonicalize(url) if c else False),
      robots=p.meta.get("robots",""),lang=p.lang,dir=p.dir,og_title=p.meta.get("og:title",""),
      images=p.img,missing_img_alt=p.images_missing_alt,empty_img_alt=p.images_empty_alt,styles=p.styles,style_links=len(p.css),
      scripts=p.scripts,form_count=p.form_count,h2_count=p.h2,unique_links=len(set(p.links)),
      is_topic="/topics/zm-r" in url,header_cache_control=x["headers"].get("cache-control",""),
      headers_security={k:x["headers"].get(k,"") for k in ["strict-transport-security","content-security-policy","x-content-type-options","x-frame-options","referrer-policy","permissions-policy"]})
    return row
def get_sitemap(path):
    u=BASE+path
    x=fetch(u,cap=3500000,timeout=35)
    if x["status"]!=200:raise RuntimeError(path+" HTTP "+str(x["status"]))
    root=ET.fromstring(x["data"])
    urls=[]
    for e in root.iter():
        if e.tag.endswith("loc") and e.text:
            value=e.text.strip()
            if urlsplit(value).hostname==HOST:urls.append(value)
    return urls
def run():
    out=Path(os.environ.get("AUDIT_DIR","."))
    out.mkdir(parents=True,exist_ok=True)
    main=get_sitemap("/sitemap.xml");topic=get_sitemap("/topics/sitemap.xml")
    urls=list(dict.fromkeys(main+topic+[BASE+x for x in PATHS]))
    # Respect source scope; never submit forms or access login/token/account paths.
    urls=[u for u in urls if urlsplit(u).hostname==HOST and not re.search(r"/(?:admin|login|logout|checkout|payment|api|private)(?:/|$)",urlsplit(u).path)]
    print("CRAWL_INVENTORY="+json.dumps({"main_sitemap":len(main),"topics_sitemap":len(topic),"unique_target_urls":len(urls)},ensure_ascii=False),flush=True)
    rows=[];start=time.monotonic()
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(inspect,u):u for u in urls}
        for i,f in enumerate(as_completed(futures),1):
            try:r=f.result()
            except Exception as e:r={"url":futures[f],"status":0,"error":str(e)[:160]}
            rows.append(r)
            if i%100==0:print("CRAWL_PROGRESS="+json.dumps({"done":i,"total":len(urls),"seconds":round(time.monotonic()-start)}),flush=True)
    rows.sort(key=lambda x:x["url"])
    title_group=defaultdict(list);description_group=defaultdict(list)
    for r in rows:
        if r.get("title"):title_group[r["title"]].append(r["url"])
        if r.get("description"):description_group[r["description"]].append(r["url"])
    noindex=[r for r in rows if "noindex" in r.get("robots","").lower()]
    issues={
      "http_failures":[{"url":r["url"],"code":r["status"],"error":r.get("error","")} for r in rows if r["status"]!=200],
      "missing_titles":[r["url"] for r in rows if r["status"]==200 and "html" in r.get("mime","") and not r.get("title")],
      "missing_descriptions":[r["url"] for r in rows if r["status"]==200 and "html" in r.get("mime","") and not r.get("description")],
      "missing_canonicals":[r["url"] for r in rows if r["status"]==200 and "html" in r.get("mime","") and not r.get("canonical")],
      "mismatching_canonicals":[{"url":r["url"],"canonical":r.get("canonical")} for r in rows if r.get("canonical") and not r.get("canonical_match")],
      "missing_h1":[r["url"] for r in rows if r["status"]==200 and "html" in r.get("mime","") and not r.get("nonempty_h1")],
      "multiple_nonempty_h1":[{"url":r["url"],"h1":r.get("h1")} for r in rows if r.get("nonempty_h1",0)>1],
      "image_alt_missing":[{"url":r["url"],"n":r.get("missing_img_alt")} for r in rows if r.get("missing_img_alt",0)>0],
      "duplicate_titles":[{"title":k[:95],"n":len(v),"examples":v[:5]} for k,v in title_group.items() if len(v)>1],
      "duplicate_descriptions":[{"description":k[:95],"n":len(v),"examples":v[:5]} for k,v in description_group.items() if len(v)>1],
      "noindex":[{"url":r["url"],"robots":r.get("robots")} for r in noindex],
      "slowest":[{"url":r["url"],"ms":r.get("ms")} for r in sorted(rows,key=lambda x:x.get("ms",0),reverse=True)[:15]]
    }
    report={"scope":"public sitemap URLs and selected other public sections, no mutations or authenticated actions",
      "inventory":{"main_sitemap":len(main),"topics_sitemap":len(topic),"unique_target_urls":len(urls),"elapsed_s":round(time.monotonic()-start)},
      "statuses":dict(Counter(r["status"] for r in rows)),"issues":issues,
      "template_examples":{k:[r for r in rows if r["url"]==BASE+k][:1] for k in PATHS},"rows":rows}
    (out/"site-crawl.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    with (out/"site-pages.csv").open("w",newline="",encoding="utf-8") as f:
        cols=["url","status","ms","title","description","canonical","canonical_match","robots","lang","nonempty_h1","images","missing_img_alt","styles","style_links","scripts"]
        writer=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore");writer.writeheader();writer.writerows(rows)
    print("CRAWL_FINAL="+json.dumps({
       "inventory":report["inventory"],"statuses":report["statuses"],
       "counts":{k:len(v) for k,v in issues.items()},
       "http_failures":issues["http_failures"][:30],
       "missing_titles":issues["missing_titles"][:20],
       "missing_descriptions":issues["missing_descriptions"][:20],
       "mismatch_canonicals":issues["mismatching_canonicals"][:14],
       "duplicate_titles":issues["duplicate_titles"][:9],
       "noindex":issues["noindex"][:14],
       "top_slow":issues["slowest"][:8],
       "security_header_sample":[{"url":r["url"],"headers":r.get("headers_security")} for r in rows if r["url"] in [BASE+"/",BASE+"/store/",BASE+"/about/",BASE+"/tala/",BASE+"/business/"]]
    },ensure_ascii=False),flush=True)
if __name__=="__main__":run()
