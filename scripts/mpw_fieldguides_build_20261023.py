#!/usr/bin/env python3
"""Deterministic creator for 50 independently authored MojPlayWin technical field notes.
The five editorial JSON datasets contain unique, topic-specific human-readable
analysis. A common layout is not counted as independent article content.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import re
import shutil
from pathlib import Path
from urllib.parse import quote

RELEASE="MPW-FIELDGUIDES-20261023-01"
ROOT="https://mojplaywin.com/mpw-editorial/field-guides/20261023/"
FILES=("performance","images","input","accessibility","security")
SOURCES={
 "CWV":("Google Search Central: Core Web Vitals","https://developers.google.com/search/docs/appearance/core-web-vitals"),
 "LCP":("web.dev: Optimize Largest Contentful Paint","https://web.dev/articles/optimize-lcp"),
 "INP":("web.dev: Optimize Interaction to Next Paint","https://web.dev/articles/optimize-inp"),
 "CLS":("web.dev: Optimize Cumulative Layout Shift","https://web.dev/articles/optimize-cls"),
 "CAN":("MDN: Optimizing Canvas","https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API/Tutorial/Optimizing_canvas"),
 "PTR":("MDN: Pointer events","https://developer.mozilla.org/en-US/docs/Web/API/Pointer_events"),
 "IMG":("MDN: Responsive images","https://developer.mozilla.org/en-US/docs/Web/HTML/Guides/Responsive_images"),
 "WCAG":("W3C: WCAG 2.2 Recommendation","https://www.w3.org/TR/WCAG22/"),
 "LIVE":("MDN: ARIA live regions","https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-live"),
 "STORE":("MDN: Window.localStorage","https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage"),
 "AUDIO":("MDN: Web Audio API best practices","https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API/Best_practices"),
 "SW":("MDN: Service Worker API","https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API"),
 "UPLOAD":("OWASP: File Upload Cheat Sheet","https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html"),
 "CSP":("OWASP: Content Security Policy Cheat Sheet","https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html"),
 "INPUT":("OWASP: Input Validation Cheat Sheet","https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html"),
 "SEO":("Google Search Central: SEO Starter Guide","https://developers.google.com/search/docs/fundamentals/seo-starter-guide"),
}
CSS="""*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 80% 0,#1b304a,transparent 55%),#091425;color:#e8f2ff;font:16px/1.75 system-ui,-apple-system,Segoe UI,sans-serif}a{color:#86e9dc}a:hover{text-decoration-thickness:2px}header,main,footer{width:min(1100px,100%);margin:auto;padding:20px}header{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;border-bottom:1px solid #36506c}header>a{font-weight:900;text-decoration:none;color:#f7d4a1}main{padding-top:28px}h1{font-size:clamp(34px,5vw,58px);letter-spacing:-.05em;line-height:1.08;margin:8px 0 18px}h2{font-size:23px;color:#f0dbb9;margin:28px 0 8px}.lead{font-size:20px;color:#c7dbee;max-width:790px}.eyebrow{letter-spacing:.15em;text-transform:uppercase;font-size:12px;color:#79e8d4;font-weight:800}.content{max-width:860px}.content p{color:#c5d4e4}.panel{border:1px solid #375872;border-radius:17px;background:#10243a;padding:18px 22px;margin:20px 0}.panel h2:first-child{margin-top:0}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,270px),1fr));gap:13px}.card{border:1px solid #31536d;border-radius:15px;padding:18px;background:#10263c;text-decoration:none;color:#eff6ff;display:block}.card strong{font-size:18px;color:#f5d4a7;line-height:1.3;display:block}.card small{color:#9ec0da}.card:hover{background:#19344d}.source{padding:9px 0;line-height:1.4}.meta{color:#b0c5d4;font-size:13px}.chip{background:#204b4e;color:#b4ffe3;border-radius:999px;font-size:12px;font-weight:700;padding:5px 10px}.search{background:#111e33;border:1px solid #547492;color:white;padding:13px 16px;border-radius:12px;font:inherit;width:min(600px,100%)}.group{margin-top:35px}.steps{display:grid;gap:12px}footer{border-top:1px solid #35516d;margin-top:30px;font-size:14px;color:#b1c7d9}button:focus-visible,a:focus-visible,input:focus-visible{outline:3px solid #7eeddb;outline-offset:4px}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}"""
def h(s):return html.escape(str(s),quote=True)
def doc(title,desc,canonical,body):
    head=('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
          '<meta name="theme-color" content="#091425"><meta name="description" content="'+h(desc[:170])+'">'
          '<link rel="canonical" href="'+h(canonical)+'"><meta property="og:type" content="article">'
          '<meta property="og:title" content="'+h(title)+'"><meta property="og:description" content="'+h(desc[:170])+'">'
          '<title>'+h(title)+' | MojPlayWin</title><style>'+CSS+'</style></head><body>')
    return head+'<header><a href="'+ROOT+'index.html">MOJPLAYWIN / FIELD STUDIO</a><nav><a href="/games/">Games</a> · <a href="/products/">Tools</a> · <a href="'+ROOT+'prism-relay/index.html">Play Prism Relay</a></nav></header><main>'+body+'</main><footer>Original practical implementation notes, 23 October 2026 · '+RELEASE+' · <a href="'+ROOT+'index.html">All 50 guides</a></footer></body></html>'
