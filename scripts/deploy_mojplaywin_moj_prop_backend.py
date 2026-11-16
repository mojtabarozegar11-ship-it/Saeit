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
from scripts.mojprop_schema_preflight_c83 import check_schema_closure, migration_operations_signature
from scripts.mojprop_db_release_evidence import verify_database_restore_evidence


ROOT = Path("/home/zomorod2/Saeit-staging")
DOCROOT = Path("/home/zomorod2/mojplaywin.com")
BACKUP_ROOT = Path("/home/zomorod2/.mojplaywin-moj-prop-backups")
INDEPENDENT_DB_EVIDENCE_ROOT = Path("/home/zomorod2/.mojprop-private-db-restore-evidence")
URLCONF = Path("config/urls.py")
SETTINGSCONF = Path("config/settings.py")
FILES = (
    Path("core/models.py"),
    Path("core/admin.py"),
    # The no-JS presenter must be installed before the importing CRM view.
    Path("core/mojprop_accessible_intake.py"),
    Path("core/mojprop_views.py"),
    Path("core/mojprop_receipts.py"),
    Path("core/mojprop_catalog_contract.py"),
    Path("core/mojprop_workflow.py"),
    Path("core/mojprop_offer_draft.py"),
    Path("core/mojprop_quote_contract.py"),
    Path("core/mojprop_quote_views.py"),
    # The owner CRM sales queue was missing from the live cPanel tree (C95).
    # Ship as a rollback-tracked source module with the reviewed intake.
    Path("core/management/commands/mojprop_sales_action_queue.py"),
    Path("core/signal_free_models.py"),
    Path("core/guest_recovery_models.py"),
    Path("core/signal_free_views.py"),
    Path("core/migrations/0041_mojprop_request.py"),
    Path("core/migrations/0042_mojprop_offer.py"),
    Path("core/migrations/0043_mojprop_digital_inquiry.py"),
    Path("core/migrations/0044_mojprop_acceptance_evidence.py"),
    Path("core/migrations/0045_mojprop_delivery_evidence.py"),
    Path("core/migrations/0046_signal_free_subscription.py"),
    Path("core/migrations/0047_mpw_guest_email_recovery.py"),
    Path("scripts/mojprop_schema_preflight_c83.py"),
    Path("scripts/mojprop_db_release_evidence.py"),
    Path("scripts/mojprop_live_database_identity_c85.py"),
)
ALL_FILES = (URLCONF, SETTINGSCONF) + FILES
REPLACE_FILES = tuple(path for path in FILES if path not in (
    Path("core/models.py"), Path("core/admin.py"),
    # Private evidence must be verified from the staged bundle, not installed
    # into the production application source tree.
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
        ("def action_queue_snapshot(", (repo_root / "core/management/commands/mojprop_sales_action_queue.py").read_text(encoding="utf-8")),
        ("mojprop_receipt_status", view),
        ("from .mojprop_receipts import", view),
        ("MojPropRequest", model),
        ('path("moj-prop-intake/"', urls),
        ('path("moj-prop-status/"', urls),
        ("get_token", view),
        ("_ip_hash", view),
        ("MojSignalFreeSubscription", (repo_root / "core/signal_free_models.py").read_text(encoding="utf-8")),
        ("MOJTABA_SIGNAL_FREE_SIGNUP_ENABLED", (repo_root / SETTINGSCONF).read_text(encoding="utf-8")),
        ('path("moj-signal-free-subscribe/"', urls),
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
    assert_safe_parent(target, ROOT)
    # A dangling symlink reports exists() == False; never treat it as absent.
    if target.is_symlink():
        raise RuntimeError("unsafe live backend target symlink before backup")
    if target.exists():
        assert_regular(target, "live target")
        saved = backup / relative
        assert_safe_parent(saved, backup)
        saved.parent.mkdir(parents=True, exist_ok=True)
        original_sha = digest(target)
        shutil.copy2(target, saved)
        if digest(saved) != original_sha:
            raise RuntimeError("backend backup copy differs from live source")
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
    if target.is_symlink():
        raise RuntimeError("backend live replacement target became symlink")
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
    if "class MojPropRequest(" in live:
        print("MOJ_PROP_MODEL_ALREADY_PATCHED")
        return
    staged = source.read_text(encoding="utf-8")
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
    if "class MojPropRequestAdmin(" in live:
        print("MOJ_PROP_ADMIN_ALREADY_PATCHED")
        return
    staged = source.read_text(encoding="utf-8")
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


def patch_free_model_import(target: Path, source: Path) -> None:
    """Attach only the independently reviewed free model to the owner code."""
    assert_regular(target, "live model module")
    required = "from .signal_free_models import MojSignalFreeSubscription"
    if required not in source.read_text(encoding="utf-8"):
        raise RuntimeError("reviewed free subscription model import is missing")
    live = target.read_text(encoding="utf-8")
    if required in live:
        return
    if "from django.db import models" not in live:
        raise RuntimeError("unrecognized live models module")
    mode = stat.S_IMODE(target.stat().st_mode)
    atomic_write_text(target, live.rstrip() + "\n\n" + required + "\n", mode)
    print("SIGNAL_FREE_MODEL_IMPORT_INSTALLED")



def patch_recovery_model_import(target: Path, source: Path) -> None:
    """Install only the disabled recovery model import required by current source."""
    assert_regular(target, "live recovery model module")
    assert_regular(source, "staged recovery model source")
    required = "from .guest_recovery_models import GuestOrderEmail, GuestRecoveryToken, GuestRecoveryRate"
    if required not in source.read_text(encoding="utf-8"):
        raise RuntimeError("reviewed recovery model import is missing")
    live = target.read_text(encoding="utf-8")
    if required in live:
        return
    if "from django.db import models" not in live:
        raise RuntimeError("live models module has no safe recovery import anchor")
    mode = stat.S_IMODE(target.stat().st_mode)
    atomic_write_text(target, live.rstrip() + "\n\n" + required + "\n", mode)
    print("MPW_RECOVERY_MODEL_IMPORT_INSTALLED")


def patch_free_admin_readonly(target: Path, source: Path) -> None:
    """Do not grant any action that could subscribe, email or charge buyers."""
    assert_regular(target, "live admin")
    live = target.read_text(encoding="utf-8")
    if "class MojSignalFreeSubscriptionAdmin(" in live:
        return
    staged = source.read_text(encoding="utf-8")
    marker = "\nfrom .signal_free_models import MojSignalFreeSubscription\n"
    if staged.count(marker) != 1:
        raise RuntimeError("reviewed read-only free subscription admin missing")
    addon = staged[staged.index(marker) + 1:]
    if "class MojSignalFreeSubscriptionAdmin(" not in addon:
        raise RuntimeError("reviewed read-only admin class missing")
    mode = stat.S_IMODE(target.stat().st_mode)
    atomic_write_text(target, live.rstrip() + "\n\n" + addon.rstrip() + "\n", mode)
    print("SIGNAL_FREE_READONLY_ADMIN_INSTALLED")


def patch_free_settings(target: Path, source: Path) -> None:
    """Never activate marketing when adding the strictly disabled setting."""
    assert_regular(target, "live settings")
    staged = source.read_text(encoding="utf-8")
    line = 'MOJTABA_SIGNAL_FREE_SIGNUP_ENABLED = env.bool("MOJTABA_SIGNAL_FREE_SIGNUP_ENABLED", default=False)'
    if line not in staged:
        raise RuntimeError("reviewed default-off signup setting missing")
    live = target.read_text(encoding="utf-8")
    if "MOJTABA_SIGNAL_FREE_SIGNUP_ENABLED" in live:
        if line not in live:
            raise RuntimeError("different live free signup feature flag requires review")
        return
    if "EMAIL_BACKEND" not in live or "env.bool" not in live:
        raise RuntimeError("live SMTP environment setting helpers are unrecognized")
    mode = stat.S_IMODE(target.stat().st_mode)
    atomic_write_text(target, live.rstrip() + "\n\n" + line + "\n", mode)
    print("SIGNAL_FREE_EMAIL_FLAG_DEFAULT_DISABLED")


def patch_free_urlconf(target: Path) -> None:
    """Add exactly three root-level routes; never depend on a static directory."""
    assert_regular(target, "live URL configuration")
    live = target.read_text(encoding="utf-8")
    expected = (
        'path("moj-signal-free-subscribe/"',
        'path("moj-signal-free-confirm/<str:token>/"',
        'path("moj-signal-free-unsubscribe/<str:token>/"',
    )
    matches = [marker in live for marker in expected]
    if all(matches):
        return
    if any(matches) or "from django.urls import" not in live or "urlpatterns" not in live:
        raise RuntimeError("partial or unsupported free membership URL configuration")
    addition = (
        "\n\n# One separate opt-in service for mojtaba.bot.ai education only.\n"
        "from core.signal_free_views import signal_free_subscribe, signal_free_confirm, signal_free_unsubscribe\n"
        "urlpatterns += [\n"
        '    path("moj-signal-free-subscribe/", signal_free_subscribe, name="moj_signal_free_subscribe"),\n'
        '    path("moj-signal-free-confirm/<str:token>/", signal_free_confirm, name="moj_signal_free_confirm"),\n'
        '    path("moj-signal-free-unsubscribe/<str:token>/", signal_free_unsubscribe, name="moj_signal_free_unsubscribe"),\n'
        "]\n"
    )
    mode = stat.S_IMODE(target.stat().st_mode)
    atomic_write_text(target, live.rstrip() + addition, mode)
    print("SIGNAL_FREE_ROOT_ENDPOINTS_INSTALLED")


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
    """Verify every saved file before any restore write; DB restore is separate."""
    if backup.is_symlink() or not backup.is_dir():
        raise RuntimeError("backend backup directory missing or unsafe")
    manifest_path = backup / "manifest.json"
    assert_regular(manifest_path, "backend backup manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if type(manifest) is not dict:
        raise RuntimeError("backend backup manifest must be a dictionary")
    if manifest.get("files") != [str(relative) for relative in ALL_FILES]:
        raise RuntimeError("backend backup inventory differs from pinned installer")
    if type(manifest.get("run_id")) is not str:
        raise RuntimeError("backend backup run_id is invalid")
    validate_run_id(manifest["run_id"])
    if manifest["run_id"] != backup.name:
        raise RuntimeError("backend backup run_id mismatch")
    if type(manifest.get("commit")) is not str:
        raise RuntimeError("backend backup commit is invalid")
    validate_commit(manifest["commit"])
    for relative in ALL_FILES:
        entry = manifest.get(str(relative))
        if type(entry) is not dict or type(entry.get("existed")) is not bool:
            raise RuntimeError("backend backup entry missing or invalid")
        saved = backup / relative
        assert_safe_parent(saved, backup)
        if entry["existed"]:
            sha = entry.get("sha256")
            mode = entry.get("mode")
            if type(sha) is not str or re.fullmatch(r"[0-9a-f]{64}", sha) is None:
                raise RuntimeError("backend saved source has invalid digest")
            if type(mode) is not int or not 0 <= mode <= 0o777:
                raise RuntimeError("backend saved source has invalid mode")
            assert_regular(saved, "backend saved source")
            if digest(saved) != sha:
                raise RuntimeError("backend saved source digest mismatch")
        elif saved.exists() or saved.is_symlink():
            raise RuntimeError("unexpected backup file for absent live source")
    return manifest


def mark_schema_migration_started(backup: Path) -> None:
    """Durably mark the backup unsafe for a source-only rollback BEFORE DDL.

    A later explicit 'rollback RUN_ID' must not bypass the deploy-time guard.
    Absence or corruption of the phase marker fails closed during restore.
    """
    manifest = verify_backup_manifest(backup)
    if manifest.get("schema_migration_attempted") is not False:
        raise RuntimeError("backup's pre-migration phase is not verified")
    manifest["schema_migration_attempted"] = True
    target = backup / "manifest.json"
    assert_regular(target, "pre-migration manifest")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".mojprop-schema-phase-", dir=str(backup)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(manifest, output, ensure_ascii=False, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
        directory_fd = os.open(str(backup), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()
    if verify_backup_manifest(backup).get("schema_migration_attempted") is not True:
        raise RuntimeError("schema migration phase marker was not persisted")


def restore(backup: Path) -> None:
    # Unlike file-by-file checks, a corrupt later file cannot partially revert
    # earlier live files. This is NOT a substitute for a DB restore.
    manifest = verify_backup_manifest(backup)
    if manifest.get("schema_migration_attempted") is not False:
        raise RuntimeError(
            "source-only rollback DENIED: database migration may have started; "
            "independent schema reconciliation and recovery are required"
        )
    for relative in ALL_FILES:
        entry = manifest[str(relative)]
        target = ROOT / relative
        assert_safe_parent(target, ROOT)
        if entry["existed"]:
            saved = backup / relative
            assert_regular(saved, "backend backup")
            if digest(saved) != entry["sha256"]:
                raise RuntimeError("backend backup changed during restore")
            atomic_replace(saved, target, int(entry["mode"]))
            if digest(target) != entry["sha256"]:
                raise RuntimeError("restored backend source hash mismatch")
        elif target.exists() or target.is_symlink():
            assert_regular(target, "unexpected target")
            target.unlink()
    restart_passenger()
    print("MOJ_PROP_BACKEND_ROLLBACK=PASS")


def recover_failed_deploy(backup: Path, *, schema_migration_attempted: bool) -> None:
    """Deny file-only rollback after attempting database schema changes.

    A failing migrate command may already have committed DDL. An independent
    DBA must reconcile database and application before source is rolled back.
    """
    if type(schema_migration_attempted) is not bool:
        raise RuntimeError("migration attempt state is unverified")
    if schema_migration_attempted:
        raise RuntimeError(
            "database migration attempted; automatic source-only rollback DENIED: "
            "hold release and independently reconcile or restore the database "
            "before changing application files"
        )
    restore(backup)


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
    if staged_root.is_symlink() or not staged_root.is_dir():
        raise RuntimeError("backend staging root is missing or unsafe")
    for relative in ALL_FILES:
        assert_regular(staged_root / relative, "backend staged file")
    # Fail before touching live application files or its database schema.
    closure = check_schema_closure(ROOT, staged_root)
    print("MOJ_PROP_SCHEMA_CLOSURE=PASS; MIGRATIONS=" + ",".join(closure["source_chain"]))
    print("MOJ_PROP_DB_RESTORE_EVIDENCE=INDEPENDENTLY_REQUIRED")
    # The reviewed commercial chain includes 0047 guest email recovery.
    # A source-only check NEVER substitutes for an isolated MariaDB restore.
    # Refuse an unknown later migration before backing up or writing files.
    migration_target = "0047_mpw_guest_email_recovery"
    if (closure["source_chain"][-1] != migration_target
            or closure["source_chain"] != [
                "0041_mojprop_request", "0042_mojprop_offer",
                "0043_mojprop_digital_inquiry",
                "0044_mojprop_acceptance_evidence",
                "0045_mojprop_delivery_evidence",
                "0046_signal_free_subscription",
                migration_target,
            ]):
        raise RuntimeError("Moj Prop backend installer schema target is stale; release denied")
    # Release requires a separately signed MariaDB *restore rehearsal* and a
    # fingerprint of the actual connected live DB. A workflow flag is not proof.
    require_independent_db_restore(run_id, commit, staged_root)

    backup = BACKUP_ROOT / run_id
    if backup.exists():
        raise RuntimeError(f"refusing to reuse backend backup: {backup}")
    backup.mkdir(parents=True, mode=0o700)
    manifest = {"run_id": run_id, "commit": commit, "files": [str(item) for item in ALL_FILES], "schema_migration_attempted": False}
    for relative in ALL_FILES:
        backup_target(ROOT / relative, backup, manifest, relative)
    (backup / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    verify_backup_manifest(backup)

    schema_migration_attempted = False
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
        patch_recovery_model_import(ROOT / Path("core/models.py"), staged_root / Path("core/models.py"))
        patch_admin(ROOT / Path("core/admin.py"), staged_root / Path("core/admin.py"))
        patch_urlconf(ROOT / URLCONF)
        patch_free_model_import(ROOT / Path("core/models.py"), staged_root / Path("core/models.py"))
        patch_free_admin_readonly(ROOT / Path("core/admin.py"), staged_root / Path("core/admin.py"))
        patch_free_settings(ROOT / SETTINGSCONF, staged_root / SETTINGSCONF)
        patch_free_urlconf(ROOT / URLCONF)

        python = choose_python()
        run_checked([str(python), "manage.py", "check", "--deploy"], ROOT)
        # Never run an unscoped 'migrate': that could apply other apps'
        # unreviewed pending DDL on the commercial production database.
        # Schema closure rejected any unknown core migration >=0041.
        # Set BEFORE launching migrations: DDL may be committed even if the
        # command errors or times out; never assume a clean schema rollback.
        mark_schema_migration_started(backup)
        schema_migration_attempted = True
        run_checked([str(python), "manage.py", "migrate",
                     "core", migration_target, "--noinput"], ROOT)
        run_checked([str(python), "manage.py", "collectstatic", "--noinput"], ROOT)

        restart_passenger()
        print("MOJ_PROP_BACKEND_DEPLOY=PASS")
        print("MOJ_PROP_BACKEND_COMMIT=" + commit)
        print("MOJ_PROP_BACKUP=" + str(backup))
    except Exception:
        # Preserve the original exception for pre-migration failures after
        # restoring files. A post-migration failure is held, not "rolled back".
        recover_failed_deploy(
            backup, schema_migration_attempted=schema_migration_attempted
        )
        raise


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        raise SystemExit("usage: script.py selftest [repo_root] | deploy RUN_ID COMMIT STAGED_ROOT | rollback RUN_ID")
    action = argv[1]
    if action == "selftest":
        selftest(Path(argv[2]).resolve() if len(argv) > 2 else Path.cwd())
        return 0
    if action == "verify-db-restore" and len(argv) == 5:
        require_independent_db_restore(argv[2], argv[3], Path(argv[4]).resolve())
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