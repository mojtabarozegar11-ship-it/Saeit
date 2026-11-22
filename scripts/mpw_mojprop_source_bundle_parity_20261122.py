#!/usr/bin/env python3
"""Read-only Moj Prop source parity gate for the manually routed owner cPanel app.

This is deliberately NOT a deployer and is NOT a financial admission gate.
It reads twelve selected source files and direct source dependencies to expose a *known* class of mixed-version
release that could make the live rules and the buyer's promised terms diverge.
A source match does NOT prove active LSWSGI processes reloaded, legal eligibility,
an invoice, company reward reserves, settled blockchain transfers or delivery.

Usage (on the authorized owner cPanel account): python3 -B - --check
No subprocesses, HTTP, writes, crontab changes, payments or app restarts.
"""
from __future__ import annotations

import hashlib
import json
import stat
import sys
from pathlib import Path

PUBLIC_EFFECTIVE_ROOT = Path("/home/zomorod2/Saeit-mojplaywin-integrated-20261119")

# Pinned reviewed candidate blobs for the isolated simulation-stage ledger as of 22 Nov 2026.
# Never guess parity from a runtime environment variable or a Django release flag.
REQUIRED = {
    "prop_firm/simulation_policy.py": "15c5771e340315ebd649f92224ddd9bce138a256",
    "prop_firm/rules.py": "550269ebf2de3e2f1b50ade0939680597845e224",
    "prop_firm/simulation_payout.py": "e79a9677a14f5c2813d4f4e3b4d3622bb62474eb",
    "prop_firm/starter30_paid_admission.py": "663bbde80fbe867a644589bc687bbed2840125af",
    "prop_firm/policy_integrity.py": "68dfaf2a31e6f63f2c25f8eea93843f27f73d7d8",
    "prop_firm/starter30_live.py": "3c006d15dd6b35d5128ec3af7d03def28841b8e4",
    "prop_firm/customer_portal_views.py": "f918d8b6645dd168014e6a2dd718bd851afc7884",
    # Candidate model blob includes the isolated simulation tier and transition receipt.
    "prop_firm/models.py": "cc668e879ad7f730d08732f0284f1c8979d7987e",
    "prop_firm/simulation_identity_adapter.py": "0b4e6bf2050634816314b0ced5b8e424f5a5d2ad",
    "prop_firm/starter30_checkout_email.py": "dc6cdf6daae0b3649a1db4811f4aa3834e37df38",
    "prop_firm/starter30_receiver_pool.py": "2e34e773846fc8903915a784bf3d07de5a411014",
    "config/mojprop_db_router.py": "d3f255e6a71615ac9f86fcee632eb9b49da0eca8",
}
EXPECTED_COUNT = 12


def git_blob(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def check_bundle(root: Path) -> dict:
    """No side effects: inspect only file existence, type and exact Git blobs."""
    rows = []
    for relative, expected in REQUIRED.items():
        path = root / relative
        status = "MISSING"
        actual = None
        try:
            if path.is_symlink() or path.parent.is_symlink():
                status = "UNSAFE_LINK"
            elif path.is_file():
                info = path.stat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    status = "UNSAFE_FILE"
                else:
                    actual = git_blob(path.read_bytes())
                    status = "MATCH" if actual == expected else "DRIFT"
        except OSError:
            status = "UNREADABLE"
        rows.append({
            "file": relative,
            "status": status,
            "expected_blob": expected,
            "actual_blob": actual,
        })
    match_count = sum(row["status"] == "MATCH" for row in rows)
    summary = {
        "scope": "exactly_twelve_production_source_files_only",
        "source_root": str(root),
        "checked": len(rows),
        "matched": match_count,
        "missing": sum(row["status"] == "MISSING" for row in rows),
        "drift": sum(row["status"] == "DRIFT" for row in rows),
        "unsafe_or_unreadable": sum(row["status"] in ("UNSAFE_LINK", "UNSAFE_FILE", "UNREADABLE") for row in rows),
        "source_bundle_matches": (len(rows) == EXPECTED_COUNT and match_count == EXPECTED_COUNT),
        "worker_reload_proven": False,
        "financial_release_proven": False,
        "written_live_changes": 0,
        "components": rows,
    }
    return summary


def main(args: list[str]) -> int:
    if args != ["--check"]:
        print("Only read-only --check is supported.", file=sys.stderr)
        return 64
    report = check_bundle(PUBLIC_EFFECTIVE_ROOT)
    print(json.dumps(report, sort_keys=True, ensure_ascii=True))
    return 0 if report["source_bundle_matches"] else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
