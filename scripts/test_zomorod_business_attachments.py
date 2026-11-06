#!/usr/bin/env python3
"""Production-like localhost tests for the additive private ZM document vault.

All requests use disposable filesystem and SQLite fixtures. No live host, secret,
messages, financial writes or external transfer is touched.
"""
from __future__ import annotations

import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SOURCE = Path(__file__).resolve().parents[1] / "content/zomorod-business/attachments.php"
COOKIE = "ZM_BUSINESS=fixture-session-0001"
PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n"


def http(url: str, *, data: bytes | None = None, headers: dict | None = None) -> tuple[int, bytes, dict]:
    request = Request(url, data=data, headers=headers or {}, method="POST" if data is not None else "GET")
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, response.read(), dict(response.headers)
    except HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


def multipart(fields: dict[str, str], *, name: str, blob: bytes) -> tuple[bytes, str]:
    boundary = "zm-safe-attachment-fixture-20261031"
    pieces = []
    for key, value in fields.items():
        pieces.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
    pieces.extend([
        f'--{boundary}\r\nContent-Disposition: form-data; name="attachment"; filename="{name}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode(),
        blob, b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])
    return b"".join(pieces), "multipart/form-data; boundary=" + boundary


def check(condition: bool, detail: str) -> None:
    if not condition:
        raise AssertionError(detail)


def main() -> None:
    check(SOURCE.is_file(), "attachment source missing")
    with tempfile.TemporaryDirectory(prefix="zm-attachments-qa-") as temp:
        home = Path(temp)
        private = home / ".private/zomorod-business"
        private.mkdir(parents=True, mode=0o700)
        server_root = home / "public_html"
        endpoint = server_root / "business/attachments"
        endpoint.mkdir(parents=True)
        shutil.copyfile(SOURCE, endpoint / "index.php")
        sessions = home / "sessions"
        sessions.mkdir(mode=0o700)
        db_file = private / "management.sqlite3"
        with sqlite3.connect(db_file) as db:
            db.executescript("""
                CREATE TABLE users(id INTEGER PRIMARY KEY, role TEXT NOT NULL, active INTEGER NOT NULL);
                CREATE TABLE documents(id INTEGER PRIMARY KEY, title TEXT NOT NULL);
                CREATE TABLE projects(id INTEGER PRIMARY KEY, title TEXT NOT NULL);
                INSERT INTO users VALUES(1,'admin',1);
                INSERT INTO documents VALUES(1,'یک پرونده مصنوعی');
                INSERT INTO projects VALUES(1,'یک پروژه مصنوعی');
            """)
        subprocess.run([
            "php", "-d", f"session.save_path={sessions}", "-r",
            'session_name("ZM_BUSINESS");session_id("fixture-session-0001");session_start();'
            '$_SESSION["uid"]=1;session_write_close();',
        ], check=True, capture_output=True)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base = f"http://127.0.0.1:{port}/business/attachments/"
        server = subprocess.Popen(
            ["php", "-d", f"session.save_path={sessions}", "-S", f"127.0.0.1:{port}", "-t", str(server_root)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(40):
                try:
                    status, _, _ = http(base)
                    break
                except (URLError, TimeoutError):
                    time.sleep(.1)
            else:
                raise AssertionError("PHP HTTP server did not start")
            check(status == 403, "anonymous access did not fail closed")
            status, html, response_headers = http(base, headers={"Cookie": COOKIE})
            check(status == 200 and b'enctype="multipart/form-data"' in html, "authorized form unavailable")
            check(response_headers.get("X-Robots-Tag") == "noindex, nofollow", "private indexing not disabled")
            check(not (private / "document_vault_v1").exists(), "GET created storage")
            csrf_match = re.search(rb'name="csrf" value="([a-f0-9]{64})"', html)
            check(csrf_match is not None, "CSRF token missing")
            csrf = csrf_match.group(1).decode()
            base_hash = hashlib.sha256(db_file.read_bytes()).hexdigest()

            fields = {"csrf": "wrong", "title": "سند آزمون", "category": "اداری"}
            body, content_type = multipart(fields, name="sample.pdf", blob=PDF)
            headers = {"Cookie": COOKIE, "Content-Type": content_type}
            check(http(base, data=body, headers=headers)[0] == 403, "CSRF bypass")
            check(not (private / "document_vault_v1").exists(), "invalid CSRF wrote data")

            fields["csrf"] = csrf
            fields["document_id"] = "1"
            fields["project_id"] = "1"
            bad_body, content_type = multipart(fields, name="bad.php", blob=b"<?php echo 1;")
            headers["Content-Type"] = content_type
            check(http(base, data=bad_body, headers=headers)[0] == 422, "executable file accepted")
            check(not (private / "document_vault_v1").exists(), "rejected file wrote data")

            good_body, content_type = multipart(fields, name="document.pdf", blob=PDF)
            headers["Content-Type"] = content_type
            status, html, _ = http(base, data=good_body, headers=headers)
            check(status == 200 and "فایل در بایگانی خصوصی ذخیره شد.".encode() in html, "valid upload failed")
            vault = private / "document_vault_v1"
            metadata_files = list(vault.glob("*.json"))
            check(len(metadata_files) == 1, "metadata count incorrect")
            metadata = json.loads(metadata_files[0].read_text())
            check(metadata["document_id"] == 1 and metadata["project_id"] == 1, "document/project relation missing")
            check(metadata["sha256"] == hashlib.sha256(PDF).hexdigest(), "digest incorrect")
            check(hashlib.sha256(db_file.read_bytes()).hexdigest() == base_hash, "accounting DB was changed")
            check(oct((vault / (metadata["id"]+".pdf")).stat().st_mode & 0o777) == "0o600", "file not private")
            download_status, download_data, h = http(base+"?download="+metadata["id"], headers={"Cookie": COOKIE})
            check(download_status == 200 and download_data == PDF, "authenticated download failed")
            check("attachment" in h.get("Content-Disposition", ""), "unsafe inline file rendering")
            check(http(base+"?download="+metadata["id"])[0] == 403, "anonymous download accepted")

            with sqlite3.connect(db_file) as db:
                db.execute("UPDATE users SET active=0 WHERE id=1")
            check(http(base, headers={"Cookie": COOKIE})[0] == 403, "disabled user retains access")
            print("ZM private attachments: 13 security/function checks passed; no production mutation.")
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)


if __name__ == "__main__":
    main()
