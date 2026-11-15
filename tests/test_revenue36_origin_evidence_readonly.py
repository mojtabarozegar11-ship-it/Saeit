"""Read-only public GitHub run attestation, without reusing production SSH secrets."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from pathlib import Path

import pytest
from scripts.revenue36_origin_evidence_readonly import (
    REPO, RUN_PROOFS, attest_one, attest_all,
)

NOW = datetime(2026, 11, 15, 8, 0, tzinfo=timezone.utc)


class Response:
    def __init__(self, data):
        self.data = json.dumps(data).encode()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, size):
        assert size <= 120001
        return self.data


def good(proof, *, started=None, **changes):
    run, attempt, sha, path, _ = proof
    data = {
        "id": run, "run_attempt": attempt, "head_sha": sha, "path": path,
        "head_branch": "main", "event": "workflow_dispatch",
        "status": "completed", "conclusion": "success",
        "run_started_at": (started or NOW - timedelta(minutes=10)).isoformat(),
        "actor": {"login": "mojtabarozegar11-ship-it"},
    }
    data.update(changes)
    return data


def opener_for(data):
    return lambda request, timeout: Response(data)


@pytest.mark.parametrize("proof", RUN_PROOFS)
def test_owner_trusted_recent_receipt_is_accepted(proof):
    result = attest_one(proof, now=NOW, opener=opener_for(good(proof)))
    assert result["verified"]
    assert result["run_id"] == proof[0]


@pytest.mark.parametrize("changes", [
    {"conclusion": "failure"}, {"status": "in_progress"},
    {"head_sha": "0"*40}, {"head_branch": "feature/test"},
    {"event": "pull_request"}, {"path": "wrong.yml"},
    {"run_attempt": 1}, {"actor": {"login": "someone-else"}},
])
def test_tampered_or_unfinished_proof_fails(changes):
    proof = RUN_PROOFS[1]
    with pytest.raises(ValueError, match="origin_proof_wrong_run_or_not_success"):
        attest_one(proof, now=NOW, opener=opener_for(good(proof, **changes)))


def test_stale_proof_cannot_be_reused_indefinitely():
    p = RUN_PROOFS[0]
    with pytest.raises(ValueError, match="origin_proof_expired_or_future"):
        attest_one(p, now=NOW, opener=opener_for(
            good(p, started=NOW - timedelta(days=4))))


def test_future_dated_proof_fails():
    p = RUN_PROOFS[0]
    with pytest.raises(ValueError, match="origin_proof_expired_or_future"):
        attest_one(p, now=NOW, opener=opener_for(
            good(p, started=NOW + timedelta(minutes=10))))


def test_wrong_repository_cannot_assert_evidence():
    with pytest.raises(ValueError, match="wrong_owner_repository"):
        attest_all(repository="someone-else/other")


def test_successful_triplet_still_cannot_approve_commercial_release():
    mapping = {p[0]: good(p) for p in RUN_PROOFS}
    def fetch(req, timeout):
        return Response(mapping[int(req.full_url.rsplit("/", 1)[1])])
    result = attest_all(now=NOW, opener=fetch, repository=REPO)
    assert len(result["proofs"]) == 3
    assert result["vps_to_cpanel_ssh_access_proven"] is True
    for key in ("mojplaywin_live_app_root_proven",
                "subsite_passenger_isolation_proven",
                "commercial_release_authorized", "payment_gateway_authorized"):
        assert result[key] is False


def test_pr_workflow_holds_all_production_secrets_and_uses_only_hosted_runner():
    root = Path(__file__).resolve().parents[1]
    wf = (root / ".github/workflows/revenue36-origin-readonly.yml").read_text()
    source = (root / "scripts/revenue36_origin_evidence_readonly.py").read_text()
    for forbidden in ("secrets.", "VPS_SSH_PRIVATE_KEY",
                      "SAEIT_HOST_SSH_PRIVATE_KEY", "ProxyJump",
                      "ssh -T", "runs-on: [self-hosted"):
        assert forbidden not in wf
    assert "runs-on: ubuntu-latest" in wf
    assert "github.event.pull_request.head.repo.full_name" in wf
    assert "persist-credentials: false" in wf
    assert "commercial_release_authorized" in source
    assert "False" in source
