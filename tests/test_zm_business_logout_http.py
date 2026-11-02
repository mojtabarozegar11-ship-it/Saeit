#!/usr/bin/env python3
"""Isolated HTTP regression tests for Zomorod private accounting logout.

Runs the real PHP app under a temporary PHP web server with a throwaway SQLite
database and session directory; never connects to the production cPanel site.
"""
from __future__ import annotations

import http.client
from pathlib import Path
import re
import shutil
import sqlite3
import socket
import subprocess
import tempfile
import time
import unittest
from urllib.parse import urlencode


SOURCE = Path(__file__).resolve().parents[1] / "content/zomorod-business/app.php"
USERNAME = "safe_admin_2026"
PASSWORD = "isolated-test-strong-password-2026"
CSRF_PATTERN = re.compile(r'name="csrf" value="([0-9a-f]{64})"')


class LogoutHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="zm-logout-http-")
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        cls.docroot = cls.root / "content/zomorod-business"
        cls.docroot.mkdir(parents=True)
        shutil.copy2(SOURCE, cls.docroot / "app.php")
        cls.private = cls.root / ".private/zomorod-business"
        cls.private.mkdir(parents=True)
        # The protected accounting DB is created only by its one-time local installer,
        # never as a side effect of the first anonymous GET.
        install = subprocess.run(
            ["php", str(cls.docroot / "app.php"), "--initialize-private-db"],
            cwd=str(cls.root), text=True, capture_output=True, timeout=10,
        )
        if install.returncode != 0:
            raise AssertionError("isolated private DB init failed: " + install.stderr[-300:])

        session_dir = cls.root / "sessions"
        session_dir.mkdir()
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        cls.server = subprocess.Popen(
            [
                "php",
                "-d", f"session.save_path={session_dir}",
                "-d", "display_errors=0",
                "-S", f"127.0.0.1:{cls.port}",
                "-t", str(cls.docroot),
            ],
            cwd=str(cls.root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cls.addClassCleanup(cls.stop_server)
        for _ in range(70):
            if cls.server.poll() is not None:
                raise AssertionError("temporary PHP server exited unexpectedly")
            try:
                status, headers, html = cls.request("GET", "/app.php")
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise AssertionError("temporary PHP server did not start")
        if status != 200 or "راه‌اندازی امن" not in html:
            raise AssertionError(f"initial isolated setup failed (HTTP {status})")
        setup_token = (cls.private / "setup.token").read_text(encoding="utf-8").strip()
        setup_cookie = cls.cookie_value(headers)
        if not setup_token or not setup_cookie:
            raise AssertionError("isolated setup did not issue token and session")
        status, _, _ = cls.request(
            "POST", "/app.php", cookie=setup_cookie,
            form={
                "csrf": cls.csrf(html), "action": "setup",
                "setup_token": setup_token, "username": USERNAME,
                "password": PASSWORD,
            },
        )
        if status != 303:
            raise AssertionError(f"isolated first-admin setup failed (HTTP {status})")

    @classmethod
    def stop_server(cls) -> None:
        if cls.server.poll() is None:
            cls.server.terminate()
            try:
                cls.server.wait(timeout=3)
            except subprocess.TimeoutExpired:
                cls.server.kill()
                cls.server.wait(timeout=3)

    @classmethod
    def request(cls, method: str, path: str, *, cookie: str | None = None,
                form: dict[str, str] | None = None) -> tuple[int, list[tuple[str, str]], str]:
        headers: dict[str, str] = {}
        if cookie is not None:
            # The app deliberately sets Secure cookies; this test sends them over
            # loopback HTTP explicitly to simulate the HTTPS cookie flow.
            headers["Cookie"] = f"ZM_BUSINESS={cookie}"
        body = urlencode(form).encode("ascii") if form is not None else None
        if form is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        conn = http.client.HTTPConnection("127.0.0.1", cls.port, timeout=4)
        try:
            conn.request(method, path, body=body, headers=headers)
            response = conn.getresponse()
            result = (
                response.status, response.getheaders(),
                response.read().decode("utf-8", "replace"),
            )
        finally:
            conn.close()
        return result

    @staticmethod
    def cookie_value(headers: list[tuple[str, str]]) -> str | None:
        for name, value in reversed(headers):
            if name.lower() == "set-cookie" and value.startswith("ZM_BUSINESS="):
                return value.split(";", 1)[0].split("=", 1)[1]
        return None

    @staticmethod
    def csrf(html: str) -> str:
        match = CSRF_PATTERN.search(html)
        if match is None:
            raise AssertionError("expected a hidden CSRF form token")
        return match.group(1)

    def setUp(self) -> None:
        status, headers, html = self.request("GET", "/app.php")
        self.assertEqual(status, 200)
        self.assertIn("ورود مدیر و حسابدار", html)
        anonymous_cookie = self.cookie_value(headers)
        self.assertIsNotNone(anonymous_cookie)
        status, headers, _ = self.request(
            "POST", "/app.php", cookie=anonymous_cookie,
            form={
                "csrf": self.csrf(html), "action": "login",
                "username": USERNAME, "password": PASSWORD,
            },
        )
        self.assertEqual(status, 303)
        self.cookie = self.cookie_value(headers)
        self.assertIsNotNone(self.cookie)
        status, _, self.dashboard = self.request("GET", "/app.php?page=dashboard", cookie=self.cookie)
        self.assertEqual(status, 200)
        self.assertIn('name="action" value="logout"', self.dashboard)

    def test_logout_control_is_post_form_with_csrf(self) -> None:
        self.assertIn('<form method="post" action="/business/"', self.dashboard)
        self.assertIn('name="action" value="logout"', self.dashboard)
        self.assertNotIn('href="?page=logout"', self.dashboard)
        self.assertRegex(self.dashboard, CSRF_PATTERN)

    def test_legacy_get_cannot_destroy_session(self) -> None:
        status, headers, _ = self.request("GET", "/app.php?page=logout", cookie=self.cookie)
        # The legacy unknown-page handler may render its error page with HTTP 200
        # because it outputs the layout before setting 404. Neither result may log out.
        self.assertIn(status, (200, 404))
        self.assertFalse(any(k.lower() == "location" for k, _ in headers))
        status, _, html = self.request("GET", "/app.php?page=dashboard", cookie=self.cookie)
        self.assertEqual(status, 200)
        self.assertIn('name="action" value="logout"', html)

    def test_invalid_logout_csrf_is_rejected_without_logging_out(self) -> None:
        for csrf in ("", "f" * 64):
            with self.subTest(csrf=csrf or "missing"):
                form = {"action": "logout"}
                if csrf:
                    form["csrf"] = csrf
                status, _, _ = self.request("POST", "/app.php", cookie=self.cookie, form=form)
                self.assertEqual(status, 403)
        status, _, html = self.request("GET", "/app.php?page=dashboard", cookie=self.cookie)
        self.assertEqual(status, 200)
        self.assertIn('name="action" value="logout"', html)

    def test_valid_logout_destroys_session_and_expires_cookie(self) -> None:
        status, headers, _ = self.request(
            "POST", "/app.php", cookie=self.cookie,
            form={"action": "logout", "csrf": self.csrf(self.dashboard)},
        )
        self.assertEqual(status, 303)
        self.assertIn(("Location", "/business/"), headers)
        cookie_headers = [
            v for k, v in headers
            if k.lower() == "set-cookie" and v.startswith("ZM_BUSINESS=")
        ]
        self.assertTrue(cookie_headers, "logout must clear the browser session cookie")
        self.assertTrue(any("Max-Age=0" in h or "expires=" in h.lower() for h in cookie_headers))
        self.assertTrue(any("path=/business/" in h and "secure" in h.lower() and
                            "httponly" in h.lower() and "samesite=strict" in h.lower()
                            for h in cookie_headers))
        status, _, html = self.request("GET", "/app.php?page=dashboard", cookie=self.cookie)
        self.assertEqual(status, 200)
        self.assertIn("ورود مدیر و حسابدار", html)
        self.assertNotIn('name="action" value="logout"', html)


    def test_financial_classification_evidence_and_immutable_reversal(self) -> None:
        """End-to-end on the temporary database; never a real purchase/payment."""
        csrf = self.csrf(self.dashboard)
        def post(page: str, action: str, **values: str) -> int:
            result, _, _ = self.request(
                "POST", "/app.php?page=" + page, cookie=self.cookie,
                form={"csrf": csrf, "action": action, **values},
            )
            return result

        self.assertEqual(post("parties", "party", name="Synthetic Finance Party",
                              kind="both"), 303)
        db_path = self.private / "management.sqlite3"
        with sqlite3.connect(db_path) as conn:
            party = conn.execute(
                "SELECT id FROM parties WHERE name='Synthetic Finance Party' ORDER BY id DESC"
            ).fetchone()[0]

        fields = {
            "kind": "purchase", "party": str(party), "invoice_no": "QA-PURCHASE-SERVICE",
            "amount": "64.50", "currency": "USD", "date": "2026-11-02",
            "due_date": "2026-11-02", "description": "Synthetic software service",
        }
        self.assertEqual(post("invoices", "invoice", **fields), 422,
                         "An unclassified purchase must not silently become inventory")
        with sqlite3.connect(db_path) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM invoices WHERE invoice_no='QA-PURCHASE-SERVICE'"
            ).fetchone()[0], 0)

        self.assertEqual(post("invoices", "invoice", purchase_class="service", **fields), 303)
        with sqlite3.connect(db_path) as conn:
            invoice_journal = conn.execute(
                "SELECT posted_entry FROM invoices WHERE invoice_no='QA-PURCHASE-SERVICE'"
            ).fetchone()[0]
            postings = conn.execute(
                "SELECT a.code,l.debit,l.credit FROM journal_lines l "
                "JOIN ledger_accounts a ON a.id=l.account_id WHERE l.entry_id=? "
                "ORDER BY a.code", (invoice_journal,)
            ).fetchall()
        self.assertEqual(postings, [("2000", 0, 6450), ("5100", 6450, 0)])
        self.assertEqual(post("journal", "journal_reverse", entry_id=str(invoice_journal),
                              reason="Synthetic invoice forbidden reversal",
                              date="2026-11-02"), 422)

        sale_fields = {
            "kind": "sale", "party": str(party), "invoice_no": "QA-SALE-EVIDENCE",
            "amount": "19.00", "currency": "USD", "date": "2026-11-02",
            "due_date": "2026-11-02", "description": "Synthetic output",
        }
        self.assertEqual(post("invoices", "invoice", **sale_fields), 303)
        with sqlite3.connect(db_path) as conn:
            sale_id = conn.execute(
                "SELECT id FROM invoices WHERE invoice_no='QA-SALE-EVIDENCE'"
            ).fetchone()[0]
        payment = {
            "invoice_id": str(sale_id), "amount": "7.00", "date": "2026-11-02",
        }
        self.assertEqual(post("payments", "payment", **payment), 422)
        self.assertEqual(post("payments", "payment",
                              payment_evidence="Synthetic-Receipt-001", **payment), 303)
        with sqlite3.connect(db_path) as conn:
            note = conn.execute(
                "SELECT j.note FROM invoice_payments p "
                "JOIN journal_entries j ON j.id=p.entry_id WHERE p.invoice_id=?",
                (sale_id,)
            ).fetchone()[0]
        self.assertIn("Synthetic-Receipt-001", note)
        self.assertIn("بدون راستی‌آزمایی بانکی", note)

        self.assertEqual(post(
            "journal", "journal", currency="USD", date="2026-11-02",
            doc_no="QA-INDEPENDENT-JOURNAL", note="Synthetic manual journal",
            account_0="1010", debit_0="27.00",
            account_1="3000", credit_1="27.00"
        ), 303)
        with sqlite3.connect(db_path) as conn:
            manual_id = conn.execute(
                "SELECT id FROM journal_entries WHERE doc_no='QA-INDEPENDENT-JOURNAL'"
            ).fetchone()[0]
            original_lines = conn.execute(
                "SELECT debit,credit FROM journal_lines WHERE entry_id=? ORDER BY id",
                (manual_id,)
            ).fetchall()
        reversal_fields = {
            "entry_id": str(manual_id),
            "reason": "Synthetic posting correction",
            "date": "2026-11-02",
        }
        self.assertEqual(post("journal", "journal_reverse", **reversal_fields), 303)
        self.assertEqual(post("journal", "journal_reverse", **reversal_fields), 422)
        with sqlite3.connect(db_path) as conn:
            reverse_id = conn.execute(
                "SELECT id FROM journal_entries WHERE doc_no=?",
                ("REV-" + str(manual_id),)
            ).fetchone()[0]
            reversed_lines = conn.execute(
                "SELECT debit,credit FROM journal_lines WHERE entry_id=? ORDER BY id",
                (reverse_id,)
            ).fetchall()
            self.assertEqual(conn.execute(
                "SELECT debit,credit FROM journal_lines WHERE entry_id=? ORDER BY id",
                (manual_id,)
            ).fetchall(), original_lines)
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM journal_entries WHERE doc_no=?",
                ("REV-" + str(manual_id),)
            ).fetchone()[0], 1)
        self.assertEqual(reversed_lines,
                         [(credit, debit) for debit, credit in original_lines])


if __name__ == "__main__":
    unittest.main(verbosity=2)
