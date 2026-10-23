#!/usr/bin/env python3
"""Two bounded, evidence-preserving Stage4 wait-state improvements for VPS.

Gen1: distinguish exhausted research capacity from time-based retry.
Gen2: expose machine-readable reasons and actionable evidence/retry metadata.
Neither generation raises quota, starts purchases, fabricates evidence,
moves factory stages, changes approval policy, or touches site/public files.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

OLD = '                    return {"action": "waiting_for_evidence", "reason": "Stage 4 research is waiting for its persisted budget window or capacity policy."}'
GEN1 = '''                    status = progress.get("status")
                    reason = ("Stage 4 evidence capacity reached; independent new evidence or review is required."
                              if status == "capacity_exhausted" else
                              "Stage 4 retry window has not elapsed; do not request research yet.")
                    return {"action": "waiting_for_evidence", "reason": reason}'''
GEN2 = '''                    status = progress.get("status")
                    reason = ("Stage 4 evidence capacity reached; independent new evidence or review is required."
                              if status == "capacity_exhausted" else
                              "Stage 4 retry window has not elapsed; do not request research yet.")
                    return {"action": "waiting_for_evidence", "reason": reason,
                            "wait_code": ("capacity_exhausted" if status == "capacity_exhausted"
                                          else "retry_window_not_due"),
                            "next_retry_at": (None if status == "capacity_exhausted"
                                               else progress.get("next_retry_at")),
                            "evidence_count": len(prior_evidence) if isinstance(prior_evidence, list) else None,
                            "external_evidence_required": status == "capacity_exhausted"}'''
CONTEXT = '''                if not revised_evidence:
'''
TARGET = Path.home() / "factory-runtime/django-app/core/autonomous_brain.py"
ROOT = Path.home() / "factory-runtime/operations"
BACKUPS = ROOT / "backups/stage4-wait-classifier"
RECEIPTS = ROOT / "evidence/stage4-wait-classifier"

def sha(data):
    return hashlib.sha256(data).hexdigest()

def transform(source):
    if source.count(OLD) == 1 and source.count(GEN1) == 0 and source.count(GEN2) == 0:
        if source.count(CONTEXT + OLD) != 1:
            raise RuntimeError("STAGE4_WAIT_CONTEXT_MISMATCH")
        phase1 = source.replace(OLD, GEN1)
        phase2 = phase1.replace(GEN1, GEN2)
    elif source.count(GEN2) == 1 and source.count(OLD) == 0 and source.count(GEN1) == 0:
        return source, source, False
    else:
        raise RuntimeError("STAGE4_WAIT_EXACT_PREIMAGE_MISMATCH")
    for phase in (phase1, phase2):
        compile(phase, "autonomous_brain.py", "exec")
        assert phase.count('if not revised_evidence:') == 1
        assert phase.count('0 < len(current_evidence) <= 100') == 1
        assert phase.count('current_evidence != prior_evidence') == 1
        assert "waiting_for_evidence" in phase
        assert "capacity_exhausted" in phase
    return phase1, phase2, True

def atomic(path, data, mode):
    fd, temp = tempfile.mkstemp(prefix=".stage4-wait-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def run(expected_source_sha):
    target = TARGET
    if (target.is_symlink() or not target.is_file() or
            target.stat().st_size > 180000 or target.stat().st_size < 4000):
        raise RuntimeError("STAGE4_UNSAFE_LIVE_SOURCE")
    if not ROOT.is_dir() or ROOT.is_symlink():
        raise RuntimeError("STAGE4_RUNTIME_UNSAFE")
    lock = ROOT / "master-agent/master-cycle.lock"
    if not lock.is_file() or lock.is_symlink():
        raise RuntimeError("STAGE4_MASTER_LOCK_REQUIRED")
    with lock.open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        original = target.read_bytes()
        before = sha(original)
        if expected_source_sha and expected_source_sha != before:
            raise RuntimeError("STAGE4_SOURCE_SHA_CHANGED")
        p1, p2, should_change = transform(original.decode("utf-8"))
        for path in (BACKUPS, RECEIPTS):
            if path.is_symlink():
                raise RuntimeError("STAGE4_UNSAFE_RECEIPTS")
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not should_change:
            print("STAGE4_GEN1=ALREADY_INSTALLED")
            print("STAGE4_GEN2=ALREADY_INSTALLED")
            print("STAGE4_FINAL_SHA256=" + before)
            return
        backup = BACKUPS / ("autonomous_brain-" + before[:24] + ".py")
        if backup.exists():
            if backup.is_symlink() or backup.read_bytes() != original:
                raise RuntimeError("STAGE4_BACKUP_CONFLICT")
        else:
            with backup.open("xb") as f:
                f.write(original)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(backup, 0o600)
        mode = target.stat().st_mode & 0o777
        installed = False
        try:
            if sha(target.read_bytes()) != before:
                raise RuntimeError("STAGE4_SOURCE_CONCURRENT_EDIT")
            atomic(target, p1.encode("utf8"), mode)
            if sha(target.read_bytes()) != sha(p1.encode("utf8")):
                raise RuntimeError("STAGE4_GEN1_INSTALL_HASH_FAIL")
            print("STAGE4_GEN1=INSTALLED")
            atomic(target, p2.encode("utf8"), mode)
            after = target.read_bytes()
            if sha(after) != sha(p2.encode("utf8")) or "external_evidence_required" not in after.decode("utf8"):
                raise RuntimeError("STAGE4_GEN2_INSTALL_HASH_FAIL")
            print("STAGE4_GEN2=INSTALLED")
            receipt = {
                "schema": "saeit.factory.stage4-wait-classifier.v1",
                "created_unix": int(time.time()),
                "target": str(target),
                "old_sha256": before,
                "generation1_sha256": sha(p1.encode("utf8")),
                "generation2_sha256": sha(after),
                "backup": str(backup),
                "cap_100_preserved": True,
                "evidence_guard_preserved": True,
                "release_authorized": False,
                "public_site_files_changed": 0,
                "quality_1000_certified": False,
            }
            payload = (json.dumps(receipt, sort_keys=True, separators=(",", ":"))+"\n").encode()
            path = RECEIPTS / ("receipt-" + sha(payload)[:24] + ".json")
            with path.open("xb") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            installed = True
            print("STAGE4_FINAL_SHA256=" + receipt["generation2_sha256"])
            print("STAGE4_BACKUP_SHA256=" + before)
            print("STAGE4_RECEIPT_SHA256=" + sha(payload))
            print("STAGE4_CODE_ROLLBACK_AVAILABLE=YES")
        finally:
            if not installed:
                atomic(target, original, mode)
                if sha(target.read_bytes()) != before:
                    raise RuntimeError("STAGE4_ROLLBACK_INTEGRITY_FAILURE")
                print("STAGE4_SOURCE_ROLLBACK=COMPLETE")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--expected-source-sha", default="")
    options = p.parse_args()
    run(options.expected_source_sha)
