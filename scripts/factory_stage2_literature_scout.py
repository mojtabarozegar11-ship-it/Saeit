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
import stat
import sys
import time
import threading
import urllib.error
import urllib.parse
import urllib.request

SCHEMA="saeit.factory.stage2-literature-scout.v1"
SCOUT_ALGO_VERSION="v11-targeted-scholarly-vocabulary"
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
      "planning","calendar","new","advanced","improve","improved","issues",
      "rescue","diagnose","successful","overview","identification"}
RISK=re.compile(r"(pesticid|insecticid|herbicid|fungicid|mushroom|"
                r"forag|poison|tox|livestock|hatch|slaughter|"
                r"food safety|food process|bee|beekeep|chicken|poultry)",
                re.I)
# Exact, reviewed colloquial-to-scholarly vocabulary for the 16 blocked P0
# topics. Query expansion is not source acceptance: real indexed title/abstract
# passages, DOI, publisher diversity and independent review remain mandatory.
TARGETED_SCHOLAR_VOCAB = {
    "balcony vegetable gardening": ("urban", "container", "horticulture"),
    "productive backyard garden": ("household", "horticulture", "yield"),
    "no-dig gardening and mulching": ("tillage", "mulch", "soil"),
    "carrot and radish growing": ("daucus", "raphanus", "root"),
    "zucchini and pumpkin growing": ("cucurbita", "squash", "vegetable"),
    "container parsley and cilantro": ("petroselinum", "coriandrum", "herb"),
    "container rosemary and thyme": ("rosmarinus", "thymus", "herb"),
    "homegrown greens planner": ("leafy", "vegetable", "harvest"),
    "farm-to-buyer traceability": ("supply", "chain", "food"),
    "beekeeping for beginners": ("apiculture", "honeybee", "apis"),
    "mobile farm recordkeeping": ("digital", "smartphone", "agriculture"),
    "agtech roi workbook": ("investment", "adoption", "profitability"),
    "farm resilience checklist": ("climate", "adaptation", "risk"),
    "gardening equipment checklist": ("horticultural", "tools", "ergonomics"),
    "illustrated gardening tools": ("horticultural", "tools", "ergonomics"),
    "farming troubleshooting faq": ("diagnosis", "decision", "extension"),
}
TARGETED_SCHOLAR_SEARCHES = {
    "balcony vegetable gardening": ("urban container vegetable cultivation", "urban horticulture containers"),
    "productive backyard garden": ("household vegetable gardens productivity", "urban home garden food production"),
    "no-dig gardening and mulching": ("no tillage vegetable mulching", "soil mulch conservation tillage"),
    "carrot and radish growing": ("daucus carota root crop cultivation", "raphanus sativus agronomic growth"),
    "zucchini and pumpkin growing": ("cucurbita pepo cultivation", "cucurbita squash yield"),
    "container parsley and cilantro": ("petroselinum crispum cultivation", "coriandrum sativum production"),
    "container rosemary and thyme": ("rosmarinus officinalis cultivation", "thymus vulgaris horticulture"),
    "homegrown greens planner": ("leafy vegetable harvest scheduling", "urban leaf vegetables production"),
    "farm-to-buyer traceability": ("agri food supply chain traceability", "farm food traceability systems"),
    "beekeeping for beginners": ("apiculture honeybee colony management", "apis mellifera hive health"),
    "mobile farm recordkeeping": ("mobile digital agricultural recordkeeping", "smartphone farm management data"),
    "agtech roi workbook": ("precision agriculture technology investment adoption", "digital agriculture return investment"),
    "farm resilience checklist": ("climate resilient farm risk management", "agricultural system adaptation resilience"),
    "gardening equipment checklist": ("horticultural hand tools ergonomic safety", "garden equipment agricultural ergonomics"),
    "illustrated gardening tools": ("horticultural tools ergonomics", "manual agricultural implements safety"),
    "farming troubleshooting faq": ("agricultural diagnostic decision support", "crop extension advisory diagnosis"),
}

MAX_DOC=6_000_000
# One machine-wide process gate for anonymous API traffic, shared by all threads.
# Never classify a throttled provider as "no scientific references exist".
PROVIDER_LOCK=threading.Lock()
PROVIDER_NEXT_ALLOWED={}
PROVIDER_DEADLINE_UTC={}
MINIMUM_SPACING_SECONDS=0.7

class ProviderCoolingDown(RuntimeError):
    """Another request already hit a temporary provider quota; leave work queued."""

