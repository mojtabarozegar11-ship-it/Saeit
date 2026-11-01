#!/usr/bin/env python3
"""End-to-end, disposable tests for Zomorod's explicit private SQLite setup.

The actual PHP app runs under a loopback-only server and a temporary private
directory. No cPanel/VPS, production DB, credentials or live website are used.
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


SOURCE = Path(__file__).resolve().parents[1] / "content/zomorod-business/app.php"
REQUIRED = {
    "users", "ledger_accounts", "journal_entries", "journal_lines", "parties",
    "invoices", "invoice_payments", "inventory", "inventory_movements",
    "employees", "documents", "projects", "audit_events",
}
CSRF = re.compile(r'name="csrf" value="([0-9a-f]{64})"')


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PrivateDBBootstrapHTTPTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="zm-db-bootstrap-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.docroot = self.root / "content/zomorod-business"
        self.docroot.mkdir(parents=True)
        self.app = self.docroot / "app.php"
        shutil.copy2(SOURCE, self.app)
        self.private = self.root / ".private/zomorod-business"
        self.private.mkdir(parents=True)
        self.database = self.private / "management.sqlite3"
        self.token = self.private / "setup.token"
        session_dir = self.root / "sessions"
        session_dir.mkdir()
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self.server = subprocess.Popen(
            [
                "php", "-d", f"session.save_path={session_dir}",
                "-d", "display_errors=0", "-S", f"127.0.0.1:{self.port}",
                "-t", str(self.docroot),
            ],
            cwd=str(self.root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.addCleanup(self.stop_server)
        for _ in range(70):
            if self.server.poll() is not None:
                self.fail("temporary PHP server unexpectedly exited")
            try:
                self.http("GET")
                break
            except OSError:
                time.sleep(0.1)
        else:
            self.fail("temporary PHP server failed to start")

    def stop_server(self) -> None:
        if self.server.poll() is None:
            self.server.terminate()
            try:
                self.server.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.server.kill()
                self.server.wait(timeout=3)

    def http(self, method: str, *, cookie: str | None = None,
             data: dict[str, str] | None = None,
             query: str = "") -> tuple[int, list[tuple[str, str]], str]:
        headers: dict[str, str] = {}
        if cookie is not None:
            # Secure cookies are forwarded manually on the loopback-only test.
            headers["Cookie"] = f"ZM_BUSINESS={cookie}"
        payload = urlencode(data).encode("ascii") if data is not None else None
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        con = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            con.request(method, "/app.php" + query, body=payload, headers=headers)
            response = con.getresponse()
            return (response.status, response.getheaders(),
                    response.read().decode("utf-8", "replace"))
        finally:
            con.close()

    def install(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["php", str(self.app), "--initialize-private-db"],
            cwd=str(self.root),
            text=True, capture_output=True, timeout=10, check=False,
        )

    @staticmethod
    def cookie(headers: list[tuple[str, str]]) -> str:
        for name, value in reversed(headers):
            if name.lower() == "set-cookie" and value.startswith("ZM_BUSINESS="):
                return value.split(";", 1)[0].split("=", 1)[1]
        raise AssertionError("missing private session cookie")

    def test_missing_database_fails_closed_without_creating_it(self) -> None:
        status, _, _ = self.http("GET")
        self.assertEqual(status, 500)
        self.assertFalse(self.database.exists())
        self.assertFalse(self.token.exists())

    def test_partial_schema_fails_closed_without_migration(self) -> None:
        with sqlite3.connect(self.database) as conn:
            conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        original = digest(self.database)
        status, _, _ = self.http("GET")
        self.assertEqual(status, 500)
        self.assertEqual(digest(self.database), original)
        with sqlite3.connect(self.database) as conn:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
        self.assertEqual(tables, {"users"})

    def test_explicit_initializer_seeds_once_and_refuses_existing_data(self) -> None:
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.database.is_file())
        self.assertTrue(self.token.is_file())
        self.assertEqual(self.database.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.token.stat().st_mode & 0o777, 0o600)
        token = self.token.read_text(encoding="utf-8").strip()
        self.assertRegex(token, r"^[0-9a-f]{64}$")
        self.assertNotIn(token, result.stdout + result.stderr)
        with sqlite3.connect(self.database) as conn:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            self.assertEqual(tables, REQUIRED)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM ledger_accounts").fetchone()[0], 12)
        first_hash = digest(self.database)
        repeat = self.install()
        self.assertNotEqual(repeat.returncode, 0)
        self.assertEqual(digest(self.database), first_hash)
        self.assertEqual(self.token.read_text(encoding="utf-8").strip(), token)

    def test_setup_get_does_not_modify_database_or_setup_secret(self) -> None:
        self.assertEqual(self.install().returncode, 0)
        original = digest(self.database)
        token = self.token.read_bytes()
        for _ in range(3):
            status, _, html = self.http("GET")
            self.assertEqual(status, 200)
            self.assertIn("راه‌اندازی امن", html)
            self.assertEqual(digest(self.database), original)
            self.assertEqual(self.token.read_bytes(), token)

    def test_missing_setup_token_is_not_silently_regenerated_by_http(self) -> None:
        self.assertEqual(self.install().returncode, 0)
        original = digest(self.database)
        self.token.unlink()  # Only the isolated, disposable test token.
        status, _, _ = self.http("GET")
        self.assertEqual(status, 500)
        self.assertFalse(self.token.exists())
        self.assertEqual(digest(self.database), original)

    def test_first_admin_setup_and_authenticated_get_remain_operational(self) -> None:
        self.assertEqual(self.install().returncode, 0)
        status, headers, html = self.http("GET")
        self.assertEqual(status, 200)
        csrf = CSRF.search(html)
        self.assertIsNotNone(csrf)
        setup_secret = self.token.read_text(encoding="utf-8").strip()
        status, headers, _ = self.http(
            "POST", cookie=self.cookie(headers),
            data={
                "csrf": csrf.group(1),
                "action": "setup",
                "setup_token": setup_secret,
                "username": "owner_admin",
                "password": "safe-independent-test-password-2026",
            },
        )
        self.assertEqual(status, 303)
        self.assertFalse(self.token.exists())
        with sqlite3.connect(self.database) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
        current_hash = digest(self.database)
        session_cookie = self.cookie(headers)
        for _ in range(2):
            status, _, dashboard = self.http("GET", cookie=session_cookie, query="?page=dashboard")
            self.assertEqual(status, 200)
            self.assertIn("زمرد ملل · مدیریت جامع", dashboard)
            self.assertEqual(digest(self.database), current_hash)

    def test_symlinked_database_cannot_be_loaded_or_overwritten(self) -> None:
        target = self.root / "unrelated.sqlite3"
        with sqlite3.connect(target) as conn:
            conn.execute("CREATE TABLE unrelated (value TEXT)")
        original = digest(target)
        self.database.symlink_to(target)
        self.assertEqual(self.http("GET")[0], 500)
        self.assertNotEqual(self.install().returncode, 0)
        self.assertEqual(digest(target), original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
