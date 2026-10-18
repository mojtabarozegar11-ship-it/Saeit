"""Deploy the tested MojPlayWin Gen65+ code factory to a private cPanel stage.

Requires an already active, audited, every-minute MojPlayWin evolution Cron.
Never edits Cron, Passenger, Django, store, payments, other agents or tenants.
Reads an exact SHA256 manifest; writes only two Python sources atomically under
the preexisting private V91 extension. Holds the independent cron.lock during
the transaction; securely restores the previous source on any failure.
"""
from __future__ import annotations
import fcntl
import getpass
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

TENANT = "mojplaywin-main"
BASE = Path("/home/zomorod2/.private_mojplaywin_main_agents")
STAGE = BASE / "v91_verified_main_port_20261018"
STATE = STAGE / "operator_state"
RUNTIME = BASE / "evolution_runtime_20261018"
MODULES = STAGE / "mpw_v91_port"
EVOLUTION = MODULES / "evolution.py"
FACTORY = MODULES / "generation_factory.py"
ENABLED = "MPW_V91_MAIN_ONLY_PRIVATE_20261018"
CRON_MARK = "MPW_PRIVATE_EVOLUTION_MAIN_ONLY_20261018"
NAMES = ("evolution.py", "generation_factory.py")


def must(yes, name):
    if not yes:
        raise RuntimeError(name)


def private(directory):
    return directory.is_dir() and not directory.is_symlink() and (directory.stat().st_mode & 0o077) == 0


def read_package():
    data = sys.stdin.buffer.read(160001)
    must(0 < len(data) <= 160000, "SOURCE_PACKAGE_OUTSIDE_LIMIT")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        names = archive.getnames()
        must(sorted(names) == sorted((*NAMES, "MANIFEST.json")),
             "SOURCE_PACKAGE_NOT_EXACTLY_TWO_MODULES")
        files = {}
        for name in names:
            member = archive.getmember(name)
            must(member.isfile() and 2000 <= member.size <= 26000,
                 "INVALID_SOURCE_PACKAGE_MEMBER")
            files[name] = archive.extractfile(member).read()
    manifest = json.loads(files.pop("MANIFEST.json"))
    must(manifest.get("tenant") == TENANT
         and manifest.get("target") == "isolated_generation_factory_only"
         and isinstance(manifest.get("sha256"), dict)
         and set(manifest["sha256"]) == set(NAMES),
         "PRIVATE_DEPLOY_MANIFEST_INVALID")
    for name in NAMES:
        must(hashlib.sha256(files[name]).hexdigest() == manifest["sha256"][name],
             "SOURCE_SHA256_MISMATCH")
        compile(files[name], name, "exec")
    return files


def cron_existing():
    p = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=12)
    must(p.returncode == 0, "CRONTAB_READ_FAILED")
    marked = [line for line in p.stdout.splitlines() if CRON_MARK in line]
    must(len(marked) == 1 and marked[0].startswith("* * * * * ")
         and str(EVOLUTION) in marked[0] and "--once" in marked[0]
         and str(RUNTIME / "cron.lock") in marked[0],
         "PRIVATE_MINUTE_CRON_NOT_VERIFIED")
    return p.stdout


def json_source(path):
    must(path.is_file() and not path.is_symlink() and path.stat().st_size < 30000,
         "PRIVATE_SOURCE_PROOF_INVALID")
    return json.loads(path.read_text("utf-8"))


def atomic_source(path, raw):
    must(not path.is_symlink(), "MODULE_SYMLINK_NOT_PERMITTED")
    fd, staging = tempfile.mkstemp(prefix=".gen65-", dir=str(MODULES))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(staging, path)
    finally:
        if os.path.lexists(staging):
            os.unlink(staging)