def _slot(endpoint):
    with PROVIDER_LOCK:
        now=time.monotonic()
        deadline=PROVIDER_NEXT_ALLOWED.get(endpoint,0)
        wait=max(0.0,deadline-now)
        if wait>4:
            raise ProviderCoolingDown("SCOUT_PROVIDER_COOLING_DOWN")
        PROVIDER_NEXT_ALLOWED[endpoint]=max(now,deadline)+MINIMUM_SPACING_SECONDS
    if wait:
        time.sleep(wait)

def _limit_provider(endpoint, seconds):
    with PROVIDER_LOCK:
        deadline=time.monotonic()+max(0,seconds)
        if deadline>=PROVIDER_NEXT_ALLOWED.get(endpoint,0):
            PROVIDER_NEXT_ALLOWED[endpoint]=deadline
            PROVIDER_DEADLINE_UTC[endpoint]=(
                dt.datetime.now(dt.timezone.utc)+
                dt.timedelta(seconds=max(0,seconds))).isoformat()

def _retry_after(headers, default=120):
    value=headers.get("Retry-After") if headers else None
    try:
        return min(1800,max(30,int(value)))
    except (ValueError,TypeError):
        return default



def openalex_api_key():
    """Use an optional private, owner-only key. Never print, log or commit it."""
    key=os.environ.get("OPENALEX_API_KEY","").strip()
    if not key:
        path=Path.home()/"factory-runtime/operations/production-instructions/.openalex-api-key"
        if path.is_symlink():
            raise RuntimeError("SCOUT_OPENALEX_KEY_SYMLINK")
        if path.exists():
            info=path.stat()
            if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid()
                    or info.st_mode & 0o077):
                raise RuntimeError("SCOUT_OPENALEX_KEY_PERMISSIONS")
            key=path.read_text(encoding="ascii").strip()
    if key and not re.fullmatch(r"[A-Za-z0-9_-]{16,200}",key):
        raise RuntimeError("SCOUT_OPENALEX_KEY_FORMAT")
    return key


def query_variants(title):
    """Rotate bounded scholarly searches; strict source acceptance is unchanged.

    OpenAlex treats bare search words as AND and matches whole words. Feeding
    our internal Porter-like partial stems ('irrig', 'germin') to its search
    endpoint silently loses real irrigation and germination abstracts.
    """
    plain=[w for w in WORD_RE.findall(title.lower()) if w not in STOP]
    search_noise={"care","diagnose","diagnosis","inventory","log","workbook",
                  "checklist","calendar","planner","troubleshooting",
                  "selection","identification","cost","budget"}
    topical=[w for w in plain if w not in search_noise] or plain
    if not topical:
        topical=WORD_RE.findall(title.lower())[:3]
    base=" ".join(topical[:2])
    # Domain-specific scientific vocabulary, only for SEARCH. Original
    # paper-level relevance, unique verbatim passages and publisher diversity
    # are still required before a source packet can pass.
    scientific={
        "houseplant":("indoor","ornamental","horticulture"),
        "watering":("irrigation","moisture","water"),
        "water":("irrigation","moisture"),
        "yellow":("chlorosis",),
        "leaf":("foliar",),
        "leaves":("foliar",),
        "potting":("substrate",),
        "seedling":("germination","transplant"),
        "cutting":("propagation",),
        "hydroponic":("soilless",),
        "hydroponics":("soilless",),
        "greenhouse":("protected","cultivation"),
        "compost":("organic","matter"),
        "lighting":("photosynthesis","irradiance"),
        "light":("photosynthesis","irradiance"),
        "storage":("postharvest","preservation"),
        "mushroom":("fungal","cultivation"),
        "pest":("integrated","pest","management"),
    }
    equivalents=[]
    for term in topical[:3]:
        equivalents.extend(scientific.get(term,(term,)))
    broadened=" OR ".join(dict.fromkeys(equivalents[:4]))
    variants=[title,base,broadened,topical[0]]
    # Extra whole-word, evidence-gated searches for topics that do not match
    # a single vocabulary formulation. No lowered source-quality threshold.
    if len(topical)>=3:
        variants.append(" ".join(topical[1:3]))
    if len(equivalents)>=2:
        variants.append(" ".join(dict.fromkeys(equivalents[:2])))
    if len(topical)>=2:
        variants.append(" OR ".join(topical[:2]))
    # Prefer high-confidence scientific formulations on the first retry,
    # then explore the ordinary page/query grid without lowering thresholds.
    special=TARGETED_SCHOLAR_SEARCHES.get(str(title).strip().casefold(), ())
    return list(dict.fromkeys(v for v in (*special, *variants) if v))


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
    # Common educational terms need their conservative scientific aliases.
    # Aliases do not waive abstract evidence or publisher-diversity gates.
    synonyms={
        "houseplant":("indoor","ornamental"),
        "watering":("irrigation","moisture"),
        "water":("irrigation","moisture"),
        "yellow":("chlorosis",),
        "leaf":("foliar",),
        "lighting":("photosynthesis","irradiance"),
        "light":("photosynthesis","irradiance"),
        "potting":("substrate",),
        "pott":("substrate",),
        "cutting":("propagation",),
        "cutt":("propagation",),
        "seedling":("germination",),
        "seedl":("germination",),
        "hydroponic":("soilless",),
        "greenhouse":("protected",),
        "compost":("organic","matter"),
    }
    for alias in TARGETED_SCHOLAR_VOCAB.get(str(title).strip().casefold(), ()):
        term=normalize(alias)
        if term not in unique and len(unique)<7:
            unique.append(term)
    for term in unique[:4]:
        for alias in synonyms.get(term,()):
            # The article title/abstract tokens are normalized as well.
            # Raw "irrigation" never equals indexed "irrig"; the historic
            # mismatch silently erased valid source relevance evidence.
            normalized_alias=normalize(alias)
            if normalized_alias not in unique:
                unique.append(normalized_alias)
            if len(unique)>=7:
                return unique[:7]
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


