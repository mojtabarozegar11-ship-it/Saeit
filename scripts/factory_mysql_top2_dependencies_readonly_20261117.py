#!/usr/bin/env python3
"""Top 2 large MySQL tables: sanitized metadata-only read, no writes or user rows."""
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

def investigate(db,auth):
    tables=run("SELECT TABLE_NAME,COALESCE(ENGINE,''),COALESCE(ROW_FORMAT,''),"
       "COALESCE(DATA_LENGTH,0),COALESCE(INDEX_LENGTH,0),COALESCE(DATA_FREE,0),"
       "COALESCE(TABLE_ROWS,0) FROM information_schema.TABLES WHERE TABLE_SCHEMA="+quote(db)+
       " AND TABLE_TYPE='BASE TABLE' ORDER BY COALESCE(DATA_LENGTH,0)+COALESCE(INDEX_LENGTH,0)"
       " DESC LIMIT 3",auth)
    if len(tables)!=3 or any(len(t)!=7 or not ID.fullmatch(t[0]) for t in tables):
        raise RuntimeError("TOP_TABLES_SCHEMA_UNAVAILABLE")
    selected=tables[:2]
    ids=",".join(quote(t[0]) for t in selected)
    col=run("SELECT TABLE_NAME,COLUMN_NAME,DATA_TYPE,COALESCE(COLUMN_KEY,''),"
       "COALESCE(IS_NULLABLE,''),COALESCE(CHARACTER_MAXIMUM_LENGTH,0)"
       " FROM information_schema.COLUMNS WHERE TABLE_SCHEMA="+quote(db)+
       " AND TABLE_NAME IN ("+ids+") ORDER BY TABLE_NAME,ORDINAL_POSITION LIMIT 1000",auth)
    idx=run("SELECT TABLE_NAME,INDEX_NAME,COALESCE(NON_UNIQUE,1)"
       " FROM information_schema.STATISTICS WHERE TABLE_SCHEMA="+quote(db)+
       " AND TABLE_NAME IN ("+ids+") LIMIT 2000",auth)
    fk=run("SELECT TABLE_SCHEMA,TABLE_NAME,REFERENCED_TABLE_SCHEMA,REFERENCED_TABLE_NAME"
       " FROM information_schema.KEY_COLUMN_USAGE WHERE REFERENCED_TABLE_NAME IS NOT NULL"
       " AND ((TABLE_SCHEMA="+quote(db)+" AND TABLE_NAME IN ("+ids+"))"
       " OR (REFERENCED_TABLE_SCHEMA="+quote(db)+" AND REFERENCED_TABLE_NAME IN ("+ids+")))"
       " LIMIT 2000",auth)
    trg=run("SELECT EVENT_OBJECT_TABLE FROM information_schema.TRIGGERS"
       " WHERE TRIGGER_SCHEMA="+quote(db)+" AND EVENT_OBJECT_TABLE IN ("+ids+") LIMIT 2000",auth)
    if len(col)>=1000 or len(idx)>=2000 or len(fk)>=2000 or len(trg)>=2000:
        raise RuntimeError("METADATA_TRUNCATION")
    out=[]
    for rank,t in enumerate(selected,1):
        name,engine,rowfmt,d,ix,free,rows=t
        try:
            d,ix,free,rows=map(int,(d,ix,free,rows))
        except ValueError:raise RuntimeError("TABLE_METRICS_INVALID")
        if min(d,ix,free,rows)<0:raise RuntimeError("TABLE_METRICS_NEGATIVE")
        cc=[x for x in col if len(x)==6 and x[0]==name]
        ii=[x for x in idx if len(x)==3 and x[0]==name]
        ff=[x for x in fk if len(x)==4]
        if not cc:raise RuntimeError("NO_COLUMN_METADATA")
        kinds={};hints={};types={}
        for x in cc:
            label=family(x[2]);kinds[label]=kinds.get(label,0)+1
            v=hint(x[1]);hints[v]=hints.get(v,0)+1
            key=x[2].lower();types[key]=types.get(key,0)+1
        out.append({
          "rank":rank,"engine":engine if engine in ("InnoDB","MyISAM","Aria") else "other",
          "row_format":rowfmt if rowfmt in ("Dynamic","Compact","Compressed","Redundant","Fixed","Page") else "other",
          "data_bytes_estimate":d,"index_bytes_estimate":ix,"free_bytes_estimate":free,
          "rows_estimate":rows,"estimated_bytes_per_row":round((d+ix)/max(rows,1),1),
          "column_count":len(cc),"nullable_column_count":sum(x[4]=="YES" for x in cc),
          "primary_column_count":sum(x[3]=="PRI" for x in cc),
          "column_families":kinds,"name_based_hints_not_proof":hints,
          "longblob_columns":types.get("longblob",0),"longtext_columns":types.get("longtext",0),
          "json_columns":types.get("json",0),
          "unique_index_count":len({x[1] for x in ii if x[2]=="0"}),
          "nonunique_index_count":len({x[1] for x in ii if x[2]!="0"}),
          "outbound_fk_column_links":sum(x[0]==db and x[1]==name for x in ff),
          "inbound_fk_column_links_from_other_tables":sum(x[2]==db and x[3]==name and (x[0]!=db or x[1]!=name) for x in ff),
          "visible_trigger_count":sum(len(x)==1 and x[0]==name for x in trg),
          "no_names_or_record_content_disclosed":True,
          "no_fk_or_triggers_not_proof_of_safety":True,
        })
    return out

def main():
    if pwd.getpwuid(os.geteuid()).pw_name!=USER:raise RuntimeError("WRONG_CPANEL_USER")
    start=time.monotonic()
    size,db=get_db()
    top=investigate(db,local_auth(db))
    print("MOJ_FACTORY_MYSQL_TOP2_DEPENDENCIES="+json.dumps({
       "schema":"moj.factory.mysql.top2-dependencies.readonly.v1",
       "uapi_largest_database_bytes":size,
       "top2_total_bytes_estimate":sum(x["data_bytes_estimate"]+x["index_bytes_estimate"] for x in top),
       "top2":top,"metadata_queries_executed":5,
       "customer_rows_queried":0,"sql_changes":0,"files_created":0,"files_deleted":0,
       "safe_to_delete":False,"recovery_proven":False,
       "statistics_are_estimates":True,"elapsed_seconds":round(time.monotonic()-start,2)
    },sort_keys=True),flush=True)

if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("MOJ_FACTORY_MYSQL_TOP2_DEPENDENCIES_FAILED="+type(exc).__name__+
            ":"+str(exc)[:70],file=sys.stderr,flush=True)
        sys.exit(1)
