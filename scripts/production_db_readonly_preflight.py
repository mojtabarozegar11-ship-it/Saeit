"""Fail-closed production database preflight with no SQLite file creation.

Run before Django's migrate --check. This module intentionally avoids importing
Django models or executing any SQL against a writable connection.
"""
from __future__ import annotations

import os
import sqlite3
import stat
import sys
from pathlib import Path
from urllib.parse import quote

SQLITE_HEADER = b"SQLite format 3\x00"
REQUIRED_TABLES = frozenset(("django_migrations", "auth_user"))


class PreflightFailure(RuntimeError):
    pass


def _sidecar_state(path: Path):
    """Reject SQLite sidecars that immutable=1 cannot safely reconcile.

    Even a zero-byte WAL or a hot rollback journal is ambiguous while another
    process may be writing. Refuse them without opening or changing the files.
    """
    for suffix, reason in (("-wal", "SQLITE_WAL_ACTIVE_OR_UNSAFE"),
                           ("-shm", "SQLITE_SHM_PRESENT_OR_UNSAFE"),
                           ("-journal", "SQLITE_JOURNAL_PRESENT_OR_UNSAFE")):
        sidecar = Path(str(path) + suffix)
        try:
            sidecar.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise PreflightFailure("SQLITE_SIDECAR_INACCESSIBLE") from exc
        raise PreflightFailure(reason)


def inspect_sqlite_file(name: str | Path, base_dir: str | Path) -> int:
    """Return table count only for an existing, regular, readable Django DB."""
    path = Path(name)
    if not path.is_absolute():
        path = Path(base_dir) / path
    if path.is_symlink():
        raise PreflightFailure("SQLITE_SYMLINK_REJECTED")
    try:
        metadata = path.stat()
    except OSError as exc:
        raise PreflightFailure("SQLITE_MISSING_OR_INACCESSIBLE") from exc
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size < 4096:
        raise PreflightFailure("SQLITE_EMPTY_OR_NOT_REGULAR")

    # An immutable SQLite URI does not read an active WAL. Never attest a
    # potentially stale main-file schema while uncheckpointed changes exist.
    signature = (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns)
    _sidecar_state(path)

    try:
        with path.open("rb") as handle:
            if handle.read(16) != SQLITE_HEADER:
                raise PreflightFailure("SQLITE_INVALID_HEADER")
        # immutable=1 prevents even WAL/shared-memory sidecar writes from this
        # preflight. A non-checkpointed schema must fail closed, not be guessed.
        uri = "file:" + quote(str(path.resolve(strict=True)), safe="/") + "?mode=ro&immutable=1"
        with sqlite3.connect(uri, uri=True, timeout=3) as connection:
            connection.execute("PRAGMA query_only=ON")
            result = connection.execute("PRAGMA quick_check").fetchone()
            if not result or result[0] != "ok":
                raise PreflightFailure("SQLITE_INTEGRITY_FAILED")
            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
    except (sqlite3.Error, OSError) as exc:
        raise PreflightFailure("SQLITE_READONLY_CHECK_FAILED") from exc

    try:
        current = path.stat()
    except OSError as exc:
        raise PreflightFailure("SQLITE_CHANGED_DURING_PREFLIGHT") from exc
    current_signature = (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns)
    _sidecar_state(path)
    if current_signature != signature:
        raise PreflightFailure("SQLITE_CHANGED_DURING_PREFLIGHT")

    if not REQUIRED_TABLES.issubset(tables):
        raise PreflightFailure("SQLITE_DJANGO_SCHEMA_MISSING")
    return len(tables)


def production_database_preflight() -> str:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.conf import settings

    if settings.DEBUG:
        raise PreflightFailure("DEBUG_MUST_BE_DISABLED")
    database = settings.DATABASES["default"]
    engine = str(database.get("ENGINE", "")).rsplit(".", 1)[-1]
    name = database.get("NAME")
    if not name:
        raise PreflightFailure("DATABASE_NAME_MISSING")
    if engine == "sqlite3":
        count = inspect_sqlite_file(name, settings.BASE_DIR)
        return "SQLITE_READONLY_SCHEMA_VERIFIED tables=" + str(count)
    if engine in {"mysql", "postgresql", "oracle"}:
        # The migration gate remains separately responsible for checking the
        # remote backend. Do not open any network database connection here.
        return "NON_SQLITE_BACKEND_CONFIGURED engine=" + engine
    raise PreflightFailure("DATABASE_ENGINE_UNSUPPORTED")


if __name__ == "__main__":
    try:
        print("PRODUCTION_DB_PREFLIGHT=" + production_database_preflight())
    except Exception as exc:
        # Do not disclose paths, URLs, credentials or tracebacks into deploy logs.
        reason = str(exc) if isinstance(exc, PreflightFailure) else type(exc).__name__
        print("PRODUCTION_DB_PREFLIGHT=BLOCKED " + reason, file=sys.stderr)
        raise SystemExit(1) from None
