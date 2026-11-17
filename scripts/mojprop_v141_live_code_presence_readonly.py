#!/usr/bin/env python3
"""Metadata-only check of a candidate live cPanel MOJ PROP code tree.

Does not import Django, read .env, access any database, follow symlinks,
restart Passenger, or declare a candidate tree to be the effective WSGI app.
Source fingerprints are SHA256 of explicit small public code files only.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import stat

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
DOCROOT = HOME / "mojplaywin.com"
MAX_CODE_FILE_BYTES = 512 * 1024
CANDIDATE = {
    "private_html_view": "core/mojprop_v141_private_statement_view.py",
    "private_json_view": "core/mojprop_v141_private_portfolio_view.py",
    "prelaunch_info_view": "core/mojprop_v141_info_view.py",
    "prelaunch_html_template": "templates/moj-prop-plan1-v141-prelaunch/index.html",
    "statement_html_template": "templates/mojprop/v141-private-demo-statement.html",
    "statement_css": "core/static/core/mojprop-v141-statement.css",
    "tenant_book_migration": "prop_firm/migrations/0010_v141_virtual_tenant_books.py",
    "replay_journal_migration": "prop_firm/migrations/0009_v141_sim_replay_journal.py",
}


def _safe_dir(path: Path, *, uid: int):
    try:
        s = path.lstat()
        return stat.S_ISDIR(s.st_mode) and s.st_uid == uid and not (s.st_mode & 0o002)
    except OSError:
        return False


def _fingerprint(root: Path, relative: str, uid: int):
    path = root.joinpath(*relative.split("/"))
    try:
        # All parent directories must be ordinary and not world-writable.
        parent = path.parent
        while parent != root:
            if not _safe_dir(parent, uid=uid):
                return None
            parent = parent.parent
        s = path.lstat()
        if (not stat.S_ISREG(s.st_mode) or s.st_uid != uid or
                s.st_mode & 0o002 or not 0 < s.st_size <= MAX_CODE_FILE_BYTES):
            return None
        with path.open("rb") as fp:
            data = fp.read(MAX_CODE_FILE_BYTES + 1)
        if len(data) != s.st_size:
            return None
        return hashlib.sha256(data).hexdigest()
    except OSError:
        return None


def inspect(home: Path = HOME, *, uid: int | None = None):
    uid = os.getuid() if uid is None else uid
    app = home / "Saeit-staging"
    site = home / "mojplaywin.com"
    app_ok = _safe_dir(app, uid=uid)
    site_ok = _safe_dir(site, uid=uid)
    wsgi = bool(site_ok and _fingerprint(site, "passenger_wsgi.py", uid))
    files = {key: (_fingerprint(app, path, uid) if app_ok else None)
             for key, path in CANDIDATE.items()}
    return {
        "classification": "MOJPROP_CANDIDATE_CPANEL_CODE_READ_ONLY",
        "candidate_staging_tree_present": app_ok,
        "candidate_site_docroot_present": site_ok,
        "candidate_passenger_entry_regular": wsgi,
        "candidate_code_sha256": files,
        "all_expected_files_present": all(files.values()),
        "effective_passenger_code_mapping_verified": False,
        "live_http_route_verified": False,
        "live_user_sessions_verified": False,
        "production_schema_verified": False,
        "source_files_modified": False,
        "database_rows_read": False,
        "secret_bytes_read": False,
        "release_permitted": False,
    }


if __name__ == "__main__":
    try:
        print(json.dumps(inspect(), sort_keys=True))
    except Exception:
        print(json.dumps({"classification": "MOJPROP_CPANEL_CODE_INVENTORY_FAILED",
                          "release_permitted": False}))
        raise SystemExit(1)
