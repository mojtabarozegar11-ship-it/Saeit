"""Compare selected MariaDB identity within owner host; emit only booleans/counts.
No business rows, migrations, SQL dump, or database identifiers in output.
CLI identity is not proof of effective Passenger worker identity.
"""
import contextlib
import io
import json
import os
import pwd
import subprocess
import sys
from pathlib import Path
ROOTS={"staging":Path("/home/zomorod2/Saeit-staging"),
       "integrated":Path("/home/zomorod2/Saeit-mojplaywin-integrated-20261119")}
EXPECTED=tuple(str(i).zfill(4) for i in range(1,18))
NEW_TABLES=tuple("prop_firm_"+n for n in ("propsimulationaccount","propsimulationinvoiceowner","propsimulationidentity","propsimulationloginchallenge","propsimulationevent"))

def compare(a,b):
    out={"both_cli_connections_verified":False,"selected_database_identity_equal":False,
         "same_connection_principal":False,"migration_history_equal":False}
    if not a.get("verified") or not b.get("verified"):return out
    return {"both_cli_connections_verified":True,
            "selected_database_identity_equal":a["identity"]==b["identity"],
            "same_connection_principal":a["principal"]==b["principal"],
            "migration_history_equal":a["history"]==b["history"],
            "table_presence_equal":a["present"]==b["present"]}

def child(label):
    root=ROOTS[label]
    if not root.is_dir() or root.resolve()!=root:return {"verified":False,"reason":"root_unavailable"}
    os.chdir(root);sys.path.insert(0,str(root));os.environ["DJANGO_SETTINGS_MODULE"]="config.settings"
    # Suppress application initialization output; do not invoke WSGI,
    # management commands, or any request handler.
    import django
    django.setup()
    from django.db import connection
    if connection.vendor!="mysql":return {"verified":False,"reason":"backend_not_mysql"}
    import config.settings as source
    if not Path(source.__file__).resolve().is_relative_to(root):
        return {"verified":False,"reason":"settings_source_outside_root"}
    with connection.cursor() as c:
        c.execute("START TRANSACTION READ ONLY")
        try:
            c.execute("SELECT DATABASE(), @@hostname, @@port, CURRENT_USER()")
            row=c.fetchone()
            if not row or not all(x is not None for x in row) or str(row[0])!=str(connection.settings_dict["NAME"]):
                return {"verified":False,"reason":"selected_database_unverified"}
            c.execute("SELECT name FROM django_migrations WHERE app=%s ORDER BY name",["prop_firm"])
            rows=c.fetchmany(101)
            if len(rows)>100:return {"verified":False,"reason":"migration_history_bound"}
            marks=",".join(["%s"]*len(NEW_TABLES))
            c.execute("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE' AND TABLE_NAME IN ("+marks+")",list(NEW_TABLES))
            present=sorted(x[0] for x in c.fetchall())
            return {"verified":True,"identity":[str(x) for x in row[:3]],"principal":str(row[3]),
                    "history":[x[0] for x in rows],"present":present}
        finally:
            c.execute("ROLLBACK")

def safe_summary(a):
    if not a.get("verified"):return {"verified":False,"reason":a.get("reason","child_failed")}
    return {"verified":True,"recorded_prop_migrations":len(a["history"]),
            "known_prefixes":[x[:4] for x in a["history"] if x[:4] in EXPECTED],
            "simulation_tables_present":len(a["present"])}

def audit(source):
    out={"read_only":True,"business_rows_read":False,"migration_executed":False,"identity_values_emitted":False,
         "release_authorized":False,"effective_worker_proven":False,"roots":{}}
    if os.geteuid()==0 or pwd.getpwuid(os.geteuid()).pw_name!="zomorod2":return out
    observations={}
    for label in ROOTS:
        try:
            proc=subprocess.run([sys.executable,"-B","-c",source,label],capture_output=True,timeout=25)
            if proc.returncode or len(proc.stdout)>16000:raise ValueError()
            data=json.loads(proc.stdout)
            if not isinstance(data,dict):raise ValueError()
        except (OSError,ValueError,subprocess.SubprocessError):
            data={"verified":False,"reason":"child_failed"}
        observations[label]=data
        out["roots"][label]=safe_summary(data)
    out["comparison"]=compare(observations["staging"],observations["integrated"])
    return out

