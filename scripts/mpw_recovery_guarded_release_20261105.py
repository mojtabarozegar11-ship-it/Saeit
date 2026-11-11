#!/usr/bin/env python3
"""Guarded cPanel source stage for MPW-RECOVERY-01; email stays disabled.

Commands: preflight STAGE, publish STAGE RUN_ID DB_BACKUP_SHA256,
publish_additive STAGE RUN_ID, activate RUN_ID, verify, rollback RUN_ID.
Requires the existing cPanel Python 3.11 venv and trusted SSH relay. A dry-run
is read-only. The publish command writes ONLY reviewed code plus three new
tables after confirming migration 0039 is applied. Rollback restores code;
created tables are retained to avoid destructive loss of recovery claims.

This script is inert in GitHub: it never runs on push, PR or schedule.
"""
from __future__ import annotations

import ast
import gzip
import hashlib
import hmac
import json
import os
import pwd
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


APP = Path("/home/zomorod2/Saeit-staging")
PUBLIC = Path("/home/zomorod2/mojplaywin.com")
BACKUPS = Path("/home/zomorod2/.local/share/mpw-recovery-01-release")
ACCOUNT = "zomorod2"

FILES = {
    "guest": "services/mpw_trx_guest_commerce.py",
    "models": "core/models.py",
    "settings": "config/settings.py",
    "recovery": "services/mpw_trx_email_recovery.py",
    "recovery_models": "core/guest_recovery_models.py",
    "migration": "core/migrations/0049_mpw_guest_email_recovery.py",
    "cleanup": "core/management/commands/mpw_purge_recovery_ephemeral.py",
}
NEW_FILES = ("recovery", "recovery_models", "migration", "cleanup")
# C16: exact integrated guest/recovery source is cryptographically pinned; NEVER auto-enable email.
SOURCE_DIGESTS = {
    "guest": "9e6aca8d16a79968c32ec786377e3b9baf0dfd12ad8a8cd1f707cbd5809097ff",
    "recovery": "b359ff68da842a0dfc04f2a70f6e2b155a837bd34e68a336d98bcdc1b023661a",
    "recovery_models": "6c76a40a78ad1a91c28c4bcdbc4206034f1c45d45df76242858dc7840845fe76",
    "migration": "9913e106dee36cefab78137fb54936339c65bd68fefd6d72e616c36011866572",
    "cleanup": "0aa396229e2dec9212d0e358f6a21ff813d369405d1d253e64f17f8caf73f2d6",
}
# The live staging Passenger tree currently reports this exact reviewed
# baseline; keep the allowlist narrow so unrelated drift still aborts.
EXPECTED_GUEST_BASES = {
    "a9ea2dfc98809dc8991a5d8faf9a431d95b1c10cf4b33f174e69f9456a723d12",
    "8f16a9095cee3d39c7178d0d39d99f82e89d26ff05bcaef36019398cbf89625c",
    "151feafba4ec61c171920db79691d6dfca0dc3b6aef8f0326c22628b59ac46b9",
    "5b03b156464d631b8c543932bd9022f1177794e6ec46bf6c0f2955f6a19d10f2",
    "1740bb949311349e643adac10f524466e1bde8148a55149bc21d8016d9d55b40",
    "45815715bc66bc9e76f7135e27419ecc8abf1cff96a9971848fbe4018cbd3f42",
    "3577ec62ff1bbb9008560f04ac8118b249bcdd4e7d3206850caa697f902e5137",
    "931b3e2098bb9ef5c7fe29d1d71cd4bce49cb73093c101b0c3180c6443262ae7",
}
EXPECTED_LIVE_CORE_MIGRATIONS = ["0040_agenttask_bridge_idempotency","0041_factorymarketeligibility","0042_factory_p0_governance","0043_factory_execution_evidence","0044_factory_p0_release_integrity","0045_factory_evidence_freshness","0046_brandsite","0047_crypto_payments","0048_business_market_architecture"]
MODEL_MARKER = "# MPW_RECOVERY01_MODELS_20261105"
SETTING_MARKER = "# MPW_RECOVERY01_FLAGS_20261105"
MODEL_APPEND = (
    "\n" + MODEL_MARKER + "\n"
    "from .guest_recovery_models import GuestOrderEmail, GuestRecoveryToken, GuestRecoveryRate\n"
)
# Hard-coded OFF for the first stage. Enabling either flag is a separate,
# explicit and reviewed action, not a side effect of placing code on cPanel.
SETTING_APPEND = (
    "\n" + SETTING_MARKER + "\n"
    "MPW_GUEST_RECOVERY_ENABLED = False\n"
    "MPW_GUEST_RECOVERY_EMAIL_APPROVED = False\n"
)


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def fail(reason):
    raise RuntimeError("MPW_RECOVERY_RELEASE_ABORT:" + reason)