def citation_sentences(abstract, topic_keys, limit=2):
    """Return up to two distinct verbatim, topic-linked indexed-abstract sentences."""
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
        normalized={normalize(w) for w in WORD_RE.findall(sentence.lower())}
        matched=[k for k in topic_keys if k in normalized or any(
                 w.startswith(k) and len(k)>4 for w in normalized)]
        # Paper-level title AND abstract relevance is already enforced.
        # Requiring every individual sentence to repeat two title concepts
        # wrongly rejects a meaningful single-topic finding.
        if not matched:
            continue
        if any(x in sentence.lower() for x in
               ("http://","https://","copyright","all rights reserved")):
            continue
        if not sentence.endswith((".","!","?")):
            continue
        ranked.append((len(matched),len(sentence),sentence))
    distinct=[]
    for _,_,sentence in sorted(ranked,key=lambda q:(-q[0],q[1])):
        if sentence not in distinct:
            distinct.append(sentence)
        if len(distinct)==limit:
            break
    return distinct


def citation_sentence(abstract, topic_keys):
    candidates=citation_sentences(abstract,topic_keys,limit=1)
    return candidates[0] if candidates else None


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
        # The main location is usually a DOI resolver; a verified indexed
        # accepted/published copy can instead supply an actual article URL.
        locations=work.get("locations")
        if isinstance(locations,list):
            for location in locations[:30]:
                if (not isinstance(location,dict) or
                        location.get("version") not in
                        ("publishedVersion","acceptedVersion")):
                    continue
                candidate=location.get("landing_page_url")
                candidate_host=reliable_url(candidate,worker)
                if candidate_host:
                    url,host=candidate,candidate_host
                    break
    if not host:
        return None
    abstract=abstract_from_index(work.get("abstract_inverted_index"))
    if len(abstract)<210:
        return None
    title_norm={normalize(w) for w in WORD_RE.findall(title.lower())}
    body_norm={normalize(w) for w in WORD_RE.findall(abstract.lower())}
    title_hits=sum(k in title_norm for k in topic_keys)
    body_hits=sum(k in body_norm for k in topic_keys)
    if title_hits<1 or body_hits<min(2,len(topic_keys)):
        return None
    excerpts=citation_sentences(abstract,topic_keys)
    if not excerpts:
        return None
    excerpt=excerpts[0]
    ident=work.get("id")
    if not isinstance(ident,str) or not re.fullmatch(
            r"https://openalex\.org/W[0-9]{6,15}",ident):
        return None
    return {
        "openalex_id":ident, "doi":doi, "url":url, "host":host,
        "title":title, "publication_year":year, "publisher":publisher,
        "venue":source.get("display_name"), "abstract_sha256":
            hashlib.sha256(abstract.encode("utf8")).hexdigest(),
        "support_sentence":excerpt, "support_sentences":excerpts,
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
    return reserve_diverse_papers(distinct)


def registrable_host(host):
    # Conservative offline eTLD grouping: never mistake many subdomains
    # under one institutional publisher for independent domains.
    parts=host.lower().removeprefix("www.").split(".")
    suffix3={("co","uk"),("ac","uk"),("org","uk"),("gov","uk"),
             ("edu","au"),("com","au"),("co","nz"),("com","br")}
    if len(parts)>2 and tuple(parts[-2:]) in suffix3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])