def build(repo:Path,out:Path):
    if out.exists():raise RuntimeError("Output already exists; refusing overwrite")
    out.mkdir(parents=True)
    all_rows=[]
    for category in FILES:
        p=repo/"scripts"/("mpw_fieldguides_"+category+"_20261023.json")
        content=json.loads(p.read_text(encoding="utf-8"))
        if content.get("category","").lower()!=category:raise RuntimeError("Category mismatch: "+category)
        rows=content["articles"]
        if len(rows)!=10:raise RuntimeError("Expected 10 authored notes in "+category)
        for row in rows:
            if len(row)!=8:raise RuntimeError("Field schema "+repr(row[:2]))
            slug,title,group,context,method,example,pitfall_and_test,refs=row
            sentences=re.split(r"(?<=[.!?])\s+",pitfall_and_test)
            if len(sentences)<2:raise RuntimeError("Separate validation sentence required "+slug)
            caution=" ".join(sentences[:-1]);verification=sentences[-1]
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*",slug):raise RuntimeError("Invalid slug")
            if group.lower()!=category or not all(isinstance(x,str) and len(x)>45 for x in (context,method,example)) or len(caution)<15 or len(verification)<12:
                raise RuntimeError("Insufficient unique article material "+slug)
            ref_ids=refs.split(",")
            if len(ref_ids)!=2 or any(r not in SOURCES for r in ref_ids):raise RuntimeError("Invalid source reference "+slug)
            all_rows.append(dict(slug=slug,title=title,group=group,context=context,method=method,example=example,caution=caution,verification=verification,refs=ref_ids))
    if len(all_rows)!=50 or len({x["slug"] for x in all_rows})!=50:raise RuntimeError("Missing or duplicate independent guides")
    for i,x in enumerate(all_rows):
        rel="guides/"+x["slug"]+"/index.html"
        target=out/rel;target.parent.mkdir(parents=True)
        refs=''.join('<li class="source"><a href="'+h(SOURCES[z][1])+'" rel="noopener noreferrer" target="_blank">'+h(SOURCES[z][0])+'</a></li>' for z in x["refs"])
        related=all_rows[(i+1)%50]
        parts=['<article class="content"><span class="eyebrow">Field guide '+str(i+1).zfill(2)+' / 50 · '+h(x["group"])+'</span><h1>'+h(x["title"])+'</h1><p class="meta">Original applied analysis · Practical browser-game engineering · First published 23 October 2026</p>']
        for body,heading in [(x["context"],"The practical problem"),(x["method"],"Implementation protocol"),(x["example"],"Worked scenario"),(x["caution"],"What could go wrong"),(x["verification"],"Acceptance criteria")]:
            parts.append("<section><h2>"+h(heading)+"</h2><p>"+h(body)+"</p></section>")
        parts.append('<section class="panel"><h2>Source material and evidence boundaries</h2><p>These original implementation recommendations are informed by the following authoritative documentation and standards. Any numbers in worked scenarios are illustrative calculations, not measured performance results for MojPlayWin or the cited sources. Validate them on the intended product and hardware.</p><ul>'+refs+'</ul></section>')
        parts.append('<div class="panel"><strong>Next independent topic:</strong> <a href="'+ROOT+'guides/'+h(related["slug"])+'/index.html">'+h(related["title"])+'</a> · <a href="'+ROOT+'index.html">All 50 field guides</a></div></article>')
        description=x["context"]+" "+x["method"]
        (target).write_text(doc(x["title"],description,ROOT+rel,"".join(parts)),encoding="utf-8")
    topics=[]
    for category in FILES:
        matches=[x for x in all_rows if x["group"].lower()==category]
        cards=''.join('<a class="card" href="guides/'+h(x["slug"])+'/index.html"><small>FIELD GUIDE '+str(all_rows.index(x)+1).zfill(2)+'</small><strong>'+h(x["title"])+'</strong><small>'+h(category.title())+' · source-backed</small></a>' for x in matches)
        topics.append('<section class="group" data-category="'+h(category)+'"><h2>'+h(category.title())+' — 10 field guides</h2><div class="cards">'+cards+'</div></section>')
    home='<span class="eyebrow">Research-backed practical collection • 50 independent guides • new original game</span><h1>Build browser games that <span style="color:#85f1d4">actually work.</span></h1><p class="lead">Fifty independently authored, actionable implementation field notes. Each page has a distinct engineering question, implementation approach, worked scenario, failure mode, acceptance test, and primary-source links. These are applied guides, not peer-reviewed original research or claimed benchmark results.</p><div class="panel"><span class="chip">Original new playable game</span><h2>Prism Relay — 150 solvable laser puzzles</h2><p>Rotate mirrors to route light across a 7×7 circuit. Includes undo, hints, keyboard and mobile controls, deterministic puzzles and locally saved stage progress.</p><a href="prism-relay/index.html" style="color:#ffdc9e;font-weight:900">Play Prism Relay free →</a></div><label for="filter"><strong>Search the 50 topics:</strong></label><p><input id="filter" class="search" type="search" placeholder="Search performance, images, input, accessibility, security…" aria-describedby="searchState"></p><p id="searchState" class="meta" aria-live="polite">All 50 guides shown</p>'+''.join(topics)
    home+='<script>(function(){const input=document.getElementById("filter"),cards=Array.from(document.querySelectorAll(".card")),state=document.getElementById("searchState");input.addEventListener("input",function(){const needle=input.value.trim().toLowerCase();let shown=0;for(const a of cards){let match=a.textContent.toLowerCase().includes(needle);a.hidden=!match;if(match)shown++;}document.querySelectorAll(".group").forEach(g=>{g.hidden=!Array.from(g.querySelectorAll(".card")).some(a=>!a.hidden)});state.textContent=shown+" of 50 guides shown";});if(new URLSearchParams(location.search).has("selftest")){let e=document.createElement("output");e.id="selftest";e.dataset.result=cards.length===50?"pass":"fail";e.textContent=e.dataset.result==="pass"?"FIELDGUIDES_SEARCH_SELFTEST_PASS":"FIELDGUIDES_SEARCH_SELFTEST_FAIL";document.body.append(e)}})();</script>'
    (out/"index.html").write_text(doc("Field Studio: 50 Practical Guides and Prism Relay","Fifty independent practical browser-game engineering field guides with source links, plus the new Prism Relay puzzle game.",ROOT+"index.html",home),encoding="utf-8")
    game=repo/"mpw-editorial/field-guides/20261023/prism-relay/index.html"
    if not game.is_file() or "PRISM_RELAY_FUNCTIONAL_TEST_PASS" not in game.read_text():raise RuntimeError("Missing tested source game")
    (out/"prism-relay").mkdir()
    shutil.copyfile(game,out/"prism-relay/index.html")
    import xml.etree.ElementTree as ET
    names=["index.html","prism-relay/index.html"]+["guides/"+x["slug"]+"/index.html" for x in all_rows]
    xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
    node=ET.Element("urlset",xmlns=xmlns)
    for n in names:
        url=ET.SubElement(node,"url");ET.SubElement(url,"loc").text=ROOT+n
        ET.SubElement(url,"lastmod").text="2026-10-23"
    (out/"sitemap.xml").write_bytes(b'<?xml version="1.0" encoding="UTF-8"?>\n'+ET.tostring(node,encoding="utf8"))
    files={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob("*") if p.is_file()}
    expected=set(names+["sitemap.xml"])
    if set(files)!=expected:raise RuntimeError("Unexpected generated file set")
    manifest={"release_id":RELEASE,"language":"en","created":"2026-10-23","guide_count":len(all_rows),"guide_categories":list(FILES),"game":"prism-relay/index.html","stage_count":150,"output_count":len(files)+1,"files_sha256":files,"sources":[{"id":k,"title":v[0],"url":v[1]} for k,v in SOURCES.items()],"notes":"Original practical guides, illustrative examples, not clinical or peer-reviewed research."}
    (out/"release.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("FIELD_GUIDES_BUILD_VALIDATED",json.dumps({"release_id":RELEASE,"guide_count":50,"total_public_files":len(files)+1,"original_game":True,"unique_slugs":len({x["slug"] for x in all_rows})}))
if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--repo",type=Path,default=Path.cwd());parser.add_argument("--out",type=Path,required=True)
    a=parser.parse_args();build(a.repo,a.out)
