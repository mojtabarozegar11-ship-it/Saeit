#!/usr/bin/env python3
"""PICM-only, rollback-protected private CPU-worker release on the known VPS.

Never touches the factory, ComfyUI, Passenger, other sites or user-generated data.
Invoked by a pinned-key, owner-gated GitHub Actions workflow after queue preflight.
"""
import hashlib
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path.home() / ".local/share/saeit-picm"
WORKER = ROOT / "worker.py"
TOKEN = ROOT / "worker-token"
PIDFILE = ROOT / "worker.pid"
LOG = ROOT / "worker.log"
PATTERN = re.compile(r"^[0-9]{1,20}$")


def guard_regular(path):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("PICM_UNSAFE_OR_MISSING_FILE")


def process_ours(pid):
    try:
        data = (Path("/proc") / str(pid) / "cmdline").read_bytes().replace(b"\0", b" ")
        return b"saeit-picm/worker.py" in data
    except OSError:
        return False


def start_worker():
    with LOG.open("ab") as log, open(os.devnull, "rb") as null:
        child = subprocess.Popen([sys.executable, "-u", str(WORKER)],
                                 cwd=str(ROOT), stdin=null, stdout=log,
                                 stderr=subprocess.STDOUT, start_new_session=True,
                                 close_fds=True)
    PIDFILE.write_text(str(child.pid) + "\n", encoding="ascii")
    time.sleep(4)
    if child.poll() is not None or not process_ours(child.pid):
        raise RuntimeError("PICM_NEW_WORKER_NOT_ALIVE")
    return child.pid


def stop_worker(pid):
    if not process_ours(pid):
        raise RuntimeError("PICM_UNEXPECTED_PREVIOUS_WORKER")
    os.kill(pid, signal.SIGTERM)
    for _ in range(32):
        if not process_ours(pid):
            return
        time.sleep(0.25)
    raise RuntimeError("PICM_OLD_WORKER_NOT_STOPPED")


def release(run_id, expected_sha):
    if not PATTERN.fullmatch(run_id) or not re.fullmatch(r"[a-f0-9]{64}", expected_sha):
        raise RuntimeError("PICM_INVALID_DEPLOY_ARGUMENT")
    if ROOT.is_symlink() or not ROOT.is_dir() or os.getuid() == 0:
        raise RuntimeError("PICM_VPS_ROOT_UNSAFE")
    for path in (WORKER, TOKEN, PIDFILE, LOG):
        guard_regular(path)
    if not (ROOT / "worker.lock").is_file():
        raise RuntimeError("PICM_WORKER_LOCK_MISSING")
    old_pid = int(PIDFILE.read_text(encoding="ascii").strip())
    if not process_ours(old_pid):
        raise RuntimeError("PICM_ACTIVE_WORKER_MISSING")
    log_lines = LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-60:]
    relevant = [v for v in log_lines if any(w in v for w in (
        "PICM_QUEUE_EMPTY", "PICM_JOB_CLAIMED", "PICM_JOB_DELIVERED_",
        "PICM_JOB_REPORTED_FAILED_"))]
    if not relevant or "PICM_JOB_CLAIMED" in relevant[-1]:
        raise RuntimeError("PICM_RENDER_ACTIVE_OR_UNKNOWN")
    if any(Path("/proc/" + str(old_pid) + "/task/" + str(old_pid) + "/children").read_text().strip().split()):
        raise RuntimeError("PICM_WORKER_CHILD_PROCESS_ACTIVE")

    candidate = ROOT / ("worker.py.candidate." + run_id)
    guard_regular(candidate)
    if hashlib.sha256(candidate.read_bytes()).hexdigest() != expected_sha:
        raise RuntimeError("PICM_CANDIDATE_HASH_MISMATCH")
    backup_dir = ROOT / ".release-backups"
    if backup_dir.is_symlink():
        raise RuntimeError("PICM_BACKUP_DIR_UNSAFE")
    backup_dir.mkdir(mode=0o700, exist_ok=True)
    backup = backup_dir / ("worker-before-" + run_id + ".py")
    if backup.exists() or backup.is_symlink():
        raise RuntimeError("PICM_REUSED_RELEASE")
    shutil.copy2(WORKER, backup)
    backup.chmod(0o600)
    previous_hash = hashlib.sha256(backup.read_bytes()).hexdigest()
    changed = False
    new_pid = None
    try:
        candidate.chmod(0o600)
        os.replace(candidate, WORKER)
        changed = True
        stop_worker(old_pid)
        new_pid = start_worker()
        assert hashlib.sha256(WORKER.read_bytes()).hexdigest() == expected_sha
        print("PICM_PRIVATE_WORKER_RELEASE_SUCCESS")
        print("PICM_RELEASE_BACKUP_REFERENCE=" + run_id)
        print("PICM_NEW_WORKER_PID=" + str(new_pid))
        return
    except Exception:
        if changed:
            print("PICM_WORKER_RELEASE_REVERTING", flush=True)
            if new_pid is not None and process_ours(new_pid):
                stop_worker(new_pid)
            recovery = ROOT / ("worker.py.recovery." + run_id)
            shutil.copy2(backup, recovery)
            os.replace(recovery, WORKER)
            assert hashlib.sha256(WORKER.read_bytes()).hexdigest() == previous_hash
            if not process_ours(old_pid):
                try:
                    start_worker()
                    print("PICM_PREVIOUS_WORKER_RESTORED", flush=True)
                except Exception:
                    print("PICM_ROLLBACK_RESTART_FAILED", flush=True)
        raise


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: picm_private_worker_release.py RUN_ID SHA256")
    release(sys.argv[1], sys.argv[2])
