#!/usr/bin/env python3
"""Disposable end-to-end PHP/HTTP tests for isolated IRR bank subledgers.

Never uses live bank credentials, account/card numbers or production data.
"""
from __future__ import annotations

import http.client
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import time
import unittest
from urllib.parse import urlencode


SOURCE = Path(__file__).resolve().parents[1] / "content/zomorod-business"
TOKEN = re.compile(r'name="csrf" value="([0-9a-f]{64})"')


@unittest.skipUnless(shutil.which("php"), "PHP CLI is required for PHP/HTTP acceptance")
class BankLedgerHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(prefix="zm-banking-isolated-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.web = cls.root / "content/zomorod-business"
        cls.web.mkdir(parents=True)
        for filename in ("app.php", "banking.php"):
            shutil.copy2(SOURCE / filename, cls.web / filename)
        private = cls.root / ".private/zomorod-business"
        private.mkdir(parents=True)
        cls.database = private / "management.sqlite3"
        init = subprocess.run(["php", str(cls.web / "app.php"), "--initialize-private-db"],
                              capture_output=True, text=True, timeout=20)
        if init.returncode:
            raise AssertionError("synthetic setup failed: " + init.stderr[-300:])
        sessions = cls.root / "sessions"
        sessions.mkdir()
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        cls.server = subprocess.Popen(
            ["php", "-d", f"session.save_path={sessions}", "-d", "display_errors=0",
             "-S", f"127.0.0.1:{cls.port}", "-t", str(cls.web)],
            cwd=str(cls.root), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        cls.addClassCleanup(cls.shutdown)
        for _ in range(70):
            try:
                status, headers, page = cls.http("GET", "/app.php")
                break
            except OSError:
                if cls.server.poll() is not None:
                    raise AssertionError("synthetic server failed to start")
                time.sleep(0.1)
        else:
            raise AssertionError("synthetic server timeout")
        assert status == 200 and "راه‌اندازی امن" in page
        setup_token = (private / "setup.token").read_text().strip()
        status, headers, _ = cls.http("POST", "/app.php", cls.cookie(headers),
                                      {"action": "setup", "csrf": cls.csrf(page),
                                       "setup_token": setup_token,
                                       "username": "bank_admin_test",
                                       "password": "synthetic-only-strong-test-password"})
        assert status == 303
        cls.admin_cookie = cls.cookie(headers)
        with sqlite3.connect(cls.database) as db:
            cls.actor_id = db.execute("SELECT id FROM users WHERE username='bank_admin_test'").fetchone()[0]
            db.execute("INSERT INTO users(username,password_hash,role,active) VALUES('bank_viewer_test','disabled','viewer',1)")
            db.execute("INSERT INTO parties(name,kind) VALUES('Synthetic customer','customer')")
            party = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute("INSERT INTO journal_entries(doc_no,doc_date,note,entered_by) VALUES('OPEN-SALE','2026-11-01','synthetic sale',?)", (cls.actor_id,))
            posted = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            accounts = dict(db.execute("SELECT code,id FROM ledger_accounts"))
            db.executemany(
                "INSERT INTO journal_lines(entry_id,account_id,debit,credit,currency) VALUES(?,?,?,?,?)",
                [(posted,accounts['1100'],300000,0,'IRR'),(posted,accounts['4000'],0,300000,'IRR')],
            )
            db.execute("INSERT INTO invoices(invoice_no,kind,party_id,invoice_date,due_date,description,amount,currency,posted_entry,created_by) VALUES(?,?,?,?,?,?,?,?,?,?)",
                       ('TEST-SALE-001','sale',party,'2026-11-01','2026-11-02','synthetic',300000,'IRR',posted,cls.actor_id))
            cls.invoice = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute("INSERT INTO journal_entries(doc_no,doc_date,note,entered_by) VALUES('OPEN-USD','2026-11-01','synthetic usd',?)", (cls.actor_id,))
            posted_usd = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.executemany("INSERT INTO journal_lines(entry_id,account_id,debit,credit,currency) VALUES(?,?,?,?,?)",
                           [(posted_usd,accounts['1100'],1000,0,'USD'),(posted_usd,accounts['4000'],0,1000,'USD')])
            db.execute("INSERT INTO invoices(invoice_no,kind,party_id,invoice_date,due_date,description,amount,currency,posted_entry,created_by) VALUES(?,?,?,?,?,?,?,?,?,?)",
                       ('TEST-USD','sale',party,'2026-11-01','2026-11-02','synthetic',1000,'USD',posted_usd,cls.actor_id))
            cls.usd_invoice = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    @classmethod
    def shutdown(cls) -> None:
        if cls.server.poll() is None:
            cls.server.terminate()
            try: cls.server.wait(timeout=3)
            except subprocess.TimeoutExpired:
                cls.server.kill()
                cls.server.wait(timeout=3)

    @classmethod
    def http(cls, method: str, path: str = "/banking.php", cookie: str | None = None,
             form: dict[str,str] | None = None) -> tuple[int,list[tuple[str,str]],str]:
        headers = {}
        if cookie: headers["Cookie"] = "ZM_BUSINESS=" + cookie
        body = urlencode(form).encode("utf-8") if form is not None else None
        if form is not None: headers["Content-Type"] = "application/x-www-form-urlencoded"
        connection = http.client.HTTPConnection("127.0.0.1", cls.port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status,response.getheaders(),response.read().decode("utf-8","replace")
        finally:
            connection.close()

    @staticmethod
    def cookie(headers: list[tuple[str,str]]) -> str:
        for key,value in headers:
            if key.lower()=="set-cookie" and value.startswith("ZM_BUSINESS="):
                return value.split(";",1)[0].split("=",1)[1]
        raise AssertionError("synthetic session cookie not found")

    @staticmethod
    def csrf(body: str) -> str:
        value = TOKEN.search(body)
        if not value: raise AssertionError("CSRF token missing")
        return value.group(1)

    def _setup_banks(self) -> str:
        _,_,page=self.http("GET",cookie=self.admin_cookie)
        token=self.csrf(page)
        with sqlite3.connect(self.database) as db:
            exists=db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='bank_payment_evidence'").fetchone()[0]
        if not exists:
            status,_,_=self.http("POST",cookie=self.admin_cookie,
                                 form={"csrf":token,"action":"configure"})
            self.assertEqual(status,303)
        return token

    def payment_form(self, token: str, reference: str, *, bank: str = "1011",
                     amount: str = "1200.00", invoice: int | None = None) -> dict[str,str]:
        return {"csrf":token,"action":"payment","invoice_id":str(invoice or self.invoice),
                "bank_code":bank,"amount":amount,"date":"2026-11-02","evidence":reference}

    def test_01_anonymous_is_denied(self) -> None:
        status,headers,body=self.http("GET")
        self.assertEqual(status,403)
        self.assertNotIn("Synthetic customer",body)
        self.assertTrue(any(key.lower()=="cache-control" and "no-store" in value for key,value in headers))

    def test_02_configure_requires_csrf_and_is_atomic(self) -> None:
        _,_,page=self.http("GET",cookie=self.admin_cookie)
        before=self.count("ledger_accounts","code IN ('1011','1012')")
        status,_,_=self.http("POST",cookie=self.admin_cookie,
                             form={"csrf":"bad","action":"configure"})
        self.assertEqual(status,403)
        self.assertEqual(self.count("ledger_accounts","code IN ('1011','1012')"),before)
        if before==0:
            status,_,_=self.http("POST",cookie=self.admin_cookie,
                                 form={"csrf":self.csrf(page),"action":"configure"})
            self.assertEqual(status,303)
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute("SELECT code,type FROM ledger_accounts WHERE code IN ('1011','1012') ORDER BY code").fetchall(),
                             [('1011','asset'),('1012','asset')])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='bank_payment_evidence'").fetchone()[0],1)

    def test_03_invoice_receipt_uses_selected_bank_and_is_balanced(self) -> None:
        token=self._setup_banks()
        status,headers,_=self.http("POST",cookie=self.admin_cookie,
                                   form=self.payment_form(token,"synthetic-ref-unique-001",bank="1012"))
        self.assertEqual(status,303)
        with sqlite3.connect(self.database) as db:
            result=db.execute("SELECT p.id,p.entry_id,b.bank_account_id FROM invoice_payments p JOIN bank_payment_evidence b ON b.payment_id=p.id WHERE b.evidence='synthetic-ref-unique-001'").fetchone()
            self.assertIsNotNone(result)
            payment_id,entry_id,account_id=result
            self.assertEqual(db.execute("SELECT code FROM ledger_accounts WHERE id=?",(account_id,)).fetchone()[0],'1012')
            lines=db.execute("SELECT a.code,l.debit,l.credit FROM journal_lines l JOIN ledger_accounts a ON a.id=l.account_id WHERE l.entry_id=? ORDER BY l.id",(entry_id,)).fetchall()
            self.assertEqual(lines,[('1012',120000,0),('1100',0,120000)])
            self.assertEqual(db.execute("SELECT SUM(debit)-SUM(credit) FROM journal_lines WHERE entry_id=?",(entry_id,)).fetchone()[0],0)
            self.assertEqual(db.execute("SELECT user_id,verb,subject,entity_id FROM audit_events ORDER BY id DESC LIMIT 1").fetchone(),
                             (self.actor_id,'create','bank-invoice-payment',payment_id))

    def test_04_duplicate_reference_does_not_post_twice(self) -> None:
        token=self._setup_banks()
        first=self.payment_form(token,"synthetic-idempotency-unique-002",bank="1011",amount="100.00")
        status,_,_=self.http("POST",cookie=self.admin_cookie,form=first)
        self.assertEqual(status,303)
        before=self.count("invoice_payments")
        status,_,body=self.http("POST",cookie=self.admin_cookie,
                                form=first)
        self.assertEqual(status,409)
        self.assertIn("قبلاً",body)
        self.assertEqual(self.count("invoice_payments"),before)

    def test_05_invalid_bank_currency_and_overpayment_are_rejected(self) -> None:
        token=self._setup_banks()
        before=self.count("invoice_payments")
        for form in (
            self.payment_form(token,"synthetic-bad-bank",bank="1010"),
            self.payment_form(token,"synthetic-bad-usd",invoice=self.usd_invoice),
            self.payment_form(token,"synthetic-overpay",amount="9000000.00"),
        ):
            status,_,_=self.http("POST",cookie=self.admin_cookie,form=form)
            self.assertEqual(status,422)
        self.assertEqual(self.count("invoice_payments"),before)

    def test_06_bank_ids_never_appear_in_source_or_http(self) -> None:
        source=(SOURCE/"banking.php").read_text()
        # Account/card numbers are owner-only information and must never be literals in source.
        self.assertNotRegex(source,r"(?<!\d)\d{10,16}(?!\d)")
        status,_,page=self.http("GET",cookie=self.admin_cookie)
        self.assertEqual(status,200)
        self.assertIn("بانک ملت",page)
        self.assertIn("بانک شهر",page)
        self.assertNotRegex(page,r"(?<!\d)\d{10,16}(?!\d)")

    def count(self,table: str,where: str = "1=1") -> int:
        with sqlite3.connect(self.database) as db:
            return db.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0]


if __name__ == "__main__": unittest.main()
