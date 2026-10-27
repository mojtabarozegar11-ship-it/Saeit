#!/usr/bin/env python3
"""Read-only information architecture audit for MojPlayWin, sitemap-wide."""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import html
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

BASE = "https://mojplaywin.com"
HEADERS = {"User-Agent": "MojPlayWinSiteAudit/20261027 (owner quality assurance)"}

def clean(t):
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)
    t = re.sub(r"<(?:script|style)\b[^>]*>.*?</(?:script|style)>", " ", t, flags=re.I | re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()

def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as resp:
            data=resp.read(400000).decode("utf-8","replace")
            status=resp.status
            effective=resp.url
    except urllib.error.HTTPError as exc:
        return dict(url=url,status=exc.code,error=str(exc), effective=url)
    except Exception as exc:
        return dict(url=url,status=0,error=repr(exc),effective=url)
    if not data.lstrip().startswith("<") or "<html" not in data[:2000].lower():
        return dict(url=url,status=status,content_type="non-html",len=len(data),effective=effective)
    title_match=re.search(r"<title\b[^>]*>(.*?)</title>",data,re.I | re.S)
    h1=re.findall(r"<h1\b[^>]*>(.*?)</h1>",data,re.I | re.S)
    heads=re.findall(r"<h2\b[^>]*>(.*?)</h2>",data,re.I | re.S)
    canonical=re.findall(r'<link\b[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)',data,re.I)
    footer=re.search(r"<footer\b",data,re.I)
    main_end=re.search(r"</main\s*>",data,re.I)
    body=data
    body=re.sub(r"<(?:header|nav|footer|aside)\b[^>]*>.*?</(?:header|nav|footer|aside)>"," ",body,flags=re.I|re.S)
    paragraphs=[clean(x) for x in re.findall(r"<p\b[^>]*>(.*?)</p>",body,re.I|re.S)]
    unique_long=list(dict.fromkeys(re.sub(r"\s+"," ",p.lower()) for p in paragraphs if len(p)>105))
    anchors=re.findall(r'href=["\']([^"\']+)["\']',data,re.I)
    return dict(url=url,status=status,effective=effective,len=len(data),title=clean(title_match.group(1))[:90] if title_match else "",h1=[clean(x)[:120] for x in h1],h2=[clean(x)[:110] for x in heads],canonical=canonical,
                main_open=len(re.findall(r"<main\b",data,re.I)),main_close=len(re.findall(r"</main\s*>",data,re.I)),
                footer_order="main-before-footer" if main_end and footer and main_end.start()<footer.start() else "misordered-or-missing",
                long_paragraphs=unique_long,internal_links=sum(1 for x in anchors if x.startswith("/")),late_visible_section=bool(footer and re.search(r"<section\b",data[footer.end():],re.I)))

def main():
    with urllib.request.urlopen(urllib.request.Request(BASE+"/sitemap.xml",headers=HEADERS),timeout=30) as response:
        root=ET.fromstring(response.read())
    urls=list(dict.fromkeys(x.text for x in root.iter() if x.tag.endswith("loc") and x.text and x.text.startswith(BASE)))
    print("ARCHITECTURE_AUDIT_SITEMAP",len(urls),flush=True)
    results=[]
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures={pool.submit(get,url):url for url in urls}
        for future in as_completed(futures):
            results.append(future.result())
    errs=[(x["url"],x.get("status"),x.get("error","")) for x in results if x.get("status")!=200]
    print("SITE_HTTP_FAILURES",len(errs),repr(errs[:35]))
    html_pages=[x for x in results if x.get("status")==200 and "long_paragraphs" in x]
    print("HTML_PAGE_COUNT",len(html_pages))
    canonicals=defaultdict(list)
    exact_titles=defaultdict(list)
    shared=defaultdict(list)
    for p in html_pages:
        for c in p["canonical"]:canonicals[c].append(p["url"])
        if p["title"]:exact_titles[p["title"]].append(p["url"])
        for para in set(p["long_paragraphs"]):shared[para].append(p["url"])
    print("DUPLICATE_CANONICALS",repr({k:v for k,v in canonicals.items() if len(v)>1})[:5000])
    print("DUPLICATE_TITLES",repr({k:v for k,v in exact_titles.items() if len(v)>1})[:5000])
    missing_h1=[p["url"].replace(BASE,"") for p in html_pages if len(p["h1"])!=1]
    missing_canonical=[p["url"].replace(BASE,"") for p in html_pages if len(p["canonical"])!=1]
    print("H1_COUNT_ANOMALIES",len(missing_h1),repr(missing_h1[:35]))
    print("CANONICAL_COUNT_ANOMALIES",len(missing_canonical),repr(missing_canonical[:35]))
    seen_urls=[]
    for p in sorted(html_pages,key=lambda x:x["url"]):
        if p["main_open"]!=p["main_close"] or p["footer_order"]!="main-before-footer" or p["late_visible_section"]:
            seen_urls.append((p["url"].replace(BASE,""),p["main_open"],p["main_close"],p["footer_order"],p["late_visible_section"]))
    print("STRUCTURAL_ANOMALIES",len(seen_urls),repr(seen_urls[:55]))
    common=sorted(((len(set(us)),len(p),p[:150],sorted(set(us))[:9]) for p,us in shared.items() if len(set(us))>=3),reverse=True)
    print("CROSS_PAGE_REUSED_PARAGRAPHS",len(common))
    for n,length,sample,urls in common[:30]:
        print("SHARED_PARA",n,length,repr(sample),repr([u.replace(BASE,"") for u in urls]))
    score=[]
    for p in html_pages:
        shared_n=sum(1 for para in p["long_paragraphs"] if len(set(shared[para]))>=4)
        count=len(p["long_paragraphs"])
        score.append((shared_n / count if count else 0,shared_n,count,p["url"].replace(BASE,""),p["len"],len(p["h2"]),p["h1"][:1]))
    for rec in sorted(score,reverse=True)[:45]:print("PAGE_SHARED_RATIO",repr(rec))
    print("SITE_ARCHITECTURE_AUDIT_COMPLETE",len(urls),len(html_pages),len(errs))
    if len(urls)<152 or errs or seen_urls:
        raise RuntimeError("Incomplete site map, HTTP failures or broken semantic structure")
    if any(len(v)>1 for v in canonicals.values()) or any(len(v)>1 for v in exact_titles.values()):
        raise RuntimeError("Duplicate canonical/title map")
    print("SITE_ARCHITECTURE_LIVE_INTEGRITY_PASS",len(urls),"URLs","long_reused_paragraphs",len(common))

if __name__ == "__main__":main()
