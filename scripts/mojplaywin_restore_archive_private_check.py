#!/usr/bin/env python3
"""Run the private, read-only archive diagnostic entirely ON the authorized VPS.

Call with base64-encoded, reviewed recovery module, reviewed probe and exact
known archive stem. Decrypted bytes travel only between two local subprocesses.
No keys, customer bytes or file/link names leave the VPS; no files written.
"""
from __future__ import annotations

import base64
import json
import re
import subprocess
import sys

def main(argv):
    if len(argv) != 3:
        raise SystemExit(2)
    recovery64, probe64, stem = argv
    if not re.fullmatch(r"mojplaywin_20261017_direct_[0-9]{8,12}", stem):
        raise SystemExit(2)
    try:
        probe_src = base64.b64decode(probe64, validate=True)
        recovery_src = base64.b64decode(recovery64, validate=True)
        if len(probe_src) > 50000 or len(recovery_src) > 50000:
            raise RuntimeError("module_size")
        mod = {"__name__": "read_only_archive_probe"}
        exec(compile(probe_src, "<reviewed-probe-source>", "exec"), mod)
        runner = (
            'import sys,base64;d={"__name__":"private_recovery"};'
            'exec(compile(base64.b64decode(sys.argv[1]),"<reviewed-recovery-source>","exec"),d);'
            'd["STEM"]=sys.argv[2];d["decrypt_to_stdout"]("files")'
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", runner, recovery64, stem],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        try:
            if proc.stdout is None:
                raise RuntimeError("missing_pipe")
            report = mod["probe"](proc.stdout)
            proc.stdout.close()
            code = proc.wait(timeout=90)
            report["source_integrity_verified_by_probe"] = bool(
                code == 0 and report.get("source_completion_footer_seen")
            )
            report["decryption_exit_ok"] = code == 0
            report["production_modified"] = False
            report["release_permitted"] = False
            print(json.dumps(report, sort_keys=True, separators=(",", ":")), flush=True)
            if code != 0 or not report.get("source_completion_footer_seen"):
                raise SystemExit(1)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
    except Exception as error:
        print(json.dumps({
            "classification": "READ_ONLY_PRIVATE_ARCHIVE_PROBE_FAILED",
            "error_class": type(error).__name__,
            "release_permitted": False,
            "production_modified": False,
        }, sort_keys=True))
        raise SystemExit(1)

if __name__ == "__main__":
    main(sys.argv[1:])
