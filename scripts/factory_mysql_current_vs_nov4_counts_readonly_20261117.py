#!/usr/bin/env python3
"""Only aggregate COUNT/MIN/MAX values from live MySQL two largest tables.
No column contents or customer records exported; strictly read-only.
Historical Nov4 manifests are compared but restorability not assumed.
"""
import json,os,pwd,re,shutil,stat,subprocess,sys,time,urllib.parse
from pathlib import Path
USER="zomorod2"
ROOT=Path("/home/zomorod2")
ID=re.compile(r"^[A-Za-z0-9_]{1,64}$")
MAX=300000

def get_db():
    p=subprocess.run(["uapi","--output=json","Mysql","list_databases"],
       stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=40)
    if p.returncode or len(p.stdout)>MAX:raise RuntimeError("UAPI_UNAVAILABLE")
    r=json.loads(p.stdout)["result"]
    if r.get("status")!=1 or not isinstance(r.get("data"),list):raise RuntimeError("UAPI_SCHEMA")
    a=[]
    for x in r["data"]:
        n=x.get("database");b=x.get("disk_usage")
        if isinstance(b,str) and b.isdigit():b=int(b)
        if not isinstance(n,str) or not ID.fullmatch(n) or type(b)!=int or b<0:
            raise RuntimeError("UAPI_DB_ROW_INVALID")
        a.append((b,n))
    a.sort(reverse=True)
    if not a or a[0][0]<10*1024**3:raise RuntimeError("EXPECTED_DB_NOT_FOUND")
    return a[0]

def local_auth(db):
    found=set()
    for rel in ("Saeit-staging/.env","Saeit-staging/.env.production",
                "Saeit-staging/.env.local","mojplaywin.com/.env",
                "Saeit/.env","Saeit/.env.production"):
        p=ROOT/rel
        try:
            st=p.lstat()
            if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.geteuid() or not 0<st.st_size<=65536:continue
            body=p.read_text(encoding="utf8",errors="replace")
        except OSError:continue
        for line in body.splitlines():
            m=re.match(r"^\s*(?:export\s+)?DATABASE_URL\s*=\s*(.*?)\s*$",line)
            if not m:continue
            try:
                url=urllib.parse.urlsplit(m.group(1).strip().strip('"').strip("'"))
                if url.scheme.lower() not in ("mysql","mariadb","mysql2"):continue
                if urllib.parse.unquote(url.path.lstrip("/"))!=db:continue
                host=(url.hostname or "localhost").lower()
                user=urllib.parse.unquote(url.username or "")
                secret=urllib.parse.unquote(url.password or "")
                if host not in ("localhost","127.0.0.1") or url.port not in (None,3306) or not user or not secret:continue
                found.add((host,user,secret))
            except (ValueError,TypeError):continue
    if len(found)!=1:raise RuntimeError("LOCAL_DB_DSN_NOT_UNAMBIGUOUS")
    return next(iter(found))

def run(sql,auth):
    exe=shutil.which("mariadb") or shutil.which("mysql")
    if not exe:raise RuntimeError("MYSQL_CLI_MISSING")
    host,user,secret=auth
    env=dict(os.environ,MYSQL_PWD=secret,MYSQL_HISTFILE=os.devnull,HISTFILE=os.devnull)
    p=subprocess.run([exe,"--no-defaults","--host="+host,"--user="+user,
        "--connect-timeout=8","--batch","--raw","--skip-column-names",
        "--skip-auto-rehash","--execute",sql],stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,env=env,timeout=55)
    if p.returncode or len(p.stdout)>MAX:raise RuntimeError("READ_ONLY_METADATA_UNAVAILABLE")
    lines=p.stdout.decode("utf8",errors="replace").splitlines()
    if any(len(line)>2048 for line in lines):raise RuntimeError("METADATA_LINE_TOO_LONG")
    return [line.split("\t") for line in lines]

def quote(s):
    if not ID.fullmatch(s):raise RuntimeError("UNSAFE_DB_IDENTIFIER")
    return "'"+s+"'"

