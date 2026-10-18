#!/usr/bin/env python3
"""Bounded read-only metadata inspection for MojPlayWin existing purchasable products.

Print no product titles, owners, rows, wallet keys, DB credentials or prices.
Reports solely counts of existing tables and active/priced offers.
"""
import json, os, re, subprocess
from pathlib import Path
from urllib.parse import urlsplit, unquote

app=Path("/home/zomorod2/Saeit-staging")
doc=Path("/home/zomorod2/mojplaywin.com")
urls=[]
for f in [app/".env",app/".env.production",app/".env.local",doc/".env"]:
    if f.is_file() and not f.is_symlink() and f.stat().st_size<=65536:
        for line in f.read_text(encoding="utf-8",errors="replace").splitlines():
            m=re.match(r'^\s*(?:export\s+)?DATABASE_URL\s*=\s*(.*?)\s*$',line)
            if m: urls.append(urlsplit(m.group(1).strip().strip('"'')))
result={"classification":"MOJPLAYWIN_CRYPTO_PRODUCT_READINESS_READONLY",
        "connection_valid":False,"model_product_table":False,"crypto_offer_table":False,
        "active_priced_products":None,"active_crypto_offers":None,
        "changed_production_data":False,"release_authorized":False}
if len(urls)==1:
    u=urls[0]
    if u.scheme in ("mysql","mariadb","mysql2") and u.username and u.password and u.path:
        env=dict(os.environ,MYSQL_PWD=unquote(u.password))
        cmd=["timeout","20s","mariadb","--no-defaults","--batch","--skip-column-names",
             "--host="+(u.hostname or "localhost"),"--user="+unquote(u.username),
             "--database="+unquote(u.path.lstrip("/")),"--connect-timeout=6"]
        if u.port:cmd.append("--port="+str(u.port))
        # First prove table existence without attempting data reads.
        sql=("SELECT COUNT(*) FROM information_schema.TABLES "
             "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('core_product','core_mojcryptooffer')")
        q=subprocess.run(cmd+["--execute="+sql],env=env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=24)
        if q.returncode==0:
            result["connection_valid"]=True
            names=subprocess.run(cmd+["--execute=SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('core_product','core_mojcryptooffer')"],
                                 env=env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=24)
            if names.returncode==0:
                setnames=set(names.stdout.decode("ascii","replace").splitlines())
                result["model_product_table"]="core_product" in setnames
                result["crypto_offer_table"]="core_mojcryptooffer" in setnames
                for field,table,where in [
                    ("active_priced_products","core_product","active=1 AND price>0"),
                    ("active_crypto_offers","core_mojcryptooffer","active=1")]:
                    if table in setnames:
                        q=subprocess.run(cmd+["--execute=SELECT COUNT(*) FROM "+table+" WHERE "+where],
                                         env=env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=24)
                        if q.returncode==0:
                            try:result[field]=int(q.stdout.decode().strip())
                            except (ValueError,UnicodeError):pass
print(json.dumps(result,sort_keys=True))
