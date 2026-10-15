#!/usr/bin/env python3
"""Readonly foreign-key and content lineage audit of two isolated factory DBs.

No personal data, product titles, hashes of personal strings, or secret paths printed.
No writes and no accidental database creation (SQLite URI mode=ro).
"""
from __future__ import annotations
import collections
import hashlib
import json
import os
from pathlib import Path
import sqlite3

os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
from django.conf import settings

HOME=Path.home()
D=Path(settings.DATABASES["default"]["NAME"]).resolve()
P=(HOME/"factory-runtime/private/factory-fresh-isolated.sqlite3").resolve()
if D == P:
    raise RuntimeError("SAME_DATABASE_NO_SPLIT")

def open_ro(p):
    conn=sqlite3.connect(p.as_uri()+"?mode=ro",uri=True,timeout=12)
    conn.row_factory=sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn

def table_cols(conn,table):
    return {r[1] for r in conn.execute("PRAGMA table_info("+table+")")}

def collect(conn):
    columns=table_cols(conn,"core_product")
    wanted={"id","title","metadata","price","active","factory_managed","owner_id","knowledge_article_id"}
    if not wanted.issubset(columns):
        raise RuntimeError("PRODUCT_SCHEMA_DIFFERENCE")
    data={}
    for row in conn.execute("SELECT id,title,metadata,price,active,factory_managed,owner_id,knowledge_article_id FROM core_product ORDER BY id LIMIT 10000"):
        meta={}
        try:
            candidate=json.loads(row["metadata"]) if isinstance(row["metadata"],str) else row["metadata"]
            if isinstance(candidate,dict):
                meta=candidate
        except (TypeError,ValueError):
            pass
        fields={k:row[k] for k in row.keys()}
        fields["factory_state"]=str(meta.get("factory_state",""))[:80]
        val=meta.get("validation",{})
        fields["validation_outcome"]=str(val.get("outcome","")) if isinstance(val,dict) else ""
        fields["metadata_fingerprint"]=hashlib.sha256(
            json.dumps(meta,sort_keys=True,ensure_ascii=False).encode("utf-8")).hexdigest()
        data[row["id"]]=fields
    return data

def linked_product_ids(conn, table, parent_col):
    if not {"id",parent_col}.issubset(table_cols(conn,table)):
        return set()
    return {r[0] for r in conn.execute(
        "SELECT DISTINCT "+parent_col+" FROM "+table+" WHERE "+parent_col+" IS NOT NULL")}
 
with open_ro(D) as main, open_ro(P) as private:
    m=collect(main)
    p=collect(private)
    main_ids=set(m)
    priv_ids=set(p)
    common=main_ids & priv_ids
    extra=priv_ids-main_ids
    missing=main_ids-priv_ids
    counter=collections.Counter()
    for pid in common:
        a,b=m[pid],p[pid]
        counter["OVERLAP_IDENTICAL_TITLE"]+=int(a["title"]==b["title"])
        counter["OVERLAP_DIFFERENT_TITLE"]+=int(a["title"]!=b["title"])
        counter["OVERLAP_IDENTICAL_METADATA"]+=int(a["metadata_fingerprint"]==b["metadata_fingerprint"])
        counter["OVERLAP_DIFFERENT_METADATA"]+=int(a["metadata_fingerprint"]!=b["metadata_fingerprint"])
        counter["OVERLAP_SAME_VALIDATION_OUTCOME"]+=int(a["validation_outcome"]==b["validation_outcome"])
        counter["OVERLAP_OWNER_DISCREPANCY"]+=int(a["owner_id"]!=b["owner_id"])
    extra_unpriced=sum(1 for i in extra if not float(p[i]["price"] or 0))
    extra_unowned=sum(1 for i in extra if p[i]["owner_id"] is None)
    extra_no_knowledge=sum(1 for i in extra if p[i]["knowledge_article_id"] is None)
    extra_active=sum(1 for i in extra if bool(p[i]["active"]))
    extra_needs_research=sum(1 for i in extra if p[i]["factory_state"]=="needs_research")
    private_run_ids=linked_product_ids(private,"core_factoryrun","product_id")
    main_run_ids=linked_product_ids(main,"core_factoryrun","product_id")
    private_project_count=private.execute("SELECT COUNT(*) FROM core_researchproject").fetchone()[0]
    private_run_count=private.execute("SELECT COUNT(*) FROM core_factoryrun").fetchone()[0]
    private_task_count=private.execute("SELECT COUNT(*) FROM core_agenttask").fetchone()[0]
    print("DB_COMPARE_MAIN_PRODUCTS="+str(len(main_ids)))
    print("DB_COMPARE_PRIVATE_PRODUCTS="+str(len(priv_ids)))
    print("DB_COMPARE_SHARED_IDS="+str(len(common)))
    print("DB_COMPARE_PRIVATE_ONLY="+str(len(extra)))
    print("DB_COMPARE_MAIN_ONLY="+str(len(missing)))
    for k,v in sorted(counter.items()):
        print("DB_COMPARE_"+k+"="+str(v))
    print("DB_COMPARE_PRIVATE_EXTRA_NO_PRICE="+str(extra_unpriced))
    print("DB_COMPARE_PRIVATE_EXTRA_NO_OWNER="+str(extra_unowned))
    print("DB_COMPARE_PRIVATE_EXTRA_NO_ARTICLE="+str(extra_no_knowledge))
    print("DB_COMPARE_PRIVATE_EXTRA_ACTIVE="+str(extra_active))
    print("DB_COMPARE_PRIVATE_EXTRA_NEEDS_RESEARCH="+str(extra_needs_research))
    print("DB_COMPARE_PRIVATE_EXTRA_LINKED_TO_FACTORY_RUN="+str(len(extra & private_run_ids)))
    print("DB_COMPARE_MAIN_LINKED_TO_FACTORY_RUN="+str(len(main_ids & main_run_ids)))
    print("DB_COMPARE_PRIVATE_RUN_TOTAL="+str(private_run_count))
    print("DB_COMPARE_PRIVATE_PROJECT_TOTAL="+str(private_project_count))
    print("DB_COMPARE_PRIVATE_AGENTTASK_TOTAL="+str(private_task_count))
    print("DB_COMPARE_AUTO_RECONCILIATION_ALLOWED=false")
    print("DB_COMPARE_READ_ONLY_DONE")