def main():
    os.umask(0o077)
    must(getpass.getuser() == "zomorod2", "WRONG_CPANEL_OWNER")
    files = read_package()
    must(all(private(folder) for folder in (BASE, STAGE, STATE, RUNTIME, MODULES)),
         "PRIVATE_STAGE_NOT_ISOLATED")
    must((STATE / "enabled").is_file()
         and not (STATE / "enabled").is_symlink()
         and (STATE / "enabled").read_text().strip() == ENABLED,
         "MASTER_PRIVATE_ENABLED_FLAG_NOT_VERIFIED")
    must((MODULES / "ORIGIN.json").is_file()
         and not (MODULES / "ORIGIN.json").is_symlink(),
         "V91_SOURCE_ORIGIN_NOT_VERIFIED")
    original_cron = cron_existing()
    prior_report = json_source(RUNTIME / "last_report.json")
    must(prior_report.get("tenant") == TENANT and
         prior_report.get("master_generation") == 64 and
         prior_report.get("auto_published") is False and
         prior_report.get("shared_runtime_modified") is False and
         prior_report.get("executed_financial_actions") == 0,
         "PRIVATE_MASTER_REPORT_UNTRUSTED")
    must(EVOLUTION.is_file() and not EVOLUTION.is_symlink(),
         "ORIGINAL_EVOLUTION_MODULE_NOT_FOUND")
    must(not FACTORY.is_symlink(), "FACTORY_SYMLINK_BLOCKED")
    previous = {EVOLUTION: EVOLUTION.read_bytes(),
                FACTORY: FACTORY.read_bytes() if FACTORY.exists() else None}
    lock = RUNTIME / "cron.lock"
    must(not lock.is_symlink(), "CRON_LOCK_SYMLINK")
    fd = os.open(str(lock), os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    installed = False
    try:
        # Wait only for a bounded existing cron invocation to finish.
        got = False
        for _ in range(20):
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                got = True
                break
            except BlockingIOError:
                time.sleep(0.35)
        must(got, "PRIVATE_CRON_BUSY_NOT_INTERRUPTED")
        must(cron_existing() == original_cron, "CRON_CHANGED_DURING_STAGE")
        try:
            # Install the dependency FIRST and the evolution entrypoint LAST.
            atomic_source(FACTORY, files["generation_factory.py"])
            atomic_source(EVOLUTION, files["evolution.py"])
            installed = True
            for name, path in (("generation_factory.py", FACTORY),
                               ("evolution.py", EVOLUTION)):
                must(hashlib.sha256(path.read_bytes()).hexdigest()
                     == hashlib.sha256(files[name]).hexdigest(), "INSTALLED_HASH_MISMATCH")
            # Cron lock is held; execute one explicit safe private cycle.
            process = subprocess.run([shutil.which("python3") or "/usr/bin/python3",
                                      "-B", str(EVOLUTION), "--once"],
                                     capture_output=True, text=True, timeout=45)
            must(process.returncode == 0, "GEN65_FACTORY_PRIVATE_EXECUTION_FAILED:"
                 + process.stderr[-350:])
            result = json.loads(process.stdout)
            must(result.get("status") == "active_private_learning"
                 and result.get("next_generation") >= 65
                 and result.get("generation_experimental_only") is True,
                 "GEN65_GENERATION_RESULT_MISSING")
            candidate = RUNTIME / "generations" / "generation65.py"
            manifest = RUNTIME / "generations" / "generation65.json"
            last = RUNTIME / "last_generation_report.json"
            must(all(p.is_file() and not p.is_symlink()
                     for p in (candidate, manifest, last)),
                 "REAL_GEN65_PYTHON_NOT_CREATED")
            manifest_data = json_source(manifest)
            status = json_source(last)
            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            must(manifest_data["tenant"] == TENANT
                 and manifest_data["generation"] == 65
                 and manifest_data["parent_generation"] == 64
                 and manifest_data["code_sha256"] == digest
                 and status.get("generation") >= 65
                 and manifest_data["promotion_authorized"] is False
                 and manifest_data["auto_deploy"] is False
                 and manifest_data["executed_in_production"] is False,
                 "GEN65_PROVENANCE_OR_DEPLOYMENT_GATE_FAILED")
            compile(candidate.read_bytes(), "generated_gen65_quarantined.py", "exec")
            current = json_source(RUNTIME / "last_report.json")
            must(current["tenant"] == TENANT
                 and current["master_generation"] == 64
                 and current["self_modified_code"] is False
                 and current["auto_published"] is False
                 and current["executed_financial_actions"] == 0
                 and current["shared_runtime_modified"] is False,
                 "GENERATION_BYPASSED_PRIVATE_GUARD")
            must(cron_existing() == original_cron, "UNRELATED_CRON_EDIT_FOUND")
            print(json.dumps({"status": "GEN65_NEW_PYTHON_GENERATION_CREATED",
                  "tenant": TENANT, "generation": 65, "parent_generation": 64,
                  "source_sha256": digest,
                  "gene": manifest_data["capability_gene"],
                  "verified_outcomes": current["verified_outcome_count"],
                  "master_still_generation": current["master_generation"],
                  "schedule": "* * * * *",
                  "factory_connected_to_minute_cron": True,
                  "quarantined_not_promoted": True,
                  "public_site_modified": False, "finance_modified": False,
                  "cron_modified": False, "shared_passenger_restarted": False},
                  ensure_ascii=False, sort_keys=True))
        except BaseException:
            for module in (EVOLUTION, FACTORY):
                if previous[module] is not None:
                    atomic_source(module, previous[module])
                elif module.exists() and not module.is_symlink():
                    module.unlink()
            raise
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
