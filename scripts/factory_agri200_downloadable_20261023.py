#!/usr/bin/env python3
"""Make real, reproducible, *private* bilingual research navigator ZIPs.

A navigator is a functioning offline reference/observation tool, NOT a finished
agronomy manual, an independent scientific review, or a sale authorization.
Every source and manuscript is verified against the immutable Stage-2->5 chain.
"""
import argparse
import fcntl
import hashlib
import html
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import sys
import zipfile

SCHEMA = "saeit.factory.agri200.research-navigator-candidate.v1"
NAME = re.compile(r"WO-[0-9]{8}--r[0-9]{3}\.json\Z")
LOCALES = ("fa-IR", "en-US")
MAX_DOC = 600_000


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_module(path, name):
    p = Path(path)
    if not p.is_file() or p.is_symlink():
        raise RuntimeError("CANDIDATE_UNSAFE_DEPENDENCY")
    spec = importlib.util.spec_from_file_location(name, str(p))
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def data_script(value):
    """JSON in inert script tag: prevent markup/script-breakout."""
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return (raw.replace("&", "\\u0026").replace("<", "\\u003c")
               .replace(">", "\\u003e").replace("\u2028", "\\u2028")
               .replace("\u2029", "\\u2029"))


def render_navigator(design, research, editions, order_id):
    chapters = design["chapters"]
    sources = research["sources"]
    if len(chapters) < 5 or len(sources) < 4:
        raise RuntimeError("CANDIDATE_INSUFFICIENT_EVIDENCE")
    payload = {
        "order": order_id,
        "titles": {loc: editions[loc]["title"] for loc in LOCALES},
        "chapters": [
            {"n": unit["unit"], "fa": unit["title_fa"],
             "en": unit["title_en"], "ids": unit["source_ids"]}
            for unit in chapters],
        "sources": [
            {"id": item["id"], "title": item["title"],
             "publisher": item["publisher"], "url": item["url"],
             "year": item.get("publication_year"), "doi": item.get("doi", "")}
            for item in sources],
    }
    script_data = data_script(payload)
    return """<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Evidence Navigator | راهنمای مرور شواهد پژوهشی</title>
<style>
:root{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color-scheme:light;
--ink:#18372c;--muted:#50685d;--line:#ccdcd2;--paper:#fcfdf9;--accent:#137b57}
*{box-sizing:border-box}body{margin:0;background:#eaf2ec;color:var(--ink)}
header{background:linear-gradient(115deg,#073b2a,#17674b);color:white;padding:30px max(20px,calc((100vw - 980px)/2))}
main{max-width:980px;margin:auto;padding:20px}
h1{margin:4px 0 12px;font-size:clamp(24px,4vw,36px)}
h2{margin:0 0 14px}section{background:var(--paper);padding:22px;border-radius:16px;margin:18px 0;border:1px solid var(--line);box-shadow:0 4px 16px #1a523a0d}
small,.muted{color:var(--muted)}.pill{background:#d8eee0;padding:4px 10px;border-radius:30px;display:inline-block}
button,select,input,textarea{font:inherit;color:inherit}button{cursor:pointer;border:0;border-radius:9px;background:var(--accent);color:#fff;padding:11px 17px}button:focus-visible,a:focus-visible,input:focus-visible,textarea:focus-visible{outline:3px solid #efa620}
input,textarea,select{border:1px solid #acc2b2;background:white;border-radius:8px;padding:10px;width:100%}
label{display:block;font-weight:650;margin:10px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
.article{border:1px solid var(--line);border-radius:12px;padding:14px;background:white}
.article a{color:#075d46;overflow-wrap:anywhere}ul{padding-inline-start:24px}
@media print{header{background:white;color:black}section{box-shadow:none}button,#filter{display:none!important}body{background:white}}
</style></head><body>
<header><div class="pill" style="color:#143c2b">Private evidence-linked learning tool / ابزار یادگیری پژوهش‌محور</div>
<h1 id="title"></h1><p id="disclaimer"></p>
<button id="lang" type="button" aria-label="Switch language">English / فارسی</button></header>
<main><section><h2 id="topics-title"></h2><div id="chapters" class="grid"></div></section>
<section><h2 id="references-title"></h2>
<label id="filter-label" for="filter"></label><input id="filter" type="search">
<div id="sources" class="grid" aria-live="polite"></div></section>
<section><h2 id="observation-title"></h2><p id="observation-help"></p>
<div class="grid"><label><span id="field-label"></span><input id="field" maxlength="100" placeholder="Field / Farm"></label>
<label><span id="date-label"></span><input id="date" type="date"></label></div>
<label id="notes-label" for="notes"></label><textarea id="notes" rows="6" maxlength="15000"></textarea>
<p><button id="export" type="button"></button> <button id="print" type="button"></button></p>
<p class="muted" id="privacy"></p></section></main>
<script id="metadata" type="application/json">""" + script_data + """</script>
<script>
"use strict";
const data=JSON.parse(document.getElementById("metadata").textContent);
const $=id=>document.getElementById(id);
const dict={
fa:{"disclaimer":"این ابزار فقط مرور منابع و ثبت مشاهدات است. متن کامل مطالعات، اعتبار علمی و توصیه‌های اجرایی هنوز مستقل تأیید نشده‌اند. داده ساختگی یا نسخه مصرف نهاده ارائه نمی‌شود.",
"topics-title":"فصل‌ها و مسیر بررسی","references-title":"منابع قابل ردیابی","filter-label":"جست‌وجو در منابع",
"observation-title":"دفتر مشاهده شخصی","observation-help":"مشاهدات خودتان را بنویسید؛ برداشت علمی یا دستور مصرف را از روی این فهرست منابع استنتاج نکنید.",
"field-label":"محل مطالعه","date-label":"تاریخ","notes-label":"مشاهدات و ابهامات",
"export":"دریافت گزارش CSV","print":"چاپ / ذخیره PDF","privacy":"ورودی‌ها فقط در این مرورگر نگهداری می‌شوند و به هیچ سروری ارسال نمی‌شوند.",
"source":"منبع","year":"سال","none":"موردی پیدا نشد"},
en:{"disclaimer":"Research navigation and personal observations only. Full papers, scientific claims and operational recommendations remain unverified. This tool does not invent field data or prescribe inputs.",
"topics-title":"Chapters and evidence tasks","references-title":"Traceable sources","filter-label":"Search sources",
"observation-title":"Personal observation log","observation-help":"Record your own observations; a bibliography alone cannot establish a safe intervention.",
"field-label":"Study location","date-label":"Date","notes-label":"Observations and open questions",
"export":"Download CSV log","print":"Print / save as PDF","privacy":"Your entries stay in this browser and are not transmitted to a server.",
"source":"Source","year":"Year","none":"No matching sources"}};
let lang="fa";
const storageKey="saeit-evidence-"+data.order;
try{const saved=JSON.parse(localStorage.getItem(storageKey)||"{}");for(const id of ["field","date","notes"]){if(typeof saved[id]==="string")$(id).value=saved[id].slice(0,id==="notes"?15000:100)}}catch(_){}
for(const id of ["field","date","notes"]){$(id).addEventListener("input",()=>{try{localStorage.setItem(storageKey,JSON.stringify({field:$("field").value,date:$("date").value,notes:$("notes").value}))}catch(_){}})}
function para(parent,text,tag){const el=document.createElement(tag||"p");el.textContent=String(text);parent.appendChild(el);return el}
function render(){
const t=dict[lang];document.documentElement.lang=lang==="fa"?"fa":"en";document.documentElement.dir=lang==="fa"?"rtl":"ltr";
$("title").textContent=data.titles[lang==="fa"?"fa-IR":"en-US"];
for(const key of Object.keys(t)){const e=$(key);if(e)e.textContent=t[key]}
$("filter").placeholder=t["filter-label"];
const c=$("chapters");c.replaceChildren();for(const unit of data.chapters){const e=document.createElement("article");e.className="article";para(e,unit.n+". "+unit[lang],"h3");para(e,t.source+": "+unit.ids.join(", "),"small");c.appendChild(e)}
const s=$("sources");s.replaceChildren();const query=$("filter").value.toLocaleLowerCase();
let count=0;for(const ref of data.sources){if(![ref.id,ref.title,ref.publisher,ref.doi||""].join(" ").toLocaleLowerCase().includes(query))continue;
const e=document.createElement("article");e.className="article";para(e,ref.title,"h3");para(e,ref.publisher+" · "+t.year+" "+(ref.year||"?"));const a=document.createElement("a");a.textContent=ref.id+" ↗";a.href=ref.url;a.target="_blank";a.rel="noopener noreferrer";e.appendChild(a);s.appendChild(e);count++}
if(!count)para(s,t.none)}
$("lang").addEventListener("click",()=>{lang=lang==="fa"?"en":"fa";render()});
$("filter").addEventListener("input",render);
$("print").addEventListener("click",()=>window.print());
$("export").addEventListener("click",()=>{
const rows=[["Order","Location","Date","Notes"],[data.order,$("field").value,$("date").value,$("notes").value]];
const csv=rows.map(row=>row.map(value=>'"'+String(value).replaceAll('"','""')+'"').join(",")).join("\r\n");
const blob=new Blob(["\ufeff",csv],{type:"text/csv;charset=utf-8"});
const url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="observation-"+data.order+".csv";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)});
render();
</script></body></html>
"""


