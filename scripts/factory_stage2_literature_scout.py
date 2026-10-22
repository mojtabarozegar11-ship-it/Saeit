#!/usr/bin/env python3
"""Autonomous, evidence-constrained Stage-2 agriculture research scout.

Discover real indexed scientific papers from OpenAlex, optionally inspect
Crossref metadata, and make narrowly traceable source-to-claim workpapers
using ONLY short, exact sentences present in retrieved indexed abstracts.
This is bibliographic desk research, not field research or independent
scientific validation. No LLM or paid key required. Fail closed on incomplete
relevance, references, or provenance. Does not touch live websites.
"""
import argparse
import concurrent.futures
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SCHEMA="saeit.factory.stage2-literature-scout.v1"
EVIDENCE_SCHEMA="saeit.factory.stage2-source-evidence.v1"
TOPIC_ID=re.compile(r"AGRI-[0-9]{3}\Z")
WORD_RE=re.compile(r"[a-z]{3,}")
SAFE_KEYS={"openalex":"https://api.openalex.org/works",
           "crossref":"https://api.crossref.org/works"}
STOP={"for","the","and","with","from","guide","basics","basic","how","to",
      "easy","complete","step","steps","practical","simple","diy","home",
      "plant","plants","growing","grow","care","raising","crop","crops",
      "management","project","projects","manual","planner","worksheet",
      "workbook","field","farm","farming","garden","gardening","production",
      "small","scale","beginner","best","safe","using","method","methods",
      "planning","calendar","new","advanced","improve","improved","issues"}
RISK=re.compile(r"(pesticid|insecticid|herbicid|fungicid|mushroom|"
                r"forag|poison|tox|livestock|hatch|slaughter|"
                r"food safety|food process|bee|beekeep|chicken|poultry)",
                re.I)
MAX_DOC=6_000_000


def sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
                separators=(",",":")).encode("utf8")).hexdigest()


