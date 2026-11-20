"""Read-only migration-specific protection scope, not a backup or release authorization."""
import json, os, pwd, sys
from pathlib import Path
ROOT=Path("/home/zomorod2/Saeit-staging")
LEGACY="prop_firm_propaccount"
FINANCIAL=frozenset("prop_firm_"+n for n in ("propplan1invoice","propplan1receipt","tronsettlementledger","proprewardreserveallocation","proprewardcommitment"))
NEW=frozenset("prop_firm_"+n for n in ("propsimulationaccount","propsimulationinvoiceowner","propsimulationidentity","propsimulationloginchallenge","propsimulationevent"))

def classify(meta, edges, user_table):
    tables={n:(engine,int(size)) for n,engine,size in meta}
    roots=FINANCIAL|{LEGACY,user_table,"django_migrations"}
    found=roots & tables.keys()
    scope=set(found)
    for _ in range(len(tables)+1):
        added={parent for child,parent,same in edges if same and child in scope and parent in tables}
        if added<=scope:break
        scope.update(added)
    external={(c,p) for c,p,same in edges if c in scope and (not same or p not in tables)}
    incoming={(c,p) for c,p,same in edges if same and p in scope and c not in scope}
    return {"required_existing_roots":len(roots),"missing_existing_roots":len(roots-found),
            "legacy_account_present":LEGACY in tables,"shared_auth_present":user_table in tables,
            "migration_history_present":"django_migrations" in tables,
            "new_target_tables_already_present":len(NEW & tables.keys()),
            "closure_tables":len(scope),"estimated_closure_bytes":sum(tables[n][1] for n in scope),
            "estimated_legacy_account_bytes":tables.get(LEGACY,("",0))[1],
            "estimated_shared_auth_bytes":tables.get(user_table,("",0))[1],
            "all_scope_innodb":bool(scope) and all(tables[n][0]=="InnoDB" for n in scope),
            "external_or_missing_parent_edges":len(external),"incoming_dependencies":len(incoming),
            "full_database_restore_proven":False,"scope_backup_approved":False}

def audit():
    out={"read_only":True,"business_rows_read":False,"migration_executed":False,"release_authorized":False,"metadata_complete":False}
    if os.geteuid()==0 or pwd.getpwuid(os.geteuid()).pw_name!="zomorod2" or ROOT.resolve()!=ROOT or not ROOT.is_dir():return out
    try:
        os.chdir(ROOT);sys.path.insert(0,str(ROOT));os.environ["DJANGO_SETTINGS_MODULE"]="config.settings"
        import django
        django.setup()
        from django.db import connection
        from django.contrib.auth import get_user_model
        if connection.vendor!="mysql":return out
        with connection.cursor() as c:
            c.execute("SELECT TABLE_NAME,ENGINE,COALESCE(DATA_LENGTH,0)+COALESCE(INDEX_LENGTH,0) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE'")
            meta=c.fetchmany(5001)
            c.execute("SELECT TABLE_NAME,REFERENCED_TABLE_NAME,REFERENCED_TABLE_SCHEMA=DATABASE() FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL")
            edges=c.fetchmany(20001)
            if len(meta)>5000 or len(edges)>20000:return out
            c.execute("SELECT DATA_TYPE,NUMERIC_PRECISION,NUMERIC_SCALE,IS_NULLABLE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s",[LEGACY,"starting_capital_usd"])
            cols=c.fetchall()
        out["scope"]=classify(meta,edges,get_user_model()._meta.db_table)
        out["legacy_column_exact_type"]=len(cols)==1 and tuple(cols[0])==("decimal",18,2,"NO")
        out["metadata_complete"]=True
    except Exception as e:
        out["error_type"]=type(e).__name__
    return out
if __name__=="__main__":
    print("MOJPROP_MIGRATION_PROTECTION_READONLY="+json.dumps(audit(),sort_keys=True))
