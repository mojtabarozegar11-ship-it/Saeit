"""Read-only preflight of the independently provisioned MOJ PROP schema.
Use the already-authorized owner CLI credential, never print identifiers
or row contents. Existence checks are not a data export or restore proof.
"""
import copy
import json
import os
import pwd
import re
import sys
from pathlib import Path
ROOT=Path("/home/zomorod2/Saeit-mojplaywin-integrated-20261119")
TARGET="zomorod2_mojprop"
BASELINE=("0001_initial","0002_provisional_profit_ledger","0003_social_evidence",
"0004_four_week_challenge","0005_trade_origin_and_position_id","0006_ten_plan_enrollment",
"0007_equity_broker_source","0008_prospect_contact_intake","0009_plan1_invoice_gateway","0010_reward_reserve_ledger")
LEGACY={"prop_firm_"+n for n in ("proptrader","propaccount","propexecution",
"propequityobservation","propdecisionlog","propprofitallocation","propprofitjournalline",
"propchallengeenrollment","propsocialevidence","propinterest","tronsettlementledger",
"propplan1invoice","propplan1receipt","proprewardreserveallocation","proprewardcommitment")}
NEW={"prop_firm_"+n for n in ("propsimulationaccount","propsimulationinvoiceowner",
"propsimulationidentity","propsimulationloginchallenge","propsimulationevent")}
AUTH={"auth_user","auth_group","auth_permission","auth_user_groups","auth_user_user_permissions","auth_group_permissions","django_content_type","django_migrations"}
ALLOWED=LEGACY|NEW|AUTH|{"django_session"}
def classify(tables,history):
    names=set(tables)
    return {"table_count":len(names),"legacy_prop_tables":len(names&LEGACY),
        "missing_legacy_prop_tables":len(LEGACY-names),"new_simulation_tables":len(names&NEW),
        "unknown_table_count":len(names-ALLOWED),"auth_tables_complete":AUTH<=names,
        "session_table_present":"django_session" in names,
        "exact_prop_0010_history":set(history)==set(BASELINE)}
def audit():
    out={"read_only":True,"row_contents_read":False,"row_presence_checked":False,
         "database_changed":False,"release_authorized":False,"target_verified":False,
         "dedicated_principal_verified":False,"restore_verified":False}
    if os.geteuid()==0 or pwd.getpwuid(os.geteuid()).pw_name!="zomorod2":return out
    db=None
    try:
        if not ROOT.is_dir() or ROOT.resolve()!=ROOT:return out
        os.chdir(ROOT);sys.path.insert(0,str(ROOT));os.environ["DJANGO_SETTINGS_MODULE"]="config.settings"
        import django
        django.setup()
        from django.db import connection
        if connection.vendor!="mysql":return out
        if connection.settings_dict.get("NAME")!= "zomorod2_sites_main":return out
        config=copy.deepcopy(connection.settings_dict)
        config["NAME"]=TARGET
        db=connection.__class__(config,alias="mojprop_readonly_probe")
        with db.cursor() as c:
            c.execute("START TRANSACTION READ ONLY")
            try:
                c.execute("SELECT DATABASE()")
                if c.fetchone()!=(TARGET,):return out
                out["target_verified"]=True
                c.execute("SELECT TABLE_NAME,ENGINE,COALESCE(DATA_LENGTH,0)+COALESCE(INDEX_LENGTH,0) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE'")
                rows=c.fetchmany(201)
                if len(rows)>200:return out
                names={r[0] for r in rows}
                if "django_migrations" not in names:return out
                c.execute("SELECT name FROM django_migrations WHERE app=%s",["prop_firm"])
                history=c.fetchmany(101)
                if len(history)>100:return out
                out.update(classify(names,[r[0] for r in history]))
                out["estimated_bytes"]=sum(int(r[2]) for r in rows)
                out["all_tables_innodb"]=all(r[1]=="InnoDB" for r in rows)
                c.execute("SELECT COUNT(*) FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL AND REFERENCED_TABLE_SCHEMA<>DATABASE()")
                out["cross_schema_fk_count"]=int(c.fetchone()[0])
                # Fixed identifiers only; return aggregate nonempty count, never any row.
                checks=sorted(names&(LEGACY|NEW|{"auth_user","django_session"}))
                nonempty=0
                for table in checks:
                    c.execute("SELECT EXISTS(SELECT 1 FROM `"+table+"` LIMIT 1)")
                    nonempty+=int(bool(c.fetchone()[0]))
                out.update(row_presence_checked=True,checked_business_auth_tables=len(checks),
                           nonempty_checked_tables=nonempty,metadata_complete=True)
            finally:c.execute("ROLLBACK")
    except Exception as exc:out["error_type"]=type(exc).__name__
    finally:
        if db is not None:db.close()
    return out
if __name__=="__main__":
    print("MOJPROP_DEDICATED_DB_READONLY="+json.dumps(audit(),sort_keys=True))
