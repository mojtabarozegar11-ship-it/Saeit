#!/usr/bin/env python3
"""Safely deploy the Moj Prop public-intake backend to the pinned Passenger app.

The live Saeit staging tree contains owner-preserved modules that are not present
in the current public repository snapshot. Models, admin, and URL configuration
are therefore patched additively; they are never replaced wholesale.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import signal
import stat
import time
import subprocess
import sys
import tempfile

# SSH executes this file by absolute path: insert the bundle root explicitly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.mojprop_schema_preflight_c83 import (check_schema_closure, migration_operations_signature,
    has_reviewed_legacy_suffix, LEGACY_BASELINES)
from scripts.mojprop_db_release_evidence import verify_database_restore_evidence


ROOT = Path("/home/zomorod2/Saeit-staging")
DOCROOT = Path("/home/zomorod2/mojplaywin.com")
BACKUP_ROOT = Path("/home/zomorod2/.mojplaywin-moj-prop-backups")
INDEPENDENT_DB_EVIDENCE_ROOT = Path("/home/zomorod2/.mojprop-private-db-restore-evidence")
URLCONF = Path("config/urls.py")
FILES = (
    Path("core/models.py"),
    Path("core/admin.py"),
    Path("core/mojprop_views.py"),
    Path("core/mojprop_receipts.py"),
    Path("core/mojprop_catalog_contract.py"),
    Path("core/mojprop_workflow.py"),
    Path("core/mojprop_offer_draft.py"),
    Path("core/mojprop_quote_contract.py"),
    Path("core/mojprop_quote_views.py"),
    Path("core/migrations/0041_mojprop_request.py"),
    Path("core/migrations/0042_mojprop_offer.py"),
    Path("core/migrations/0043_mojprop_digital_inquiry.py"),
    Path("core/migrations/0044_mojprop_acceptance_evidence.py"),
    Path("core/migrations/0045_mojprop_delivery_evidence.py"),
    Path("scripts/mojprop_schema_preflight_c83.py"),
    Path("scripts/fixtures/mojprop_legacy_request_source_c84.py"),
    Path("scripts/fixtures/mojprop_legacy_admin_source_c84.py"),
    Path("scripts/mojprop_db_release_evidence.py"),
    Path("scripts/mojprop_live_database_identity_c85.py"),
)
ALL_FILES = (URLCONF,) + FILES
REPLACE_FILES = tuple(path for path in FILES if path not in (
    Path("core/models.py"), Path("core/admin.py"),
    Path("scripts/fixtures/mojprop_legacy_request_source_c84.py"),
    Path("scripts/fixtures/mojprop_legacy_admin_source_c84.py"),
    Path("scripts/mojprop_db_release_evidence.py"),
    Path("scripts/mojprop_live_database_identity_c85.py"),
))


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_run_id(value: str) -> str:
    if not value.isdigit() or len(value) > 20:
        raise ValueError("invalid workflow run id")
    return value


def validate_commit(value: str) -> str:
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("invalid source commit")
    return value


def assert_regular(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"{label} is missing or unsafe: {path}")


def assert_safe_parent(path: Path, root: Path) -> None:
    # Path.parent alone can encounter a lexical root/../outside escape after
    # apparently reaching root; never accept path traversal or alien roots.
    if not path.is_absolute() or not root.is_absolute():
        raise RuntimeError(f"unsafe relative source path: {path}")
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise RuntimeError(f"source path escapes reviewed root: {path}") from None
    if ".." in relative.parts or not relative.parts:
        raise RuntimeError(f"source path traversal refused: {path}")
    current = path.parent
    while current != root:
        if current == Path("/"):
            raise RuntimeError(f"unsafe parent chain: {path}")
        if current.is_symlink():
            raise RuntimeError(f"symlink parent refused: {current}")
        current = current.parent


def compile_python(path: Path) -> None:
    compile(path.read_text(encoding="utf-8"), str(path), "exec")


def assert_staged_inventory(repo_root: Path) -> None:
    if repo_root.is_symlink() or not repo_root.is_dir():
        raise RuntimeError("backend staging root is missing or unsafe")
    for relative in ALL_FILES:
        source = repo_root / relative
        assert_safe_parent(source, repo_root)
        assert_regular(source, "backend staged file")


def selftest(repo_root: Path) -> None:
    assert_staged_inventory(repo_root)
    for relative in ALL_FILES:
        source = repo_root / relative
        if source.suffix == ".py":
            compile_python(source)
    view = (repo_root / "core/mojprop_views.py").read_text(encoding="utf-8")
    urls = (repo_root / "config/urls.py").read_text(encoding="utf-8")
    model = (repo_root / "core/models.py").read_text(encoding="utf-8")
    required = (
        ("mojprop_intake", view),
        ("mojprop_receipt_status", view),
        ("from .mojprop_receipts import", view),
        ("MojPropRequest", model),
        ('path("moj-prop-intake/"', urls),
        ('path("moj-prop-status/"', urls),
        ("get_token", view),
        ("_ip_hash", view),
    )
    missing = [marker for marker, text in required if marker not in text]
    if missing:
        raise RuntimeError(f"backend selftest missing markers: {missing}")
    check_schema_closure(repo_root, repo_root)
    print("MOJ_PROP_BACKEND_SELFTEST=PASS")


def choose_python() -> Path:
    candidates = (
        Path("/home/zomorod2/virtualenv/Saeit-staging/3.11/bin/python"),
        Path("/home/zomorod2/virtualenv/Saeit/3.11/bin/python"),
        ROOT / ".venv/bin/python",
    )
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise RuntimeError("verified Django Python runtime not found")


def safe_source_mode(mode: int) -> int:
    if (type(mode) is not int or mode < 0 or mode > 0o777
            or mode & 0o022):
        raise RuntimeError("unsafe group/world-writable commercial source mode")
    return mode


def backup_target(target: Path, backup: Path, manifest: dict, relative: Path) -> None:
    assert_safe_parent(target, ROOT)
    # Path.exists() is False for a dangling symlink. Recording it as an
    # absent original would make a subsequent rollback remove owner-owned
    # routing state rather than restore it. Reject before creating a backup.
    if target.is_symlink():
        raise RuntimeError("unsafe live target symlink before backup")
    if target.exists():
        assert_regular(target, "live target")
        saved = backup / relative
        # A hostile symlink below the private backup directory must not
        # redirect saved customer-facing application source elsewhere.
        assert_safe_parent(saved, backup)
        saved.parent.mkdir(parents=True, exist_ok=True)
        source_mode = safe_source_mode(stat.S_IMODE(target.stat().st_mode))
        original_sha = digest(target)
        shutil.copy2(target, saved)
        if digest(saved) != original_sha:
            raise RuntimeError("live backend backup copy failed checksum verification")
        manifest[str(relative)] = {
            "existed": True,
            "sha256": original_sha,
            "mode": source_mode,
        }
    else:
        manifest[str(relative)] = {"existed": False}


def atomic_replace(source: Path, target: Path, mode: int) -> None:
    assert_regular(source, "staged source")
    assert_safe_parent(target, ROOT)
    # A symlink appearing after initial backup/preflight is a race or
    # unexpected owner edit, not a file we are authorized to overwrite.
    if target.is_symlink():
        raise RuntimeError("unsafe live target symlink before replacement")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.mojprop-", dir=str(target.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            with source.open("rb") as incoming:
                shutil.copyfileobj(incoming, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_text(target: Path, text: str, mode: int) -> None:
    assert_safe_parent(target, ROOT)
    # This path is used for URL configuration and the selected migration.
    # A symlink installed after preflight is an owner-owned file boundary.
    if target.is_symlink():
        raise RuntimeError("unsafe live target symlink before text replacement")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.mojprop-", dir=str(target.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def install_migration(source: Path, target: Path) -> None:
    assert_regular(source, "staged migration")
    if target.is_symlink():
        raise RuntimeError("unsafe pre-existing Moj Prop migration symlink")
    if target.exists():
        assert_regular(target, "live intake migration")
        if migration_operations_signature(target) != migration_operations_signature(source):
            raise RuntimeError("refusing to overwrite a different previously applied migration")
        # A potentially applied migration must not have its dependency
        # graph silently rewritten on another release attempt.
        print("MOJ_PROP_INTAKE_MIGRATION_PRESERVED")
        return
    migration_dir = ROOT / "core/migrations"
    candidates = []
    for item in migration_dir.glob("*.py"):
        if item.is_symlink() or not item.is_file():
            continue
        match = re.match(r"^([0-9]+)_([a-zA-Z0-9_]+)[.]py$", item.name)
        # The full commercial chain 0041..0045 depends on 0041. Taking
        # 0045 as 0041's parent would create a cyclic migration graph.
        if not match:
            continue
        if int(match.group(1)) >= 41:
            # Never make the initial intake migration depend on an existing
            # later revision, including a concurrent migration above 0045.
            continue
        candidates.append((int(match.group(1)), item.stem))
    if not candidates:
        raise RuntimeError("reviewed core migration parent is missing")
    highest = max(number for number, _ in candidates)
    heads = [name for number, name in candidates if number == highest]
    if len(heads) != 1:
        raise RuntimeError("ambiguous core migration parent, refusing automatic selection")
    parent = heads[0]
    text = source.read_text(encoding="utf-8")
    baseline_names = (
        "0040_commercefunnelevent",
        "0039_educationassessment_educationattempt_and_more",
    )
    # Only rewrite the actual AST dependency, not text inside a comment,
    # module docstring or an unrelated migration expression.
    def actual_core_parent(content: str) -> str:
        tree = ast.parse(content)
        classes = [node for node in tree.body
                   if isinstance(node, ast.ClassDef) and node.name == "Migration"]
        if len(classes) != 1:
            raise RuntimeError("staged Moj Prop migration class is ambiguous")
        assignments = [node.value for node in classes[0].body
                       if isinstance(node, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == "dependencies"
                               for t in node.targets)]
        if len(assignments) != 1:
            raise RuntimeError("staged Moj Prop dependencies are ambiguous")
        parents = [node for node in ast.walk(assignments[0])
                   if isinstance(node, ast.Tuple) and len(node.elts) == 2
                   and isinstance(node.elts[0], ast.Constant)
                   and node.elts[0].value == "core"
                   and isinstance(node.elts[1], ast.Constant)
                   and isinstance(node.elts[1].value, str)]
        if len(parents) != 1:
            raise RuntimeError("staged Moj Prop core dependency is ambiguous")
        return parents[0].elts[1].value
    original_parent = actual_core_parent(text)
    if original_parent not in baseline_names:
        raise RuntimeError("staged Moj Prop migration baseline parent is unreviewed")
    marker = f'("core", "{original_parent}")'
    if text.count(marker) != 1:
        raise RuntimeError("staged Moj Prop migration parent cannot be replaced uniquely")
    text = text.replace(marker, f'("core", "{parent}")', 1)
    if actual_core_parent(text) != parent:
        raise RuntimeError("staged Moj Prop migration parent rewrite failed")
    mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o640
    atomic_write_text(target, text, mode)
    print("MOJ_PROP_MIGRATION_PARENT=" + parent)


def patch_models(target: Path, source: Path) -> None:
    assert_regular(target, "live models")
    assert_regular(source, "staged models")
    live = target.read_text(encoding="utf-8")
    staged = source.read_text(encoding="utf-8")
    legacy = "class MojPropRequest(" in live and "class MojPropOffer(" not in live
    if "class MojPropRequest(" in live and not legacy:
        print("MOJ_PROP_MODEL_ALREADY_PATCHED")
        return
    if legacy:
        root = source.parents[1]
        if not has_reviewed_legacy_suffix(ROOT, root, "core/models.py"):
            raise RuntimeError("unreviewed partial live Moj Prop model; abort")
        snapshot = (root / LEGACY_BASELINES["core/models.py"]).read_text(
            encoding="utf-8"
        ).rstrip()
        live = live.rstrip()[:-len(snapshot)]
        print("MOJ_PROP_REVIEWED_LEGACY_MODEL_UPGRADE=TRUE")
    marker = "\nclass MojPropRequest("
    start = staged.find(marker)
    if start < 0:
        raise RuntimeError("staged MojPropRequest class is missing")
    block = staged[start + 1 :].rstrip() + "\n"
    if "class T(" not in live or "from django.db import models" not in live:
        raise RuntimeError("live models file has no safe additive-model anchors")
    mode = stat.S_IMODE(target.stat().st_mode)
    atomic_write_text(target, live.rstrip() + "\n\n" + block, mode)
    print("MOJ_PROP_MODEL_PATCH=PASS")


def patch_admin(target: Path, source: Path) -> None:
    assert_regular(target, "live admin")
    assert_regular(source, "staged admin")
    live = target.read_text(encoding="utf-8")
    staged = source.read_text(encoding="utf-8")
    legacy = ("class MojPropRequestAdmin(" in live
              and "class MojPropOfferAdmin(" not in live)
    if "class MojPropRequestAdmin(" in live and not legacy:
        print("MOJ_PROP_ADMIN_ALREADY_PATCHED")
        return
    if legacy:
        root = source.parents[1]
        if not has_reviewed_legacy_suffix(ROOT, root, "core/admin.py"):
            raise RuntimeError("unreviewed partial live Moj Prop admin; abort")
        snapshot = (root / LEGACY_BASELINES["core/admin.py"]).read_text(
            encoding="utf-8"
        ).rstrip()
        live = live.rstrip()[:-len(snapshot)]
        print("MOJ_PROP_REVIEWED_LEGACY_ADMIN_UPGRADE=TRUE")
    # Source main includes the complete commercial model import; a strict
    # equality test for the old one-model import prevented every fresh setup.
    marker = "\nfrom .models import MojPropRequest, MojPropOffer, MojPropDeliveryEvidence\n"
    start = staged.find(marker)
    if start < 0:
        raise RuntimeError("staged Moj Prop admin import contract is missing")
    block = staged[start + 1 :].rstrip() + "\n"
    if "from django.contrib import admin" not in live or "ModelAdmin" not in live:
        raise RuntimeError("live admin file has no safe additive-admin anchors")
    mode = stat.S_IMODE(target.stat().st_mode)
    atomic_write_text(target, live.rstrip() + "\n\n" + block, mode)
    print("MOJ_PROP_ADMIN_PATCH=PASS")


def _declared_url_routes(source: str) -> dict[str, str]:
    """Bind actual urlpatterns routes to view names, not misleading text."""
    tree = ast.parse(source)
    imports_path = any(
        isinstance(node, ast.ImportFrom) and node.module == "django.urls"
        and any(alias.name == "path" and alias.asname is None
                for alias in node.names)
        for node in tree.body
    )
    if not imports_path:
        raise RuntimeError("live URL configuration does not import path")
    expressions = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "urlpatterns"
            for target in node.targets
        ):
            expressions.append(node.value)
        elif (isinstance(node, ast.AugAssign)
              and isinstance(node.target, ast.Name)
              and node.target.id == "urlpatterns"):
            expressions.append(node.value)
    if not expressions:
        raise RuntimeError("live URL configuration has no safe urlpatterns definition")
    routes: dict[str, str] = {}
    for expression in expressions:
        for node in ast.walk(expression):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "path" and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                route = node.args[0].value
                view = (node.args[1].id if len(node.args) > 1
                        and isinstance(node.args[1], ast.Name) else "")
                if route in routes:
                    raise RuntimeError("duplicate Moj Prop or Django route requires review")
                routes[route] = view
    return routes


def patch_urlconf(target: Path) -> None:
    """Install actual Django route entries, not misleading text in comments."""
    assert_regular(target, "live URL configuration")
    assert_safe_parent(target, ROOT)
    source = target.read_text(encoding="utf-8")
    actual = _declared_url_routes(source)
    expected_views = {
        "moj-prop-intake/": "mojprop_intake",
        "moj-prop-status/": "mojprop_receipt_status",
        "moj-prop-quote/<str:token>/": "customer_quote",
    }
    for route, view in expected_views.items():
        if route in actual and actual[route] != view:
            raise RuntimeError("live Moj Prop URL route points to an unreviewed view")
    intake_exists = "moj-prop-intake/" in actual
    status_exists = "moj-prop-status/" in actual
    quote_exists = "moj-prop-quote/<str:token>/" in actual
    if intake_exists and status_exists and quote_exists:
        print("MOJ_PROP_URLCONF_ALREADY_PATCHED")
        return
    missing_imports = []
    routes = []
    if not intake_exists:
        missing_imports.append("mojprop_intake")
        routes.append('path("moj-prop-intake/", mojprop_intake, name="mojprop_intake")')
    if not status_exists:
        missing_imports.append("mojprop_receipt_status")
        routes.append('path("moj-prop-status/", mojprop_receipt_status, name="mojprop_receipt_status")')
    # Quote links are independently disabled by default. Publishing a
    # guarded URL route does NOT issue a proposal or make it payable.
    if not quote_exists:
        routes.append('path("moj-prop-quote/<str:token>/", customer_quote, name="mojprop_quote_public")')
    additions = "\n\n# Moj Prop intake/status and private, owner-gated quote lookup.\n"
    if missing_imports:
        additions += "from core.mojprop_views import " + ", ".join(missing_imports) + "\n"
    if not quote_exists:
        additions += "from core.mojprop_quote_views import customer_quote\n"
    additions += "urlpatterns += [" + ", ".join(routes) + "]\n"
    mode = stat.S_IMODE(target.stat().st_mode)
    atomic_write_text(target, source.rstrip() + additions, mode)
    print("MOJ_PROP_URLCONF_PATCH=PASS")

def _passenger_config() -> str | None:
    candidates = []
    on_path = shutil.which("passenger-config")
    if on_path:
        candidates.append(Path(on_path))
    for pattern in (
        "/opt/cpanel/ea-*/root/usr/bin/passenger-config",
        "/opt/cpanel/ea-*/root/usr/local/bin/passenger-config",
        "/usr/local/cpanel/3rdparty/**/passenger-config",
        "/usr/local/bin/passenger-config",
        "/usr/bin/passenger-config",
    ):
        candidates.extend(Path("/").glob(pattern.lstrip("/")))
    seen = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return key
    return None


def _print_passenger_diagnostics() -> None:
    for command in ("uapi", "whmapi1", "apachectl", "httpd", "cloudlinux-selector", "selectorctl"):
        resolved = shutil.which(command)
        print(f"MOJ_PROP_{command.upper()}=" + (resolved or "NOT_FOUND"))
    selector = shutil.which("cloudlinux-selector")
    if selector:
        try:
            result = subprocess.run(
                [selector, "get", "--json", "--interpreter", "python", "--user", "zomorod2"],
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
            print("MOJ_PROP_SELECTOR_GET_STATUS=" + str(result.returncode))
            print("MOJ_PROP_SELECTOR_GET=" + result.stdout[:4000].replace("\n", " "))
            if result.stderr:
                print("MOJ_PROP_SELECTOR_GET_ERR=" + result.stderr[:1000].replace("\n", " "))
        except Exception as exc:
            print("MOJ_PROP_SELECTOR_GET_ERROR=" + type(exc).__name__)
    uapi = shutil.which("uapi")
    if uapi:
        try:
            result = subprocess.run(
                [uapi, "--output=json", "PassengerApps", "list_applications"],
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
            print("MOJ_PROP_UAPI_LIST_STATUS=" + str(result.returncode))
            print("MOJ_PROP_UAPI_LIST=" + result.stdout[:4000].replace("\n", " "))
            if result.stderr:
                print("MOJ_PROP_UAPI_LIST_ERR=" + result.stderr[:1000].replace("\n", " "))
        except Exception as exc:
            print("MOJ_PROP_UAPI_LIST_ERROR=" + type(exc).__name__)
    try:
        result = subprocess.run(
            ["ps", "-eo", "pid,user,comm,args"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in result.stdout.splitlines():
            lowered = line.lower()
            if any(token in lowered for token in ("passenger", "passenger_wsgi", "saeit-staging", "mojplaywin.com")):
                print("MOJ_PROP_PROCESS=" + line[:500])
    except Exception as exc:
        print("MOJ_PROP_PROCESS_DIAGNOSTIC_ERROR=" + type(exc).__name__)


def _restart_public_lswsgi_workers() -> None:
    marker = "/home/zomorod2/mojplaywin.com/passenger_wsgi.py"
    pids = []
    proc_root = Path("/proc")
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            command = (entry / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", "replace").strip()
        except (FileNotFoundError, PermissionError, OSError):
            continue
        if "lswsgi" in command and marker in command:
            pids.append(int(entry.name))
    print("MOJ_PROP_PUBLIC_LSWGI_TARGETS=" + ",".join(str(pid) for pid in sorted(pids)))
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError as exc:
            raise RuntimeError(f"Cannot restart MojPlayWin lswsgi worker {pid}") from exc
    if pids:
        time.sleep(2)
    print("MOJ_PROP_PUBLIC_LSWGI_RESTART=PASS")


def restart_passenger() -> None:
    restart = DOCROOT / "tmp" / "restart.txt"
    if restart.is_symlink():
        raise RuntimeError("Passenger restart path is a symlink")
    restart.parent.mkdir(parents=True, exist_ok=True)
    restart.touch()
    _print_passenger_diagnostics()
    passenger_config = _passenger_config()
    print("MOJ_PROP_PASSENGER_CONFIG=" + (passenger_config or "NOT_FOUND"))
    if passenger_config:
        result = subprocess.run(
            [passenger_config, "restart-app", str(DOCROOT), "--ignore-app-not-running"],
            check=False,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Passenger restart failed with exit code {result.returncode}")
        print("MOJ_PROP_PASSENGER_RESTART=PASS")
        _restart_public_lswsgi_workers()
        return
    selector = shutil.which("cloudlinux-selector")
    if selector:
        # CloudLinux registers the shared WSGI application under this root;
        # MojPlayWin's Apache vhost points its passenger_wsgi.py at the same tree.
        app_root = "Saeit-staging"
        attempts = (
            [selector, "restart", "--json", "--interpreter", "python", "--user", "zomorod2", "--app-root", app_root],
            [selector, "restart", "--json", "--interpreter", "python", "--app-root", app_root],
        )
        for command in attempts:
            result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=60)
            print("MOJ_PROP_SELECTOR_RESTART_STATUS=" + str(result.returncode))
            print("MOJ_PROP_SELECTOR_RESTART=" + result.stdout[:2000].replace("\n", " "))
            if result.returncode == 0:
                print("MOJ_PROP_PASSENGER_RESTART=CLOUDLINUX_SELECTOR")
                _restart_public_lswsgi_workers()
                return
        raise RuntimeError("CloudLinux Python Selector could not restart mojplaywin.com")
    _restart_public_lswsgi_workers()
    print("MOJ_PROP_PASSENGER_RESTART=TOUCH_ONLY")


def require_private_backup_directory(backup: Path) -> None:
    # File mode alone cannot protect a backup when another user may rename
    # the run directory under a writable parent or redirect its ancestors.
    for directory in (backup.parent, backup):
        if (directory.is_symlink() or not directory.is_dir()
                or stat.S_IMODE(directory.stat().st_mode) & 0o077):
            raise RuntimeError("private backend backup directory required")
        if any(parent.is_symlink() for parent in directory.parents):
            raise RuntimeError("backend backup has symlink ancestor")


def verify_backup_manifest(backup: Path) -> dict:
    """Verify the *entire* pinned backup before changing any restored file.

    This protects Python source recovery integrity only. MariaDB requires its
    own independently proven snapshot and restore procedure.
    """
    require_private_backup_directory(backup)
    manifest_path = backup / "manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise RuntimeError("backend backup manifest is missing")
    # The fixed small source inventory never requires a large JSON manifest.
    # Refuse a malformed oversized file before allocating and parsing it.
    if not 2 <= manifest_path.stat().st_size <= 1024 * 1024:
        raise RuntimeError("backend backup manifest size is unsafe")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if type(manifest) is not dict:
        raise RuntimeError("backend backup manifest format is invalid")
    if manifest.get("files") != [str(path) for path in ALL_FILES]:
        raise RuntimeError("backend backup file inventory differs from pinned installer")
    if type(manifest.get("run_id")) is not str:
        raise RuntimeError("backend backup run id is missing")
    validate_run_id(manifest["run_id"])
    if backup.name != manifest["run_id"]:
        raise RuntimeError("backend backup run id does not match directory")
    if type(manifest.get("commit")) is not str:
        raise RuntimeError("backend backup commit is missing")
    validate_commit(manifest["commit"])
    for relative in ALL_FILES:
        entry = manifest.get(str(relative))
        if type(entry) is not dict or type(entry.get("existed")) is not bool:
            raise RuntimeError("backend backup entry is missing or malformed")
        saved = backup / relative
        assert_safe_parent(saved, backup)
        if entry["existed"]:
            if type(entry.get("sha256")) is not str or not re.fullmatch(
                r"[0-9a-f]{64}", entry["sha256"]
            ):
                raise RuntimeError("backend backup digest is malformed")
            mode = entry.get("mode")
            if type(mode) is not int or mode < 0 or mode > 0o777:
                raise RuntimeError("backend backup mode is invalid")
            safe_source_mode(mode)
            assert_regular(saved, "backend saved source")
            if digest(saved) != entry["sha256"]:
                raise RuntimeError("backend backup source checksum mismatch")
        elif saved.exists() or saved.is_symlink():
            raise RuntimeError("backend backup inventory contains unexpected source")
    return manifest


def restore(backup: Path) -> None:
    # Verify all files before touching any of the live source; otherwise an
    # invalid backup found halfway through restore leaves the app half reverted.
    manifest = verify_backup_manifest(backup)
    for relative in ALL_FILES:
        entry = manifest[str(relative)]
        target = ROOT / relative
        assert_safe_parent(target, ROOT)
        if entry["existed"]:
            saved = backup / relative
            assert_safe_parent(saved, backup)
            assert_regular(saved, "backend backup")
            if digest(saved) != entry["sha256"]:
                raise RuntimeError("backend source changed during restore")
            atomic_replace(saved, target, int(entry["mode"]))
            if digest(target) != entry["sha256"]:
                raise RuntimeError("backend restored source failed verification")
        elif target.exists() or target.is_symlink():
            assert_regular(target, "unexpected target")
            target.unlink()
    restart_passenger()
    print("MOJ_PROP_BACKEND_ROLLBACK=PASS")


def run_checked(command: list[str], cwd: Path) -> None:
    print("RUNNING=" + " ".join(command[:3]))
    subprocess.run(command, cwd=str(cwd), check=True, timeout=300)


def require_independent_db_restore(run_id: str, commit: str, staged_root: Path) -> dict:
    """Deny release without a separate signed restore of the *connected* DB.

    Read-only: a real target connection fingerprint and independent receipt
    are necessary, but not sufficient for production launch authorization.
    """
    run_id, commit = validate_run_id(run_id), validate_commit(commit)
    # The independent reviewer must sign before GitHub Actions starts. Its
    # case ID cannot be the GitHub run ID, which is unknown until dispatch.
    evidence_case = os.environ.get("MOJPROP_APPROVED_RESTORE_CASE_ID", "")
    if not evidence_case:
        raise RuntimeError("pre-approved independent restore case ID is required")
    evidence_case = validate_run_id(evidence_case)
    key = os.environ.get("MOJPROP_INDEPENDENT_RESTORE_VERIFIER_KEY", "")
    evidence_root = os.environ.get("MOJPROP_PRIVATE_DB_RESTORE_ROOT", "")
    if len(key.encode("utf-8")) < 32 or evidence_root != str(INDEPENDENT_DB_EVIDENCE_ROOT):
        raise RuntimeError("independent DB restore proof and reviewer key required")
    if ROOT.is_symlink() or not ROOT.is_dir():
        raise RuntimeError("Django live application root is missing")
    script = staged_root / "scripts/mojprop_live_database_identity_c85.py"
    assert_regular(script, "staged connected MariaDB identity checker")
    python = choose_python()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    result = subprocess.run(
        [str(python), str(script)], cwd=str(ROOT), env=env,
        capture_output=True, text=True, timeout=45, check=False,
    )
    actual_identity = result.stdout.strip()
    if result.returncode != 0 or not re.fullmatch(r"[0-9a-f]{64}", actual_identity):
        raise RuntimeError("actual connected MariaDB identity is unverified")
    verified = verify_database_restore_evidence(
        root=INDEPENDENT_DB_EVIDENCE_ROOT,
        run_id=evidence_case, source_commit=commit,
        database_identity_sha256=actual_identity,
        verifier_key=key.encode("utf-8"),
    )
    if verified.get("rehearsal_receipt_verified") is not True:
        raise RuntimeError("signed independent DB restore receipt was not verified")
    # Do not print database credentials, reviewer signature or private backups.
    print("MOJ_PROP_INDEPENDENT_DB_RESTORE_EVIDENCE=VERIFIED")
    return verified


def deploy(run_id: str, commit: str, staged_root: Path) -> None:
    run_id = validate_run_id(run_id)
    commit = validate_commit(commit)
    if ROOT.is_symlink() or not ROOT.is_dir():
        raise RuntimeError("Passenger application root is missing or redirected")
    if DOCROOT.is_symlink() or not DOCROOT.is_dir():
        raise RuntimeError("MojPlayWin document root is missing or redirected")
    assert_regular(DOCROOT / "passenger_wsgi.py", "Passenger routing file")
    if "Saeit-staging" not in (DOCROOT / "passenger_wsgi.py").read_text(
        encoding="utf-8", errors="replace"
    ):
        raise RuntimeError("Passenger routing file no longer points to Saeit-staging")
    assert_staged_inventory(staged_root)
    # Fail before touching live application files or its database schema.
    closure = check_schema_closure(ROOT, staged_root)
    print("MOJ_PROP_SCHEMA_CLOSURE=PASS; MIGRATIONS=" + ",".join(closure["source_chain"]))
    print("MOJ_PROP_DB_RESTORE_EVIDENCE=INDEPENDENTLY_REQUIRED")
    # No source file, backup or schema mutation until independent proof.
    require_independent_db_restore(run_id, commit, staged_root)

    if (BACKUP_ROOT.is_symlink() or not BACKUP_ROOT.is_dir()
            or stat.S_IMODE(BACKUP_ROOT.stat().st_mode) & 0o077
            or any(parent.is_symlink() for parent in BACKUP_ROOT.parents)):
        raise RuntimeError("private backend backup root not provisioned")
    backup = BACKUP_ROOT / run_id
    if backup.exists() or backup.is_symlink():
        raise RuntimeError(f"refusing to reuse backend backup: {backup}")
    backup.mkdir(mode=0o700)
    manifest = {"run_id": run_id, "commit": commit, "files": [str(item) for item in ALL_FILES]}
    for relative in ALL_FILES:
        backup_target(ROOT / relative, backup, manifest, relative)
    (backup / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    # No live write occurs before every saved file passes digest+inventory.
    verify_backup_manifest(backup)

    try:
        for relative in REPLACE_FILES:
            target = ROOT / relative
            if relative == Path("core/migrations/0041_mojprop_request.py"):
                install_migration(staged_root / relative, target)
            else:
                current_mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o640
                atomic_replace(staged_root / relative, target, current_mode)
                if digest(target) != digest(staged_root / relative):
                    raise RuntimeError(f"post-copy hash mismatch: {relative}")
        patch_models(ROOT / Path("core/models.py"), staged_root / Path("core/models.py"))
        patch_admin(ROOT / Path("core/admin.py"), staged_root / Path("core/admin.py"))
        patch_urlconf(ROOT / URLCONF)

        python = choose_python()
        run_checked([str(python), "manage.py", "check", "--deploy"], ROOT)
        # Never run an unscoped 'migrate': that could apply other apps'
        # unreviewed pending DDL on the commercial production database.
        # Schema closure rejected any unknown core migration >=0041.
        run_checked([str(python), "manage.py", "migrate",
                     "core", "0045_mojprop_delivery_evidence", "--noinput"], ROOT)
        run_checked([str(python), "manage.py", "collectstatic", "--noinput"], ROOT)

        restart_passenger()
        print("MOJ_PROP_BACKEND_DEPLOY=PASS")
        print("MOJ_PROP_BACKEND_COMMIT=" + commit)
        print("MOJ_PROP_BACKUP=" + str(backup))
    except Exception:
        restore(backup)
        raise


def staged_cli_root(argument: str) -> Path:
    # Path.resolve() silently dereferences symlinks and hides the original
    # caller-supplied staging root from the subsequent symlink security gate.
    path = Path(os.path.abspath(argument))
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise RuntimeError("symlinked staged command path is forbidden")
    return path


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        raise SystemExit("usage: script.py selftest [repo_root] | deploy RUN_ID COMMIT STAGED_ROOT | rollback RUN_ID")
    action = argv[1]
    if action == "selftest":
        selftest(staged_cli_root(argv[2]) if len(argv) > 2 else Path.cwd())
        return 0
    if action == "verify-db-restore" and len(argv) == 5:
        require_independent_db_restore(argv[2], argv[3], staged_cli_root(argv[4]))
        return 0
    if action == "deploy" and len(argv) == 5:
        deploy(argv[2], argv[3], staged_cli_root(argv[4]))
        return 0
    if action == "rollback" and len(argv) == 3:
        restore(BACKUP_ROOT / validate_run_id(argv[2]))
        return 0
    raise SystemExit("invalid arguments")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))