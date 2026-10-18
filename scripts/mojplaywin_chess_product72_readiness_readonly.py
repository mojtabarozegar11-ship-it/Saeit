#!/usr/bin/env python3
"""Read-only readiness of previously approved MojPlayWin chess ebook product #72.

No product descriptions, customer records, secrets, filenames, or pdf content
are emitted. Uses only exact product PK 72 and private ebook directory.
"""
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit, unquote

HOME=Path("/home/zomorod2")
BOOK=HOME/"MojPlayWin_Private_Assets"/"chess-improvement-2026"
SHARED=HOME/"Saeit-staging"
WEB=HOME/"mojplaywin.com"
PRODUCT_ID=72

def observe():
    result={
        "classification":"MOJPLAYWIN_CHESS_PRODUCT72_LIVE_READONLY",
        "product_id":PRODUCT_ID, "approved_price_usd":"7.50",
        "private_book_folder_exists":BOOK.is_dir() and not BOOK.is_symlink(),
        "private_book_folder_outside_public_docroot":not BOOK.is_relative_to(WEB),
        "valid_pdf_count":0, "unambiguous_single_private_pdf":False,
        "live_db_connected":False,"product_exists":False,
        "product_active":None,"live_price_usd_matches_approved":False,
        "product_currency_usd":False,
        "production_changes":False,"ready_to_sell_today":False,
    }
    if BOOK.is_dir() and not BOOK.is_symlink():
        count=0
        for p in BOOK.iterdir():
            if not p.is_symlink() and p.is_file() and p.suffix.lower()==".pdf" and p.stat().st_size>1000:
                try:
                    with p.open("rb") as handle:
                        if handle.read(5)==b"%PDF-":
                            count+=1
                except OSError:
                    pass
        result["valid_pdf_count"]=count
        result["unambiguous_single_private_pdf"]=count==1
    urls=[]
    for path in (SHARED/".env",SHARED/".env.production",SHARED/".env.local",WEB/".env"):
        if path.is_file() and not path.is_symlink() and path.stat().st_size<=65536:
            for line in path.read_text(encoding="utf-8",errors="replace").splitlines():
                m=re.match(r'^\s*(?:export\s+)?DATABASE_URL\s*=\s*(.*?)\s*$',line)
                if m: urls.append(urlsplit(m.group(1).strip().strip(chr(34)+chr(39))))
    if len(urls)!=1:
        result["db_connection_source_unique"]=False
        return result
    u=urls[0]
    if u.scheme not in ("mysql","mariadb","mysql2") or not u.username or not u.password or not u.path:
        return result
    env=dict(os.environ,MYSQL_PWD=unquote(u.password))
    cmd=["timeout","22s","mariadb","--no-defaults","--batch","--skip-column-names",
         "--host="+(u.hostname or "localhost"),"--user="+unquote(u.username),
         "--database="+unquote(u.path.lstrip("/")),"--connect-timeout=6"]
    if u.port: cmd.append("--port="+str(u.port))
    q=subprocess.run(cmd+["--execute=SELECT active,price,currency FROM core_product WHERE id=72 LIMIT 1"],
                     env=env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=25)
    if q.returncode==0:
        result["live_db_connected"]=True
        rows=q.stdout.decode("ascii","replace").strip().splitlines()
        if len(rows)==1:
            cols=rows[0].split("\t")
            if len(cols)==3:
                result["product_exists"]=True
                result["product_active"]=cols[0]=="1"
                try: result["live_price_usd_matches_approved"]=float(cols[1])==7.5
                except ValueError: pass
                result["product_currency_usd"]=cols[2]=="USD"
    result["ready_to_sell_today"]=all((
        result["unambiguous_single_private_pdf"],
        result["product_active"],result["live_price_usd_matches_approved"],
        result["product_currency_usd"]
    ))
    return result

if __name__=="__main__":
    print(json.dumps(observe(),sort_keys=True))
