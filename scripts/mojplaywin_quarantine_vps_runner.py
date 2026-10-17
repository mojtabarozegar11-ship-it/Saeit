#!/usr/bin/env python3
"""Existing encrypted archive → private transient VPS directory, quarantining links.

No cPanel connection, no Django, no production writes, no Passenger operations.
Files are restored to a private directory and deleted on completion. Symlinks
with absolute targets are NOT created; this is not a full restore proof.
"""
from __future__ import annotations
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import types
from pathlib import Path

STEM = "mojplaywin_20261017_direct_39028678930"

def load_source(encoded: str, label: str):
    raw = base64.b64decode(encoded, validate=True)
    if not raw or len(raw) > 60000:
        raise ValueError("unexpected module size")
    module = types.ModuleType(label)
    exec(compile(raw, "<reviewed-archive-module>", "exec"), module.__dict__)
    return module

def main(args):
    if len(args) != 2:
        raise ValueError("two reviewed modules expected")
    test = load_source(args[0], "private_quarantine_test")
    recovery_b64 = args[1]
    if not re.fullmatch(r"[A-Za-z0-9+/=]+", recovery_b64 or "") or len(recovery_b64)>100000:
        raise ValueError("invalid recovery module")
    program = ("import sys,base64,types;"
               "m=types.ModuleType('recovery');"
               "exec(compile(base64.b64decode(sys.argv[1]),'<reviewed-recovery>','exec'),m.__dict__);"
               "m.STEM=sys.argv[2];m.decrypt_to_stdout('files')")
    with tempfile.TemporaryDirectory(prefix=".mpw-quarantine-audit-",dir=str(Path.home())) as td:
        os.chmod(td,0o700)
        p = subprocess.Popen([sys.executable,"-c",program,recovery_b64,STEM],
                             stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        try:
            if p.stdout is None:
                raise ValueError("GPG private stream absent")
            report = test.recover(p.stdout,td)
            p.stdout.close()
            if p.wait(timeout=90) != 0:
                raise ValueError("GPG source integrity not verified")
            expected={
                "regular_files_restored":32476,
                "directories_restored":2489,
                "absolute_links_quarantined":3,
                "symlinks_restored":0,
                "hardlinks_restored":0,
                "root_count_restored":2
            }
            for key,value in expected.items():
                if report.get(key)!=value:
                    raise ValueError("verified archive manifest changed")
            if not report.get("ordinary_content_restored") or report.get("restore_complete"):
                raise ValueError("invalid partial recovery classification")
            print(json.dumps({
                "classification":"PRIVATE_QUARANTINED_FILE_CONTENT_RESTORED",
                "ordinary_files":report["regular_files_restored"],
                "bytes":report["regular_bytes_restored"],
                "directories":report["directories_restored"],
                "absolute_links_skipped":report["absolute_links_quarantined"],
                "roots":report["root_count_restored"],
                "gpg_integrity_ok":True,
                "complete_restore":False,
                "live_files_modified":False,
                "passenger_restarted":False,
                "release_permitted":False,
            },sort_keys=True),flush=True)
        finally:
            if p.poll() is None:
                p.kill()
                p.wait()

if __name__=="__main__":
    try:
        main(sys.argv[1:])
    except Exception as exc:
        print(json.dumps({"classification":"PRIVATE_QUARANTINED_FILE_TEST_FAILED",
                          "reason_type":type(exc).__name__,
                          "complete_restore":False,"release_permitted":False,
                          "live_files_modified":False},sort_keys=True))
        raise SystemExit(1)
