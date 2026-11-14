#!/usr/bin/env python3
"""cPanel static sales-page preflight. No writes, file content or customer data."""
from __future__ import annotations
import os
from pathlib import Path
import stat
import pwd

CODES = ("AGR-01", "RS-01", "RS-02", "RS-03", "WEB-01", "SEO-01")
ROOT = Path.home() / "public_html"
TARGET = ROOT / "services" / "scope"

def flag(name: str, value: object) -> None:
    print(f"ZM_STATIC_{name}={str(value).lower()}")

def safe_directory(path: Path) -> bool:
    try:
        p = path.stat()
        return path.is_dir() and not path.is_symlink() and stat.S_ISDIR(p.st_mode) and p.st_uid == os.getuid()
    except OSError:
        return False

def main() -> int:
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        flag("PREFLIGHT_STATE", "WRONG_HOST_IDENTITY")
        return 12
    if not safe_directory(ROOT):
        flag("PREFLIGHT_STATE", "UNSAFE_DOCROOT")
        return 13
    services = ROOT / "services"
    scope = services / "scope"
    flag("PUBLIC_DOCROOT_SAFE", "true")
    flag("SERVICES_DIRECTORY_EXISTS", str(services.exists() or services.is_symlink()))
    flag("SERVICES_DIRECTORY_SYMLINK", str(services.is_symlink()))
    flag("SCOPE_DIRECTORY_EXISTS", str(scope.exists() or scope.is_symlink()))
    flag("SCOPE_DIRECTORY_SYMLINK", str(scope.is_symlink()))
    collision = False
    for code in CODES:
        path = scope / code
        exists = path.exists() or path.is_symlink()
        flag(code.replace("-", "_") + "_EXISTING_TARGET", str(exists))
        collision = collision or exists
    try:
        free_bytes = os.statvfs(ROOT).f_bavail * os.statvfs(ROOT).f_frsize
    except OSError:
        free_bytes = 0
    flag("FREE_AT_LEAST_2MB", str(free_bytes >= 2_000_000))
    dot_htaccess = ROOT / ".htaccess"
    flag("HTACCESS_PRESENT", str(dot_htaccess.is_file() and not dot_htaccess.is_symlink()))
    safe = (
        not services.is_symlink() and not scope.is_symlink()
        and (not services.exists() or safe_directory(services))
        and (not scope.exists() or safe_directory(scope))
        and not collision and free_bytes >= 2_000_000
    )
    # This does NOT prove web-server rewrite order, or authorize deployment.
    flag("NO_FILE_COLLISIONS", str(not collision))
    flag("FILE_ONLY_STAGE_CANDIDATE", str(safe))
    flag("HTTP_ROUTING_VERIFIED", "unknown")
    flag("PRODUCTION_WRITE_PERFORMED", "false")
    return 0 if safe else 14

if __name__ == "__main__":
    raise SystemExit(main())
