#!/usr/bin/env python3
"""Autonomous *read-only* factory evidence backlog sidecar.

Never fabricates research, publishes a product, modifies the factory database,
touches cron, uses a model/API, or changes the main factory loop. It writes a
minimal privacy-preserving manifest under an explicitly private output folder.
Python 3.8+, standard library only.
"""
import argparse
import collections
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unicodedata

ROOT = Path(__file__).resolve().parent


def load_file(module_name, file):
    spec=importlib.util.spec_from_file_location(module_name,str(file))
    if spec is None or spec.loader is None:
        raise RuntimeError("MODULE_UNAVAILABLE:"+module_name)
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def safe_output(destination, obj):
    dest=Path(destination)
    if dest.exists() and dest.is_symlink():
        raise RuntimeError("OUTPUT_IS_SYMLINK")
    dest.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    os.chmod(str(dest.parent),0o700)
    serialized=json.dumps(obj,sort_keys=True,indent=2,ensure_ascii=False)+"\n"
    if dest.is_file() and dest.read_text(encoding="utf-8")==serialized:
        return False
    fd,temp=tempfile.mkstemp(dir=str(dest.parent),prefix=".research-stage.")
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            f.write(serialized)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp,0o600)
        os.replace(temp,str(dest))
        return True
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def compare_database_sources(private_path, django_path):
    """Inspect separate SQLite files only; never equate integer IDs with identity."""
    a=Path(private_path).expanduser().resolve()
    b=Path(django_path).expanduser().resolve()
    if not a.is_file() or not b.is_file() or a.is_symlink() or b.is_symlink():
        raise RuntimeError("DATABASE_SOURCE_MISSING_OR_SYMLINK")
    same=a.samefile(b)
    def fetch_ids(path):
        c=sqlite3.connect(path.as_uri()+"?mode=ro",uri=True,timeout=12)
        try:
            c.execute("PRAGMA query_only=ON")
            fields={row[1] for row in c.execute("PRAGMA table_info(core_product)")}
            if not {"id","title","active","factory_managed"}.issubset(fields):
                raise RuntimeError("PRODUCT_SCHEMA_INCOMPATIBLE")
            rows=list(c.execute("SELECT id,title,factory_managed,active FROM core_product ORDER BY id LIMIT 100001"))
            if len(rows)>100000:
                raise RuntimeError("DATABASE_COMPARE_EXCEEDS_BOUNDED_LIMIT")
            return {int(i): (" ".join(unicodedata.normalize("NFKC",str(t or "")).split()).casefold(),
                             bool(f),bool(act)) for i,t,f,act in rows}
        finally:
            c.close()
    original=fetch_ids(a)
    reference=fetch_ids(b)
    matching_ids=set(original)&set(reference)
    different=sum(original[i][0]!=reference[i][0] for i in matching_ids)
    return {
        "private_product_count":len(original),
        "django_product_count":len(reference),
        "private_drafts":sum(f and not act for _,f,act in original.values()),
        "django_drafts":sum(f and not act for _,f,act in reference.values()),
        "database_files_are_identical":same,
        "overlapping_numeric_ids":len(matching_ids),
        "overlap_ids_with_different_normalized_titles":different,
        "private_only_numeric_ids":len(set(original)-set(reference)),
        "django_only_numeric_ids":len(set(reference)-set(original)),
        "auto_reconciliation_allowed":False,
        "scope_note":"Distinct SQLite files must never be matched by integer primary key alone.",
    }


