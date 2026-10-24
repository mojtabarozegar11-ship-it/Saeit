#!/usr/bin/env python3
"""Real, limited and license-safe primary-source acquisition for ALL factory orders.

Reads immutable owner-rejected source work packets. Does not mutate any product,
quality grade, retailer, sale, or published site. Index metadata is NOT full text.
The source corpus is deduplicated across orders by normalized DOI.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import URLError, HTTPError
from xml.etree import ElementTree as ET

SCHEMA = "saeit.factory.primary-fulltext-live-acquisition.v1"
NAME = re.compile(r"WO-[0-9]{8}--r[0-9]{3}\.json\Z")
DOI = re.compile(r"10\.[0-9]{4,9}/[-._;()/:A-Za-z0-9]+\Z", re.I)
WORD = re.compile(r"[a-z]{4,}")
STOP = {"with", "from", "that", "these", "have", "were", "which", "this", "their", "into", "than", "using", "study", "results", "show", "there", "also", "between", "found", "based"}
ROOT_API = "https://www.ebi.ac.uk/europepmc/webservices/rest"
MAX_META, MAX_XML = 1_500_000, 18_000_000

class Blocked(ValueError):
    pass

class TemporaryFailure(RuntimeError):
    pass

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TemporaryFailure("NETWORK_REDIRECT_NOT_ALLOWED")

def ensure(condition, reason):
    if not condition:
        raise Blocked(reason)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def canonical(obj):
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()

def safe_dir(p):
    ensure(not p.is_symlink(), "UNSAFE_DIRECTORY_SYMLINK")
    p.mkdir(parents=True, exist_ok=True, mode=0o700)
    ensure(p.is_dir() and not p.is_symlink(), "UNSAFE_DIRECTORY")
    os.chmod(p, 0o700)

def safe_read(p, size=3_000_000):
    ensure(p.is_file() and not p.is_symlink() and 0 < p.stat().st_size <= size,
           "SOURCE_PACKET_MISSING_OR_UNSAFE")
    return p.read_bytes()

def once(path, data):
    safe_dir(path.parent)
    ensure(not path.is_symlink(), "EVIDENCE_SYMLINK")
    if path.exists():
        ensure(path.is_file() and safe_read(path, MAX_XML+1) == data,
               "IMMUTABLE_EVIDENCE_CONFLICT")
        return False
    fd, temp = tempfile.mkstemp(prefix=".primary-acq-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        try:
            os.link(temp, path)
        except FileExistsError:
            ensure(safe_read(path, MAX_XML+1) == data, "IMMUTABLE_EVIDENCE_CONFLICT")
            return False
        return True
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def key(doi):
    return sha(doi.lower().encode("utf-8"))

def normalize_doi(value):
    ensure(isinstance(value, str), "DOI_NOT_STRING")
    d = value.lower().replace("https://doi.org/", "", 1).strip()
    ensure(DOI.fullmatch(d) is not None and len(d) <= 255, "DOI_INVALID")
    return d

def collect(area):
    path = area / "stage-02/primary-fulltext-repair-inbox"
    ensure(path.is_dir() and not path.is_symlink(), "SOURCE_REWORK_QUEUE_UNAVAILABLE")
    files = sorted(p for p in path.iterdir()
                   if p.is_file() and not p.is_symlink() and NAME.fullmatch(p.name))
    ensure(files, "EMPTY_SOURCE_REWORK_QUEUE")
    unique = {}
    orders = []
    total = 0
    for p in files:
        packet = json.loads(safe_read(p))
        ensure(packet.get("order_file") == p.name and
               packet.get("schema") == "saeit.factory.scientific-source-repair.v1" and
               packet.get("qc1000_approved") is False and
               packet.get("public_distribution_allowed") is False and
               packet.get("all_claims_verified") is False,
               "REWORK_PACKET_QC_OR_ORIGIN_INVALID")
        tasks = packet.get("scientific_primary_source_tasks")
        claims = packet.get("scientific_claims")
        ensure(isinstance(tasks, list) and len(tasks) >= 4
               and isinstance(claims, list) and len(claims) >= 5,
               "SOURCE_OR_CLAIM_LIST_MISSING")
        order = {"order_file":p.name,"claims":claims,"tasks":[]}
        for task in tasks:
            ensure(isinstance(task, dict) and
                   task.get("original_fulltext_retrieved") is False and
                   task.get("exact_supporting_pages_verified") is False and
                   task.get("required_action") ==
                   "FETCH_LICENSABLE_PRIMARY_FULLTEXT_AND_CHECK_EXACT_PASSAGES",
                   "FORGED_PRIMARY_SOURCE_STATUS")
            # Never silently drop no-DOI tasks: leave explicitly blocked.
            doi = task.get("doi")
            if doi is None:
                order["tasks"].append({"source_id":task.get("source_id"),
                                       "doi":None,"state":"DOI_NOT_AVAILABLE"})
                total += 1
                continue
            norm = normalize_doi(doi)
            ensure(isinstance(task.get("source_id"), str), "SOURCE_ID_INVALID")
            unique.setdefault(norm, set()).add(p.name)
            order["tasks"].append({"source_id":task["source_id"],"doi":norm,
                                   "linked_claim_ids":task.get("linked_claim_ids", [])})
            total += 1
        orders.append(order)
    return unique, orders, total

def live_get(url, max_bytes):
    # Fixed provider/endpoint only. No publisher scraping, redirects or arbitrary URL fetch.
    ensure(url.startswith(ROOT_API+"/"), "UNAPPROVED_EVIDENCE_ORIGIN")
    try:
        req = Request(url, headers={"User-Agent":"SaeitFactoryScientificReview/1.0",
                                    "Accept":"application/json, application/xml, text/xml"})
        with build_opener(NoRedirect()).open(req, timeout=9) as response:
            ensure(response.status == 200, "SOURCE_HTTP_NOT_OK")
            data = response.read(max_bytes+1)
            ensure(0 < len(data) <= max_bytes, "SOURCE_PAYLOAD_SIZE_INVALID")
            return data
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise TemporaryFailure("SOURCE_HTTP_"+str(exc.code)) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise TemporaryFailure("SOURCE_NETWORK_"+type(exc).__name__) from exc

def license_ok(license_info):
    s = license_info.lower().replace("https://", "http://")
    if "creativecommons.org/publicdomain/zero/" in s:
        return True
    if any(x in s for x in ("/by-nc", "/by-nd", "noncommercial", "non-commercial", "no derivatives", "all rights reserved")):
        return False
    return ("creativecommons.org/licenses/by/" in s
            or "creativecommons.org/licenses/by-sa/" in s)

def xml_parts(raw, doi, pmcid):
    ensure(raw is not None and b"<!ENTITY" not in raw.upper(), "UNSAFE_OR_EMPTY_XML")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise Blocked("JATS_XML_PARSE_FAILED") from exc
    def tag(node):
        return node.tag.rsplit("}", 1)[-1]
    ensure(tag(root) == "article", "NOT_JATS_ARTICLE")
    doc_dois = [("".join(n.itertext())).strip().lower()
                for n in root.iter() if tag(n) == "article-id" and
                n.attrib.get("pub-id-type") == "doi"]
    ensure(doi in doc_dois, "FULLTEXT_DOI_MISMATCH")
    licences = []
    for n in root.iter():
        if tag(n) == "license":
            licences.append(" ".join([str(v) for k,v in n.attrib.items()
                                      if k.rsplit("}", 1)[-1] in ("href","license-type")]
                                     + [" ".join("".join(n.itertext()).split())[:900]]))
    license_info = " | ".join(licences)[:1600]
    body = next((n for n in root if tag(n) == "body"), None)
    ensure(body is not None, "PRIMARY_ARTICLE_BODY_MISSING")
    paragraphs = [" ".join("".join(n.itertext()).split())
                  for n in body.iter() if tag(n) == "p"]
    paragraphs = [p for p in paragraphs if len(p) >= 70]
    ensure(sum(len(x) for x in paragraphs) >= 1400, "PRIMARY_ARTICLE_BODY_TOO_SHORT")
    return license_info, paragraphs

def citation_candidates(statement, paragraphs):
    """Potential body passages only. Never a scientific/semantic validation."""
    basis = {x for x in WORD.findall(str(statement).lower()) if x not in STOP}
    ranked = []
    if len(basis) < 3:
        return []
    for index, p in enumerate(paragraphs):
        vocab = set(WORD.findall(p.lower()))
        score = round(len(vocab & basis) / len(basis), 3)
        if score >= 0.35:
            ranked.append((score, index, p))
    ranked.sort(key=lambda row:(-row[0], row[1]))
    return [{"body_paragraph_index":index+1,
             "keyword_overlap_fraction":score,
             "candidate_excerpt_max_25_words":" ".join(p.split()[:25]),
             "human_semantic_and_scientific_verification":"REQUIRED"}
            for score,index,p in ranked[:2]]

def evaluate(doi, http_get=live_get):
    url = ROOT_API+"/search?"+urlencode({"query":'DOI:"'+doi+'"',
                                            "format":"json","pageSize":"3","resultType":"core"})
    blob = http_get(url, MAX_META)
    ensure(blob is not None, "PMC_SEARCH_UNAVAILABLE")
    result = json.loads(blob).get("resultList",{}).get("result",[])
    found = next((r for r in result if isinstance(r, dict)
                  and str(r.get("doi", "")).lower() == doi), None)
    if found is None:
        return {"state":"DOI_NOT_INDEXED_AT_EUROPE_PMC","recheck_via_other_provider":True}, None, []
    if str(found.get("isRetracted","")).upper() in ("Y","TRUE"):
        return {"state":"RETRACTION_FLAGGED","pmcid":found.get("pmcid")}, None, []
    pmcid = found.get("pmcid")
    if not isinstance(pmcid, str) or not re.fullmatch(r"PMC[0-9]{3,12}", pmcid):
        return {"state":"NO_PMC_FULLTEXT_LINK","recheck_via_other_provider":True}, None, []
    raw = http_get(ROOT_API+"/"+pmcid+"/fullTextXML", MAX_XML)
    if raw is None:
        return {"state":"PMC_FULLTEXT_XML_NOT_PUBLIC","pmcid":pmcid}, None, []
    try:
        license_info, paragraphs = xml_parts(raw, doi, pmcid)
    except Blocked as exc:
        return {"state":"FULLTEXT_REJECTED_"+str(exc),
                "pmcid":pmcid, "body_validated":False}, None, []
    if not license_ok(license_info):
        return {"state":"COMMERCIAL_REUSE_LICENSE_NOT_VERIFIED",
                "pmcid":pmcid,"license_excerpt":license_info[:160]}, None, []
    return {"state":"LICENSED_FULLTEXT_ARCHIVED","pmcid":pmcid,
            "body_validated":True,"xml_sha256":sha(raw),
            "xml_bytes":len(raw),"body_paragraph_count":len(paragraphs),
            "license_evidence":license_info[:600],
            "source_link":ROOT_API+"/"+pmcid+"/fullTextXML",
            "automated_claim_verification":False,
            "independent_qc1000_approved":False}, raw, paragraphs


def map_claim_candidates(target, orders):
    """Produce a private, immutable evidence report per fully inspected product.

    Automatic lexical candidate discovery is NOT expert fact-checking.
    Missing licensed full text remains an explicit scientific blocker.
    """
    mapped = 0
    paragraphs_cache = {}
    for order in orders:
        map_path = target/"claim-candidate-maps"/order["order_file"]
        if map_path.exists():
            prior = json.loads(safe_read(map_path, 4_000_000))
            ensure(prior.get("order_file") == order["order_file"] and
                   prior.get("qc1000_approved") is False and
                   prior.get("public_distribution_allowed") is False and
                   prior.get("all_scientific_claims_verified") is False,
                   "FORGED_CLAIM_MAP")
            continue
        evidence = {}
        completed = True
        for task in order["tasks"]:
            doi = task["doi"]
            if doi is None:
                continue
            metadata_path = target/"metadata"/(key(doi)+".json")
            if not metadata_path.exists():
                completed = False
                break
            evidence[task["source_id"]] = json.loads(safe_read(metadata_path))
        if not completed:
            continue
        claim_rows = []
        for claim in order["claims"]:
            findings = []
            for source_id in claim.get("source_ids", []):
                evidence_row = evidence.get(source_id)
                if evidence_row is None:
                    findings.append({"source_id":source_id,"state":"NO_DOI_OR_NO_VERIFIABLE_SOURCE",
                                     "candidates":[]})
                    continue
                doi = evidence_row["doi"]
                options = []
                if evidence_row["state"] == "LICENSED_FULLTEXT_ARCHIVED":
                    if doi not in paragraphs_cache:
                        raw = safe_read(target/"licensed-xml"/(key(doi)+".xml"), MAX_XML+1)
                        ensure(sha(raw) == evidence_row["xml_sha256"],
                               "SOURCE_BODY_CHANGED")
                        _, body = xml_parts(raw,doi,evidence_row["pmcid"])
                        if len(paragraphs_cache) >= 16:
                            paragraphs_cache.clear()
                        paragraphs_cache[doi] = body
                    options = citation_candidates(claim.get("indexed_abstract_statement",""),
                                                  paragraphs_cache[doi])
                findings.append({"source_id":source_id,
                                 "state":evidence_row["state"],
                                 "candidate_body_passages":options,
                                 "scientific_claim_supported":False,
                                 "independent_verification":"PENDING"})
            claim_rows.append({"claim_id":claim.get("claim_id"),
                               "indexed_abstract_statement":claim.get("indexed_abstract_statement"),
                               "reviewer_assistance_only":findings,
                               "claim_truth_verified":False})
        document = {"schema":"saeit.factory.primary-source-claim-candidate-map.v1",
                    "order_file":order["order_file"],
                    "source_count":len(order["tasks"]),
                    "licensed_source_count":sum(x["state"]=="LICENSED_FULLTEXT_ARCHIVED"
                                                for x in evidence.values()),
                    "all_scientific_claims_verified":False,
                    "independent_scientific_review_completed":False,
                    "qc1000_approved":False,"public_distribution_allowed":False,
                    "commercial_release":False,"claims":claim_rows}
        if once(map_path, canonical(document)):
            mapped += 1
    return mapped


def replace_cursor(path, obj):
    """The only mutable state is a small recoverable scheduling cursor."""
    ensure(not path.is_symlink(), "CURSOR_SYMLINK")
    safe_dir(path.parent)
    fd, tmp = tempfile.mkstemp(prefix=".cursor-",dir=path.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"wb") as out:
            out.write(canonical(obj))
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def execute(factory_private, batch=20, dry_run=False, http_get=live_get):
    ensure(1 <= batch <= 100, "BATCH_OUT_OF_RANGE")
    area = Path(factory_private).resolve()/"production-instructions"
    ensure(area.is_dir() and not area.is_symlink(), "PRIVATE_FACTORY_MISSING")
    unique, orders, total = collect(area)
    target = area/"stage-02/primary-source-acquisition-v1"
    if dry_run:
        return {"orders":len(orders),"source_tasks":total,"unique_dois":len(unique),
                "network_attempts":0,"dry_run":True,"qc1000_approvals":0}
    safe_dir(target)
    safe_dir(target/"metadata")
    safe_dir(target/"licensed-xml")
    lock = target/".primary-acquisition.lock"
    ensure(not lock.is_symlink(), "LOCK_SYMLINK")
    counts = Counter()
    cursor = target/".rotation-cursor.json"
    with lock.open("a+b") as stream:
        os.fchmod(stream.fileno(),0o600)
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        ensure(not cursor.is_symlink(), "UNSAFE_ROTATION_CURSOR")
        dois = list(unique)
        if cursor.exists():
            position = json.loads(safe_read(cursor, 2048))
            ensure(position.get("schema") == SCHEMA and
                   type(position.get("next_index")) is int and
                   position["next_index"] >= 0, "CURSOR_INVALID")
            start = position["next_index"] % len(dois)
        else:
            start = 0
        next_index = start
        for offset in range(len(dois)):
            if counts["attempted"] >= batch:
                break
            index = (start+offset) % len(dois)
            next_index = (index+1) % len(dois)
            doi = dois[index]
            k = key(doi)
            p = target/"metadata"/(k+".json")
            if p.exists():
                meta = json.loads(safe_read(p))
                ensure(meta.get("doi") == doi and
                       meta.get("qc1000_approved") is False and
                       meta.get("public_distribution_allowed") is False,
                       "EXISTING_EVIDENCE_FORGED")
                if meta.get("state") == "LICENSED_FULLTEXT_ARCHIVED":
                    xml = target/"licensed-xml"/(k+".xml")
                    ensure(sha(safe_read(xml, MAX_XML+1)) == meta["xml_sha256"],
                           "PRIMARY_XML_HASH_MISMATCH")
                counts["cached"] += 1
                continue
            counts["attempted"] += 1
            try:
                result, raw, _ = evaluate(doi, http_get)
                if raw is not None:
                    once(target/"licensed-xml"/(k+".xml"),raw)
                record = {"schema":SCHEMA,"doi":doi,"doi_key_sha256":k,
                          "source_orders":len(unique[doi]),"retrieved_at_utc":
                          datetime.now(timezone.utc).isoformat(),
                          **result,
                          "claim_candidate_assessment":"NOT_SEMANTICALLY_VERIFIED",
                          "qc1000_approved":False,"public_distribution_allowed":False,
                          "independent_scientific_review_completed":False}
                once(p,canonical(record))
                counts[result["state"]] += 1
            except (TemporaryFailure, OSError) as exc:
                # One broken publisher/provider lookup must NEVER starve the rest.
                # Rotation postpones this DOI while independent sources continue.
                counts["transient_retry_pending"] += 1
                counts["last_network_error"] = str(exc)[:90]
                continue
            except (ValueError, TypeError, KeyError, ET.ParseError) as exc:
                counts["blocked_source"] += 1
                counts["last_blocked"] = type(exc).__name__+":"+str(exc)[:80]
                continue
        replace_cursor(cursor, {"schema":SCHEMA,"next_index":next_index})
    counts["new_order_claim_candidate_maps"] = map_claim_candidates(target, orders)
    counts["orders"] = len(orders)
    counts["source_tasks"] = total
    counts["unique_dois"] = len(unique)
    counts["remaining_unique_dois"] = sum(
        not (target/"metadata"/(key(doi)+".json")).exists() for doi in unique)
    counts["qc1000_approvals"] = 0
    counts["publications"] = 0
    return dict(counts)

if __name__ == "__main__":
    arg = argparse.ArgumentParser()
    arg.add_argument("--factory-private",required=True)
    arg.add_argument("--batch",type=int,default=20)
    arg.add_argument("--dry-run",action="store_true")
    args=arg.parse_args()
    try:
        print(json.dumps(execute(args.factory_private,args.batch,args.dry_run),
                         sort_keys=True,ensure_ascii=False),flush=True)
    except Exception as exc:
        print("PRIMARY_FULLTEXT_ACQUISITION_ERROR:"+type(exc).__name__+":"+str(exc)[:160],
              file=sys.stderr)
        raise SystemExit(1)
