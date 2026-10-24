#!/usr/bin/env python3
"""License-verified alternative literature candidates for rejected factory work.

Never substitute a paper for a claim automatically. This is private reviewer
assistance, not scientific authorship, field evidence, QC1000 or publication.
Original source packets, XML and product archives remain immutable.
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlencode

SCHEMA = "saeit.factory.qc184.licensed-alternative-discovery.v1"
STOP = {"study", "studies", "research", "based", "using", "analysis",
        "review", "effect", "effects", "among", "during", "from", "with",
        "between", "results", "improved", "assessment", "evaluation",
        "evidence", "experimental", "application", "agricultural"}
WORDS = re.compile(r"[a-z]{4,}")
NAME = re.compile(r"WO-[0-9]{8}--r[0-9]{3}\.json\Z")
BAD_SOURCE = {"DOI_NOT_INDEXED_AT_EUROPE_PMC", "NO_PMC_FULLTEXT_LINK",
              "COMMERCIAL_REUSE_LICENSE_NOT_VERIFIED",
              "PMC_FULLTEXT_XML_NOT_PUBLIC", "ARCHIVED_LICENSE_RECHECK_REQUIRED"}
NO_APPROVAL = {"qc1000_approved": False, "commercial_release": False,
               "public_distribution_allowed": False,
               "independent_scientific_review_completed": False}

def primary_module(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("PRIMARY_WORKER_MISSING_OR_UNSAFE")
    spec = importlib.util.spec_from_file_location("qc184_primary", path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

def terms(text):
    words = [x for x in WORDS.findall(str(text).lower()) if x not in STOP]
    return list(dict.fromkeys(words))[:9]

def candidate_search_query(title):
    chosen = terms(title)
    if len(chosen) < 2:
        return None
    # Every term is an alphanumeric token. Never pass source-owned syntax.
    return " AND ".join(chosen[:3]) + " AND OPEN_ACCESS:y"

def collect_work(area, p):
    unique, orders, _ = p.collect(area)
    inbox = area / "stage-02/primary-fulltext-repair-inbox"
    target = area / "stage-02/primary-source-acquisition-v1"
    work = {}
    for order in orders:
        packet = json.loads(p.safe_read(inbox / order["order_file"]))
        for task in packet["scientific_primary_source_tasks"]:
            doi = p.normalize_doi(task["doi"]) if task.get("doi") else None
            title = task.get("title")
            if not isinstance(title, str) or len(title.strip()) < 12:
                continue
            # Scope to known DOI keys. No unverified arbitrary URL fetch.
            if doi is None or doi not in unique:
                continue
            metadata = target / "metadata" / (p.key(doi) + ".json")
            if not metadata.exists():
                continue  # Original primary acquisition still processing.
            row = p.read_verified_evidence(target, doi)
            if row["state"] not in BAD_SOURCE and not row["state"].startswith("FULLTEXT_REJECTED_"):
                continue
            if doi not in work:
                work[doi] = {"doi":doi, "title": title.strip()[:350],
                             "state": row["state"],
                             "order_count":len(unique[doi])}
    return work, len(orders)

def search_one(row, p, http_get):
    query = candidate_search_query(row["title"])
    if query is None:
        return {"state": "TITLE_TOO_VAGUE_FOR_SAFE_DISCOVERY",
                "query": None, "candidates": []}, []
    url = p.ROOT_API + "/search?" + urlencode({
        "query": query, "format": "json", "pageSize": "8",
        "resultType": "core"})
    raw = http_get(url, p.MAX_META)
    if raw is None:
        raise p.TemporaryFailure("CANDIDATE_SEARCH_UNAVAILABLE")
    entries = json.loads(raw).get("resultList", {}).get("result", [])
    if not isinstance(entries, list):
        raise ValueError("CANDIDATE_INDEX_MALFORMED")
    proposals = []
    archives = []
    seen = set()
    wanted = set(terms(row["title"]))
    for item in entries[:8]:
        if not isinstance(item, dict):
            continue
        try:
            doi = p.normalize_doi(item.get("doi"))
        except (ValueError, TypeError):
            continue
        pmcid = item.get("pmcid")
        title = item.get("title")
        if (doi == row["doi"] or doi in seen or
                not isinstance(title, str) or
                not isinstance(pmcid, str) or
                re.fullmatch(r"PMC[0-9]{3,12}", pmcid) is None or
                str(item.get("isRetracted", "")).upper() in ("Y", "TRUE")):
            continue
        overlap = sorted(wanted & set(terms(title)))
        # Lexical relevance is ONLY a search filter, never claim verification.
        if len(overlap) < 2:
            continue
        try:
            body = http_get(p.ROOT_API + "/" + pmcid + "/fullTextXML", p.MAX_XML)
            if body is None:
                continue
            license_text, paragraphs = p.xml_parts(body, doi, pmcid)
            if not p.license_ok(license_text):
                continue
        except p.TemporaryFailure:
            raise
        except (p.Blocked, ValueError, TypeError):
            continue
        seen.add(doi)
        proposals.append({
            "candidate_doi":doi, "pmcid":pmcid, "title":title[:500],
            "original_source_doi":row["doi"],
            "overlapping_title_terms":overlap[:6],
            "licensed_xml_sha256":p.sha(body),
            "licensed_xml_bytes":len(body),
            "license_evidence":license_text[:600],
            "body_paragraphs":len(paragraphs),
            "retraction_index_flag":False,
            "claim_support_verified":False, "source_substitution_approved":False,
            "human_domain_review_required":True})
        archives.append((doi, body))
        if len(proposals) >= 2:
            break
    return {"state": "LICENSED_CANDIDATES_REQUIRE_INDEPENDENT_REVIEW"
            if proposals else "NO_MATCHING_LICENSED_CANDIDATE_FOUND",
            "query":query, "candidates":proposals}, archives

def execute(factory_private, primary_worker, batch=8, dry_run=False,
            http_get=None):
    if type(batch) is not int or not 1 <= batch <= 30:
        raise ValueError("REPLACEMENT_BATCH_INVALID")
    p = primary_module(primary_worker)
    area = Path(factory_private).resolve() / "production-instructions"
    if not area.is_dir() or area.is_symlink():
        raise ValueError("FACTORY_PRIVATE_AREA_UNAVAILABLE")
    work, orders = collect_work(area, p)
    if dry_run:
        return {"orders":orders, "eligible_unusable_dois":len(work),
                "network_attempts":0, "dry_run":True, **NO_APPROVAL}
    target = area / "stage-02/licensed-alternative-discovery-v1"
    for sub in ("reports", "licensed-xml"):
        p.safe_dir(target / sub)
    lock = target / ".discovery.lock"
    if lock.is_symlink():
        raise ValueError("DISCOVERY_LOCK_SYMLINK")
    counts = Counter()
    names = sorted(work)
    cursor = target / ".rotation-cursor.json"
    getter = http_get or p.live_get
    with lock.open("a+b") as handle:
        os.fchmod(handle.fileno(), 0o600)
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        old = json.loads(p.safe_read(cursor)) if cursor.exists() else {
            "schema":SCHEMA, "next_index":0}
        if (old.get("schema") != SCHEMA or
                type(old.get("next_index")) is not int or
                old["next_index"] < 0):
            raise ValueError("DISCOVERY_CURSOR_INVALID")
        start = old["next_index"] % len(names) if names else 0
        offset = 0
        while offset < len(names) and counts["attempted"] < batch:
            index = (start + offset) % len(names)
            offset += 1
            row = work[names[index]]
            report_path = target / "reports" / (p.key(row["doi"]) + ".json")
            if report_path.exists():
                record = json.loads(p.safe_read(report_path, 200000))
                if (record.get("schema") != SCHEMA or
                        record.get("original_doi") != row["doi"] or
                        record.get("qc1000_approved") is not False or
                        record.get("public_distribution_allowed") is not False):
                    raise ValueError("DISCOVERY_REPORT_FORGED")
                # Negative matches are rechecked after 7 days, never hot-looped.
                stamp = datetime.fromisoformat(record["searched_utc"])
                if record.get("candidates") or datetime.now(timezone.utc)-stamp < timedelta(days=7):
                    counts["cached"] += 1
                    continue
            counts["attempted"] += 1
            try:
                result, archives = search_one(row, p, getter)
                for doi, body in archives:
                    p.once(target/"licensed-xml"/(p.key(doi)+".xml"),body)
                report = {"schema":SCHEMA, "original_doi":row["doi"],
                          "original_title":row["title"],
                          "original_source_state":row["state"],
                          "original_linked_orders":row["order_count"],
                          "searched_utc":datetime.now(timezone.utc).isoformat(),
                          "independent_reviewer_required":True,
                          "not_an_automatic_source_substitution":True,
                          **result, **NO_APPROVAL}
                p.replace_cursor(report_path, report)
                counts[result["state"]] += 1
                counts["licensed_alternatives_found"] += len(result["candidates"])
            except (p.TemporaryFailure, OSError) as exc:
                counts["transient_retry_pending"] += 1
                counts["last_transient"] = str(exc)[:90]
            except (ValueError, TypeError, KeyError) as exc:
                counts["invalid_source_blocked"] += 1
                counts["last_blocked"] = type(exc).__name__ + ":" + str(exc)[:90]
        if names:
            p.replace_cursor(cursor, {"schema":SCHEMA,
                           "next_index":(start+offset)%len(names)})
    reports = [x for x in (target/"reports").iterdir()
               if x.is_file() and not x.is_symlink() and x.suffix==".json"]
    counts.update({"orders":orders, "eligible_unusable_dois":len(work),
                   "reports_total":len(reports),
                   "scientific_approvals_created":0,
                   "publications_created":0})
    return dict(counts)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--factory-private",required=True)
    ap.add_argument("--primary-worker",required=True)
    ap.add_argument("--batch",type=int,default=8)
    ap.add_argument("--dry-run",action="store_true")
    args=ap.parse_args()
    try:
        print(json.dumps(execute(args.factory_private,args.primary_worker,
                                 args.batch,args.dry_run),
                         sort_keys=True,ensure_ascii=False),flush=True)
    except Exception as exc:
        print("QC184_ALTERNATIVE_DISCOVERY_ERROR:"+
              type(exc).__name__+":"+str(exc)[:180],file=sys.stderr)
        raise SystemExit(1)

if __name__ == "__main__":
    main()