def reserve_diverse_papers(candidates):
    """Reserve genuinely independent domains before enforcing the cache cap."""
    ordered=sorted(candidates,key=lambda x:(
        -x["relevance_score"],-x["publication_year"],x["openalex_id"]))
    selected=[]
    domains=set()
    publishers=set()
    for item in ordered:
        domain=registrable_host(item["host"])
        publisher=item["publisher"].casefold().strip()
        if domain not in domains and publisher not in publishers:
            selected.append(item)
            domains.add(domain)
            publishers.add(publisher)
            if len(selected)==10:
                break
    selected_ids={item["openalex_id"] for item in selected}
    for item in ordered:
        if len(selected)==20:
            break
        if item["openalex_id"] not in selected_ids:
            selected.append(item)
            selected_ids.add(item["openalex_id"])
    return selected


def diverse_four_or_five(papers):
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
    if (len(chosen)<4 or
            len(set(registrable_host(p["host"]) for p in chosen))<3 or
            len(set(p["publisher"].lower() for p in chosen))<3):
        return []
    return chosen


def evidence_gap_reason(order,papers):
    """Explain the desk-research gate without claiming missing evidence exists."""
    if len(papers)<4:
        return "under_four_topic_relevant_article_abstracts"
    chosen=diverse_four_or_five(papers)
    if not chosen:
        return "insufficient_independent_publishers_or_domains"
    if set(locale_scopes(order))!={"fa-IR","en-US"}:
        return "missing_bilingual_scope"
    if len({paper["support_sentence"] for paper in chosen})!=len(chosen):
        return "duplicate_indexed_abstract_claims"
    if len(chosen)==4 and not any(
            isinstance(p.get("support_sentences"),list)
            and len(p["support_sentences"])>=2
            and isinstance(p["support_sentences"][1],str)
            and p["support_sentences"][1]!=p["support_sentence"]
            and p["support_sentences"][1] not in
                {q["support_sentence"] for q in chosen}
            for p in chosen):
        return "fifth_distinct_verbatim_claim_unavailable"
    return "additional_provenance_or_validation_review"


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
    chosen=diverse_four_or_five(papers)
    if not chosen:
        return None
    locales=locale_scopes(order)
    if set(locales)!={"fa-IR","en-US"}:
        return None
    # Five claims cannot merely repeat the same quoted text under
    # different publication IDs. Genuine source diversity is insufficient
    # when all claimed findings are indistinguishable.
    if len({p["support_sentence"] for p in chosen})!=len(chosen):
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
            "original_publisher_verification":"not_performed",
            "indexed_sentence_sha256":
                hashlib.sha256(paper["support_sentence"].encode("utf8")).hexdigest()
        })
    # Stage 2 requires five independently traceable claims, but only four
    # scientific source publications. A genuinely different verbatim passage
    # from the fourth publication can be a fifth claim; a repeated quote cannot.
    if len(chosen)==4:
        second=next((
            (n,p["support_sentences"][1]) for n,p in enumerate(chosen,1)
            if isinstance(p.get("support_sentences"),list)
            and len(p["support_sentences"])>=2
            and isinstance(p["support_sentences"][1],str)
            and p["support_sentences"][1] != p["support_sentence"]
            and p["support_sentences"][1] not in
                [item["statement"] for item in claims]
        ),None)
        if second is None:
            return None
        source_n,statement=second
        claims.append({
            "id":"claim5","statement":statement,
            "source_ids":["scholar"+str(source_n)],
            "assertion_type":"second_distinct_verbatim_indexed_abstract_sentence",
            "original_publisher_verification":"not_performed",
            "indexed_sentence_sha256":
                hashlib.sha256(statement.encode("utf8")).hexdigest()
        })
    safety_sensitive=bool(RISK.search(str(order.get("subject",""))))
    result={
        "schema":EVIDENCE_SCHEMA,
        "source_product_id":order["source_product_id"],
        "revision":revision,
        "work_order_sha256":worker.sha(order),
        "locale_scopes":locales, "sources":sources, "claims":claims,
        "scientific_review_completed":False,
        "public_distribution_allowed":False,
        "requires_independent_specialist_review":True,
        "safety_sensitive_review_hold":safety_sensitive,
        "collection_method":"openalex_verified_short_abstract_extracts_not_primary_pages",
        "independent_original_page_recheck":False,
        "research_quality_limitations":[
            "Quoted sentences are grounded in retrieved index abstracts but original publisher full text has not been inspected.",
            "Bibliographic metadata is not proof of field performance, local agronomic safety or commercial value.",
            "Scientific specialist review, original publisher checking and complete localized book manuscripts are still required."
        ] + (["Safety-sensitive subject: no operational advice, treatment protocol, approval, or publication until appropriate independent specialist review."] if safety_sensitive else [])
    }
    worker.validate_evidence(result,order,revision)
    return result