def reproducible_zip(files, root_name):
    names = sorted(files)
    if not names or len(names) > 12 or any(
            not isinstance(x, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", x)
            for x in names):
        raise RuntimeError("CANDIDATE_UNSAFE_MEMBER")
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in names:
            content = files[name]
            if not isinstance(content, bytes) or not 0 < len(content) <= MAX_DOC:
                raise RuntimeError("CANDIDATE_UNSAFE_PAYLOAD")
            info = zipfile.ZipInfo(root_name+"/"+name, (2020,1,1,0,0,0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, content)
    out=stream.getvalue()
    with zipfile.ZipFile(io.BytesIO(out)) as z:
        if z.testzip() or set(z.namelist()) != {root_name+"/"+n for n in names}:
            raise RuntimeError("CANDIDATE_ZIP_VERIFICATION_FAILED")
        if any(z.read(root_name+"/"+n) != files[n] for n in names):
            raise RuntimeError("CANDIDATE_ZIP_CONTENT_MISMATCH")
    return out


def package_one(area, name, lib, stage5):
    if not NAME.fullmatch(name):
        raise RuntimeError("CANDIDATE_ORDER_ID_INVALID")
    handoff, prototype, design, research, order, editions = stage5.verified_stage4(area, name, lib)
    stage5_manifest=lib.read(area/"stage-05/completed-drafts"/name)
    if (stage5_manifest.get("schema") != stage5.SCHEMA
            or stage5_manifest.get("order_id") != handoff["order_id"]
            or stage5_manifest.get("stage2_research_sha256") != lib.digest(research)
            or stage5_manifest.get("stage4_prototype_sha256") != lib.digest(prototype)
            or stage5_manifest.get("commercial_release") is not False):
        raise RuntimeError("CANDIDATE_STAGE5_MANIFEST_INTEGRITY")
    manuscripts={}
    for locale in LOCALES:
        path=area/"stage-05/drafts"/name[:-5]/(locale+".md")
        if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_DOC:
            raise RuntimeError("CANDIDATE_MANUSCRIPT_MISSING")
        raw=path.read_bytes()
        if digest(raw)!=stage5_manifest["manuscript_sha256"][locale] or len(raw.split())<1000:
            raise RuntimeError("CANDIDATE_MANUSCRIPT_HASH_MISMATCH")
        manuscripts[locale]=raw
    safe_sources=[{"id":s["id"],"title":s["title"],
                   "publisher":s["publisher"],"url":s["url"],
                   "doi":s.get("doi"),"publication_year":s.get("publication_year")}
                  for s in research["sources"]]
    readme=("# Offline Agricultural Evidence Navigator / راهنمای آفلاین منابع کشاورزی\n\n"
            "Open index.html locally for a bilingual, searchable reference explorer, "
            "chapter roadmap and CSV observation journal. Markdown files are accompanying "
            "research-method workbook DRAFTS, not validated crop-care manuals.\n\n"
            "Educational bibliography and method tool only. Not independently reviewed; "
            "not authorized for public sale or agronomic recommendations. "
            "Source titles and links belong to their publishers. No fabricated field data.\n").encode("utf-8")
    files={"index.html":render_navigator(design,research,editions,handoff["order_id"]).encode(),
           "fa-IR.md":manuscripts["fa-IR"],
           "en-US.md":manuscripts["en-US"],
           "sources.json":(json.dumps(safe_sources,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode(),
           "README.md":readme}
    files["integrity.json"]=(json.dumps({
        "schema":SCHEMA,"order_id":handoff["order_id"],
        "stage5_manifest_sha256":lib.digest(stage5_manifest),
        "contents_sha256":{k:digest(v) for k,v in sorted(files.items())},
        "technical_package_complete":True,
        "scientific_quality_certified":False,
        "ready_for_paid_store":False,
        "public_distribution_allowed":False,
    },sort_keys=True,indent=2)+"\n").encode()
    zip_bytes=reproducible_zip(files,"agri-"+name[:-5])
    sha=digest(zip_bytes)
    dest=area/"stage-05/downloadable-candidates"/name[:-5]
    stage5.write_once(dest/("navigator-"+sha+".zip"),zip_bytes,lib)
    receipt={"schema":SCHEMA,"order_id":handoff["order_id"],
             "stage5_manifest_sha256":lib.digest(stage5_manifest),
             "zip_sha256":sha,"zip_bytes":len(zip_bytes),
             "file_hashes":{k:digest(v) for k,v in sorted(files.items())},
             "archive_relative_path":str(dest.relative_to(area)/("navigator-"+sha+".zip")),
             "technical_package_complete":True,"scientific_quality_certified":False,
             "ready_for_paid_store":False,"public_distribution_allowed":False}
    return lib.once(area/"stage-05/downloadable-receipts"/name,receipt)


def fair_selection(names, state, batch):
    """Persist a cursor so orders after the first batch cannot be starved."""
    if state is None:
        state={"schema":"saeit.factory.agri200.navigator-cursor.v1","next_index":0}
    if (state.get("schema")!="saeit.factory.agri200.navigator-cursor.v1"
            or type(state.get("next_index")) is not int
            or state["next_index"]<0):
        raise RuntimeError("CANDIDATE_CURSOR_INVALID")
    total=len(names)
    start=state["next_index"]%total if total else 0
    count=min(batch,total)
    selected=[names[(start+i)%total] for i in range(count)]
    return selected,{"schema":"saeit.factory.agri200.navigator-cursor.v1",
                     "next_index":(start+count)%total if total else 0}


def execute(root, lib, stage5, batch=250, only_order_id=None):
    if only_order_id is not None and (not isinstance(only_order_id,str)
                                   or re.fullmatch(r"WO-[0-9]{8}",only_order_id) is None):
        raise RuntimeError("CANDIDATE_TARGET_ORDER_INVALID")
    area=Path(root).resolve()/"production-instructions"
    inbox=area/"stage-05/completed-drafts"
    if inbox.is_symlink() or not inbox.is_dir():
        raise RuntimeError("CANDIDATE_STAGE5_INBOX_MISSING")
    lib.private_dir(area/"stage-05/downloadable-receipts")
    lib.private_dir(area/"stage-05/downloadable-candidates")
    lock=area/".research-navigator-build.lock"
    if lock.is_symlink():
        raise RuntimeError("CANDIDATE_UNSAFE_LOCK")
    with lock.open("a+b") as handle:
        os.fchmod(handle.fileno(),0o600)
        fcntl.flock(handle.fileno(),fcntl.LOCK_EX)
        names=sorted(p.name for p in inbox.iterdir()
                     if p.is_file() and not p.is_symlink() and NAME.fullmatch(p.name))
        cursor_path=area/"stage-05/downloadable-cursor.json"
        if cursor_path.is_symlink():
            raise RuntimeError("CANDIDATE_CURSOR_SYMLINK")
        state=lib.read(cursor_path) if cursor_path.exists() else None
        selected,new_state=fair_selection(names,state,batch)
        if only_order_id is not None:
            selected=[name for name in names if name.startswith(only_order_id+"--r")][:batch]
        made=blocked=0
        for name in selected:
            try:
                made+=int(package_one(area,name,lib,stage5))
            except (KeyError,RuntimeError,ValueError,TypeError,OSError,zipfile.BadZipFile) as e:
                blocked+=1
                lib.atomic(area/"stage-05/downloadable-blocked"/name,{
                    "order_file":name,"reason":type(e).__name__+":"+str(e)[:180],
                    "scientific_quality_certified":False,"public_distribution_allowed":False})
        if only_order_id is None:
            lib.atomic(cursor_path,new_state)
        result={"private_downloadable_candidate_zips":len(list(
                  (area/"stage-05/downloadable-receipts").glob("WO-*.json"))),
                "new_packages_this_tick":made,"blocked_this_tick":blocked,
                "inspected_this_tick":len(selected),
                "scientific_approvals_created":0,"paid_publications_created":0,
                "sites_modified":False}
        lib.atomic(area/"stage-05/downloadable-candidate-status.json",result)
        return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--factory-private",required=True)
    parser.add_argument("--stage34-worker",required=True)
    parser.add_argument("--stage5-worker",required=True)
    parser.add_argument("--batch",type=int,default=250)
    parser.add_argument("--only-order-id")
    a=parser.parse_args()
    if not 1<=a.batch<=500:raise RuntimeError("CANDIDATE_BATCH_INVALID")
    lib=load_module(a.stage34_worker,"candidate_stage34")
    stage5=load_module(a.stage5_worker,"candidate_stage5")
    print(json.dumps(execute(a.factory_private,lib,stage5,a.batch,
                             only_order_id=a.only_order_id),
                     ensure_ascii=False,sort_keys=True),flush=True)


if __name__=="__main__":
    try:main()
    except Exception as e:
        print("CANDIDATE_WORKER_ERROR="+type(e).__name__+":"+str(e)[:180],file=sys.stderr)
        sys.exit(1)
