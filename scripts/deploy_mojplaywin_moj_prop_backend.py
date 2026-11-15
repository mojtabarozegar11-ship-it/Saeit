#!/usr/bin/env python3
"""Safely deploy the Moj Prop public-intake backend to the pinned Passenger app.

The live Saeit staging tree contains owner-preserved modules that are not present
in the current public repository snapshot. Models, admin, and URL configuration
are therefore patched additively; they are never replaced wholesale.
"""

from __future__ import annotations

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


ROOT = Path("/home/zomorod2/Saeit-staging")
DOCROOT = Path("/home/zomorod2/mojplaywin.com")
BACKUP_ROOT = Path("/home/zomorod2/.mojplaywin-moj-prop-backups")
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
)
ALL_FILES = (URLCONF,) + FILES
REPLACE_FILES = tuple(path for path in FILES if path not in (
    Path("core/models.py"), Path("core/admin.py"),
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
    current = path.parent
    while current != root:
        if current == Path("/"):
            raise RuntimeError(f"unsafe parent chain: {path}")
        if current.is_symlink():
            raise RuntimeError(f"symlink parent refused: {current}")
        current = current.parent


def compile_python(path: Path) -> None:
    compile(path.read_text(encoding="utf-8"), str(path), "exec")


def selftest(repo_root: Path) -> None:
    for relative in ALL_FILES:
        source = repo_root / relative
        assert_regular(source, "source")
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


def backup_target(target: Path, backup: Path, manifest: dict, relative: Path) -> None:
    if target.exists():
        assert_regular(target, "live target")
        saved = backup / relative
        saved.parent.mkdir(parents=True, exist_ok=True)
        original_sha = digest(target)
        shutil.copy2(target, saved)
        if digest(saved) != original_sha:
            raise RuntimeError("live backend backup copy failed checksum verification")
        manifest[str(relative)] = {
            "existed": True,
            "sha256": original_sha,
            "mode": stat.S_IMODE(target.stat().st_mode),
        }
    else:
        manifest[str(relative)] = {"existed": False}


def atomic_replace(source: Path, target: Path, mode: int) -> None:
    assert_regular(source, "staged source")
    assert_safe_parent(target, ROOT)
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
    parent = max(candidates, key=lambda value: (value[0], value[1]))[1] if candidates else "0001_initial"
    text = source.read_text(encoding="utf-8")
    baseline_markers = (
        '("core", "0040_commercefunnelevent")',
        '("core", "0039_educationassessment_educationattempt_and_more")',
    )
    marker = next((candidate for candidate in baseline_markers if candidate in text), None)
    if marker is None:
        raise RuntimeError("staged Moj Prop migration baseline marker is missing")
    text = text.replace(marker, f'("core", "{parent}")', 1)
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


def patch_urlconf(target: Path) -> None:
    """Install both API routes, repairing an older intake-only deployment."""
    assert_regular(target, "live URL configuration")
    source = target.read_text(encoding="utf-8")
    intake_exists = 'path("moj-prop-intake/"' in source
    status_exists = 'path("moj-prop-status/"' in source
    quote_exists = 'path("moj-prop-quote/<str:token>/"' in source
    if intake_exists and status_exists and quote_exists:
        print("MOJ_PROP_URLCONF_ALREADY_PATCHED")
        return
    if "from django.urls import" not in source or "urlpatterns" not in source:
        raise RuntimeError("live URL configuration has no safe Django path anchor")
    import_line = next(
        (line for line in source.splitlines() if line.startswith("from django.urls import ")),
        "",
    )
    if "path" not in import_line:
        raise RuntimeError("live URL configuration does not import path")
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


def verify_backup_manifest(backup: Path) -> dict:
    """Verify the *entire* pinned backup before changing any restored file.

    This protects Python source recovery integrity only. MariaDB requires its
    own independently proven snapshot and restore procedure.
    """
    if backup.is_symlink() or not backup.is_dir():
        raise RuntimeError("backend backup directory is missing or symlinked")
    manifest_path = backup / "manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise RuntimeError("backend backup manifest is missing")
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
        if entry["existed"]:
            if type(entry.get("sha256")) is not str or not re.fullmatch(
                r"[0-9a-f]{64}", entry["sha256"]
            ):
                raise RuntimeError("backend backup digest is malformed")
            mode = entry.get("mode")
            if type(mode) is not int or mode < 0 or mode > 0o777:
                raise RuntimeError("backend backup mode is invalid")
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
            assert_regular(saved, "backend backup")
            atomic_replace(saved, target, int(entry["mode"]))
        elif target.exists():
            assert_regular(target, "unexpected target")
            target.unlink()
    restart_passenger()
    print("MOJ_PROP_BACKEND_ROLLBACK=PASS")


def run_checked(command: list[str], cwd: Path) -> None:
    print("RUNNING=" + " ".join(command[:3]))
    subprocess.run(command, cwd=str(cwd), check=True, timeout=300)


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
    if staged_root.is_symlink() or not staged_root.is_dir():
        raise RuntimeError("backend staging root is missing or unsafe")
    for relative in ALL_FILES:
        assert_regular(staged_root / relative, "backend staged file")
    # Fail before touching live application files or its database schema.
    closure = check_schema_closure(ROOT, staged_root)
    print("MOJ_PROP_SCHEMA_CLOSURE=PASS; MIGRATIONS=" + ",".join(closure["source_chain"]))
    print("MOJ_PROP_DB_RESTORE_EVIDENCE=INDEPENDENTLY_REQUIRED")

    backup = BACKUP_ROOT / run_id
    if backup.exists():
        raise RuntimeError(f"refusing to reuse backend backup: {backup}")
    backup.mkdir(parents=True, mode=0o700)
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


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        raise SystemExit("usage: script.py selftest [repo_root] | deploy RUN_ID COMMIT STAGED_ROOT | rollback RUN_ID")
    action = argv[1]
    if action == "selftest":
        selftest(Path(argv[2]).resolve() if len(argv) > 2 else Path.cwd())
        return 0
    if action == "deploy" and len(argv) == 5:
        deploy(argv[2], argv[3], Path(argv[4]).resolve())
        return 0
    if action == "rollback" and len(argv) == 3:
        restore(BACKUP_ROOT / validate_run_id(argv[2]))
        return 0
    raise SystemExit("invalid arguments")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))