def inspect(database, destination, *, limit=50, compare_db=None):
    if not isinstance(limit,int) or isinstance(limit,bool) or limit<1 or limit>100:
        raise ValueError("BOUNDED_PRODUCT_LIMIT_REQUIRED")
    db=Path(database).expanduser().resolve()
    dest=Path(destination).expanduser()
    if not db.is_file():
        raise RuntimeError("FACTORY_DB_NOT_FOUND")
    if dest.exists() and dest.is_symlink():
        raise RuntimeError("PRIVATE_OUT_SYMLINK")
    dest.mkdir(parents=True,exist_ok=True,mode=0o700)
    os.chmod(str(dest),0o700)
    pilot=load_file("factory_private_pilot",ROOT/"factory_first_product_pilot.py")
    gate=load_file("factory_private_evidence_gate",ROOT/"factory_evidence_quality.py")
    lock=dest/".evidence-inspection.lock"
    if lock.is_symlink():
        raise RuntimeError("LOCK_SYMLINK")
    with lock.open("a+b") as mutex:
        os.chmod(str(lock),0o600)
        try:
            fcntl.flock(mutex.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status":"already_running","processed":0}
        conn=sqlite3.connect(db.as_uri()+"?mode=ro",uri=True,timeout=12)
        conn.row_factory=sqlite3.Row
        try:
            conn.execute("PRAGMA query_only=ON")
            columns={col[1] for col in conn.execute("PRAGMA table_info(core_product)")}
            if not {"id","active","factory_managed"}.issubset(columns):
                raise RuntimeError("PRODUCT_SCHEMA_INCOMPATIBLE")
            all_ids=[row[0] for row in conn.execute(
                "SELECT id FROM core_product WHERE factory_managed=1 AND active=0 ORDER BY id LIMIT 10001"
            )]
            if len(all_ids)>10000:
                raise RuntimeError("RESEARCH_BACKLOG_EXCEEDS_BOUNDED_CAP")
            cursor_path=dest/"cursor.json"
            if cursor_path.is_symlink():
                raise RuntimeError("CURSOR_SYMLINK")
            try:
                previous=int(json.loads(cursor_path.read_text(encoding="utf-8")).get("last_product_id",0))
            except (OSError,ValueError,TypeError,AttributeError):
                previous=0
            after=next((n for n,item in enumerate(all_ids) if item>previous),0)
            ids=(all_ids[after:]+all_ids[:after])[:limit]
            candidates=[]
            reason_count=collections.Counter()
            title_counts=collections.Counter()
            for ident in ids:
                bundle=pilot.prepare(conn,ident)
                title=unicodedata.normalize("NFKC",str(bundle.get("title") or ""))
                key=" ".join(title.split()).casefold()
                if key:
                    title_counts[key]+=1
                current=gate.assess(bundle)
                reason_count.update(current["blockers"])
                candidates.append({
                    "product_id":ident,
                    "research_gate":current["research_gate"],
                    "evidence_completeness_workload_percent":current["evidence_completeness_workload_percent"],
                    "counts":current["counts"],
                    "blocker_codes":current["blockers"],
                    "publish_authorized":False,
                })
        finally:
            conn.close()
        pending=sum(1 for row in candidates if row["research_gate"]=="RESEARCH_BLOCKED")
        consistency=compare_database_sources(db,compare_db) if compare_db is not None else None
        summary={
            "schema":"saeit.factory.evidence-sidecar.v1",
            "data_source_scope":"factory-private-sqlite-only",
            "data_source_consistency":consistency,
            "mode":"read_only_order_independent_research_worklist",
            "database_mutations":0,
            "external_calls":0,
            "product_count":len(candidates),
            "total_factory_drafts_in_scope":len(all_ids),
            "unscanned_in_this_batch":max(0,len(all_ids)-len(candidates)),
            "duplicate_title_occurrences_in_batch":sum(max(0,v-1) for v in title_counts.values()),
            "duplicate_title_groups_in_batch":sum(int(v>1) for v in title_counts.values()),
            "last_scanned_product_id":ids[-1] if ids else previous,
            "research_blocked":pending,
            "quantitative_research_review_candidates":len(candidates)-pending,
            "blocker_frequency":dict(sorted(reason_count.items())),
            "products":candidates,
            "commercial_quality_approved":False,
            "publishable_count":0,
            "approval_bypass":False,
            "note":"Research evidence counts are candidate metrics, never independently certified product quality.",
        }
        changed=safe_output(dest/"latest.json",summary)
        if ids:
            safe_output(dest/"cursor.json",{"last_product_id":ids[-1]})
        return {"status":"ok","processed":len(candidates),"blocked":pending,
                "total_drafts":len(all_ids),"unscanned":max(0,len(all_ids)-len(candidates)),
                "duplicates":summary["duplicate_title_occurrences_in_batch"],
                "changed":changed,"publishable":0}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db",required=True)
    parser.add_argument("--out",required=True)
    parser.add_argument("--limit",type=int,default=50)
    parser.add_argument("--compare-db",help="Actual Django default SQLite path for read-only source separation check")
    opt=parser.parse_args(argv)
    result=inspect(opt.db,opt.out,limit=opt.limit,compare_db=opt.compare_db)
    for key,value in result.items():
        print("FACTORY_RESEARCH_SIDECAR_"+str(key).upper()+"="+str(value),flush=True)
    print("FACTORY_RESEARCH_SIDECAR_PUBLICATION=false",flush=True)
    return 0


if __name__=="__main__":
    try: sys.exit(main())
    except Exception as e:
        print("FACTORY_RESEARCH_SIDECAR_ERROR="+type(e).__name__,file=sys.stderr,flush=True)
        sys.exit(1)
