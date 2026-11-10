#!/usr/bin/env python3
"""Fail-closed checks for the *public* MojPlayWin Passenger application.

This file is streamed to cPanel over fingerprint-pinned SSH; it is never
installed, and it never emits .env values, command output or database records.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit


PUBLIC_DIR = Path("/home/zomorod2/mojplaywin.com")
EXPECTED_ROOT = Path("/home/zomorod2/Saeit-staging")
VENV_PREFIX = "/home/zomorod2/virtualenv/"
READONLY_OPERATIONS = {"cpanel_preflight", "django_check", "django_migrations"}
REQUIRED_MIGRATIONS = (
    "core.0049_mpw_guest_email_recovery",
    "mpw_commerce.0004_guesttrxdelivery",
)


class EvidenceUnavailable(Exception):
    """No positive result may be claimed without the exact runtime proof."""


def declared_app_root(bootstrap: str) -> str:
    """Read only a literal APP assignment; never execute passenger_wsgi.py."""
    try:
        module = ast.parse(bootstrap)
    except SyntaxError as exc:
        raise EvidenceUnavailable("PUBLIC_BOOTSTRAP_NOT_PARSEABLE") from exc
    assignments = []
    for stmt in ast.walk(module):
        if isinstance(stmt, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "APP"
            for target in stmt.targets
        ):
            assignments.append(stmt.value.value if isinstance(stmt.value, ast.Constant) else None)
        elif isinstance(stmt, (ast.AugAssign, ast.AnnAssign)) and isinstance(stmt.target, ast.Name) and stmt.target.id == "APP":
            assignments.append(None)
    if len(assignments) != 1 or not isinstance(assignments[0], str):
        raise EvidenceUnavailable("PUBLIC_BOOTSTRAP_APP_AMBIGUOUS")
    return assignments[0]


def passenger_interpreter(htaccess: str) -> Path:
    """Select only the interpreter declared for this public document root."""
    entries = re.findall(r"^\s*PassengerPython\s+(\S+)\s*$", htaccess, re.MULTILINE)
    if len(entries) != 1:
        raise EvidenceUnavailable("PUBLIC_PASSENGER_PYTHON_UNVERIFIED")
    path = Path(entries[0].strip("'\""))
    if not str(path).startswith(VENV_PREFIX) or path.name not in ("python", "python3", "python3.11"):
        raise EvidenceUnavailable("PUBLIC_PASSENGER_PYTHON_OUT_OF_SCOPE")
    if not path.is_file() or not os.access(path, os.X_OK):
        raise EvidenceUnavailable("PUBLIC_PASSENGER_PYTHON_MISSING")
    return path


def non_sqlite_database_declared(env_text: str) -> None:
    """Detect a definite DB URI without logging or returning its value."""
    values = []
    for line in env_text.splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "DATABASE_URL":
            values.append(value.strip().strip("'\""))
    if len(values) != 1:
        raise EvidenceUnavailable("PUBLIC_DATABASE_URL_MISSING_OR_AMBIGUOUS")
    try:
        scheme = urlsplit(values[0]).scheme.lower()
    except ValueError as exc:
        raise EvidenceUnavailable("PUBLIC_DATABASE_URL_INVALID") from exc
    if scheme not in ("mysql", "mariadb"):
        raise EvidenceUnavailable("PUBLIC_DATABASE_URL_NOT_VERIFIED_MARIADB")


def verify_public_context() -> Path:
    """Prove the observed public WSGI route before any Django query."""
    bootstrap = PUBLIC_DIR / "passenger_wsgi.py"
    htaccess = PUBLIC_DIR / ".htaccess"
    if not bootstrap.is_file() or not htaccess.is_file():
        raise EvidenceUnavailable("PUBLIC_PASSENGER_FILES_UNAVAILABLE")
    if declared_app_root(bootstrap.read_text(encoding="utf-8")) != str(EXPECTED_ROOT):
        raise EvidenceUnavailable("PUBLIC_APP_ROOT_MISMATCH")
    if not EXPECTED_ROOT.is_dir() or EXPECTED_ROOT.resolve() != EXPECTED_ROOT:
        raise EvidenceUnavailable("PUBLIC_APP_ROOT_UNAVAILABLE_OR_REDIRECTED")
    if not (EXPECTED_ROOT / "manage.py").is_file():
        raise EvidenceUnavailable("PUBLIC_MANAGE_PY_MISSING")
    settings = EXPECTED_ROOT / "config" / "settings.py"
    if not settings.is_file():
        raise EvidenceUnavailable("PUBLIC_SETTINGS_MISSING")
    source = settings.read_text(encoding="utf-8")
    if "read_env" not in source or "DATABASE_URL" not in source:
        raise EvidenceUnavailable("PUBLIC_DATABASE_SETTINGS_UNVERIFIED")
    env_path = EXPECTED_ROOT / ".env"
    if not env_path.is_file():
        raise EvidenceUnavailable("PUBLIC_DOTENV_MISSING")
    non_sqlite_database_declared(env_path.read_text(encoding="utf-8"))
    return passenger_interpreter(htaccess.read_text(encoding="utf-8"))


def run_readonly_django(interpreter: Path, operation: str) -> int:
    """Run with a bounded, clean environment and print *only* status summaries."""
    args = [str(interpreter), "manage.py"]
    args += ["check"] if operation == "django_check" else ["showmigrations", "--plan"]
    env = {key: os.environ[key] for key in ("HOME", "PATH", "LANG", "LC_ALL") if key in os.environ}
    env.update({"DJANGO_SETTINGS_MODULE": "config.settings", "SAEIT_ENV": "production", "PYTHONNOUSERSITE": "1"})
    try:
        result = subprocess.run(
            args, cwd=str(EXPECTED_ROOT), env=env, capture_output=True,
            text=True, timeout=65, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise EvidenceUnavailable("PUBLIC_DJANGO_COMMAND_UNAVAILABLE") from None
    if result.returncode != 0:
        raise EvidenceUnavailable("PUBLIC_DJANGO_COMMAND_FAILED")
    if operation == "django_check":
        print("PUBLIC_DJANGO_CHECK=PASSED")
        return 0
    lines = result.stdout.splitlines()
    applied = sum(bool(re.match(r"^\s*\[X\]\s+", line)) for line in lines)
    pending = sum(bool(re.match(r"^\s*\[ \]\s+", line)) for line in lines)
    if applied + pending == 0:
        raise EvidenceUnavailable("PUBLIC_MIGRATION_PLAN_EMPTY_OR_UNPARSEABLE")
    print(f"PUBLIC_MIGRATION_APPLIED_COUNT={applied}")
    print(f"PUBLIC_MIGRATION_PENDING_COUNT={pending}")
    for migration in REQUIRED_MIGRATIONS:
        exact = [line for line in lines if re.search(r"\]\s+" + re.escape(migration) + r"(?:\s|$)", line)]
        if len(exact) != 1:
            status = "NOT_PRESENT_IN_PLAN"
        elif re.match(r"^\s*\[X\]", exact[0]):
            status = "APPLIED"
        else:
            status = "PENDING"
        print(f"MIGRATION_{migration.replace('.', '_').upper()}={status}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in READONLY_OPERATIONS:
        print("CPANEL_DIRECT_OPERATION_DENIED", file=sys.stderr)
        return 64
    try:
        interpreter = verify_public_context()
        print("PUBLIC_MOJPLAYWIN_RUNTIME_CONTEXT=SOURCE_VERIFIED")
        if argv[1] == "cpanel_preflight":
            print("PUBLIC_DATABASE_CONFIG=NON_SQLITE_URI_PRESENT")
            print("PUBLIC_PASSENGER_PYTHON=EXECUTABLE_FOUND")
            print("PUBLIC_DATABASE_QUERY=NOT_PERFORMED")
            return 0
        return run_readonly_django(interpreter, argv[1])
    except EvidenceUnavailable as exc:
        print(f"PUBLIC_MOJPLAYWIN_READONLY_BLOCKED={exc}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError, ValueError):
        print("PUBLIC_MOJPLAYWIN_READONLY_BLOCKED=RUNTIME_EVIDENCE_UNREADABLE", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