def family(t):
    t=t.lower()
    if t in ("longblob","mediumblob","blob","tinyblob","binary","varbinary"):return "binary_blob"
    if t in ("longtext","mediumtext","text","tinytext","json"):return "text_json"
    if t in ("varchar","char","enum","set"):return "short_text"
    if t in ("datetime","timestamp","date","time","year"):return "datetime"
    if t in ("tinyint","smallint","mediumint","int","integer","bigint","decimal","float","double","bit"):return "numeric"
    return "other"

def hint(n):
    n=n.lower()
    for label,needles in (("payload",("payload","blob","file","attachment")),
        ("message",("message","email","body","content")),
        ("execution",("task","run","job","queue","result")),
        ("audit",("event","history","log","trace")),
        ("identity",("user","owner","account","customer","client"))):
        if any(x in n for x in needles):return label
    return "other"


EXPECTED = (
    ("core_agenttask",28172,1,28172),
    ("core_factoryevidence",28141,1,28141),
)

def current_aggregate(db,auth):
    top = run(
        "SELECT TABLE_NAME FROM information_schema.TABLES"
        " WHERE TABLE_SCHEMA="+quote(db)+" AND TABLE_TYPE='BASE TABLE'"
        " ORDER BY COALESCE(DATA_LENGTH,0)+COALESCE(INDEX_LENGTH,0)"
        " DESC LIMIT 2",auth)
    if len(top)!=2 or any(len(x)!=1 for x in top):
        raise RuntimeError("LIVE_TOP_TWO_SCHEMA_UNAVAILABLE")
    if set(x[0] for x in top)!=set(x[0] for x in EXPECTED):
        raise RuntimeError("HISTORICAL_TABLE_IDENTITY_NOT_MATCHING_LIVE_TOP2")
    compared=[]
    for rank,(table,historical_count,historical_min,historical_max) in enumerate(EXPECTED,1):
        if not ID.fullmatch(table):
            raise RuntimeError("TABLE_IDENTIFIER_INVALID")
        q=("SELECT COUNT(*),COALESCE(MIN(id),0),COALESCE(MAX(id),0)"
            " FROM "+db+"."+table)
        rows=run(q,auth)
        if len(rows)!=1 or len(rows[0])!=3:
            raise RuntimeError("LIVE_AGGREGATE_UNAVAILABLE")
        try:
            count,minimum,maximum=map(int,rows[0])
        except ValueError:
            raise RuntimeError("LIVE_AGGREGATE_SCHEMA")
        if min(count,minimum,maximum)<0:
            raise RuntimeError("LIVE_AGGREGATE_INVALID")
        compared.append({
            "group":"A" if rank==1 else "B",
            "historical_manifest_count_claimed":historical_count,
            "historical_manifest_min_id":historical_min,
            "historical_manifest_max_id":historical_max,
            "current_live_count":count,
            "current_min_id":minimum,
            "current_max_id":maximum,
            "count_delta_current_minus_historical":count-historical_count,
            "same_count_and_id_bounds":count==historical_count and
                  minimum==historical_min and maximum==historical_max,
            "only_numeric_aggregate_not_application_rows_exported":True,
        })
    return compared

def main():
    if pwd.getpwuid(os.geteuid()).pw_name!="zomorod2":
        raise RuntimeError("WRONG_CPANEL_ACCOUNT")
    start=time.monotonic()
    dbsize,db=get_db()
    auth=local_auth(db)
    compared=current_aggregate(db,auth)
    print("MOJ_FACTORY_MYSQL_CURRENT_VS_NOV4="+json.dumps({
       "schema":"moj.factory.mysql.current-vs-nov4-count.readonly.v1",
       "cPanel_largest_mysql_database_uapi_bytes":dbsize,
       "live_top_two_table_identity_matched":True,
       "comparison":compared,
       "historical_archive_is_current_proven":False,
       "historical_data_integrity_from_row_contents_proven":False,
       "queries_read_only":True,
       "data_modifications":0,"files_created":0,"files_deleted":0,
       "safe_to_delete":False,
       "elapsed_seconds":round(time.monotonic()-start,3),
    },sort_keys=True),flush=True)

if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("MOJ_FACTORY_MYSQL_CURRENT_VS_NOV4_FAILED="+type(exc).__name__+
            ":"+str(exc)[:65],file=sys.stderr,flush=True)
        sys.exit(1)
