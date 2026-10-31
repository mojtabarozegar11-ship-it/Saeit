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


def upload_document(base, actor, token, auction_id, category, filename, content):
    boundary="----zm-auction-fixture-7f83"
    parts=[]
    for key,value in (("csrf",token),("action","document"),
                      ("auction_id",auction_id),("category",category)):
        parts.append((f"--{boundary}\r\n"
                      f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
                      f"{value}\r\n").encode())
    parts.append((f"--{boundary}\r\n"
                  f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'
                  "Content-Type: application/octet-stream\r\n\r\n").encode())
    parts.extend((content,f"\r\n--{boundary}--\r\n".encode()))
    request=Request(base,data=b"".join(parts),method="POST",headers={
        "Cookie":f"ZM_BUSINESS=fixture-{actor}-0001",
        "Content-Type":f"multipart/form-data; boundary={boundary}",
    })
    try:
        with urlopen(request,timeout=5) as response:return response.status
    except HTTPError as error:return error.code


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
            economics={"auction_id":auction_id,"proceeds":"150000","basis":"90000",
                       "costs":"5000","reserve":"5000",
                       "rationale":"برآورد مصنوعی هزینه‌ها و جریان ورودی با فرضیات داخلی"}
            bad_economics=dict(economics,proceeds="not-a-number")
            must(post(base,"accountant",accountant_token,"scenario",bad_economics)==422,
                 "invalid economic forecast accepted")
            must(post(base,"accountant",accountant_token,"scenario",economics)==200,
                 "append-only economic scenario failed")
            must(post(base,"viewer","invalid","scenario",economics)==403,
                 "viewer wrote an economic scenario")
            with sqlite3.connect(local) as db:
                scenario=db.execute("SELECT proceeds_minor-basis_minor-costs_minor-reserve_minor FROM auction_scenarios").fetchone()
            must(scenario==(5000000,),"forecast arithmetic in private database incorrect")
            pdf=(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
                 b"trailer <<>>\n%%EOF\n")
            invalid=b"<html><body>not a pdf</body></html>"
            must(upload_document(base,"accountant",accountant_token,auction_id,"notice",
                                 "bad.html",invalid)==422,"unsafe HTML upload accepted")
            must(upload_document(base,"accountant",accountant_token,auction_id,"notice",
                                 "notice.pdf",pdf)==200,"private PDF upload failed")
            docdir=private/"auction-documents"
            with sqlite3.connect(local) as db:
                docs=db.execute("SELECT id,storage_key,sha256 FROM auction_documents").fetchall()
            must(len(docs)==1,"document audit row missing")
            must(docdir.stat().st_mode & 0o777 == 0o700,"private document directory permissions incorrect")
            stored=docdir/docs[0][1]
            must(stored.is_file() and stored.stat().st_mode & 0o777 == 0o600,
                 "private uploaded document permissions incorrect")
            must(stored.read_bytes()==pdf and docs[0][2]==hashlib.sha256(pdf).hexdigest(),
                 "uploaded document content or integrity signature incorrect")
            must(call(base+"?document="+str(docs[0][0]))[0]==403,
                 "anonymous document retrieval allowed")
            docstatus,document=call(base+"?document="+str(docs[0][0]),cookie="viewer")
            must(docstatus==200 and document==pdf,"authorized private document download failed")
            stored.write_bytes(b"tamper"+pdf)
            must(call(base+"?document="+str(docs[0][0]),cookie="viewer")[0]==503,
                 "modified private document served without integrity validation")
            stored.write_bytes(pdf)
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
            must(post(base,"admin",admin_token,"submission",scope)==409,
                 "submission accepted without archived external receipt")
            must(upload_document(base,"accountant",accountant_token,auction_id,"receipt",
                                 "participation-receipt.pdf",pdf)==200,
                 "receipt archive failed before manual participation record")
            must(post(base,"admin",admin_token,"submission",scope)==200,"submission receipt not recorded")
            must(post(base,"manager",manager_token,"outcome",dict(scope,decision="won"))==200,
                 "manual auction outcome not recorded")
            must(post(base,"admin",admin_token,"cancel",scope)==409,"closed auction modified")
            must(post(base,"accountant",accountant_token,"scenario",economics)==409,
                 "closed auction accepted new economic scenario")
            must(upload_document(base,"admin",admin_token,auction_id,"contract","contract.pdf",pdf)==200,
                 "closed auction cannot archive subsequent contract evidence")
            with sqlite3.connect(local) as db:
                must(db.execute("SELECT COUNT(*) FROM auction_documents").fetchone()[0]==3,
                     "post-outcome contract evidence not archived")
                contract_id=db.execute("SELECT id FROM auction_documents WHERE category='contract'").fetchone()[0]
            must(call(base+"?document="+str(contract_id),cookie="viewer")[0]==404,
                 "viewer retrieved restricted contract")
            must(call(base+"?document="+str(contract_id),cookie="accountant")[0]==404,
                 "accountant retrieved contract outside role")
            must(call(base+"?document="+str(contract_id),cookie="manager")[0]==200,
                 "manager cannot retrieve authorized contract")
            must(b"contract.pdf" not in call(base+"?id="+auction_id,cookie="viewer")[1],
                 "viewer can infer restricted contract metadata")
            must(upload_document(base,"accountant",accountant_token,auction_id,"contract","x.pdf",pdf)==403,
                 "accountant uploaded contract outside assigned role")
            with sqlite3.connect(local) as db:
                n=db.execute("SELECT COUNT(*) FROM auction_events").fetchone()[0]
                status=db.execute("SELECT kind,decision FROM auction_events ORDER BY id DESC LIMIT 1").fetchone()
            must(n==7 and status==("outcome","won"),"audit event timeline incorrect")
            must(hashlib.sha256(master.read_bytes()).hexdigest()==master_hash,
                 "main accounting DB modified during decision workflow")
            sell=dict(payload,reference="AUCTION-002",direction="sell",
                      title="مزایده فروش تجهیزات مصنوعی")
            must(post(base,"manager",manager_token,"create",sell)==200,
                 "sale-side auction registration failed")
            with sqlite3.connect(local) as db:
                second_id=str(db.execute("SELECT id FROM auctions WHERE reference='AUCTION-002'").fetchone()[0])
            scope2={"auction_id":second_id,"evidence":"صورتجلسه مصنوعی کمیته فروش شماره ۲"}
            must(post(base,"manager",manager_token,"review",dict(scope2,kind="technical",decision="approved"))==200,
                 "sale-side technical review failed")
            must(post(base,"admin",admin_token,"review",dict(scope2,kind="legal",decision="approved"))==200,
                 "sale-side legal review failed")
            must(post(base,"accountant",accountant_token,"review",dict(scope2,kind="financial",decision="approved"))==200,
                 "sale-side independent finance review failed")
            must(post(base,"admin",admin_token,"executive",scope2)==409,
                 "executive approval allowed without documentary and economic evidence")
            must(post(base,"accountant",accountant_token,"scenario",
                      dict(economics,auction_id=second_id))==200,
                 "sale-side forecast failed")
            must(post(base,"admin",admin_token,"executive",scope2)==409,
                 "executive approval allowed without official notice or valuation evidence")
            must(upload_document(base,"manager",manager_token,second_id,"notice",
                                 "sale-notice.pdf",pdf)==200,
                 "sale-side notice archive failed")
            must(post(base,"admin",admin_token,"executive",scope2)==200,
                 "evidence-backed sale-side approval failed")
            must(hashlib.sha256(master.read_bytes()).hexdigest()==master_hash,
                 "business accounting database changed by sell-side workflow")
            print("ZM auctions: offline HTTP/security/workflow, economic forecast and document-integrity assertions passed; no external bid or payment.")
        finally:
            server.terminate()
            try:server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)


if __name__=="__main__":
    main()