def _safe_file(path, *, existing=True):
    if path.is_symlink() or path.parent.is_symlink() or not path.parent.is_dir():
        fail("UNSAFE_FILE:" + path.name)
    if existing and (not path.is_file() or not path.stat().st_size):
        fail("MISSING_FILE:" + path.name)
    if not existing and path.exists():
        fail("TARGET_COLLISION:" + path.name)
    return path


def guard_host():
    if pwd.getpwuid(os.geteuid()).pw_name != ACCOUNT:
        fail("WRONG_ACCOUNT")
    for root in (APP, PUBLIC):
        if root.is_symlink() or not root.is_dir() or root.resolve() != root:
            fail("UNSAFE_APP_ROOT")
    wsgi = _safe_file(PUBLIC / "passenger_wsgi.py")
    if "APP='/home/zomorod2/Saeit-staging'" not in wsgi.read_text("utf-8", "replace"):
        fail("PASSENGER_APP_MISMATCH")
    htaccess = _safe_file(PUBLIC / ".htaccess")
    if htaccess.stat().st_size > 100000:
        fail("HTACCESS_UNSAFE")
    roots = re.findall(
        r"(?im)^\s*PassengerAppRoot\s+([^\r\n#]+)",
        htaccess.read_text("utf-8", "replace"),
    )
    if (len(roots) != 1 or roots[0].strip().strip('"').strip("'").rstrip("/")
            not in (str(PUBLIC), "mojplaywin.com")):
        fail("PASSENGER_ROOT_DRIFT")
    marker = PUBLIC / "tmp/restart.txt"
    if marker.is_symlink() or marker.parent.is_symlink() or not marker.parent.is_dir():
        fail("PASSENGER_RESTART_UNSAFE")
    for filename, hook in (
        ("services/mpw_trx_public_pages.py", "_mpw_patch_public(globals())"),
        ("services/mpw_trx_commercial_web.py", "_mpw_patch_commercial(globals())"),
    ):
        code = _safe_file(APP / filename).read_text("utf-8")
        if code.count(hook) != 1 or code.count("# MPW_GUEST_CHECKOUT_LIVE_V1") != 1:
            fail("EXISTING_GUEST_HOOK_DRIFT")
        if filename.endswith("mpw_trx_commercial_web.py"):
            # Recovery delegates to this *inner* delivery function, never to
            # the outer adapter that requires the buyer's missing old cookie.
            definitions = [node for node in ast.parse(code).body
                           if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                           and node.name == "_download_paid"]
            if len(definitions) != 1:
                fail("PRIVATE_DOWNLOAD_HANDLER_DRIFT")


def _source(stage, key):
    target = stage / FILES[key]
    _safe_file(target)
    if stage.is_symlink() or not stage.is_dir() or not target.resolve().is_relative_to(stage.resolve()):
        fail("UNSAFE_STAGE_ROOT")
    data = target.read_bytes()
    if len(data) > 75000 or digest(data) != SOURCE_DIGESTS[key]:
        fail("UNREVIEWED_SOURCE:" + key)
    compile(data.decode("utf-8"), str(target), "exec")
    return data



def verify_staged_recovery_migration_parent(stage):
    """Fail before any write when the reviewed 0049 parent is not on cPanel.

    The release tar includes the 0040 source for comparison only; this
    operation does not install the parent, migrate it, or inspect order rows.
    The host must already contain the exact reviewed parent migration.
    """
    relative_parent = Path("core/migrations/0040_commercefunnelevent.py")
    staged_parent = stage / relative_parent
    installed_parent = APP / relative_parent
    for root, path in ((stage, staged_parent), (APP, installed_parent)):
        if (root.is_symlink() or not root.is_dir() or path.is_symlink()
                or not path.resolve().is_relative_to(root.resolve())):
            fail("RECOVERY_MIGRATION_PARENT_PATH_UNSAFE")
        if not path.is_file() or not (100 < path.stat().st_size < 20_000):
            fail("RECOVERY_MIGRATION_PARENT_SOURCE_MISSING")
    staged_bytes = staged_parent.read_bytes()
    if installed_parent.read_bytes() != staged_bytes:
        fail("RECOVERY_MIGRATION_PARENT_SOURCE_DRIFT")
    try:
        compile(staged_bytes.decode("utf-8"), str(staged_parent), "exec")
        tree = ast.parse(_source(stage, "migration").decode("utf-8"))
        migration = next(node for node in tree.body
                         if isinstance(node, ast.ClassDef) and node.name == "Migration")
        dependency_node = next(stmt.value for stmt in migration.body
                               if isinstance(stmt, ast.Assign)
                               and any(isinstance(name, ast.Name) and name.id == "dependencies"
                                       for name in stmt.targets))
        dependencies = ast.literal_eval(dependency_node)
    except (StopIteration, SyntaxError, UnicodeDecodeError, ValueError, TypeError) as exc:
        fail("RECOVERY_MIGRATION_PARENT_UNVERIFIABLE")
    if ("core", "0040_commercefunnelevent") not in dependencies:
        fail("RECOVERY_MIGRATION_PARENT_MISMATCH")
    return True

