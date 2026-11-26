"""Fail-closed contract for a future MojProp.top-only release.

This module deliberately performs no deployment. It prevents a release operator
from reusing a MojPlayWin document root or opening commerce without independent
restore, tenant and rollback evidence.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

PUBLIC_HOST = "mojprop.top"
REQUIRED_EVIDENCE = (
    "MOJPROP_FULL_DB_APP_MEDIA_RESTORE_VERIFIED",
    "MOJPROP_TENANT_ISOLATION_VERIFIED",
    "MOJPROP_ROLLBACK_VERIFIED",
)


def evaluate(env=None):
    env = dict(os.environ if env is None else env)
    blockers = []
    checks = [f"public host is fixed to {PUBLIC_HOST}"]
    target = str(env.get("MOJPROP_DOCROOT", "")).strip()
    if not target:
        blockers.append("MOJPROP_DOCROOT is missing; no deployment target is authorized")
    else:
        target_path = Path(target)
        if "mojplaywin" in target.lower():
            blockers.append("MojProp document root must not contain mojplaywin")
        if target_path.name not in {"mojprop.top", "www.mojprop.top"}:
            blockers.append("MOJPROP_DOCROOT basename must be mojprop.top or www.mojprop.top")
        else:
            checks.append("document root belongs to MojProp")
    for name in REQUIRED_EVIDENCE:
        if env.get(name) != "true":
            blockers.append(f"{name}=true evidence is missing")
        else:
            checks.append(f"{name}=true")
    if env.get("MOJPROP_RELEASE_APPROVED") != "true":
        blockers.append("MOJPROP_RELEASE_APPROVED=true is missing")
    else:
        checks.append("owner release approval is present")
    return {"ready": not blockers, "host": PUBLIC_HOST, "checks": checks, "blockers": blockers}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv not in ([], ["preflight"]):
        raise SystemExit("usage: mojprop_standalone_release_contract.py [preflight]")
    print(json.dumps(evaluate(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