def request_json(endpoint,parameters,timeout=10):
    if endpoint not in SAFE_KEYS.values():
        raise RuntimeError("SCOUT_UNTRUSTED_API_ENDPOINT")
    query=urllib.parse.urlencode(parameters)
    url=endpoint+"?"+query
    headers={
        "User-Agent":"SaeitFactoryResearchScout/1.1 (source verification; bounded)",
        "Accept":"application/json"}
    key=openalex_api_key() if endpoint==SAFE_KEYS["openalex"] else ""
    if key:
        headers["Authorization"]="Bearer "+key
    req=urllib.request.Request(url,headers=headers)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    _slot(endpoint)
    opener=urllib.request.build_opener(NoRedirect)
    try:
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
    except urllib.error.HTTPError as exc:
        if exc.code==429:
            # Anonymous OpenAlex has a tiny shared DAILY budget. Without a
            # Retry-After header, avoid hammering it each cron invocation.
            if exc.headers and exc.headers.get("Retry-After"):
                seconds=_retry_after(exc.headers)
            elif endpoint==SAFE_KEYS["openalex"] and not key:
                now=dt.datetime.now(dt.timezone.utc)
                tomorrow=(now+dt.timedelta(days=1)).replace(
                    hour=0,minute=2,second=0,microsecond=0)
                seconds=max(120,(tomorrow-now).total_seconds())
            else:
                seconds=600
            _limit_provider(endpoint,seconds)
            raise RuntimeError("SCOUT_API_RATE_LIMITED_429") from None
        if exc.code==403 and endpoint==SAFE_KEYS["openalex"] and key:
            # Newly created agent keys require the owner's email activation.
            # A failed authorization is NOT a missing research source. Keep
            # the retry bounded until the owner verifies the email address.
            _limit_provider(endpoint,600)
            raise RuntimeError("SCOUT_OPENALEX_KEY_NOT_YET_USABLE_403") from None
        if exc.code in (500,502,503,504):
            _limit_provider(endpoint,30)
            raise RuntimeError("SCOUT_PROVIDER_TEMPORARY_"+str(exc.code)) from None
        # Do not include the URL or possible API key in diagnostics.
        raise RuntimeError("SCOUT_PROVIDER_HTTP_"+str(exc.code)) from None