def build_plan(stage):
    """Pure source transform: no writes, Django imports or DB access."""
    old = {}
    new = {}
    for key in FILES:
        path = APP / FILES[key]
        if key in NEW_FILES:
            staged = _source(stage, key)
            if path.exists():
                # A previous interrupted run may have left an exact reviewed
                # additive file behind. Reuse it only when its bytes match the
                # pinned source; any drift remains a hard collision.
                existing = _safe_file(path).read_bytes()
                if digest(existing) != digest(staged):
                    fail("TARGET_COLLISION:" + path.name)
                old[key] = existing
            else:
                old[key] = None
            new[key] = staged
        else:
            old[key] = _safe_file(path).read_bytes()

    if digest(old["guest"]) not in EXPECTED_GUEST_BASES:
        fail("UNRECOGNIZED_GUEST_BASE:" + digest(old["guest"]))
    new["guest"] = _source(stage, "guest")
    models = old["models"].decode("utf-8")
    settings = old["settings"].decode("utf-8")
    exact_models_patch = (
        models.count(MODEL_MARKER) == 1
        and models.count("from .guest_recovery_models import GuestOrderEmail, GuestRecoveryToken, GuestRecoveryRate") == 1
        and models.rstrip().endswith(MODEL_APPEND.rstrip())
    )
    exact_settings_patch = (
        settings.count(SETTING_MARKER) == 1
        and settings.count("MPW_GUEST_RECOVERY_ENABLED = False") == 1
        and settings.count("MPW_GUEST_RECOVERY_EMAIL_APPROVED = False") == 1
        and "MPW_GUEST_RECOVERY_ENABLED = True" not in settings
        and "MPW_GUEST_RECOVERY_EMAIL_APPROVED = True" not in settings
    )
    active_settings_patch = (
        settings.count(SETTING_MARKER) == 1
        and settings.count("MPW_GUEST_RECOVERY_ENABLED = True") == 1
        and settings.count("MPW_GUEST_RECOVERY_EMAIL_APPROVED = True") == 1
        and "MPW_GUEST_RECOVERY_ENABLED = False" not in settings
        and "MPW_GUEST_RECOVERY_EMAIL_APPROVED = False" not in settings
    )
    has_any_recovery_patch = (
        MODEL_MARKER in models or SETTING_MARKER in settings
        or "from .guest_recovery_models import" in models
        or "MPW_GUEST_RECOVERY_ENABLED" in settings
    )
    if has_any_recovery_patch:
        # Idempotent continuation is allowed only for the exact reviewed
        # disabled patch or its exact already-approved active state.
        if not (exact_models_patch and (exact_settings_patch or active_settings_patch)):
            fail("EXISTING_RECOVERY_PATCH_DRIFT")
        new["models"] = old["models"]
        new["settings"] = old["settings"]
    else:
        if (models.count("class Order(") != 1 or
                models.count("class PaymentIntent(") != 1 or
                "env.bool" not in settings or "DEFAULT_FROM_EMAIL" not in settings):
            fail("DJANGO_MODEL_OR_SETTINGS_DRIFT")
        new["models"] = (models.rstrip() + MODEL_APPEND).encode("utf-8")
        new["settings"] = (settings.rstrip() + SETTING_APPEND).encode("utf-8")
    for key in ("models", "settings"):
        compile(new[key].decode("utf-8"), key, "exec")
    return old, new


CHECK_DB = r'''
import json,os
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django;django.setup()
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.conf import settings
applied=set(MigrationRecorder(connection).applied_migrations())
names=set(connection.introspection.table_names())
forward=sorted(name for app,name in applied if app=="core"
               and len(name)>=4 and name[:4].isdigit() and int(name[:4])>=40
               and name!="0049_mpw_guest_email_recovery")
print(json.dumps({"vendor":connection.vendor,
 "m39":("core","0039_educationassessment_educationattempt_and_more") in applied,
 "m49":("core","0049_mpw_guest_email_recovery") in applied,
 "unreviewed_core_migrations":forward,
 "tables":[t for t in ("core_guestorderemail","core_guestrecoverytoken","core_guestrecoveryrate") if t in names],
 "enabled":getattr(settings,"MPW_GUEST_RECOVERY_ENABLED",False) is True,
 "mail":getattr(settings,"MPW_GUEST_RECOVERY_EMAIL_APPROVED",False) is True},sort_keys=True))
'''


