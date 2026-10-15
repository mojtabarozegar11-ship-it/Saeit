#!/usr/bin/env python3
"""Bounded, repeatable private research dossiers from Astra R&D task IDs.

This is NOT a web crawler, customer interview, market verifier or product
factory. Source and private queue SQLite are both opened strictly read-only;
only small, atomic, private JSON research-work plans are written. No titles,
passages, URLs, credentials, checkout records, or personal data are exported.
Compatible with VPS Python 3.8+; network requests = zero.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from urllib.parse import urlsplit

MAX_BATCH = 50
EVIDENCE_TARGET = 100
RESEARCH_STEPS = (
    {"id": "independent_sources", "type": "external",
     "next": "Find and manually verify original, nonduplicated research sources with attributable publishers, retrieval dates and rights."},
    {"id": "competitive_benchmark", "type": "external",
     "next": "Compare use cases, cost and limits with established university or free alternatives."},
    {"id": "customer_problem", "type": "external",
     "next": "Interview genuine target users with their consent; preserve anonymized original notes."},
    {"id": "price_willingness", "type": "external",
     "next": "Collect independently evidenced ability and willingness to pay; no synthetic price labels."},
    {"id": "independent_domain_review", "type": "external",
     "next": "Obtain qualified agronomy, economics, statistical-method and accessibility review."},
    {"id": "factory_internal_audit", "type": "internal",
     "next": "Verify exact version/hash, regression tests, rights/support burden and expected artifact deliverables."},
)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _read_only(path):
    p = Path(path).expanduser()
    if p.is_symlink() or not p.is_file() or not p.stat().st_size:
        raise ValueError("READ_SOURCE_UNSAFE_OR_MISSING")
    conn = sqlite3.connect(p.resolve(strict=True).as_uri() + "?mode=ro",
                           uri=True, timeout=10)
    conn.execute("PRAGMA query_only=ON")
    conn.execute("BEGIN")
    return conn


def _domain(url):
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname or ""
        if (parsed.scheme.lower() not in ("https", "http") or
                parsed.username is not None or parsed.password is not None or
                not hostname or len(hostname) > 253 or
                not re.fullmatch(r"[a-zA-Z0-9.-]+", hostname)):
            return None
        host = hostname.rstrip(".").lower()
        if (host == "localhost" or host.endswith(".local") or
                re.fullmatch(r"\d+\.\d+\.\d+\.\d+", host)):
            return None
        return host
    except (ValueError, AttributeError, TypeError):
        return None


def _schema(db, required):
    for table, need in required.items():
        fields = {row[1] for row in db.execute("PRAGMA table_info(" + table + ")")}
        if not need.issubset(fields):
            raise ValueError("SCHEMA_MISSING_" + table)


def _candidate(db, pid):
    sources = db.execute("""
        SELECT DISTINCT s.id,s.url,s.content_hash,s.publisher,s.snapshot_hash
        FROM core_researchsource s
        JOIN core_researchproject rp ON rp.id=s.project_id
        JOIN core_factoryrun r ON r.id=rp.factory_run_id
        WHERE r.product_id=? ORDER BY s.id LIMIT 500
    """, (pid,)).fetchall()
    evidence = db.execute("""
        SELECT COUNT(DISTINCT e.id)
        FROM core_evidence e
        JOIN core_researchproject rp ON rp.id=e.project_id
        JOIN core_factoryrun r ON r.id=rp.factory_run_id
        JOIN core_researchsource s ON s.id=e.source_id AND s.project_id=rp.id
        WHERE r.product_id=?
    """, (pid,)).fetchone()[0]
    attributable=set()
    candidate_refs=0
    unique_refs=set()
    strong_content_hash=0
    snapshots=0
    for _sid,url,content_hash,publisher,snap in sources:
        domain=_domain(url or "")
        if domain and (publisher or "").strip():
            candidate_refs+=1
            attributable.add(domain)
            unique_refs.add(((url or "").strip().lower(),(content_hash or "").strip().lower()))
        if re.fullmatch(r"[a-fA-F0-9]{64}",(content_hash or "")):
            strong_content_hash+=1
        if re.fullmatch(r"[a-fA-F0-9]{64}",(snap or "")):
            snapshots+=1
    candidate_refs=min(len(unique_refs),candidate_refs)
    return {
        "source_rows_inspected_max500":len(sources),
        "structurally_attributed_unique_references_unverified":candidate_refs,
        "distinct_publisher_domains_unverified":len(attributable),
        "linked_evidence_rows_unverified":int(evidence),
        "strong_content_sha256_rows_unverified":strong_content_hash,
        "snapshot_sha256_rows_unverified":snapshots,
    }


def build(legacy_path, research_path, output_path, *, limit=25):
    if not (1 <= limit <= MAX_BATCH):
        raise ValueError("BATCH_LIMIT_OUT_OF_RANGE")
    output=Path(output_path).expanduser()
    if output.is_symlink() or not output.is_dir():
        raise ValueError("PRIVATE_OUTPUT_DIRECTORY_UNSAFE")
    out=output.resolve(strict=True)
    if out.stat().st_mode & 0o077:
        raise ValueError("PRIVATE_OUTPUT_DIRECTORY_PERMISSIONS")
    if out == Path(legacy_path).expanduser().parent.resolve():
        raise ValueError("PRIVATE_OUTPUT_CANNOT_BE_LEGACY_DIR")
    with _read_only(legacy_path) as old, _read_only(research_path) as queue:
        _schema(old,{
            "core_researchsource":{"id","project_id","url","content_hash","publisher","snapshot_hash"},
            "core_researchproject":{"id","factory_run_id"},
            "core_factoryrun":{"id","product_id"},
            "core_evidence":{"id","source_id","project_id"},
        })
        _schema(queue,{"research_tasks":{
            "legacy_product_id","stage","source_refs_unverified",
            "market_demand_verified","sale_ready","quality_score",
        }})
        entries=queue.execute(
            "SELECT legacy_product_id,stage,market_demand_verified,sale_ready,"
            "quality_score FROM research_tasks "
            "WHERE stage='WAITING_FOR_EVIDENCE' "
            "ORDER BY legacy_product_id LIMIT ?",(limit,)).fetchall()
        if queue.execute("SELECT COUNT(*) FROM research_tasks "
                         "WHERE market_demand_verified<>0 OR sale_ready<>0 "
                         "OR quality_score IS NOT NULL").fetchone()[0]:
            raise ValueError("RETAIL_GATE_NOT_FAIL_CLOSED")
        summaries=[]
        for pid,stage,market,sale,score in entries:
            if market or sale or score is not None:
                raise ValueError("UNVERIFIED_COMMERCIAL_CLAIM")
            source=_candidate(old,int(pid))
            dossier={
                "schema_version":1, "research_id":"legacy-factory-product:"+str(pid),
                "stage":"WAITING_FOR_EVIDENCE",
                "source_data":"legacy_database_read_only",
                "research_evidence_target":EVIDENCE_TARGET,
                "independently_verified_research_items":0,
                "remaining_independent_evidence_items":EVIDENCE_TARGET,
                "observed_source_statistics":source,
                "external_actions_required":5,
                "internal_actions_required":1,
                "next_research_actions":list(RESEARCH_STEPS),
                "domain_review_verified":False,
                "customer_problem_verified":False,
                "buyer_willingness_to_pay_verified":False,
                "license_review_verified":False,
                "commercial_quality_score":None,
                "price_justified":False,
                "release_authorized":False,
                "market_research_performed_by_this_run":False,
                "warnings":["Numbers count source records, not source reliability, domain validation, demand or paid value.",
                            "No actual external research is performed by this offline generator."],
            }
            target=out/("research-"+str(pid)+".json")
            if target.is_symlink() or (target.exists() and not target.is_file()):
                raise ValueError("DOSSIER_FILE_UNSAFE")
            fd,tmp=tempfile.mkstemp(prefix=".astra-dossier-",suffix=".tmp",dir=str(out))
            try:
                with os.fdopen(fd,"w",encoding="utf-8") as file:
                    json.dump(dossier,file,sort_keys=True,ensure_ascii=False,indent=2)
                    file.write("\n")
                    file.flush()
                    os.fsync(file.fileno())
                os.chmod(tmp,0o600)
                os.replace(tmp,str(target))
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            summaries.append({"id":int(pid),
                              "structural_refs":source["structurally_attributed_unique_references_unverified"]})
        old.execute("COMMIT")
        queue.execute("COMMIT")
    return {"mode":"PRIVATE_OFFLINE_RESEARCH_PLANS",
            "dossiers_written":len(summaries),
            "reference_count_not_independent_verification":True,
            "independently_verified_commercial_products":0,
            "network_requests":0, "customer_orders_required":False,
            "factory_databases_modified":False,
            "public_store_or_payment_modified":False,
            "generated_at_utc":_now()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-db",required=True)
    parser.add_argument("--research-db",required=True)
    parser.add_argument("--output-dir",required=True)
    parser.add_argument("--limit",type=int,default=25)
    args=parser.parse_args()
    print(json.dumps(build(args.legacy_db,args.research_db,args.output_dir,
                           limit=args.limit),sort_keys=True))


if __name__=="__main__":
    main()