def load_worker(path):
    spec=importlib.util.spec_from_file_location("factory_stage2_core",str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("SCOUT_STAGE2_WORKER_NOT_FOUND")
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def normalize(word):
    w=word.lower()
    for suffix in ("ation","izing","ing","ies","ers","es","s"):
        if len(w)>len(suffix)+4 and w.endswith(suffix):
            return w[:-len(suffix)]
    return w


def keys(title):
    unique=[]
    for w in WORD_RE.findall(str(title).lower()):
        stem=normalize(w)
        if w in STOP or stem in STOP or stem in unique:
            continue
        unique.append(stem)
    if not unique:
        unique=[normalize(x) for x in WORD_RE.findall(str(title).lower())
                if len(x)>4][:3]
    return unique[:7]


def abstract_from_index(mapping):
    if not isinstance(mapping,dict) or len(mapping)>3000:
        return ""
    length=0
    for positions in mapping.values():
        if not isinstance(positions,list) or len(positions)>200:
            return ""
        if positions:
            if not all(type(x) is int and 0<=x<=1600 for x in positions):
                return ""
            length=max(length,max(positions)+1)
    if length<24 or length>1600:
        return ""
    out=[""]*length
    for word,positions in mapping.items():
        if not isinstance(word,str) or len(word)>80:
            return ""
        for position in positions:
            if out[position]:
                return ""
            out[position]=word
    if any(not w for w in out):
        return ""
    text=" ".join(out)
    for mark in (".",",",";",":","!","?",")","]"):
        text=text.replace(" "+mark,mark)
    text=text.replace("( ","(").replace("[ ","[")
    return text[:12000]


def citation_sentence(abstract, topic_keys):
    text=abstract.replace("\n"," ").strip()
    if len(text)<210:
        return None
    sentences=re.split(r"(?<=[.!?])\s+",text)
    ranked=[]
    for sentence in sentences:
        sentence=sentence.strip()
        parts=sentence.split()
        if not 10<=len(parts)<=24 or not 58<=len(sentence)<=240:
            continue
        normalized={normalize(w) for w in WORD_RE.findall(sentence)}
        matched=[k for k in topic_keys if k in normalized or any(
                 w.startswith(k) and len(k)>4 for w in normalized)]
        if not matched or len(matched)<min(2,len(topic_keys)):
            continue
        if any(x in sentence.lower() for x in
               ("http://","https://","copyright","all rights reserved")):
            continue
        if not sentence.endswith((".","!","?")):
            continue
        ranked.append((len(matched),len(sentence),sentence))
    if not ranked:
        return None
    return sorted(ranked,key=lambda q:(-q[0],q[1]))[0][2]


def reliable_url(value,worker):
    if not isinstance(value,str):
        return None
    try:
        host=worker.validate_public_https(value)
    except (ValueError,TypeError):
        return None
    if host in ("openalex.org","api.openalex.org","doi.org","dx.doi.org"):
        return None
    return host


def usable_paper(work,topic_keys,worker):
    if not isinstance(work,dict) or work.get("is_retracted") is not False:
        return None
    if work.get("type") not in ("article","review"):
        return None
    title=work.get("display_name") or work.get("title")
    doi=work.get("doi")
    if not isinstance(title,str) or not 18<=len(title)<=400:
        return None
    if not isinstance(doi,str) or not doi.startswith("https://doi.org/"):
        return None
    year=work.get("publication_year")
    if type(year) is not int or not 1980<=year<=2026:
        return None
    venue=work.get("primary_location")
    if not isinstance(venue,dict):
        return None
    source=venue.get("source")
    if not isinstance(source,dict):
        return None
    publisher=(source.get("host_organization_name") or
               source.get("display_name") or "")
    if not isinstance(publisher,str) or not 6<=len(publisher)<=180:
        return None
    url=venue.get("landing_page_url")
    host=reliable_url(url,worker)
    if not host:
        # OpenAlex frequently records a doi.org resolver as its primary
        # landing URL. Prefer a real publisher/institutional OA landing URL
        # if one is included; never count the DOI resolver itself as an
        # independent publisher domain.
        alternate=work.get("best_oa_location")
        if isinstance(alternate,dict):
            candidate=alternate.get("landing_page_url")
            alternative_host=reliable_url(candidate,worker)
            if alternative_host:
                url=candidate
                host=alternative_host
    if not host:
        return None
    abstract=abstract_from_index(work.get("abstract_inverted_index"))
    if len(abstract)<210:
        return None
    title_norm={normalize(w) for w in WORD_RE.findall(title)}
    body_norm={normalize(w) for w in WORD_RE.findall(abstract)}
    title_hits=sum(k in title_norm for k in topic_keys)
    body_hits=sum(k in body_norm for k in topic_keys)
    if title_hits<1 or body_hits<min(2,len(topic_keys)):
        return None
    excerpt=citation_sentence(abstract,topic_keys)
    if not excerpt:
        return None
    ident=work.get("id")
    if not isinstance(ident,str) or not re.fullmatch(
            r"https://openalex\.org/W[0-9]{6,15}",ident):
        return None
    return {
        "openalex_id":ident, "doi":doi, "url":url, "host":host,
        "title":title, "publication_year":year, "publisher":publisher,
        "venue":source.get("display_name"), "abstract_sha256":
            hashlib.sha256(abstract.encode("utf8")).hexdigest(),
        "support_sentence":excerpt,
        "relevance_score":3*title_hits+body_hits,
        "retrieval_type":"OpenAlex indexed abstract",
    }


def select_papers(results,topic_keys,worker):
    if not isinstance(results,list) or len(results)>200:
        return []
    candidates=[]
    for work in results:
        usable=usable_paper(work,topic_keys,worker)
        if usable:
            candidates.append(usable)
    candidates.sort(key=lambda x:(-x["relevance_score"],
                    -x["publication_year"],x["openalex_id"]))
    distinct=[]
    seen_ids=set()
    seen_doi=set()
    for item in candidates:
        if item["doi"].lower() in seen_doi or item["openalex_id"] in seen_ids:
            continue
        seen_ids.add(item["openalex_id"])
        seen_doi.add(item["doi"].lower())
        distinct.append(item)
        if len(distinct)==20:
            break
    return distinct


def registrable_host(host):
    # Conservative offline eTLD grouping: never mistake many subdomains
    # under one institutional publisher for independent domains.
    parts=host.lower().removeprefix("www.").split(".")
    suffix3={("co","uk"),("ac","uk"),("org","uk"),("gov","uk"),
             ("edu","au"),("com","au"),("co","nz"),("com","br")}
    if len(parts)>2 and tuple(parts[-2:]) in suffix3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def diverse_five(papers):
    chosen=[]
    domains=set()
    publishers=set()
    for paper in papers:
        domain=registrable_host(paper["host"])
        publisher=paper["publisher"].lower()
        if domain in domains or publisher in publishers:
            continue
        chosen.append(paper)
        domains.add(domain)
        publishers.add(publisher)
        if len(chosen)==5:
            return chosen
    for paper in papers:
        if len(chosen)==5:
            break
        if paper not in chosen:
            chosen.append(paper)
    if (len(chosen)!=5 or
            len(set(registrable_host(p["host"]) for p in chosen))<3 or
            len(set(p["publisher"].lower() for p in chosen))<3):
        return []
    return chosen


def locale_scopes(order):
    scopes={}
    editions=order.get("editions")
    if not isinstance(editions,list):
        return {}
    for entry in editions:
        if not isinstance(entry,dict) or entry.get("locale") not in ("fa-IR","en-US"):
            continue
        scope=(
            "Literature discovery for "+str(entry["locale"])+": " +
            str(entry.get("title","")) +
            "; geographical audience: "+str(entry.get("audience",""))+
            ". Research metadata and cited abstracts are preliminary; verify "
            "local agronomic applicability, safety and seasonal schedules at editing."
        )
        scopes[entry["locale"]]=scope
    return scopes


def evidence_from_papers(order,revision,papers,worker):
    if RISK.search(str(order.get("subject",""))):
        return None
    chosen=diverse_five(papers)
    if not chosen:
        return None
    locales=locale_scopes(order)
    if set(locales)!={"fa-IR","en-US"}:
        return None
    sources=[]
    claims=[]
    for n,paper in enumerate(chosen,1):
        ident="scholar"+str(n)
        sources.append({
            "id":ident, "publisher":paper["publisher"],
            "title":paper["title"], "url":paper["url"],
            "checked_date":dt.date.today().isoformat(),
            "evidence_note":(
                "OpenAlex abstract index retrieved and checked for exact "
                "supporting sentence by SHA256; primary publisher text and "
                "regional agronomic applicability remain unverified."),
            "doi":paper["doi"], "openalex_id":paper["openalex_id"],
            "publication_year":paper["publication_year"],
            "abstract_sha256":paper["abstract_sha256"],
            "support_sentence_sha256":
                hashlib.sha256(paper["support_sentence"].encode("utf8")).hexdigest(),
            "source_medium":"OpenAlex bibliographic abstract; original source not independently verified"
        })
        claims.append({
            "id":"claim"+str(n), "statement":paper["support_sentence"],
            "source_ids":[ident],
            "assertion_type":"verbatim_short_indexed_abstract_sentence",
            "original_publisher_verification":"not_performed"
        })
    result={
        "schema":EVIDENCE_SCHEMA,
        "source_product_id":order["source_product_id"],
        "revision":revision,
        "work_order_sha256":worker.sha(order),
        "locale_scopes":locales, "sources":sources, "claims":claims,
        "scientific_review_completed":False,
        "public_distribution_allowed":False,
        "collection_method":"openalex_verified_short_abstract_extracts_not_primary_pages",
        "independent_original_page_recheck":False,
        "research_quality_limitations":[
            "Quoted sentences are grounded in retrieved index abstracts but original publisher full text has not been inspected.",
            "Bibliographic metadata is not proof of field performance, local agronomic safety or commercial value.",
            "Scientific specialist review, original publisher checking and complete localized book manuscripts are still required."
        ]
    }
    worker.validate_evidence(result,order,revision)
    return result


def request_json(endpoint,parameters,timeout=10):
    if endpoint not in SAFE_KEYS.values():
        raise RuntimeError("SCOUT_UNTRUSTED_API_ENDPOINT")
    query=urllib.parse.urlencode(parameters)
    url=endpoint+"?"+query
    req=urllib.request.Request(url,headers={
        "User-Agent":"SaeitFactoryResearchScout/1.0 (non-commercial provenance verification)",
        "Accept":"application/json"})
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    opener=urllib.request.build_opener(NoRedirect)
    with opener.open(req,timeout=timeout) as response:
        if response.status!=200:
            raise RuntimeError("SCOUT_API_NOT_OK:"+str(response.status))
        length=response.headers.get("Content-Length")
        if length and int(length)>MAX_DOC:
            raise RuntimeError("SCOUT_API_RESPONSE_TOO_LARGE")
        data=response.read(MAX_DOC+1)
        if len(data)>MAX_DOC:
            raise RuntimeError("SCOUT_API_RESPONSE_TOO_LARGE")
        obj=json.loads(data.decode("utf8"))
        if not isinstance(obj,dict):
            raise RuntimeError("SCOUT_NONOBJECT_API_RESPONSE")
        return obj


def fetch_openalex(title):
    # A narrowly worded topic may have no exact scientific article title;
    # retry with its meaningful subject terms, but never bypass the
    # independently checked relevance/abstract/source-diversity gates.
    subject=" ".join(keys(title)[:4]) or title
    data=request_json(SAFE_KEYS["openalex"],{
        "search":subject,
        "per_page":40,
        "select":"id,display_name,doi,publication_year,type,is_retracted,abstract_inverted_index,primary_location,best_oa_location,cited_by_count"
    },timeout=12)
    value=data.get("results")
    if not isinstance(value,list):
        raise RuntimeError("SCOUT_INVALID_OPENALEX_RESULTS")
    return value


def crossref_metadata(title):
    data=request_json(SAFE_KEYS["crossref"],{
        "query.title":title,"rows":12,
        "select":"DOI,title,publisher,published,URL,type"
    },timeout=10)
    return data.get("message",{}).get("items",[])


def cite_candidates_crossref(items,title):
    selected=[]
    lookup=set(keys(title))
    for item in items[:12]:
        if not isinstance(item,dict):
            continue
        titles=item.get("title")
        if not isinstance(titles,list) or not titles:
            continue
        title0=titles[0]
        doi=item.get("DOI")
        if not isinstance(title0,str) or not isinstance(doi,str):
            continue
        overlap=lookup.intersection({normalize(w) for w in WORD_RE.findall(title0)})
        if len(overlap)<min(2,len(lookup)):
            continue
        selected.append({"title":title0[:400],"doi":"https://doi.org/"+doi,
                         "publisher":str(item.get("publisher",""))[:150],
                         "record_kind":"Crossref metadata only, not verified research"})
    return selected[:10]


def ranking(topic):
    return int(topic.rsplit("-",1)[1])


def sources_for_topic(root,worker,record,fetcher,backstop):
    area=root/"production-instructions"
    ident=record["source_product_id"]
    order_id=record["id"]
    title=next((e.get("title") for e in record.get("editions",[])
                if isinstance(e,dict) and e.get("locale")=="en-US"),None)
    if not isinstance(title,str) or len(title)<8:
        raise RuntimeError("SCOUT_MISSING_ENGLISH_TITLE:"+ident)
    name=ident+"--r001.json"
    output=area/"stage-02"/"literature-candidates"/name
    evidence_path=area/"stage-02"/"source-evidence"/name
    if evidence_path.exists():
        return "already_seeded"
    terms=keys(title)
    try:
        raw=fetcher(title)
        papers=select_papers(raw,terms,worker)
    except Exception as exc:
        packet={
            "schema":SCHEMA,"source_product_id":ident,"order_id":order_id,
            "source_search_query":title,
            "status":"external_research_api_unavailable",
            "last_error":type(exc).__name__+":"+str(exc)[:160],
            "research_completed":False,"source_verified_count":0,
            "checked_utc":utc(),"commercial_release":False
        }
        worker.atomic(output,packet)
        return "api_unavailable"
    result=None
    try:
        result=evidence_from_papers(record,1,papers,worker)
    except (RuntimeError,ValueError,KeyError) as exc:
        pass
    if result is not None:
        # The packet is a documented short-excerpt literature finding, not
        # independently verified primary scientific evidence or product QA.
        if not evidence_path.exists():
            worker.atomic(evidence_path,result)
        return "traceable_abstracts"
    fallback=[]
    if len(papers)<4:
        try:
            fallback=cite_candidates_crossref(backstop(title),title)
        except Exception:
            pass
    candidate={
        "schema":SCHEMA,"source_product_id":ident,"order_id":order_id,
        "source_search_query":title,"search_keywords":terms,
        "status":"indexed_references_found_require_additional_research",
        "indexed_abstract_candidates":papers[:12],
        "crossref_bibliographic_candidates":fallback,
        "indexed_abstract_candidate_count":len(papers),
        "independent_publisher_fulltext_checked":False,
        "stage2_documentation_complete":False,"stage3_handoff":False,
        "commercial_release":False,"quality1000_approved":False,
        "checked_utc":utc()
    }
    worker.atomic(output,candidate)
    return "needs_more_research"


def run(root,stage2_program,fetcher=fetch_openalex,backstop=crossref_metadata,
        batch=200,workers=3):
    root=Path(root).expanduser().resolve()
    worker=load_worker(stage2_program)
    area=root/"production-instructions"
    index=worker.read(area/"owner-agri200-p0-index.json")
    ids=index.get("order_ids_ranked",[])
    if len(ids)!=200 or len(set(ids))!=200:
        raise RuntimeError("SCOUT_BAD_P0_INDEX")
    stage=area/"stage-02"
    worker.directory(stage)
    lock=stage/".research-scout.lock"
    if lock.is_symlink():
        raise RuntimeError("SCOUT_UNSAFE_LOCK")
    with lock.open("a+b") as lk:
        os.chmod(lock,0o600)
        try:
            fcntl.flock(lk.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            return {"already_running":True}
        pending=[]
        for rank,ident in enumerate(ids,1):
            path=area/"stage-02"/"inbox"/(ident+"--r001.json")
            packet,order=worker.verified_stage1_packet(area,path.name)
            if order.get("source_product_id")!="AGRI-%03d"%rank:
                raise RuntimeError("SCOUT_INDEX_ORDER_MISMATCH")
            if (stage/"source-evidence"/(order["source_product_id"]+"--r001.json")).exists():
                continue
            out=stage/"literature-candidates"/(order["source_product_id"]+"--r001.json")
            if out.exists():
                old=worker.read(out)
                try:
                    checked=dt.datetime.fromisoformat(old["checked_utc"])
                    if dt.datetime.now(dt.timezone.utc)-checked<dt.timedelta(hours=18):
                        continue
                except (ValueError,KeyError,TypeError):
                    pass
            pending.append(order)
        selected=pending[:batch]
        counts={"traceable_abstracts":0,"needs_more_research":0,
                "api_unavailable":0,"already_seeded":0}
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures=[pool.submit(sources_for_topic,root,worker,o,fetcher,backstop)
                     for o in selected]
            for future in concurrent.futures.as_completed(futures):
                value=future.result()
                counts[value]+=1
        report={
            "schema":SCHEMA,"input_priority_order_count":200,
            "attempted_this_run":len(selected),
            "source_evidence_automatically_documented":counts["traceable_abstracts"],
            "still_require_manual_or_external_research":counts["needs_more_research"],
            "external_provider_unavailable":counts["api_unavailable"],
            "previously_seeded":counts["already_seeded"],
            "desk_research_verification_required":True,
            "human_specialist_reviews_completed":0,
            "sites_changed":False,"checked_utc":utc()
        }
        worker.atomic(stage/"literature-scout-status.json",report)
        return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--factory-private",required=True)
    p.add_argument("--stage2-program",required=True)
    p.add_argument("--batch",type=int,default=100)
    p.add_argument("--workers",type=int,default=3)
    args=p.parse_args()
    if not 1<=args.batch<=200 or not 1<=args.workers<=4:
        raise ValueError("SCOUT_INVALID_BOUNDED_EXECUTION")
    output=run(args.factory_private,args.stage2_program,batch=args.batch,
               workers=args.workers)
    for key,value in output.items():
        print("FACTORY_STAGE2_SCOUT_"+key.upper()+"="+str(value))


if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print("FACTORY_STAGE2_SCOUT_ERROR="+type(exc).__name__+":"+str(exc)[:250],
              file=sys.stderr)
        raise SystemExit(1)
