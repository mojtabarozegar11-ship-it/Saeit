#!/usr/bin/env python3
"""Atomic, reversible main-domain-only release for the MPW QA coordinator.

Only three allowlisted MojPlayWin-specific source files and ONE marked Cron
entry can change. No public content, commerce, global URLs/settings, migrations,
or sibling domains are written. Passenger is deliberately not restarted because
its WSGI app is shared with protected child sites.
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone

TENANT = "mojplaywin-main"
SITE = Path("/home/zomorod2/mojplaywin.com")
APP = Path("/home/zomorod2/Saeit-staging")
PRIVATE = Path("/home/zomorod2/.private_mojplaywin_main_agents")
EVO = PRIVATE / "evolution_runtime_20261018"
OWN = EVO / "onepass_agent_quality"
RELEASES = OWN / "releases"
RUNNER = OWN / "mpw_onepass_private_evolution.py"
FILES = {
    "runner.py": RUNNER,
    "telemetry.py": APP / "command_center/mpw_private_telemetry.py",
    "dashboard.html": APP / "command_center/templates/command_center/mpw_agent_monitor.html",
}
MARK = "MPW_ONEPASS_QUALITY_MAIN_ONLY_20261019"
CRON = ("7,22,37,52 * * * * /usr/bin/flock -n " + str(OWN / "cron.lock")
        + " /usr/bin/python3 -B " + str(RUNNER)
        + " --once > " + str(OWN / "last_run.log") + " 2>&1 # " + MARK)
SCHEMA = "mpw.onepass.release.v1"


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def private(path):
    return path.is_dir() and not path.is_symlink() and path.stat().st_mode & 0o077 == 0


def atomic(path, content, mode=0o600):
    require(not path.is_symlink(), "SYMLINK_DESTINATION_BLOCKED")
    fd, temp = tempfile.mkstemp(prefix=".mpw-release-", dir=str(path.parent))
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.lexists(temp):
            os.unlink(temp)


def preflight():
    require(private(PRIVATE) and private(EVO), "INVALID_MPWS_PRIVATE_ROOT")
    require(os.geteuid() == PRIVATE.stat().st_uid, "WRONG_CPANEL_USER")
    require(APP.is_dir() and not APP.is_symlink() and SITE.is_dir()
            and not SITE.is_symlink(), "EXPECTED_MPWS_APP_MISSING")
    wsgi = SITE / "passenger_wsgi.py"
    htaccess = SITE / ".htaccess"
    require(not wsgi.is_symlink() and not htaccess.is_symlink()
            and wsgi.is_file() and htaccess.is_file(), "UNSAFE_PASSENGER_ROOT")
    require(("APP='" + str(APP) + "'") in wsgi.read_text("utf-8", "replace"),
            "ACTUAL_MOJPLAYWIN_PASSENGER_APP_DRIFT")
    require(("PassengerAppRoot " + str(SITE)) in htaccess.read_text("utf-8", "replace"),
            "ACTUAL_MOJPLAYWIN_DOCROOT_DRIFT")
    for target in FILES.values():
        require(not target.is_symlink(), "TARGET_SYMLINK_BLOCKED")
        if target == RUNNER:
            require(not OWN.is_symlink(), "RUNNER_PARENT_SYMLINK")
        else:
            require(target.parent.is_dir() and not target.parent.is_symlink(),
                    "TARGET_DIRECTORY_NOT_PRESENT")


def read_package(raw):
    require(5000 < len(raw) < 55_000, "MPW_PACKAGE_SIZE_INVALID")
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        names = archive.getnames()
        require(len(names) == 4 and set(names) == set(FILES) | {"manifest.json"},
                "UNEXPECTED_PACKAGE_MEMBERS")
        require(all(row.isfile() and not row.issym() and not row.islnk()
                    and 0 < row.size < 30000 for row in archive.getmembers()),
                "UNSAFE_RELEASE_ARCHIVE")
        manifest = json.load(archive.extractfile("manifest.json"))
        require(manifest.get("tenant") == TENANT and manifest.get("schema") == SCHEMA,
                "WRONG_TENANT_RELEASE")
        hashes = manifest.get("sha256")
        require(isinstance(hashes, dict) and set(hashes) == set(FILES),
                "BAD_RELEASE_MANIFEST")
        payload = {}
        for name in FILES:
            data = archive.extractfile(name).read()
            require(hashlib.sha256(data).hexdigest() == hashes[name],
                    "RELEASE_ARTIFACT_SHA_MISMATCH:" + name)
            if name.endswith(".py"):
                compile(data, name, "exec")
            else:
                require(b'MojPlayWin' in data and b'mpw_agent_monitor_api' in data,
                        "UNEXPECTED_MAIN_PANEL_TEMPLATE")
            payload[name] = data
        require(b"mpw.onepass.agent_quality.v1" in payload["runner.py"],
                "RUNNER_SCHEMA_MISMATCH")
        return payload


def current_cron():
    proc = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=15)
    require(proc.returncode == 0, "CANNOT_READ_TENANT_CRONTAB")
    return proc.stdout


def set_cron(raw):
    proc = subprocess.run(["crontab", "-"], input=raw, capture_output=True, text=True, timeout=15)
    require(proc.returncode == 0, "TENANT_CRONTAB_WRITE_FAILED")


def stage_backup(release, old, cron):
    release.mkdir(mode=0o700, parents=False, exist_ok=False)
    snap = {}
    for name, target in FILES.items():
        found = target.is_file() and not target.is_symlink()
        before = target.read_bytes() if found else None
        require(before is None or len(before) < 50_000, "SOURCE_NOT_SAFE:" + name)
        snap[name] = {
            "exists": found,
            "sha256": hashlib.sha256(before).hexdigest() if found else None,
            "mode": stat.S_IMODE(target.stat().st_mode) if found else 0o600,
        }
        if found:
            atomic(release / (name + ".old"), before)
    atomic(release / "crontab.old", cron.encode("utf-8"))
    return snap


def restore(release, *, require_installed_hashes=False):
    manifest_path = release / "release.json"
    require(manifest_path.is_file() and not manifest_path.is_symlink(), "ROLLBACK_RELEASE_MANIFEST_MISSING")
    snap = json.loads(manifest_path.read_text("utf-8"))
    require(snap.get("tenant") == TENANT and snap.get("schema") == SCHEMA and
            set(snap.get("originals", {})) == set(FILES), "ROLLBACK_TENANT_OR_SCOPE_INVALID")
    if require_installed_hashes:
        for name, target in FILES.items():
            if target.is_file():
                require(hashlib.sha256(target.read_bytes()).hexdigest() ==
                        snap["installed_sha256"][name], "ROLLBACK_SOURCE_DRIFT:" + name)
    for name, target in FILES.items():
        previous = snap["originals"][name]
        if previous["exists"]:
            backup = release / (name + ".old")
            require(backup.is_file() and not backup.is_symlink()
                    and hashlib.sha256(backup.read_bytes()).hexdigest() == previous["sha256"],
                    "ROLLBACK_BACKUP_HASH_MISMATCH:" + name)
            atomic(target, backup.read_bytes(), previous["mode"])
        elif target.is_file() and not target.is_symlink():
            target.unlink()
    before = (release / "crontab.old").read_text("utf-8")
    existing = current_cron()
    current_marker = [line for line in existing.splitlines() if MARK in line]
    # Do not discard any other tenant's new jobs installed in the meantime.
    old_markers = [line for line in before.splitlines() if MARK in line]
    if current_marker == [CRON] and not old_markers:
        filtered = "\n".join(line for line in existing.splitlines() if MARK not in line)
        set_cron(filtered.rstrip("\n") + "\n")
    elif current_marker:
        raise RuntimeError("ROLLBACK_CRON_OWNERSHIP_DRIFT")
    atomic(release / "rolled_back.json", json.dumps({"tenant": TENANT, "done": True}).encode())
    return {"tenant": TENANT, "status": "scoped_sources_restored", "passenger_restarted": False,
            "other_site_files_touched": False}


def install(run_id, expected, stream):
    preflight()
    require(re.fullmatch(r"[0-9a-f]{64}", expected) is not None, "EXPECTED_BUNDLE_SHA_REQUIRED")
    raw = stream.read(55_001)
    require(hashlib.sha256(raw).hexdigest() == expected, "BUNDLE_DIGEST_MISMATCH")
    payload = read_package(raw)
    OWN.mkdir(mode=0o700, exist_ok=True)
    require(private(OWN) and not RELEASES.is_symlink(), "UNSAFE_MPWS_ONEPASS_DIR")
    RELEASES.mkdir(mode=0o700, exist_ok=True)
    require(private(RELEASES), "UNSAFE_BACKUP_DIRECTORY")
    old_cron = current_cron()
    old_markers = [line for line in old_cron.splitlines() if MARK in line]
    require(not old_markers or old_markers == [CRON], "EXISTING_QA_CRON_CONFLICT")
    release = RELEASES / run_id
    require(not release.exists() and not release.is_symlink(), "RELEASE_ALREADY_EXISTS")
    originals = stage_backup(release, {}, old_cron)
    record = {"schema": SCHEMA, "tenant": TENANT, "run_id": run_id,
              "originals": originals, "installed_sha256": {
                  key: hashlib.sha256(raw).hexdigest() for key, raw in payload.items()},
              "created_utc": datetime.now(timezone.utc).isoformat(),
              "automatic_sibling_restart": False}
    atomic(release / "release.json", json.dumps(record, sort_keys=True).encode())
    try:
        require(current_cron() == old_cron, "CONCURRENT_CRON_CHANGE")
        for name, content in payload.items():
            atomic(FILES[name], content, originals[name]["mode"])
        run = subprocess.run(["/usr/bin/python3", "-B", str(RUNNER), "--once"],
                             capture_output=True, text=True, timeout=60)
        require(run.returncode == 0, "PRIVATE_QA_CANARY_FAILED:" + run.stderr[-400:])
        proof = json.loads(run.stdout.strip().splitlines()[-1])
        require(proof.get("status") == "real_evidence_audit_and_rework_ledger_updated"
                and proof.get("tenant") == TENANT and proof.get("component_count") == 103
                and proof.get("other_sites_modified") is False,
                "QA_ENGINE_CANARY_NOT_PROVEN")
        # Django check loads code on a fresh interpreter, but does not reload
        # shared Passenger or modify any database or public page.
        python = "/home/zomorod2/virtualenv/Saeit-staging/3.11/bin/python"
        require(Path(python).is_file(), "PASSENGER_VENV_MISSING")
        check = subprocess.run([python, "-B", "manage.py", "check"],
                               cwd=str(APP), capture_output=True, text=True, timeout=85)
        require(check.returncode == 0, "SHARED_DJANGO_SOURCE_CHECK_FAILED:" + check.stderr[-400:])
        if not old_markers:
            set_cron(old_cron.rstrip("\n") + "\n" + CRON + "\n")
        done = current_cron()
        require(sum(MARK in line for line in done.splitlines()) == 1
                and all(line in done.splitlines() for line in old_cron.splitlines()),
                "OTHER_CRON_ENTRY_MODIFIED")
        return {"tenant": TENANT, "status": "onepass_quality_engine_installed",
                "real_component_checks": 103, "modules_imported_only": proof["modules_imported_only"],
                "rework_issues_open": proof["open_rework_items"], "sibling_files_modified": False,
                "shared_passenger_restarted": False, "main_site_code_staged": True,
                "live_dashboard_restart_deferred_to_avoid_shared_site_impact": True,
                "cron": "7,22,37,52 * * * *"}
    except BaseException:
        restore(release)
        raise


def main():
    require(len(sys.argv) == 4 and sys.argv[1] == "install"
            or len(sys.argv) == 3 and sys.argv[1] == "rollback", "USAGE")
    mode = sys.argv[1]
    run_id = sys.argv[2]
    require(re.fullmatch(r"[0-9]{6,20}", run_id), "INVALID_RELEASE_ID")
    if mode == "rollback":
        preflight()
        report = restore(RELEASES / run_id, require_installed_hashes=True)
    else:
        report = install(run_id, sys.argv[3], sys.stdin.buffer)
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    os.umask(0o077)
    main()
