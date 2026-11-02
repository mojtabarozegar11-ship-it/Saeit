#!/usr/bin/env python3
"""Real HTTP acceptance of the read-only Zomorod accounting insights page.

All records, cookies and DBs are synthetic and local to a disposable directory.
"""
from __future__ import annotations

import hashlib
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


HERE = Path(__file__).resolve().parents[1] / "content/zomorod-business"
CSRF = re.compile(r'name="csrf" value="([0-9a-f]{64})"')


class InsightsHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="zm-insights-qa-")
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        cls.web = cls.root / "content/zomorod-business"
        cls.web.mkdir(parents=True)
        for filename in ("app.php", "insights.php"):
            shutil.copy2(HERE / filename, cls.web / filename)
        cls.private = cls.root / ".private/zomorod-business"
        cls.private.mkdir(parents=True)
        cls.database = cls.private / "management.sqlite3"
        init = subprocess.run(
            ["php", str(cls.web / "app.php"), "--initialize-private-db"],
            cwd=str(cls.root), capture_output=True, text=True, timeout=12,
        )
        if init.returncode:
            raise AssertionError("disposable setup failed: " + init.stderr[-200:])
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
        for _ in range(80):
            if cls.server.poll() is not None:
                raise AssertionError("isolated PHP server failed")
            try:
                status, hdr, page = cls.http("GET", "/app.php")
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise AssertionError("isolated HTTP server timed out")
        if status != 200 or "راه‌اندازی امن" not in page:
            raise AssertionError("first-admin bootstrap did not render")
        token = (cls.private / "setup.token").read_text().strip()
        status, hdr, _ = cls.http(
            "POST", "/app.php", cls.cookie(hdr),
            {"action": "setup", "csrf": cls.csrf(page), "setup_token": token,
             "username": "qa_2026_owner", "password": "local-only-long-strong-password-2026"},
        )
        if status != 303:
            raise AssertionError("first-admin creation rejected")
        cls.auth_cookie = cls.cookie(hdr)
        with sqlite3.connect(cls.database) as db:
            db.execute("PRAGMA foreign_keys=ON")
            cls.user_id = db.execute("SELECT id FROM users WHERE username='qa_2026_owner'").fetchone()[0]
            db.execute("INSERT INTO parties(name,kind) VALUES(?,?)", ("QA <script>alert(1)</script>", "both"))
            party = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            for number, kind, due, amount, currency in (
                ("QA-RECEIVABLE", "sale", "2000-01-01", 25000, "EUR"),
                ("QA-PAYABLE", "purchase", "2099-01-01", 10000, "USD"),
            ):
                db.execute("INSERT INTO journal_entries(doc_no,doc_date,note,entered_by) VALUES(?,?,?,?)",
                           ("JV-" + number, "2000-01-01", "isolated", cls.user_id))
                journal = db.execute("SELECT last_insert_rowid()").fetchone()[0]
                db.execute("""INSERT INTO invoices(invoice_no,kind,party_id,invoice_date,due_date,
                    description,amount,currency,posted_entry,created_by) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (number, kind, party, "2000-01-01", due, "test", amount, currency, journal, cls.user_id))
            db.execute("INSERT INTO journal_entries(doc_no,doc_date,note,entered_by) VALUES(?,?,?,?)",
                       ("JV-QA-PAYMENT", "2000-01-02", "test", cls.user_id))
            journal = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            invoice_id = db.execute("SELECT id FROM invoices WHERE invoice_no='QA-RECEIVABLE'").fetchone()[0]
            db.execute("INSERT INTO invoice_payments(invoice_id,amount,paid_on,entry_id,created_by) VALUES(?,?,?,?,?)",
                       (invoice_id, 5000, "2000-01-02", journal, cls.user_id))

    @classmethod
    def shutdown(cls) -> None:
        if cls.server.poll() is None:
            cls.server.terminate()
            try:
                cls.server.wait(timeout=3)
            except subprocess.TimeoutExpired:
                cls.server.kill()
                cls.server.wait(timeout=3)

    @classmethod
    def http(cls, method: str, path: str = "/insights.php", cookie: str | None = None,
             form: dict[str, str] | None = None) -> tuple[int, list[tuple[str, str]], str]:
        headers = {}
        if cookie:
            # Secure HTTPS cookie is explicitly forwarded over local loopback for testing.
            headers["Cookie"] = "ZM_BUSINESS=" + cookie
        data = urlencode(form).encode("ascii") if form is not None else None
        if form is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        connection = http.client.HTTPConnection("127.0.0.1", cls.port, timeout=5)
        try:
            connection.request(method, path, body=data, headers=headers)
            response = connection.getresponse()
            return response.status, response.getheaders(), response.read().decode("utf-8", "replace")
        finally:
            connection.close()

    @staticmethod
    def cookie(headers: list[tuple[str, str]]) -> str:
        for name, value in headers:
            if name.lower() == "set-cookie" and value.startswith("ZM_BUSINESS="):
                return value.split(";", 1)[0].split("=", 1)[1]
        raise AssertionError("session cookie not returned")

    @staticmethod
    def csrf(body: str) -> str:
        match = CSRF.search(body)
        if not match:
            raise AssertionError("CSRF input not returned")
        return match.group(1)

    def setUp(self) -> None:
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE users SET active=1,role='admin' WHERE id=?", (self.user_id,))

    def test_anonymous_does_not_see_private_records(self) -> None:
        status, headers, body = self.http("GET")
        self.assertEqual(status, 403)
        self.assertNotIn("QA-RECEIVABLE", body)
        self.assertNotIn("250.00", body)
        self.assertNotIn("<script>", body)
        self.assertTrue(any(k.lower() == "cache-control" and "no-store" in v.lower()
                            for k, v in headers))

    def test_reuses_existing_login_and_real_balances(self) -> None:
        status, _, body = self.http("GET", cookie=self.auth_cookie)
        self.assertEqual(status, 200)
        self.assertIn("QA-RECEIVABLE", body)
        self.assertIn("QA-PAYABLE", body)
        self.assertIn("200.00", body)  # EUR: 250 invoiced - 50 internally paid
        self.assertIn("100.00", body)  # USD future payable
        self.assertIn("سررسیدگذشته", body)
        self.assertIn("QA &lt;script&gt;alert(1)&lt;/script&gt;", body)
        self.assertNotIn("QA <script>", body)
        self.assertIn("تأییدیه بانک", body)

    def test_role_is_revalidated_and_inactive_account_is_denied(self) -> None:
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE users SET role='viewer' WHERE id=?", (self.user_id,))
        status, _, body = self.http("GET", cookie=self.auth_cookie)
        self.assertEqual(status, 200)
        self.assertIn("qa_2026_owner · viewer", body)
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE users SET active=0 WHERE id=?", (self.user_id,))
        status, _, body = self.http("GET", cookie=self.auth_cookie)
        self.assertEqual(status, 403)
        self.assertNotIn("QA-RECEIVABLE", body)

    def test_post_is_not_allowed_to_write_ledger(self) -> None:
        status, headers, body = self.http("POST", cookie=self.auth_cookie, form={"action": "invoice"})
        self.assertEqual(status, 405)
        self.assertTrue(any(k.lower() == "allow" and v == "GET" for k, v in headers))
        self.assertNotIn("QA-RECEIVABLE", body)

    def test_readonly_access_does_not_touch_financial_database(self) -> None:
        def fingerprint() -> dict[str, str]:
            # SQLite readers update the transient -shm lock/read-mark page.
            # Only durable DB + WAL bytes must remain unchanged by a GET.
            return {file.name: hashlib.sha256(file.read_bytes()).hexdigest()
                    for file in self.private.glob("management.sqlite3*")
                    if file.is_file() and file.name != "management.sqlite3-shm"}
        before = fingerprint()
        status, _, _ = self.http("GET", cookie=self.auth_cookie)
        self.assertEqual(status, 200)
        self.assertEqual(fingerprint(), before)

    def test_missing_private_database_fails_closed(self) -> None:
        hidden = self.private / "management.test-hidden.sqlite3"
        self.database.rename(hidden)
        try:
            status, _, body = self.http("GET", cookie=self.auth_cookie)
            self.assertEqual(status, 503)
            self.assertNotIn("QA-RECEIVABLE", body)
            self.assertFalse(self.database.exists())
        finally:
            hidden.rename(self.database)


if __name__ == "__main__":
    unittest.main()
