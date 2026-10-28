#!/usr/bin/env python3
"""Register 200 owner-priority agriculture education topics as PRIVATE orders.

These are production instructions, never manuscripts, stock, verified goods or
site listings. The factory must independently author and verify both editions.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

SCHEMA="saeit.factory.production-instructions.v1"
ORIGIN="owner_requested_agri200_p0"
INDEX_SCHEMA="saeit.factory.owner-agri200-p0-index.v1"
ID_PATTERN=re.compile(r"AGRI-([0-9]{3})")
ORDER_PATTERN=re.compile(r"WO-([0-9]{8})\.json")
HASH_PATTERN=re.compile(r"[0-9a-f]{64}")


def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,
                      separators=(",",":")).encode("utf8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def private_dir(path):
    if path.is_symlink():raise ValueError("P0_SYMLINK_DIRECTORY")
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    if not path.is_dir() or path.is_symlink():raise ValueError("P0_UNSAFE_DIRECTORY")
    os.chmod(path,0o700)


def save(path,value):
    private_dir(path.parent)
    fd,temp=tempfile.mkstemp(prefix=".agri200-",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as out:
            out.write(json.dumps(value,ensure_ascii=False,sort_keys=True,
                                 indent=2).encode("utf8")+b"\n")
            out.flush();os.fsync(out.fileno())
        os.chmod(temp,0o600)
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)


def read(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>2_000_000:
        raise ValueError("P0_UNSAFE_SOURCE:"+path.name)
    data=json.loads(path.read_text(encoding="utf8"))
    if not isinstance(data,dict):raise ValueError("P0_OBJECT_REQUIRED")
    return data


def catalog(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>70_000:
        raise ValueError("P0_CATALOG_UNSAFE")
    rows=[]
    for raw in path.read_text(encoding="utf8").splitlines():
        line=raw.strip()
        if not line or line.startswith("#"):continue
        parts=line.split("|")
        if len(parts)!=3:raise ValueError("P0_CATALOG_COLUMN_COUNT")
        ident,fa,en=(p.strip() for p in parts)
        if not ID_PATTERN.fullmatch(ident):raise ValueError("P0_BAD_ID")
        if not 7<=len(fa)<=160 or not 7<=len(en)<=160:
            raise ValueError("P0_BAD_TITLE")
        if any(c in fa+en for c in "\r\n\x00"):raise ValueError("P0_CONTROL_CHAR")
        rows.append((ident,fa,en))
    if len(rows)!=200 or len({x[0] for x in rows})!=200:
        raise ValueError("P0_REQUIRES_200_UNIQUE_TITLES")
    if [x[0] for x in rows]!=["AGRI-%03d"%n for n in range(1,201)]:
        raise ValueError("P0_CATALOG_PRIORITY_ORDER")
    if len({x[1] for x in rows})!=200 or len({x[2].casefold() for x in rows})!=200:
        raise ValueError("P0_DUPLICATE_TOPIC")
    return rows


def make_order(ident,fa,en,rank):
    content={
        "origin":ORIGIN,"source_product_id":ident,
        "source_sha256":digest({"id":ident,"fa":fa,"en":en}),
        "priority":"P0","priority_rank":rank,
        "priority_reason":"OWNER_DIRECTIVE_2026_10_22",
        "family_id":"F01","related_learning_family":"F07",
        "phase":"specialist_agriculture_booklet_authoring",
        "slot":1,"subject":fa,
        "instruction":"Write two genuinely localized, original agriculture training booklets "
                      "from research to tested editable sources, illustrated accessible "
                      "PDF and a separate cited reference list. Do not count this order "
                      "as a completed booklet or auto-promote it to a sale-ready good.",
        "editions":[
            {"locale":"fa-IR","site":"zomorodmelal.ir","title":fa,
             "audience":"Iran; examples, agronomic climate, regulations and units independently localized"},
            {"locale":"en-US","site":"mojplaywin.com","title":en,
             "audience":"United States and international; local growing zones, measures and standards independently localized"}
        ],
        "acceptance":[
            "Original useful step-by-step field instructions, illustrations and worked examples for both locales",
            "Credible traceable scientific or extension references for each material agronomic claim",
            "Practical checklists, local seasonal decision tables and editable worksheets",
            "Validate safety-critical pesticide, mushroom, animal and food handling against local rules",
            "Proofread each localized manuscript independently; inspect actual final PDF rendering",
            "Hash-bound source, PDF and evidence, specialist assessment and strict QA1000 before sale"
        ],
        "product_goal_count":2,"technical_product_release":False,
        "schema":SCHEMA,"status":"issued","instruction_kind":"private_factory_work_order",
        "independent_of_websites":True,"requires_customer_order":False,
        "api_required":False,"manufacturing_qa_passed":False,
        "publication_approved":False,"public_distribution_allowed":False,
        "warehouse_goods_created":False,"commercial_release":False,
        "requested_production_language_count":2
    }
    content["fingerprint"]=digest({k:v for k,v in content.items() if k not in ("schema","status","instruction_kind","fingerprint")})
    return content


def install(root,catalog_path):
    root=Path(root).expanduser().resolve()
    if not root.is_dir() or root.is_symlink():raise ValueError("P0_FACTORY_ROOT_MISSING")
    rows=catalog(catalog_path)
    area=root/"production-instructions"
    queue=area/"orders"
    private_dir(area);private_dir(queue)
    lock_path=area/".orders.lock"
    if lock_path.is_symlink():raise ValueError("P0_UNSAFE_LOCK")
    with lock_path.open("a+b") as lock:
        os.chmod(lock_path,0o600)
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        old=[]
        for path in sorted(queue.iterdir()):
            if path.is_symlink() or not path.is_file() or not ORDER_PATTERN.fullmatch(path.name):
                raise ValueError("P0_INVALID_EXISTING_QUEUE")
            item=read(path)
            if item.get("schema")!=SCHEMA or item.get("id")!=path.stem or item.get("public_distribution_allowed") is not False:
                raise ValueError("P0_UNSAFE_EXISTING_ORDER")
            if item.get("status") not in ("issued","in_engineering","blocked_rework","completed_verified"):
                raise ValueError("P0_BAD_EXISTING_STATUS")
            if not HASH_PATTERN.fullmatch(str(item.get("fingerprint",""))):
                raise ValueError("P0_BAD_EXISTING_FINGERPRINT")
            old.append(item)
        # An existing index is an immutable historical identity boundary.
        # After an authorized cleanup, never silently recreate deleted orders
        # with fresh WO IDs or overwrite the old owner index.
        index_path=area/"owner-agri200-p0-index.json"
        historical_ids=None
        if index_path.exists() or index_path.is_symlink():
            prior=read(index_path)
            historical_ids=prior.get("order_ids_ranked")
            if (prior.get("schema")!=INDEX_SCHEMA or
                    not isinstance(historical_ids,list) or len(historical_ids)!=200 or
                    any(not isinstance(i,str) or not ORDER_PATTERN.fullmatch(i+".json")
                        for i in historical_ids) or len(set(historical_ids))!=200):
                raise ValueError("P0_HISTORICAL_INDEX_INVALID")
            for ident in historical_ids:
                path=queue/(ident+".json")
                if path.is_symlink() or not path.is_file():
                    raise ValueError("P0_HISTORICAL_ORDER_MISSING_RECONCILE_NOT_RECREATE")
        if len(old)+200>15000:raise ValueError("P0_ORDER_STORAGE_CAP")
        current={}
        for item in old:
            if item.get("origin")!=ORIGIN:continue
            ident=item.get("source_product_id")
            if ident in current:raise ValueError("P0_DUPLICATE_PRIOR")
            current[ident]=item
        if historical_ids is not None:
            ranked_existing=[current.get(ident,{}).get("id") for ident,_,_ in rows]
            if ranked_existing!=historical_ids:
                raise ValueError("P0_HISTORICAL_INDEX_ORDER_DRIFT")
        expected={ident:make_order(ident,fa,en,rank) for rank,(ident,fa,en) in enumerate(rows,1)}
        for ident,item in current.items():
            if ident not in expected:raise ValueError("P0_UNEXPECTED_OLD_TOPIC")
            if any(item.get(k)!=v for k,v in expected[ident].items() if k not in ("id","created_utc","status")):
                raise ValueError("P0_EXISTING_TOPIC_CONFLICT:"+ident)
        serial=max((int(i["id"].split("-")[1]) for i in old),default=0)
        created=0
        for ident,_,_ in rows:
            if ident in current:continue
            serial+=1
            item=dict(expected[ident],id="WO-%08d"%serial)
            path=queue/(item["id"]+".json")
            if path.exists() or path.is_symlink():raise ValueError("P0_ORDER_ID_COLLISION")
            save(path,item)
            current[ident]=item
            created+=1
        ids=[current[ident]["id"] for ident,_,_ in rows]
        index={"schema":INDEX_SCHEMA,"status":"P0_REGISTERED_PENDING_MANUFACTURING",
               "topic_count":200,"edition_goal_count":400,
               "first_priority":True,"order_ids_ranked":ids,
               "catalog_sha256":hashlib.sha256(Path(catalog_path).read_bytes()).hexdigest(),
               "commercial_release":False,"qa1000_certified":False,
               "site_deployments":0,"factory_authoring_completed":0}
        save(area/"owner-agri200-p0-index.json",index)
        return {"created":created,"registered":len(ids),"editions":400,
                "index":str(area/"owner-agri200-p0-index.json")}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--factory-private",required=True)
    p.add_argument("--catalog",required=True)
    args=p.parse_args()
    result=install(args.factory_private,args.catalog)
    print("FACTORY_OWNER_AGRI_P0_NEW_ORDERS="+str(result["created"]))
    print("FACTORY_OWNER_AGRI_P0_REGISTERED="+str(result["registered"]))
    print("FACTORY_OWNER_AGRI_P0_EDITION_GOAL="+str(result["editions"]))
    print("FACTORY_OWNER_AGRI_P0_BOOKLETS_COMPLETED=0")
    print("FACTORY_OWNER_AGRI_P0_SITE_PUBLICATION=false")


if __name__=="__main__":
    main()
