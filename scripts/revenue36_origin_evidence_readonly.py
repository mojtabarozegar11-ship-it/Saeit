#!/usr/bin/env python3
"""Verify recent, successful, previously pinned production read-only workflow runs.

This checker has NO cPanel/VPS credentials, SSH, payments, deployment or DB access.
Never equate a healthy SSH tunnel with an approved commercial release.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from urllib.request import Request, urlopen

REPO = "mojtabarozegar11-ship-it/Saeit"
MAX_AGE = timedelta(hours=72)
RUN_PROOFS = (
    (43157969516, 3, "b17da7183138d0567d659732e9c458958f43d539",
     ".github/workflows/vps-to-cpanel-ssh-readonly-20261112.yml",
     "vps_to_cpanel_ssh"),
    (43162619527, 6, "6dc9856bd22c1bd4ade38000cc09cde00d463e80",
     ".github/workflows/cpanel-direct-command-bridge.yml",
     "cpanel_passenger_inventory"),
    (43162853620, 2, "634f7c5612f0bdc8b377fc3103fae629b3b1957f",
     ".github/workflows/cpanel-direct-command-bridge.yml",
     "cpanel_company_django_check"),
)


def attest_one(proof, *, now=None, opener=urlopen):
    number, min_attempt, commit, workflow, label = proof
    moment = now or datetime.now(timezone.utc)
    request = Request(
        f"https://api.github.com/repos/{REPO}/actions/runs/{number}",
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": "Saeit-Owner-Readonly-OriginEvidence/1.0"},
    )
    with opener(request, timeout=16) as response:
        raw = response.read(120001)
    if len(raw) > 120000:
        raise ValueError("oversized_github_attestation")
    record = json.loads(raw)
    if not isinstance(record, dict):
        raise ValueError("invalid_github_attestation")
    if (record.get("id") != number
            or record.get("event") != "workflow_dispatch"
            or record.get("head_branch") != "main"
            or record.get("head_sha") != commit
            or record.get("path") != workflow
            or record.get("status") != "completed"
            or record.get("conclusion") != "success"
            or type(record.get("run_attempt")) is not int
            or record["run_attempt"] < min_attempt
            or not isinstance(record.get("actor"), dict)
            or record["actor"].get("login") != "mojtabarozegar11-ship-it"):
        raise ValueError("origin_proof_wrong_run_or_not_success")
    started = datetime.fromisoformat(str(record.get("run_started_at", "")).replace("Z", "+00:00"))
    if (started.tzinfo is None
            or started > moment + timedelta(minutes=5)
            or moment - started > MAX_AGE):
        raise ValueError("origin_proof_expired_or_future")
    return {"label": label, "verified": True, "run_id": number,
            "run_attempt": record["run_attempt"]}


def attest_all(*, now=None, opener=urlopen, repository=None):
    if (repository if repository is not None else os.environ.get("GITHUB_REPOSITORY")) != REPO:
        raise ValueError("wrong_owner_repository")
    found = [attest_one(proof, now=now, opener=opener) for proof in RUN_PROOFS]
    if len(found) != len(RUN_PROOFS) or not all(row["verified"] for row in found):
        raise ValueError("origin_access_proof_incomplete")
    return {
        "classification": "OWNER_SELFHOSTED_READONLY_ACCESS_PROVEN",
        "proofs": found,
        "vps_to_cpanel_ssh_access_proven": True,
        "passenger_inventory_readonly_proven": True,
        "django_company_root_check_proven": True,
        "mojplaywin_live_app_root_proven": False,
        "subsite_passenger_isolation_proven": False,
        "commercial_release_authorized": False,
        "payment_gateway_authorized": False,
    }


if __name__ == "__main__":
    try:
        result = attest_all()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        # Print only a bounded error class, never API body or credentials.
        print("ORIGIN_READONLY_ATTESTATION=BLOCKED:" + type(exc).__name__)
        raise SystemExit(1) from None
    print("ORIGIN_READONLY_ATTESTATION=" + json.dumps(result, sort_keys=True))
