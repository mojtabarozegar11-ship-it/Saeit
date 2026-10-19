"""Activate audited Gen65 as a genuine *private* every-minute evaluator on cPanel.

No new cron, no Passenger, no Django code, no public master upgrade, no sites,
no store/payment operations. Atomic rollback of only private source and flag.
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
ROOT = Path("/home/zomorod2/.private_mojplaywin_main_agents")
STAGE = ROOT / "v91_verified_main_port_20261018"
PRIVATE = ROOT / "evolution_runtime_20261018"
ENGINE = STAGE / "mpw_v91_port"
ENTRY = ENGINE / "evolution.py"
GEN65 = ENGINE / "gen65_runtime.py"
CONTROL = PRIVATE / "gen65_operation_enabled.json"
REPORT = PRIVATE / "gen65_operational_report.json"
MARK = "MPW_PRIVATE_EVOLUTION_MAIN_ONLY_20261018"
FILES = {"evolution.py": ENTRY, "gen65_runtime.py": GEN65}


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


def is_private(folder):
    return folder.is_dir() and not folder.is_symlink() and (folder.stat().st_mode & 0o077) == 0


def read_package():
    data = sys.stdin.buffer.read(120001)
    require(0 < len(data) <= 120000, "PRIVATE_PACKAGE_SIZE_INVALID")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as package:
        names = package.getnames()
        require(set(names) == {"evolution.py", "gen65_runtime.py", "manifest.json"}
                and len(names) == 3, "UNKNOWN_PACKAGE_MEMBER")
        content = {}
        for name in names:
            info = package.getmember(name)
            require(info.isfile() and 0 < info.size <= 23000,
                    "INVALID_PRIVATE_MODULE_SIZE")
            content[name] = package.extractfile(info).read()
    manifest = json.loads(content.pop("manifest.json"))
    require(manifest.get("tenant") == TENANT
            and manifest.get("scope") == "private_operational_gen65_only"
            and set(manifest.get("sha256", {})) == set(FILES),
            "PRIVATE_PACKAGE_MANIFEST_REJECTED")
    for name, raw in content.items():
        require(hashlib.sha256(raw).hexdigest() == manifest["sha256"][name],
                "PRIVATE_SOURCE_SHA_MISMATCH")
        compile(raw, name, "exec")
    return content


def read_json(path, max_bytes=30000):
    require(path.is_file() and not path.is_symlink()
            and path.stat().st_size <= max_bytes, "PRIVATE_JSON_EVIDENCE_INVALID")
    return json.loads(path.read_text("utf-8"))


def cron_snapshot():
    p = subprocess.run(["crontab", "-l"], text=True, capture_output=True, timeout=12)
    require(p.returncode == 0, "CRONTAB_READ_UNAVAILABLE")
    marks = [line for line in p.stdout.splitlines() if MARK in line]
    require(len(marks) == 1 and marks[0].startswith("* * * * * ")
            and str(ENTRY) in marks[0]
            and "--once" in marks[0]
            and str(PRIVATE / "cron.lock") in marks[0],
            "EXISTING_PRIVATE_ONE_MINUTE_CRON_NOT_VERIFIED")
    return p.stdout


def atom(path, raw):
    require(not path.is_symlink(), "PRIVATE_TARGET_SYMLINK_REFUSED")
    fd, tmp = tempfile.mkstemp(prefix=".private-gen65-live-", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.lexists(tmp):
            os.unlink(tmp)


def execute_once():
    p = subprocess.run([shutil.which("python3") or "/usr/bin/python3",
                        "-B", str(ENTRY), "--once"],
                       text=True, capture_output=True, timeout=40)
    require(p.returncode == 0, "PRIVATE_GEN65_EXECUTION_FAILED:" + p.stderr[-250:])
    result = json.loads(p.stdout)
    require(result.get("status") == "active_private_learning"
            and result.get("next_generation", 0) >= 65
            and result.get("gen65_runtime_status") == "gen65_operational_private"
            and result.get("gen65_active_private_generation") == 65,
            "GEN65_NOT_ACTUALLY_EXECUTED")
    return result


def main():
    os.umask(0o077)
    require(getpass.getuser() == "zomorod2", "UNEXPECTED_CPANEL_OWNER")
    files = read_package()
    require(all(is_private(x) for x in (ROOT, STAGE, PRIVATE, ENGINE,
                                       STAGE / "operator_state")),
            "PRIVATE_STAGE_NOT_ISOLATED")
    flag = STAGE / "operator_state" / "enabled"
    require(flag.is_file() and not flag.is_symlink()
            and flag.read_text("utf-8").strip() == "MPW_V91_MAIN_ONLY_PRIVATE_20261018",
            "OWNER_PRIVATE_AGENT_WORKER_DISABLED")
    prior = read_json(PRIVATE / "last_report.json")
    require(prior.get("tenant") == TENANT
            and prior.get("master_generation") == 64
            and prior.get("auto_published") is False
            and prior.get("shared_runtime_modified") is False,
            "PRIVATE_GEN64_BASELINE_NOT_VERIFIED")
    original_cron = cron_snapshot()
    gen_manifest = read_json(PRIVATE / "generations" / "generation65.json", 4500)
    generated = PRIVATE / "generations" / "generation65.py"
    require(generated.is_file() and not generated.is_symlink()
            and gen_manifest.get("tenant") == TENANT
            and gen_manifest.get("generation") == 65
            and gen_manifest.get("parent_generation") == 64
            and gen_manifest.get("quality_threshold") == 95
            and gen_manifest.get("minimum_sources") == 2
            and gen_manifest.get("promotion_authorized") is False
            and gen_manifest.get("auto_deploy") is False,
            "GEN65_QUARANTINE_PROVENANCE_INVALID")
    generated_sha = hashlib.sha256(generated.read_bytes()).hexdigest()
    require(generated_sha == gen_manifest.get("code_sha256"),
            "GEN65_GENERATED_SOURCE_HASH_CHANGED")
    require(ENTRY.is_file() and not ENTRY.is_symlink()
            and not GEN65.is_symlink() and not CONTROL.is_symlink()
            and not REPORT.is_symlink(),
            "PREEXISTING_PRIVATE_MODULE_SYMLINK")
    before = {ENTRY: ENTRY.read_bytes(), GEN65: GEN65.read_bytes() if GEN65.exists() else None,
              CONTROL: CONTROL.read_bytes() if CONTROL.exists() else None}
    lock_path = PRIVATE / "cron.lock"
    require(not lock_path.is_symlink(), "UNSAFE_CRON_LOCK")
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        acquired = False
        for attempt in range(24):
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                time.sleep(.4)
        require(acquired, "PRIVATE_CRON_BUSY_NO_FORCE_UNLOCK")
        require(cron_snapshot() == original_cron, "UNRELATED_CRON_CHANGED")
        try:
            # Run vetted controller: its hash is verified on every cycle.
            atom(GEN65, files["gen65_runtime.py"])
            atom(ENTRY, files["evolution.py"])
            config = {
                "tenant": TENANT,
                "active_private_generation": 65,
                "controller_sha256": generated_sha,
                "enabled": True,
                "scope": "private_verified_review_only",
            }
            atom(CONTROL, json.dumps(config, sort_keys=True).encode())
            for name, target in FILES.items():
                require(hashlib.sha256(target.read_bytes()).hexdigest()
                        == hashlib.sha256(files[name]).hexdigest(),
                        "NEW_PRIVATE_SOURCE_DEPLOY_VERIFICATION_FAILED")
            result = execute_once()
            proof = read_json(REPORT, 9000)
            require(proof.get("status") == "gen65_operational_private"
                    and proof.get("tenant") == TENANT
                    and proof.get("active_private_generation") == 65
                    and proof.get("existing_public_master_generation") == 64
                    and proof.get("controller_sha256") == generated_sha
                    and proof.get("public_site_changed") is False
                    and proof.get("auto_published") is False
                    and proof.get("financial_actions") == 0
                    and proof.get("shared_runtime_modified") is False,
                    "GEN65_PRIVATE_OPERATION_READBACK_FAILED")
            require(cron_snapshot() == original_cron, "PREVIOUS_CRON_MODIFIED")
            print(json.dumps({
                "status": "GEN65_PRIVATE_OPERATIONAL_AND_RUNNING",
                "tenant": TENANT, "private_active_generation": 65,
                "existing_public_master_generation": 64,
                "gen65_controller_sha256": generated_sha,
                "verified_observations": proof["verified_observations"],
                "ready_for_human_review": proof["ready_for_human_review"],
                "held_for_review": proof["held_for_review"],
                "cycle_epoch": proof["cycle_epoch"],
                "cron_schedule": "* * * * *",
                "previous_cron_jobs_unchanged": True,
                "subsites_changed": False,
                "public_site_changed": False,
                "payment_changed": False,
                "auto_published": False,
                "passenger_restarted": False,
            }, ensure_ascii=False, sort_keys=True))
        except BaseException:
            # Roll back only source and owner flag; never touch original cron.
            for target in (ENTRY, GEN65, CONTROL):
                old = before[target]
                if old is not None:
                    atom(target, old)
                elif target.exists() and not target.is_symlink():
                    target.unlink()
            raise
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