def fetch_openalex(title, page=1):
    # The caller selects a deterministic query variant on successive retries.
    # Even broad results must pass strict paper and provenance validation.
    # Search actual complete natural-language terms. Internal normalized
    # stems are only for validating hits, not OpenAlex whole-word retrieval.
    subject=" ".join(str(title).split())[:200]
    if type(page) is not int or not 1 <= page <= 8:
        raise ValueError("SCOUT_BAD_BOUNDED_RESULTS_PAGE")
    if not subject:
        raise ValueError("SCOUT_EMPTY_SCHOLARLY_QUERY")
    data=request_json(SAFE_KEYS["openalex"],{
        "search":subject,
        "page":page,
        "filter":"has_abstract:true,has_doi:true",
        "per_page":100,
        "select":"id,display_name,doi,publication_year,type,is_retracted,abstract_inverted_index,primary_location,best_oa_location,locations,cited_by_count"
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
        overlap=lookup.intersection({normalize(w) for w in WORD_RE.findall(title0.lower())})
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
    previous={}
    if output.exists():
        previous=worker.read(output)
        if (previous.get("schema")!=SCHEMA or
                previous.get("source_product_id")!=ident or
                previous.get("order_id")!=order_id):
            raise RuntimeError("SCOUT_CANDIDATE_IDENTITY_CHANGED")
    # Reuse already indexed and digest-checked abstracts before charging
    # another API search. This only creates a preliminary desk-research
    # packet, never a human attestation, product approval or release.
    cached=previous.get("indexed_abstract_candidates",[])
    if (previous.get("scout_algorithm_version") in
            ("v2-relevance-provenance",
             "v3-four-source-safety-desk-research",
             "v4-normalized-scientific-synonyms",
             "v5-publisher-diversity-gap-diagnostics",
              "v6-evidence-first-fullword-query",
              "v7-multiphase-topic-specific-query",
              "v8-bounded-progressive-search",
              "v9-paged-source-diversity",
              "v10-complete-page-grid-source-diversity",SCOUT_ALGO_VERSION)
            and isinstance(cached,list) and 4<=len(cached)<=20
            and previous.get("candidate_sha256")==sha(cached)):
        valid=[]
        for paper in cached:
            if (not isinstance(paper,dict)
                    or not isinstance(paper.get("doi"),str)
                    or not paper["doi"].startswith("https://doi.org/")
                    or not isinstance(paper.get("publisher"),str)
                    or len(paper["publisher"].strip())<6
                    or not isinstance(paper.get("title"),str)
                    or len(paper["title"])<18
                    or not isinstance(paper.get("support_sentence"),str)
                    or not re.fullmatch(r"[0-9a-f]{64}",
                            str(paper.get("abstract_sha256","")))
                    or not re.fullmatch(r"https://openalex\.org/W[0-9]{6,15}",
                            str(paper.get("openalex_id","")))
                    or reliable_url(paper.get("url"),worker)!=paper.get("host")):
                continue
            valid.append(paper)
        if len(valid)>=4:
            try:
                ready=evidence_from_papers(record,1,valid,worker)
                if ready is not None:
                    worker.atomic(evidence_path,ready)
                    return "traceable_abstracts"
            except (RuntimeError,ValueError,KeyError,TypeError):
                pass
    prior_round=previous.get("search_round",-1)
    if type(prior_round) is not int:
        raise RuntimeError("SCOUT_INVALID_SEARCH_ROUND")
    round_no=prior_round+1
    if not 0<=round_no<=10000:
        raise RuntimeError("SCOUT_INVALID_SEARCH_ROUND")
    queries=query_variants(title)
    # Visit page 1 for every distinct query before page 2, and so on.
    # The older paired modulo schedule never explored most query/page pairs.
    query=queries[round_no%len(queries)]
    page=1 + (round_no//len(queries)) % 8
    try:
        # Explore different scholarly result pages before repeated queries
        # keep returning the same publisher. Mocks/custom fetchers remain compatible.
        raw=fetcher(query,page=page) if fetcher is fetch_openalex else fetcher(query)
        papers=select_papers(raw,terms,worker)
        # Preserve previously verified abstract candidates across query
        # variants; a mismatching digest discards stale/tampered cache.
        cached=previous.get("indexed_abstract_candidates",[])
        if (isinstance(cached,list) and
                previous.get("candidate_sha256")==sha(cached)):
            by_doi={p["doi"].lower():p for p in papers}
            for paper in cached[:20]:
                if (isinstance(paper,dict) and
                        isinstance(paper.get("doi"),str) and
                        paper["doi"].startswith("https://doi.org/") and
                        isinstance(paper.get("relevance_score"),int) and
                        isinstance(paper.get("publication_year"),int) and
                        isinstance(paper.get("publisher"),str) and
                        isinstance(paper.get("title"),str) and
                        isinstance(paper.get("support_sentence"),str) and
                        isinstance(paper.get("abstract_sha256"),str) and
                        re.fullmatch(r"https://openalex\.org/W[0-9]{6,15}",
                                     str(paper.get("openalex_id",""))) and
                        reliable_url(paper.get("url"),worker)==paper.get("host")):
                    by_doi.setdefault(paper["doi"].lower(),paper)
            # Preserve independent sources discovered in later query rounds.
            papers=reserve_diverse_papers(list(by_doi.values()))
    except ProviderCoolingDown:
        return "provider_cooldown"
    except Exception as exc:
        # A transient provider error must never erase verified references
        # accumulated across prior search pages. Do not advance the cursor
        # either: retry the SAME missing query/page once service returns.
        old_candidates=previous.get("indexed_abstract_candidates",[])
        intact=(isinstance(old_candidates,list) and len(old_candidates)<=20
                and previous.get("candidate_sha256")==sha(old_candidates))
        packet={
            "schema":SCHEMA,"source_product_id":ident,"order_id":order_id,
            "source_search_query":query,"source_search_page":page,
            "search_round":prior_round,"attempted_search_round":round_no,
            "scout_algorithm_version":SCOUT_ALGO_VERSION,
            "status":"external_research_api_unavailable",
            "last_error":type(exc).__name__+":"+str(exc)[:160],
            "research_completed":False,"source_verified_count":0,
            "indexed_abstract_candidates":old_candidates if intact else [],
            "candidate_sha256":sha(old_candidates if intact else []),
            "indexed_abstract_candidate_count":len(old_candidates) if intact else 0,
            "evidence_gap_reason":previous.get("evidence_gap_reason"),
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
        "source_search_query":query,"source_search_page":page,
        "search_keywords":terms,
        "search_round":round_no,"scout_algorithm_version":SCOUT_ALGO_VERSION,
        "status":"indexed_references_found_require_additional_research",
        "indexed_abstract_candidates":papers[:20],
        "candidate_sha256":sha(papers[:20]),
        "crossref_bibliographic_candidates":fallback,
        "indexed_abstract_candidate_count":len(papers),
        "evidence_gap_reason":evidence_gap_reason(record,papers),
        "independent_publisher_fulltext_checked":False,
        "stage2_documentation_complete":False,"stage3_handoff":False,
        "commercial_release":False,"quality1000_approved":False,
        "checked_utc":utc()
    }
    worker.atomic(output,candidate)
    return "needs_more_research"


def retry_delay(candidate, title):
    """Use short retries for unexplored searches, then slow after full sweep."""
    if candidate.get("status")=="external_research_api_unavailable":
        return dt.timedelta(minutes=12)
    if candidate.get("scout_algorithm_version")!=SCOUT_ALGO_VERSION:
        return dt.timedelta(0)
    round_no=candidate.get("search_round",-1)
    if type(round_no) is not int or not -1<=round_no<=10000:
        raise RuntimeError("SCOUT_INVALID_SEARCH_ROUND")
    # A full source sweep is queries x 4 pages, not merely one page per
    # query. Do not hold outstanding orders eight hours after only ~25%
    # of available bounded search space has been explored.
    sweep_rounds=8*len(query_variants(title))
    return (dt.timedelta(minutes=15)
            if round_no+1<sweep_rounds
            else dt.timedelta(hours=8))


def run(root,stage2_program,fetcher=fetch_openalex,backstop=crossref_metadata,
        batch=200,workers=3,query_burst=1,expedite_gap_research=False):
    if not 1<=query_burst<=3:
        raise ValueError("SCOUT_INVALID_QUERY_BURST")
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
        # Restore provider cooldown across cron processes; no global secret
        # or external database is needed. The scout lock serializes writers.
        provider_state=stage/"literature-provider-cooldowns.json"
        # Anonymous rate limits must not block an owner-activated key.
        # Still preserve cooldowns when the authentication mode is unchanged.
        openalex_mode="keyed" if openalex_api_key() else "anonymous"
        with PROVIDER_LOCK:
            PROVIDER_NEXT_ALLOWED.clear()
            PROVIDER_DEADLINE_UTC.clear()
        if provider_state.exists():
            old_state=worker.read(provider_state)
            if old_state.get("schema")!="saeit.factory.provider-cooldown.v1":
                raise RuntimeError("SCOUT_BAD_PROVIDER_COOLDOWN_STATE")
            previous_mode=old_state.get("openalex_credential_mode","anonymous")
            for endpoint,until in old_state.get("blocked_until_utc",{}).items():
                if endpoint not in SAFE_KEYS.values():
                    continue
                if endpoint==SAFE_KEYS["openalex"] and previous_mode!=openalex_mode:
                    continue
                try:
                    deadline=dt.datetime.fromisoformat(until)
                    if deadline.tzinfo is None:
                        continue
                    seconds=(deadline-dt.datetime.now(dt.timezone.utc)).total_seconds()
                    if seconds>0:
                        _limit_provider(endpoint,min(seconds,86400))
                except (ValueError,TypeError):
                    continue
        # New P0 orders run before retries. Explore unused variants
        # every 15 minutes, then 8-hour cooldown after a full sweep.
        unsearched=[]
        retries=[]
        expedited=[]
        now=dt.datetime.now(dt.timezone.utc)
        for rank,ident in enumerate(ids,1):
            packet,order=worker.verified_stage1_packet(
                area,ident+"--r001.json")
            if order.get("source_product_id")!="AGRI-%03d"%rank:
                raise RuntimeError("SCOUT_INDEX_ORDER_MISMATCH")
            if (stage/"source-evidence"/(order["source_product_id"]+"--r001.json")).exists():
                continue
            out=stage/"literature-candidates"/(order["source_product_id"]+"--r001.json")
            if not out.exists():
                unsearched.append(order)
                continue
            old=worker.read(out)
            try:
                checked=dt.datetime.fromisoformat(old["checked_utc"])
                if checked.tzinfo is None:
                    raise ValueError("SCOUT_NAIVE_CANDIDATE_TIMESTAMP")
            except (ValueError,KeyError,TypeError):
                checked=dt.datetime.min.replace(tzinfo=dt.timezone.utc)
            # A version upgrade gets one immediate search burst; substantive
            # gaps stay scheduled without falsifying scholarly provenance.
            title=next((ed.get("title") for ed in order.get("editions",[])
                        if isinstance(ed,dict) and ed.get("locale")=="en-US"),"")
            minimum=retry_delay(old,title)
            if now-checked>=minimum:
                retries.append((checked,rank,order))
            elif (expedite_gap_research and checked<=now
                  and old.get("scout_algorithm_version")==SCOUT_ALGO_VERSION
                  and old.get("status")=="indexed_references_found_require_additional_research"
                  and old.get("evidence_gap_reason") in (
                      "under_four_topic_relevant_article_abstracts",
                      "insufficient_independent_publishers_or_domains")
                  and type(old.get("search_round")) is int
                  and old["search_round"]+1>=4*len(query_variants(title))):
                # A single owner-approved deployment may probe unexplored
                # pages 5-8 immediately. Normal cron retains its retry budget.
                expedited.append((checked,rank,order))
        retries.sort(key=lambda x:(x[0],x[1]))
        expedited.sort(key=lambda x:(x[0],x[1]))
        selected=(unsearched+[v[2] for v in retries]
                  +[v[2] for v in expedited])[:batch]
        expedited_ids={item[2]["source_product_id"] for item in expedited}
        counts={"traceable_abstracts":0,"needs_more_research":0,
                "api_unavailable":0,"already_seeded":0,"provider_cooldown":0}
        def research_topic(order):
            # Persist each incomplete attempt; stop at real evidence, provider
            # errors or cooldown. Hard bound of three external searches.
            last="needs_more_research"
            searched=0
            for _ in range(query_burst):
                last=sources_for_topic(root,worker,order,fetcher,backstop)
                searched+=1
                if last!="needs_more_research":
                    break
            return last,searched
        research_rounds=0
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures=[pool.submit(research_topic,o) for o in selected]
            for future in concurrent.futures.as_completed(futures):
                value,searches=future.result()
                research_rounds+=searches
                counts[value]+=1
        report={
            "schema":SCHEMA,"input_priority_order_count":200,
            "attempted_this_run":len(selected),
            "expedited_unresolved_evidence_gaps":sum(
                o["source_product_id"] in expedited_ids for o in selected),
            "evidence_review_and_release_gates_unchanged":True,
            "bounded_source_search_rounds_this_run":research_rounds,
            "max_query_variants_per_topic_this_run":query_burst,
            "source_evidence_automatically_documented":counts["traceable_abstracts"],
            "still_require_manual_or_external_research":counts["needs_more_research"],
            "external_provider_unavailable":counts["api_unavailable"],
            "requests_skipped_due_to_provider_cooldown":counts["provider_cooldown"],
            "new_orders_prioritized_before_retries":True,
            "provider_rate_limit_is_not_source_absence":True,
            "previously_seeded":counts["already_seeded"],
            "desk_research_verification_required":True,
            "human_specialist_reviews_completed":0,
            "sites_changed":False,"checked_utc":utc()
        }
        with PROVIDER_LOCK:
            blocked=dict(PROVIDER_DEADLINE_UTC)
        worker.atomic(provider_state,{
            "schema":"saeit.factory.provider-cooldown.v1",
            "blocked_until_utc":blocked,"openalex_credential_mode":openalex_mode,
            "checked_utc":utc()})
        report["openalex_key_configured"]=openalex_mode=="keyed"
        # Count actual independently indexed dossiers (not workpapers or APIs).
        report["total_research_source_evidence"] = sum(1 for rank in range(1,201)
            if (stage/"source-evidence"/("AGRI-%03d"%rank+"--r001.json")).is_file())
        report["remaining_priority_orders"] = 200 - report["total_research_source_evidence"]
        report["provider_cooldown_active"]=any(
            dt.datetime.fromisoformat(v)>dt.datetime.now(dt.timezone.utc)
            for v in blocked.values())
        worker.atomic(stage/"literature-scout-status.json",report)
        return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--factory-private",required=True)
    p.add_argument("--stage2-program",required=True)
    p.add_argument("--batch",type=int,default=100)
    p.add_argument("--workers",type=int,default=3)
    p.add_argument("--query-burst",type=int,default=1)
    p.add_argument("--expedite-gap-research",action="store_true")
    args=p.parse_args()
    if not 1<=args.batch<=200 or not 1<=args.workers<=4 or not 1<=args.query_burst<=3:
        raise ValueError("SCOUT_INVALID_BOUNDED_EXECUTION")
    output=run(args.factory_private,args.stage2_program,batch=args.batch,
               workers=args.workers,query_burst=args.query_burst,
               expedite_gap_research=args.expedite_gap_research)
    for key,value in output.items():
        print("FACTORY_STAGE2_SCOUT_"+key.upper()+"="+str(value))


if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print("FACTORY_STAGE2_SCOUT_ERROR="+type(exc).__name__+":"+str(exc)[:250],
              file=sys.stderr)
        raise SystemExit(1)