def db_state():
    # Only schema and migration metadata; no customer, token or payment rows.
    proc = subprocess.run([sys.executable, "-B", "-c", CHECK_DB],
                          cwd=APP, capture_output=True, text=True, timeout=90,
                          env={**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings",
                               "PYTHONDONTWRITEBYTECODE": "1"})
    if proc.returncode != 0:
        fail("DB_PREFLIGHT_UNAVAILABLE")
    try:
        return json.loads(proc.stdout.strip())
    except ValueError:
        fail("DB_PREFLIGHT_UNEXPECTED_OUTPUT")



def classify_migration_lineage(report):
    """Classify migration metadata, not permission to change a live schema."""
    if not isinstance(report, dict):
        return "unknown_metadata"
    migrations = report.get("unreviewed_core_migrations")
    if (not isinstance(migrations, list) or
            any(not isinstance(name, str) for name in migrations)):
        return "unknown_metadata"
    if report.get("vendor") != "mysql" or report.get("m39") is not True:
        return "unexpected_database_baseline"
    parent = "0040_commercefunnelevent"
    competing = [name for name in migrations
                 if name.startswith("0040_") and name != parent]
    if parent in migrations and competing:
        return "competing_0040_branches"
    if migrations == EXPECTED_LIVE_CORE_MIGRATIONS and parent not in migrations:
        return "known_factory_branch_needs_reconciliation"
    if parent in migrations:
        return "reviewed_recovery_parent_recorded_verify_other_gates"
    return "unrecognized_migration_lineage"


def audit_host_read_only():
    """Report cPanel migration metadata; no staging, mail, restart or writes."""
    guard_host()
    report = db_state()
    classification = classify_migration_lineage(report)
    migrations = report.get("unreviewed_core_migrations")
    print("MPW_RECOVERY01_READONLY_LINEAGE=" + json.dumps({
        "classification": classification,
        "release_authorized": False,
        "migration_names_only": migrations,
        "required_parent_applied": (
            isinstance(migrations, list) and
            "0040_commercefunnelevent" in migrations),
        "recovery_migration_applied": report.get("m49"),
        "recovery_tables_present": report.get("tables"),
        "recovery_flag_enabled": report.get("enabled"),
        "mail_flag_enabled": report.get("mail"),
    }, sort_keys=True), flush=True)
    return classification


def require_recorded_recovery_parent(report):
    """Reject an unapplied or parallel 0040 parent before any release mutation.

    A migration file being present on disk does not prove it is recorded in
    django_migrations. Read only the existing migration-name summary; never
    inspect buyers, payments or credentials.
    """
    parent = "0040_commercefunnelevent"
    applied = report.get("unreviewed_core_migrations")
    if not isinstance(applied, list) or parent not in applied:
        fail("RECOVERY_MIGRATION_PARENT_NOT_APPLIED")
    competing = [name for name in applied
                 if isinstance(name, str) and name.startswith("0040_")
                 and name != parent]
    if competing:
        fail("RECOVERY_MIGRATION_0040_BRANCH_CONFLICT")
    return True


def require_before_schema():
    report = db_state()
    before = {"vendor": "mysql", "m39": True, "m49": False,
              "unreviewed_core_migrations": EXPECTED_LIVE_CORE_MIGRATIONS, "tables": [],
              "enabled": False, "mail": False}
    post_additive = {"vendor": "mysql", "m39": True, "m49": True,
                     "unreviewed_core_migrations": EXPECTED_LIVE_CORE_MIGRATIONS,
                     "tables": ["core_guestorderemail", "core_guestrecoverytoken",
                                "core_guestrecoveryrate"],
                     "enabled": False, "mail": False}
    post_additive_active = dict(post_additive, enabled=True, mail=True)
    # Permit only the exact pre-migration baseline or the exact already-staged
    # additive state. Any customer/payment/schema drift remains a hard stop.
    if report not in (before, post_additive, post_additive_active):
        fail("MIGRATION_BASELINE_DRIFT:" + json.dumps(report, sort_keys=True, separators=(",", ":")))
    require_recorded_recovery_parent(report)
    return report


