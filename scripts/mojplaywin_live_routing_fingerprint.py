#!/usr/bin/env python3
"""Read-only on-host WSGI/.htaccess/Django URLConf topology fingerprint.

No subprocess, imports of production Django, DB operations, filesystem
mutations, network requests, restarts, or access to media/customer files.
Printed result is sanitized for a PUBLIC GitHub Actions log.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

DOCROOT = Path("/home/zomorod2/mojplaywin.com")
SHARED_ROOT = Path("/home/zomorod2/Saeit-staging")
KNOWN = ("mojtaba.roozegar", "picm", "studio.Roham", "saman",
         "zahra$$", "farnaz", "taniya")


def safe_text(p: Path) -> str | None:
    if p.is_symlink() or not p.is_file():
        return None
    try:
        # Bound read to source/config only; never read arbitrary user/media files.
        if p.stat().st_size > 1_000_000:
            return None
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def literal_routes(source: str | None) -> set[str]:
    if source is None:
        return set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    routes = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        method = getattr(node.func, "id", getattr(node.func, "attr", ""))
        if method not in {"path", "re_path"}:
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            route = arg.value.strip("^/").split("/")[0].strip("$")
            if route and not route.startswith("<"):
                routes.add(route)
    return routes


def audit(docroot: Path = DOCROOT, shared_root: Path = SHARED_ROOT) -> dict:
    wsgi = safe_text(docroot / "passenger_wsgi.py")
    htaccess = safe_text(docroot / ".htaccess")
    urlconf = safe_text(shared_root / "config" / "urls.py")
    declared = literal_routes(urlconf)
    try:
        direct_children = [
            p.name for p in docroot.iterdir()
            if p.is_dir() and not p.is_symlink() and not p.name.startswith(".")
        ] if docroot.is_dir() and not docroot.is_symlink() else []
        children_readable = True
    except OSError:
        direct_children = []
        children_readable = False
    result = {
        "classification": "READ_ONLY_LIVE_ROUTING_FINGERPRINT",
        "main_docroot_is_real_directory": docroot.is_dir() and not docroot.is_symlink(),
        "main_wsgi_readable": wsgi is not None,
        "main_htaccess_readable": htaccess is not None,
        "wsgi_references_shared_saeit_staging": None if wsgi is None else ("saeit-staging" in wsgi.lower()),
        "htaccess_passenger_config_present": None if htaccess is None else ("passenger" in htaccess.lower()),
        "htaccess_rewrite_rules_present": None if htaccess is None else ("rewriterule" in htaccess.lower()),
        "shared_django_urls_source_readable": urlconf is not None,
        "shared_django_static_literal_route_count": len(declared),
        "known_independent_routes_mentioned_in_source": {
            name: (name.lower() in urlconf.lower()) if urlconf is not None else None
            for name in KNOWN
        },
        "known_directories_in_docroot": {
            name: name in direct_children for name in KNOWN
        },
        "docroot_non_hidden_directory_count": len(direct_children),
        "docroot_directory_listing_readable": children_readable,
        "critical_limitation": "AST/static routes and immediate directories cannot enumerate dynamic Django/database routes, virtual aliases or undisclosed child apps; a complete reverse-proxy/cPanel inventory and smoke tests remain mandatory",
        "production_isolation_proven": False,
        "backup_recovery_verified": False,
        "release_permitted": False,
    }
    return result


if __name__ == "__main__":
    print(json.dumps(audit(), sort_keys=True))
