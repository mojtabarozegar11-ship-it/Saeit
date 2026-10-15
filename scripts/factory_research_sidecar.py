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


def inspect(database, destination, *, limit=50):
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
            ids=[row[0] for row in conn.execute(
                "SELECT id FROM core_product WHERE factory_managed=1 AND active=0 ORDER BY id LIMIT ?",
                (limit,))]
            candidates=[]
            reason_count=collections.Counter()
            for ident in ids:
                bundle=pilot.prepare(conn,ident)
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
        summary={
            "schema":"saeit.factory.evidence-sidecar.v1",
            "mode":"read_only_order_independent_research_worklist",
            "database_mutations":0,
            "external_calls":0,
            "product_count":len(candidates),
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
        return {"status":"ok","processed":len(candidates),"blocked":pending,
                "changed":changed,"publishable":0}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db",required=True)
    parser.add_argument("--out",required=True)
    parser.add_argument("--limit",type=int,default=50)
    opt=parser.parse_args(argv)
    result=inspect(opt.db,opt.out,limit=opt.limit)
    for key,value in result.items():
        print("FACTORY_RESEARCH_SIDECAR_"+str(key).upper()+"="+str(value),flush=True)
    print("FACTORY_RESEARCH_SIDECAR_PUBLICATION=false",flush=True)
    return 0


if __name__=="__main__":
    try: sys.exit(main())
    except Exception as e:
        print("FACTORY_RESEARCH_SIDECAR_ERROR="+type(e).__name__,file=sys.stderr,flush=True)
        sys.exit(1)