def require_db_snapshot_evidence(run, expected_sha):
    """Demand a recent, private, integrity-checked SQL dump before any DDL.

    The snapshot must already exist: this release never exports customer data,
    invokes a backup command or declares an untested restore successful.
    """
    if (not re.fullmatch(r"[0-9]{8,20}", run) or
            not re.fullmatch(r"[0-9a-f]{64}", expected_sha)):
        fail("INVALID_DB_BACKUP_ATTESTATION")
    folder = BACKUPS / "db"
    snapshot = folder / (run + ".sql.gz")
    for ancestor in (folder, *folder.parents):
        if ancestor.is_symlink():
            fail("DB_BACKUP_SYMLINK")
        if ancestor == Path("/home") / ACCOUNT:
            break
    if folder.is_symlink() or not folder.is_dir():
        fail("DB_BACKUP_MISSING")
    if stat.S_IMODE(folder.stat().st_mode) & 0o077:
        fail("DB_BACKUP_DIR_NOT_PRIVATE")
    _safe_file(snapshot)
    st = snapshot.stat()
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or
            st.st_nlink != 1 or stat.S_IMODE(st.st_mode) & 0o077 or
            st.st_size < 4096 or st.st_size > 5 * 1024**3):
        fail("DB_BACKUP_UNSAFE")
    import time
    if not 0 <= time.time() - st.st_mtime <= 24 * 3600:
        fail("DB_BACKUP_STALE")
    checksum = hashlib.sha256()
    try:
        with snapshot.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                checksum.update(chunk)
        if not hmac.compare_digest(checksum.hexdigest(), expected_sha):
            fail("DB_BACKUP_DIGEST_MISMATCH")
        # Read through the gzip CRC; reject a truncated or non-SQL artifact.
        signatures = (b"CREATE TABLE", b"core_order", b"core_paymentintent")
        seen = [False] * len(signatures)
        tail = b""
        with gzip.open(snapshot, "rb") as stream:
            while chunk := stream.read(1024 * 1024):
                sample = tail + chunk
                for idx, signature in enumerate(signatures):
                    seen[idx] |= signature in sample
                tail = sample[-64:]
        if not all(seen):
            fail("DB_BACKUP_SQL_INCOMPLETE")
    except (OSError, EOFError, ValueError) as exc:
        fail("DB_BACKUP_UNREADABLE:" + type(exc).__name__)
    return True


def _atomic(path, content, *, expected=None):
    _safe_file(path, existing=expected is not None)
    if expected is not None and digest(path.read_bytes()) != expected:
        fail("CONCURRENT_FILE_EDIT:" + path.name)
    fd, temporary = tempfile.mkstemp(prefix=".mpw-recovery-", dir=path.parent)
    try:
        mode = stat.S_IMODE(path.stat().st_mode) if expected is not None else 0o600
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        dirfd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def restart():
    path = PUBLIC / "tmp/restart.txt"
    if path.is_symlink() or path.parent.is_symlink() or not path.parent.is_dir():
        fail("UNSAFE_RESTART")
    path.touch()


