#!/usr/bin/env python3
"""Isolated end-to-end PHP HTTP regression for Zomorod auction management.

Creates disposable private SQLite/user sessions. No production DB, web site,
bid, guarantee, message or external payment is touched.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SOURCE=Path(__file__).resolve().parents[1]/"content/zomorod-business/auctions.php"


def call(url, *, fields=None, cookie=None):
    headers={}
    if cookie:headers["Cookie"]=f"ZM_BUSINESS=fixture-{cookie}-0001"
    data=urlencode(fields).encode() if fields is not None else None
    if data is not None:headers["Content-Type"]="application/x-www-form-urlencoded"
    request=Request(url,data=data,headers=headers,method="POST" if data is not None else "GET")
    try:
        with urlopen(request,timeout=5) as r:return r.status,r.read()
    except HTTPError as e:return e.code,e.read()


def must(condition,message):
    if not condition:raise AssertionError(message)


def csrf(base,actor):
    code,body=call(base,cookie=actor)
    must(code==200,f"{actor}: form not available: {code}")
    token=re.search(rb'name="csrf" value="([a-f0-9]{64})"',body)
    must(token is not None,"CSRF missing")
    return token.group(1).decode()


def post(base,actor,token,action,extra):
    fields={"csrf":token,"action":action}
    fields.update(extra)
    return call(base,cookie=actor,fields=fields)[0]


def main():
    must(SOURCE.is_file(),"PHP source missing")
    with tempfile.TemporaryDirectory(prefix="zm-auction-qa-") as td:
        root=Path(td)
        private=root/".private/zomorod-business"
        private.mkdir(parents=True,mode=0o700)
        docroot=root/"public_html"
        endpoint=docroot/"business/auctions"
        endpoint.mkdir(parents=True)
        shutil.copyfile(SOURCE,endpoint/"index.php")
        sessions=root/"sessions"
        sessions.mkdir()
        master=private/"management.sqlite3"
        with sqlite3.connect(master) as db:
            db.executescript("""
                CREATE TABLE users(id INTEGER PRIMARY KEY, role TEXT NOT NULL, active INTEGER NOT NULL);
                CREATE TABLE projects(id INTEGER PRIMARY KEY,title TEXT NOT NULL);
                INSERT INTO users VALUES(1,'admin',1);
                INSERT INTO users VALUES(2,'accountant',1);
                INSERT INTO users VALUES(3,'manager',1);
                INSERT INTO users VALUES(4,'viewer',1);
                INSERT INTO projects VALUES(1,'برنامه سرمایه‌گذاری مصنوعی');
            """)
        for who,uid in (("admin",1),("accountant",2),("manager",3),("viewer",4)):
            sid=f"fixture-{who}-0001"
            program=(f'session_name("ZM_BUSINESS");session_id("{sid}");'
                     f'session_start();$_SESSION["uid"]={uid};session_write_close();')
            subprocess.run(["php","-d",f"session.save_path={sessions}","-r",program],
                           capture_output=True,check=True)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1",0))
            port=sock.getsockname()[1]
        base=f"http://127.0.0.1:{port}/business/auctions/"
        server=subprocess.Popen([
            "php","-d",f"session.save_path={sessions}","-S",
            f"127.0.0.1:{port}","-t",str(docroot)
        ],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(40):
                try:anonymous=call(base)[0];break
                except (URLError,TimeoutError):time.sleep(.1)
            else:raise AssertionError("PHP server failed to start")
            must(anonymous==403,"anonymous access allowed")
            must(call(base,cookie="viewer")[0]==200,"viewer should have read-only access")
            must(not (private/"auctions_v1.sqlite3").exists(),"read-only GET created a DB")
            manager_token=csrf(base,"manager")
            admin_token=csrf(base,"admin")
            deadline=time.strftime("%Y-%m-%dT%H:%M",time.gmtime(time.time()+86400))
            payload={
                "reference":"AUCTION-001","direction":"buy","title":"فرصت ملک مصنوعی",
                "organizer":"برگزارکننده ساختگی","asset_type":"ملک","location":"شهر آزمون",
                "notice_url":"https://example.org/notice","deadline_utc":deadline,
                "currency":"IRR","estimate":"100000","deposit":"3000","limit":"90000",
                "project_id":"1","notes":"فقط سناریوی آفلاین"
            }
            master_hash=hashlib.sha256(master.read_bytes()).hexdigest()
            must(post(base,"manager","invalid","create",payload)==403,"CSRF guard bypassed")
            must(not (private/"auctions_v1.sqlite3").exists(),"invalid CSRF created DB")
            must(post(base,"viewer","invalid","create",payload)==403,"viewer created auction")
            bad=dict(payload);bad["notice_url"]="http://example.org/notice"
            must(post(base,"manager",manager_token,"create",bad)==422,"insecure notice URL accepted")
            past=dict(payload);past["deadline_utc"]="2020-01-01T12:00"
            must(post(base,"manager",manager_token,"create",past)==422,"past deadline accepted")
            must(post(base,"manager",manager_token,"create",payload)==200,"valid creation failed")
            local=private/"auctions_v1.sqlite3"
            must(local.is_file(),"private auction DB missing")
            must(local.stat().st_mode & 0o777 == 0o600,"private DB permissions too broad")
            with sqlite3.connect(local) as db:
                rows=db.execute("SELECT id,reference,created_by FROM auctions").fetchall()
            must(len(rows)==1 and rows[0][1]=="AUCTION-001" and rows[0][2]==3,"auction record incorrect")
            must(post(base,"manager",manager_token,"create",payload)==409,"duplicate reference accepted")
            must(hashlib.sha256(master.read_bytes()).hexdigest()==master_hash,
                 "master business DB was changed")
            auction_id=str(rows[0][0])
            accountant_token=csrf(base+"?id="+auction_id,"accountant")
            scope={"auction_id":auction_id,"evidence":"مدرک داخلی شماره QA-2026-001"}
            must(post(base,"admin",admin_token,"executive",scope)==409,"executive bypassed reviews")
            must(post(base,"manager",manager_token,"review",dict(scope,kind="technical",decision="approved"))==200,
                 "technical approval failed")
            must(post(base,"admin",admin_token,"review",dict(scope,kind="legal",decision="approved"))==200,
                 "internal legal review failed")
            must(post(base,"admin",admin_token,"review",dict(scope,kind="financial",decision="approved"))==200,
                 "initial financial review failed")
            must(post(base,"admin",admin_token,"executive",scope)==409,
                 "same finance reviewer/executive approved")
            must(post(base,"accountant",accountant_token,"review",dict(scope,kind="financial",decision="approved"))==200,
                 "independent accountant review failed")
            must(post(base,"admin",admin_token,"executive",scope)==200,"independent executive approval failed")
            must(post(base,"manager",manager_token,"review",dict(scope,kind="technical",decision="rejected"))==409,
                 "review was changed after executive approval")
            must(post(base,"admin",admin_token,"submission",dict(scope,evidence=""))==422,
                 "submission without evidence accepted")
            must(post(base,"admin",admin_token,"submission",scope)==200,"submission receipt not recorded")
            must(post(base,"manager",manager_token,"outcome",dict(scope,decision="won"))==200,
                 "manual auction outcome not recorded")
            must(post(base,"admin",admin_token,"cancel",scope)==409,"closed auction modified")
            with sqlite3.connect(local) as db:
                n=db.execute("SELECT COUNT(*) FROM auction_events").fetchone()[0]
                status=db.execute("SELECT kind,decision FROM auction_events ORDER BY id DESC LIMIT 1").fetchone()
            must(n==7 and status==("outcome","won"),"audit event timeline incorrect")
            must(hashlib.sha256(master.read_bytes()).hexdigest()==master_hash,
                 "main accounting DB modified during decision workflow")
            print("ZM auctions: 22 offline HTTP/security/workflow assertions passed; no external bid or payment.")
        finally:
            server.terminate()
            try:server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)


if __name__=="__main__":
    main()
