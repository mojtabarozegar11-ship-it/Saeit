"""Read-only partition planning: find foreign-key cut edges before moving tables.

No business rows, database name, passwords or raw SQL definitions exported.
Names in output are restricted to explicitly reviewed application tables.
Other names are represented only by counts.
"""
import json
import os
import pwd
import sys
from pathlib import Path
ROOT=Path("/home/zomorod2/Saeit-mojplaywin-integrated-20261119")
FACTORY={"core_agenttask","core_factoryevidence"}
SHARED={"core_report","core_product","core_researchsource","auth_user","django_content_type","django_migrations"}
STORE={"core_order","core_orderitem","core_paymentintent","core_paymentwebhookevent","core_guestorderemail","core_guestrecoverytoken","core_guestrecoveryrate"}
PROTECTED=FACTORY|SHARED|STORE
def group(name):
    if name in FACTORY:return "factory_heavy"
    if name in SHARED:return "shared_review"
    if name.startswith("prop_firm_"):return "mojprop"
    if name in STORE or name.startswith(("mpw_commerce_","mpw_native_checkout_")):return "store_payment"
    return "unclassified"
def plan(tables,edges):
    sizes={name:int(size) for name,size in tables}
    groups={}
    for name,size in sizes.items():
        bucket=groups.setdefault(group(name),{"tables":0,"estimated_bytes":0})
        bucket["tables"]+=1;bucket["estimated_bytes"]+=size
    cross={}
    factory_edges=[]
    external=0
    for child,parent,local in set(edges):
        if not local or child not in sizes or parent not in sizes:
            external+=1;continue
        a,b=group(child),group(parent)
        if a!=b:
            key=a+" -> "+b
            cross[key]=cross.get(key,0)+1
        if (child in FACTORY)!=(parent in FACTORY):
            factory_edges.append({"child":child if child in PROTECTED else group(child),
                                  "parent":parent if parent in PROTECTED else group(parent),
                                  "child_group":a,"parent_group":b})
    closure=set(FACTORY)&set(sizes)
    while True:
        new=closure|{parent for child,parent,local in edges if local and child in closure and parent in sizes}
        if new==closure:break
        closure=new
    inbound=sum(1 for child,parent,local in set(edges) if local and child not in closure and parent in closure)
    return {"groups":groups,"cross_group_fk_pairs":cross,"factory_boundary_edges":factory_edges,
            "factory_parent_closure_tables":len(closure),"factory_parent_closure_bytes":sum(sizes[x] for x in closure),
            "factory_closure_incoming_pairs":inbound,"external_or_missing_fk_pairs":external,
            "missing_factory_roots":len(FACTORY-set(sizes)),
            "candidate_partition_is_write_allowlist":False}
def inspect():
    out={"read_only":True,"business_rows_read":False,"database_changed":False,"metadata_complete":False,"split_executed":False}
    if os.geteuid()==0 or pwd.getpwuid(os.geteuid()).pw_name!="zomorod2":return out
    try:
        if not ROOT.is_dir() or ROOT.resolve()!=ROOT:return out
        os.chdir(ROOT);sys.path.insert(0,str(ROOT));os.environ["DJANGO_SETTINGS_MODULE"]="config.settings"
        import django
        django.setup()
        from django.db import connection
        if connection.vendor!="mysql":return out
        with connection.cursor() as c:
            c.execute("START TRANSACTION READ ONLY")
            try:
                c.execute("SELECT TABLE_NAME,COALESCE(DATA_LENGTH,0)+COALESCE(INDEX_LENGTH,0) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE'")
                rows=c.fetchmany(2001)
                if not rows or len(rows)>2000:return out
                c.execute("SELECT DISTINCT TABLE_NAME,REFERENCED_TABLE_NAME,REFERENCED_TABLE_SCHEMA=DATABASE() FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL")
                edges=c.fetchmany(10001)
                if len(edges)>10000:return out
                out["partition"]=plan(rows,edges)
                out["metadata_complete"]=True
            finally:c.execute("ROLLBACK")
    except Exception as exc:out["error_type"]=type(exc).__name__
    return out
if __name__=="__main__":
    print("MPW_DB_PARTITION_READONLY="+json.dumps(inspect(),sort_keys=True))
