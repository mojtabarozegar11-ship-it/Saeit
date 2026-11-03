#!/usr/bin/env python3
"""Real PHP/HTTP RBAC and CSRF acceptance with disposable test-only accounts."""
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


class ZmAccessHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(prefix="zm-access-isolated-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.web = cls.root / "content/zomorod-business"
        cls.web.mkdir(parents=True)
        for filename in ("app.php", "access.php"):
            shutil.copy2(SOURCE / filename, cls.web / filename)
        cls.private = cls.root / ".private/zomorod-business"
        cls.private.mkdir(parents=True)
        shutil.copy2(Path(__file__).resolve().parent / "fixtures/zm_period_controls_fixture.php", cls.private / "period_controls.php")
        shutil.copy2(SOURCE.parent / "zomorod-v11/site_store.php", cls.private / "site_store.php")
        cls.database = cls.private / "management.sqlite3"
        result = subprocess.run(["php", str(cls.web / "app.php"), "--initialize-private-db"],
                                capture_output=True, text=True, timeout=12)
        if result.returncode:
            raise AssertionError("synthetic private DB creation failed: " + result.stderr[-200:])
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
            if cls.server.poll() is not None:
                raise AssertionError("synthetic PHP server exited")
            try:
                status, headers, body = cls.http("GET", "/app.php")
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise AssertionError("synthetic PHP server startup timeout")
        if status != 200 or "راه‌اندازی امن" not in body:
            raise AssertionError("no bootstrap form")
        setup = (cls.private / "setup.token").read_text().strip()
        status, headers, _ = cls.http(
            "POST", "/app.php", cls.cookie(headers),
            {"action": "setup", "csrf": cls.csrf(body), "setup_token": setup,
             "username": "qa_access_owner", "password": "synthetic-strong-admin-password-2026"},
        )
        if status != 303:
            raise AssertionError("synthetic first admin setup refused")
        cls.admin_cookie = cls.cookie(headers)
        with sqlite3.connect(cls.database) as db:
            cls.admin_id = db.execute("SELECT id FROM users WHERE username='qa_access_owner'").fetchone()[0]
            db.execute("INSERT INTO users(username,password_hash,role,active) VALUES(?,?,?,1)",
                       ("qa_target", "isolated-no-login", "viewer"))
            cls.target_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute("INSERT INTO users(username,password_hash,role,active) VALUES(?,?,?,1)",
                       ("qa_second_admin", "isolated-no-login", "admin"))
            cls.second_admin_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute("INSERT INTO users(username,password_hash,role,active) VALUES(?,?,?,1)",
                       ('<script>alert(1)</script>', "isolated-no-login", "viewer"))

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
    def http(cls, method: str, path: str = "/access.php", cookie: str | None = None,
             form: dict[str,str] | None = None) -> tuple[int,list[tuple[str,str]],str]:
        headers = {}
        if cookie is not None:
            # The production session cookie is Secure; local loopback simulates HTTPS.
            headers["Cookie"] = "ZM_BUSINESS=" + cookie
        body = urlencode(form).encode("ascii") if form is not None else None
        if form is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        conn = http.client.HTTPConnection("127.0.0.1", cls.port, timeout=5)
        try:
            conn.request(method, path, body=body, headers=headers)
            result = conn.getresponse()
            return result.status, result.getheaders(), result.read().decode("utf-8", "replace")
        finally:
            conn.close()

    @staticmethod
    def cookie(headers: list[tuple[str,str]]) -> str:
        for key, value in headers:
            if key.lower()=="set-cookie" and value.startswith("ZM_BUSINESS="):
                return value.split(";",1)[0].split("=",1)[1]
        raise AssertionError("session cookie missing")

    @staticmethod
    def csrf(html: str) -> str:
        match = TOKEN.search(html)
        if match is None:
            raise AssertionError("CSRF value not found")
        return match.group(1)

    def setUp(self) -> None:
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE users SET active=1,role='admin' WHERE id=?",(self.admin_id,))
            db.execute("UPDATE users SET active=1,role='viewer' WHERE id=?",(self.target_id,))
            db.execute("UPDATE users SET active=1,role='admin' WHERE id=?",(self.second_admin_id,))

    def form(self, csrf: str, user: int | None = None, role: str = "accountant",
             active: str = "0") -> dict[str,str]:
        return {"action":"access_update", "csrf":csrf,
                "user_id":str(user if user is not None else self.target_id),
                "role":role, "active":active}

    def test_anonymous_access_is_denied_without_user_roster(self) -> None:
        status, headers, body = self.http("GET")
        self.assertEqual(status,403)
        self.assertNotIn("qa_target",body)
        self.assertTrue(any(k.lower()=="cache-control" and "no-store" in v
                            for k,v in headers))

    def test_current_active_admin_gets_escaped_roster(self) -> None:
        status, _, body = self.http("GET",cookie=self.admin_cookie)
        self.assertEqual(status,200)
        self.assertIn("qa_target",body)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;",body)
        self.assertNotIn("<script>alert(1)</script>",body)
        self.assertIn("حساب مدیرِ واردشده از این بخش قابل تغییر نیست",body)
        self.assertIn("ثبت تغییر دسترسی",body)

    def test_csrf_rejects_mutation_and_records_no_audit(self) -> None:
        with sqlite3.connect(self.database) as db:
            before = db.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        for token in ("", "0"*64):
            status, _, _ = self.http("POST",cookie=self.admin_cookie,form=self.form(token))
            self.assertEqual(status,403)
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute("SELECT role,active FROM users WHERE id=?",(self.target_id,)).fetchone(),("viewer",1))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0],before)

    def test_role_and_deactivation_are_atomic_and_audited(self) -> None:
        status, _, page = self.http("GET",cookie=self.admin_cookie)
        self.assertEqual(status,200)
        status, headers, _ = self.http("POST",cookie=self.admin_cookie,form=self.form(self.csrf(page)))
        self.assertEqual(status,303)
        self.assertIn(("Location","/business/access.php?updated=1"),headers)
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute("SELECT role,active FROM users WHERE id=?",(self.target_id,)).fetchone(),("accountant",0))
            self.assertEqual(db.execute("SELECT user_id,verb,subject,entity_id FROM audit_events ORDER BY id DESC LIMIT 1").fetchone(),
                             (self.admin_id,"update","user-access",self.target_id))

    def test_self_demote_is_denied_and_last_admin_stays_active(self) -> None:
        _, _, page = self.http("GET",cookie=self.admin_cookie)
        status, _, body = self.http("POST",cookie=self.admin_cookie,
                                    form=self.form(self.csrf(page),user=self.admin_id,role="viewer"))
        self.assertEqual(status,403)
        self.assertIn("حساب خود مدیر",body)
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute("SELECT role,active FROM users WHERE id=?",(self.admin_id,)).fetchone(),("admin",1))

    def test_live_role_revalidation_blocks_demoted_or_inactive_admin(self) -> None:
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE users SET role='viewer' WHERE id=?",(self.admin_id,))
        status, _, body = self.http("GET",cookie=self.admin_cookie)
        self.assertEqual(status,403)
        self.assertNotIn("qa_target",body)
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE users SET role='admin',active=0 WHERE id=?",(self.admin_id,))
        status, _, _ = self.http("GET",cookie=self.admin_cookie)
        self.assertEqual(status,403)

    def test_bad_role_and_id_are_rejected(self) -> None:
        _, _, page = self.http("GET",cookie=self.admin_cookie)
        for role,user in (("root",self.target_id),("manager",0)):
            status, _, _ = self.http("POST",cookie=self.admin_cookie,
                                     form=self.form(self.csrf(page),user=user,role=role))
            self.assertEqual(status,422)


    def test_store_manager_get_never_creates_or_mutates_catalogue(self) -> None:
        # The accounting DB is separate from the store catalogue. A private
        # dashboard GET must not call zmStoreDb(), which creates tables/WAL.
        store_db = self.private / "site_store.sqlite3"
        self.assertFalse(store_db.exists(), "Synthetic store must start absent")
        status, _, _ = self.http(
            "GET", "/app.php?page=store_manager", cookie=self.admin_cookie)
        self.assertEqual(status, 503)
        self.assertFalse(store_db.exists(), "GET silently created a store DB")
        with sqlite3.connect(store_db) as db:
            db.executescript("""
                CREATE TABLE products(id INTEGER PRIMARY KEY,sku TEXT,
                                      title TEXT,price_irr INTEGER,enabled INTEGER);
                CREATE TABLE free_digital_products(
                    id INTEGER PRIMARY KEY,sku TEXT,title TEXT,download_path TEXT,
                    artifact_sha256 TEXT,license_text TEXT,enabled INTEGER);
                CREATE TABLE payment_state(id INTEGER PRIMARY KEY,state TEXT);
                INSERT INTO payment_state VALUES(1,'not_configured');
            """)
        original = store_db.read_bytes()
        status, _, body = self.http(
            "GET", "/app.php?page=store_manager", cookie=self.admin_cookie)
        self.assertEqual(status, 200)
        self.assertIn("کاتالوگ محصولات واقعی", body)
        self.assertEqual(store_db.read_bytes(), original,
                         "GET modified the existing private catalogue")
        self.assertFalse((self.private / "site_store.sqlite3-wal").exists())


if __name__ == "__main__":
    unittest.main()