# Child source is the same reviewed module and only its constrained entrypoint.
CHILD_SOURCE = "\"\"\"Compare selected MariaDB identity within owner host; emit only booleans/counts.\nNo business rows, migrations, SQL dump, or database identifiers in output.\nCLI identity is not proof of effective Passenger worker identity.\n\"\"\"\nimport contextlib\nimport io\nimport json\nimport os\nimport pwd\nimport subprocess\nimport sys\nfrom pathlib import Path\nROOTS={\"staging\":Path(\"/home/zomorod2/Saeit-staging\"),\n       \"integrated\":Path(\"/home/zomorod2/Saeit-mojplaywin-integrated-20261119\")}\nEXPECTED=tuple(str(i).zfill(4) for i in range(1,18))\nNEW_TABLES=tuple(\"prop_firm_\"+n for n in (\"propsimulationaccount\",\"propsimulationinvoiceowner\",\"propsimulationidentity\",\"propsimulationloginchallenge\",\"propsimulationevent\"))\n\ndef compare(a,b):\n    out={\"both_cli_connections_verified\":False,\"selected_database_identity_equal\":False,\n         \"same_connection_principal\":False,\"migration_history_equal\":False}\n    if not a.get(\"verified\") or not b.get(\"verified\"):return out\n    return {\"both_cli_connections_verified\":True,\n            \"selected_database_identity_equal\":a[\"identity\"]==b[\"identity\"],\n            \"same_connection_principal\":a[\"principal\"]==b[\"principal\"],\n            \"migration_history_equal\":a[\"history\"]==b[\"history\"],\n            \"table_presence_equal\":a[\"present\"]==b[\"present\"]}\n\ndef child(label):\n    root=ROOTS[label]\n    if not root.is_dir() or root.resolve()!=root:return {\"verified\":False,\"reason\":\"root_unavailable\"}\n    os.chdir(root);sys.path.insert(0,str(root));os.environ[\"DJANGO_SETTINGS_MODULE\"]=\"config.settings\"\n    # Suppress application initialization output; do not invoke WSGI,\n    # management commands, or any request handler.\n    import django\n    django.setup()\n    from django.db import connection\n    if connection.vendor!=\"mysql\":return {\"verified\":False,\"reason\":\"backend_not_mysql\"}\n    import config.settings as source\n    if not Path(source.__file__).resolve().is_relative_to(root):\n        return {\"verified\":False,\"reason\":\"settings_source_outside_root\"}\n    with connection.cursor() as c:\n        c.execute(\"START TRANSACTION READ ONLY\")\n        try:\n            c.execute(\"SELECT DATABASE(), @@hostname, @@port, CURRENT_USER()\")\n            row=c.fetchone()\n            if not row or not all(x is not None for x in row) or str(row[0])!=str(connection.settings_dict[\"NAME\"]):\n                return {\"verified\":False,\"reason\":\"selected_database_unverified\"}\n            c.execute(\"SELECT name FROM django_migrations WHERE app=%s ORDER BY name\",[\"prop_firm\"])\n            rows=c.fetchmany(101)\n            if len(rows)>100:return {\"verified\":False,\"reason\":\"migration_history_bound\"}\n            marks=\",\".join([\"%s\"]*len(NEW_TABLES))\n            c.execute(\"SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE' AND TABLE_NAME IN (\"+marks+\")\",list(NEW_TABLES))\n            present=sorted(x[0] for x in c.fetchall())\n            return {\"verified\":True,\"identity\":[str(x) for x in row[:3]],\"principal\":str(row[3]),\n                    \"history\":[x[0] for x in rows],\"present\":present}\n        finally:\n            c.execute(\"ROLLBACK\")\n\ndef safe_summary(a):\n    if not a.get(\"verified\"):return {\"verified\":False,\"reason\":a.get(\"reason\",\"child_failed\")}\n    return {\"verified\":True,\"recorded_prop_migrations\":len(a[\"history\"]),\n            \"known_prefixes\":[x[:4] for x in a[\"history\"] if x[:4] in EXPECTED],\n            \"simulation_tables_present\":len(a[\"present\"])}\n\ndef audit(source):\n    out={\"read_only\":True,\"business_rows_read\":False,\"migration_executed\":False,\"identity_values_emitted\":False,\n         \"release_authorized\":False,\"effective_worker_proven\":False,\"roots\":{}}\n    if os.geteuid()==0 or pwd.getpwuid(os.geteuid()).pw_name!=\"zomorod2\":return out\n    observations={}\n    for label in ROOTS:\n        try:\n            proc=subprocess.run([sys.executable,\"-B\",\"-c\",source,label],capture_output=True,timeout=25)\n            if proc.returncode or len(proc.stdout)>16000:raise ValueError()\n            data=json.loads(proc.stdout)\n            if not isinstance(data,dict):raise ValueError()\n        except (OSError,ValueError,subprocess.SubprocessError):\n            data={\"verified\":False,\"reason\":\"child_failed\"}\n        observations[label]=data\n        out[\"roots\"][label]=safe_summary(data)\n    out[\"comparison\"]=compare(observations[\"staging\"],observations[\"integrated\"])\n    return out\n\nif __name__==\"__main__\":\n    try:\n        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):\n            result=child(sys.argv[1])\n    except Exception:\n        result={\"verified\":False,\"reason\":\"metadata_query_failed\"}\n    print(json.dumps(result))\n"
if __name__=="__main__":
    print("MOJPROP_DB_IDENTITY_PAIR_READONLY="+json.dumps(audit(CHILD_SOURCE),sort_keys=True))