def private_backup(run, old, new):
    if not re.fullmatch(r"[0-9]{8,20}", run):
        fail("INVALID_RUN_ID")
    # A symlinked .local/share ancestor could redirect a private backup into a
    # public or untrusted directory even when BACKUPS itself is not a symlink.
    account_root = Path("/home") / ACCOUNT
    for ancestor in (BACKUPS, *BACKUPS.parents):
        if ancestor == account_root:
            break
        if ancestor.is_symlink():
            fail("UNSAFE_BACKUP_ANCESTOR")
    BACKUPS.mkdir(parents=True, mode=0o700, exist_ok=True)
    if BACKUPS.is_symlink() or stat.S_IMODE(BACKUPS.stat().st_mode) & 0o077:
        fail("UNSAFE_BACKUP_DIR")
    folder = BACKUPS / run
    if folder.exists() or folder.is_symlink():
        fail("BACKUP_RUN_COLLISION")
    folder.mkdir(mode=0o700)
    manifest = {
        "run": run, "schema": "new_tables_only_keep_on_rollback",
        "before": {k: digest(v) if v is not None else None for k, v in old.items()},
        "after": {k: digest(v) for k, v in new.items()},
    }
    for key, payload in old.items():
        if payload is not None:
            path = folder / (key + ".before")
            with path.open("xb") as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
    path = folder / "manifest.json"
    with path.open("x") as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(manifest, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    return folder, manifest


def restore(folder, manifest, *, changed):
    # Restore only our exact still-present release bytes. Never overwrite a
    # newer administrator edit, even when recovering a partial failure.
    for key in reversed(changed):
        if key not in manifest.get("after", {}):
            continue
        path = APP / FILES[key]
        current = _safe_file(path).read_bytes()
        if digest(current) != manifest["after"][key]:
            fail("ROLLBACK_SOURCE_DRIFT:" + key)
        before = manifest["before"][key]
        if before is None:
            path.unlink()
        else:
            payload = _safe_file(folder / (key + ".before")).read_bytes()
            if digest(payload) != before:
                fail("BACKUP_CORRUPT:" + key)
            _atomic(path, payload, expected=manifest["after"][key])


MIGRATE = r'''
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django;django.setup()
from django.core.management import call_command
call_command("migrate","core","0049_mpw_guest_email_recovery",interactive=False,verbosity=0)
'''


def migrate_new_tables():
    proc = subprocess.run([sys.executable, "-B", "-c", MIGRATE],
                          cwd=APP, capture_output=True, text=True, timeout=150,
                          env={**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings",
                               "PYTHONDONTWRITEBYTECODE": "1"})
    if proc.returncode != 0:
        fail("MIGRATION_EXECUTION_FAILED")



def publish_additive(stage, run):
    """Install only the additive recovery release without a full DB dump.

    This mode is deliberately narrower than publish(): it requires the exact
    pre-migration schema baseline, writes only reviewed source files plus a
    private code manifest, runs one migration that creates three empty recovery
    tables, and verifies both tables and flags afterward. It never exports,
    reads or changes customer/order/payment rows. The public route and email
    flag remain hard-coded OFF.
    """
    guard_host()
    verify_staged_recovery_migration_parent(stage)
    old, new = build_plan(stage)
    baseline = require_before_schema()
    folder, manifest = private_backup(run, old, new)
    changed = []
    order = ("recovery", "recovery_models", "migration", "cleanup",
             "models", "guest", "settings")
    try:
        for key in order:
            _atomic(APP / FILES[key], new[key], expected=manifest["before"][key])
            changed.append(key)
        if baseline["m49"] is False:
            migrate_new_tables()
        report = db_state()
        flags_off = report["enabled"] is False and report["mail"] is False
        flags_active = report["enabled"] is True and report["mail"] is True
        if not (report["vendor"] == "mysql" and report["m49"] is True and
                report["unreviewed_core_migrations"] == EXPECTED_LIVE_CORE_MIGRATIONS and
                len(report["tables"]) == 3 and (flags_off or flags_active)):
            fail("POST_ADDITIVE_MIGRATION_STATE_DRIFT")
        restart()
    except BaseException:
        restore(folder, manifest, changed=changed)
        restart()
        raise
    print("MPW_RECOVERY01_ADDITIVE_CODE_AND_SCHEMA_STAGED;"
          "EMAIL_ENABLED=FALSE;PUBLIC_RECOVERY_ENABLED=FALSE;"
          "PAYMENTS_CREATED=0;ORDERS_CREATED=0;CUSTOMER_ROWS_READ=0")


def publish(stage, run, backup_sha):
    guard_host()
    verify_staged_recovery_migration_parent(stage)
    old, new = build_plan(stage)
    require_before_schema()
    require_db_snapshot_evidence(run, backup_sha)
    folder, manifest = private_backup(run, old, new)
    changed = []
    order = ("recovery", "recovery_models", "migration", "cleanup",
             "models", "guest", "settings")
    try:
        for key in order:
            _atomic(APP / FILES[key], new[key], expected=manifest["before"][key])
            changed.append(key)
        migrate_new_tables()
        report = db_state()
        if not (report["vendor"] == "mysql" and report["m49"] is True and
                report["unreviewed_core_migrations"] == EXPECTED_LIVE_CORE_MIGRATIONS and len(report["tables"]) == 3 and
                report["enabled"] is False and report["mail"] is False):
            fail("POST_MIGRATION_STATE_DRIFT")
        restart()
    except BaseException:
        restore(folder, manifest, changed=changed)
        restart()
        raise
    print("MPW_RECOVERY01_CODE_AND_SCHEMA_STAGED;EMAIL_ENABLED=FALSE;"
          "PUBLIC_RECOVERY_ENABLED=FALSE;PAYMENTS_CREATED=0;ORDERS_CREATED=0")


def rollback(run):
    guard_host()
    if not re.fullmatch(r"[0-9]{8,20}", run):
        fail("INVALID_RUN_ID")
    folder = BACKUPS / run
    if folder.is_symlink() or not folder.is_dir():
        fail("BACKUP_MISSING")
    meta = json.loads(_safe_file(folder / "manifest.json").read_text("utf-8"))
    if meta.get("run") != run or meta.get("schema") != "new_tables_only_keep_on_rollback":
        fail("BACKUP_MANIFEST_INVALID")
    restore(folder, meta, changed=["recovery", "recovery_models", "migration",
                                   "cleanup", "models", "guest", "settings"])
    restart()
    print("MPW_RECOVERY01_CODE_ROLLED_BACK;SCHEMA_TABLES_RETAINED=TRUE")


def activate(run):
    """Open the already staged recovery route after explicit owner approval."""
    guard_host()
    require_recorded_recovery_parent(db_state())
    if not re.fullmatch(r"[0-9]{8,20}", run):
        fail("INVALID_RUN_ID")
    path = APP / FILES["settings"]
    old = _safe_file(path).read_bytes()
    text = old.decode("utf-8")
    if text.count(SETTING_MARKER) != 1:
        fail("RELEASE_SOURCE_PATCH_MISSING:settings")
    if "MPW_GUEST_RECOVERY_ENABLED = False" not in text or "MPW_GUEST_RECOVERY_EMAIL_APPROVED = False" not in text:
        fail("RECOVERY_FLAGS_NOT_OFF")
    new = text.replace("MPW_GUEST_RECOVERY_ENABLED = False", "MPW_GUEST_RECOVERY_ENABLED = True", 1)
    new = new.replace("MPW_GUEST_RECOVERY_EMAIL_APPROVED = False", "MPW_GUEST_RECOVERY_EMAIL_APPROVED = True", 1).encode("utf-8")
    folder, manifest = private_backup(run, {"settings": old}, {"settings": new})
    try:
        _atomic(path, new, expected=manifest["before"]["settings"])
        restart()
        report = db_state()
        if not (report["enabled"] and report["mail"]):
            fail("RECOVERY_FLAGS_NOT_ACTIVE")
        import time, urllib.request
        last_status = None
        for attempt in range(1, 7):
            try:
                with urllib.request.urlopen("https://mojplaywin.com/commerce/trx-easy/recover/", timeout=25) as response:
                    last_status = response.status
            except urllib.error.HTTPError as exc:
                last_status = exc.code
            if last_status == 200:
                break
            if attempt < 6:
                time.sleep(5)
        if last_status != 200:
            # Emit a bounded local resolver diagnostic before rollback. This
            # distinguishes missing Django registration from public Passenger
            # routing/cache behavior without reading customer data.
            diag = r'''
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django; django.setup()
from django.urls import get_resolver
import inspect, importlib
target = "/commerce/trx-easy/recover/"
try:
    mod = importlib.import_module("services.mpw_trx_public_pages")
    src = inspect.getsource(mod).splitlines()
    selected = [line for line in src if any(token in line.lower()
                for token in ("trx-easy", "urlpattern", "pattern", "start_order",
                              "invoice", "download", "def "))]
    print("MPW_PUBLIC_PAGES_SOURCE_HINT=" + repr(selected[:120]))
except Exception as exc:
    print("MPW_PUBLIC_PAGES_SOURCE_HINT_ERROR=" + type(exc).__name__ + ":" + str(exc)[:240])
hits = []
def walk(patterns, prefix=""):
    for p in patterns:
        route = getattr(p, "pattern", None)
        text = str(route) if route is not None else ""
        full = prefix + text
        if hasattr(p, "url_patterns"):
            module = getattr(getattr(p, "urlconf_module", None), "__file__", None)
            if "trx-easy" in full:
                hits.append({"include": full, "module": module,
                             "patterns": [str(getattr(x, "pattern", "")) for x in p.url_patterns[:30]]})
            walk(p.url_patterns, full)
        elif "recover" in full or "trx-easy" in full:
            hits.append({"route": full, "callback": getattr(getattr(p, "callback", None), "__module__", None)})
walk(get_resolver().url_patterns)
print("MPW_RECOVERY_LOCAL_RESOLVER=" + repr({"target": target, "hits": hits[:40]}))
'''
            try:
                probe = subprocess.run([sys.executable, "-B", "-c", diag],
                                       cwd=APP, capture_output=True, text=True,
                                       timeout=30, env={**os.environ,
                                       "DJANGO_SETTINGS_MODULE":"config.settings",
                                       "PYTHONDONTWRITEBYTECODE":"1"})
                print((probe.stdout or "").strip())
            except Exception as exc:
                print("MPW_RECOVERY_LOCAL_RESOLVER_ERROR=" + type(exc).__name__)
            fail("RECOVERY_ROUTE_NOT_READY:" + str(last_status))
    except BaseException:
        restore(folder, manifest, changed=["settings"])
        restart()
        raise
    print("MPW_RECOVERY01_ACTIVE;PUBLIC_RECOVERY_ENABLED=TRUE;OUTBOUND_EMAIL=TRUE;PAYMENTS_CREATED=0;ORDERS_CREATED=0")

def disable_flags(run):
    """Fail-closed disable of recovery/email flags only."""
    guard_host()
    if not re.fullmatch(r"[0-9]{8,20}", run):
        fail("INVALID_RUN_ID")
    path = APP / FILES["settings"]
    old = _safe_file(path).read_bytes()
    text = old.decode("utf-8")
    if text.count(SETTING_MARKER) != 1:
        fail("RELEASE_SOURCE_PATCH_MISSING:settings")
    if "MPW_GUEST_RECOVERY_ENABLED = True" not in text or "MPW_GUEST_RECOVERY_EMAIL_APPROVED = True" not in text:
        fail("RECOVERY_FLAGS_NOT_ACTIVE")
    new = text.replace("MPW_GUEST_RECOVERY_ENABLED = True", "MPW_GUEST_RECOVERY_ENABLED = False", 1)
    new = new.replace("MPW_GUEST_RECOVERY_EMAIL_APPROVED = True", "MPW_GUEST_RECOVERY_EMAIL_APPROVED = False", 1).encode("utf-8")
    folder, manifest = private_backup(run, {"settings": old}, {"settings": new})
    try:
        _atomic(path, new, expected=manifest["before"]["settings"])
        restart()
        report = db_state()
        if report["enabled"] or report["mail"]:
            fail("RECOVERY_FLAGS_NOT_DISABLED")
    except BaseException:
        restore(folder, manifest, changed=["settings"])
        restart()
        raise
    print("MPW_RECOVERY01_DISABLED;PUBLIC_RECOVERY_ENABLED=FALSE;OUTBOUND_EMAIL=FALSE;PAYMENTS_CREATED=0;ORDERS_CREATED=0")


def verify():
    guard_host()
    report = db_state()
    require_recorded_recovery_parent(report)
    if (report["vendor"] != "mysql" or not report["m49"] or
            report["unreviewed_core_migrations"] != EXPECTED_LIVE_CORE_MIGRATIONS or
            len(report["tables"]) != 3 or report["enabled"] or report["mail"]):
        fail("RELEASE_NOT_SAFELY_STAGED")
    for key in SOURCE_DIGESTS:
        if digest(_safe_file(APP / FILES[key]).read_bytes()) != SOURCE_DIGESTS[key]:
            fail("RELEASE_SOURCE_DRIFT:" + key)
    for key, marker in (("models", MODEL_MARKER), ("settings", SETTING_MARKER)):
        if _safe_file(APP / FILES[key]).read_text("utf-8").count(marker) != 1:
            fail("RELEASE_SOURCE_PATCH_MISSING:" + key)
    print("MPW_RECOVERY01_STAGED_VERIFIED;PUBLIC_ROUTES=OFF;OUTBOUND_EMAIL=OFF")


def main(argv):
    if len(argv) == 2 and argv[1] == "audit":
        audit_host_read_only()
    elif len(argv) == 3 and argv[1] == "preflight":
        guard_host()
        # Read-only summary to distinguish an existing reviewed marker from
        # partial source staging; report no customer, payment or secret data.
        models_text = _safe_file(APP / FILES["models"]).read_text("utf-8")
        settings_text = _safe_file(APP / FILES["settings"]).read_text("utf-8")
        print("MPW_RECOVERY01_LIVE_SOURCE_FLAGS=" + json.dumps({
            "model_marker_count": models_text.count(MODEL_MARKER),
            "model_import_present": "from .guest_recovery_models import" in models_text,
            "setting_marker_count": settings_text.count(SETTING_MARKER),
            "recovery_flag_declaration": "MPW_GUEST_RECOVERY_ENABLED" in settings_text,
            "mail_flag_declaration": "MPW_GUEST_RECOVERY_EMAIL_APPROVED" in settings_text,
            "additive_files_present": sorted(
                key for key in NEW_FILES if (APP / FILES[key]).exists()),
        }, sort_keys=True), flush=True)
        print("MPW_RECOVERY01_LIVE_DB_STATE=" + json.dumps(db_state(), sort_keys=True),
              flush=True)
        verify_staged_recovery_migration_parent(Path(argv[2]))
        old, new = build_plan(Path(argv[2]))
        require_before_schema()
        print("MPW_RECOVERY01_PREFLIGHT=" + json.dumps({
            "changed_files": len(new),
            "existing_files": sum(value is not None for value in old.values()),
            "new_tables": 3,
            "outbound_email": False,
            "payments_or_orders_changed": False,
        }, sort_keys=True))
    elif len(argv) == 4 and argv[1] == "publish_additive":
        publish_additive(Path(argv[2]), argv[3])
    elif len(argv) == 5 and argv[1] == "publish":
        publish(Path(argv[2]), argv[3], argv[4])
    elif len(argv) == 3 and argv[1] == "activate":
        activate(argv[2])
    elif len(argv) == 3 and argv[1] == "disable_flags":
        disable_flags(argv[2])
    elif len(argv) == 2 and argv[1] == "verify":
        verify()
    elif len(argv) == 3 and argv[1] == "rollback":
        rollback(argv[2])
    else:
        raise SystemExit("Usage: release.py audit | preflight STAGE | publish_additive STAGE RUN_ID | publish STAGE RUN_ID DB_BACKUP_SHA256 | activate RUN_ID | verify | rollback RUN_ID")


if __name__ == "__main__":
    main(sys.argv)
