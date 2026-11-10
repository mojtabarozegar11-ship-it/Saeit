"""No-network, no-host-write safety checks for the optional pull transport."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/zomorod_secure_issue_pull.py"
SPEC = importlib.util.spec_from_file_location("zomorod_secure_issue_pull", MODULE_PATH)
pull = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pull)


def comment(comment_id, *, owner=True, edited=False, marker=True):
    envelope = {
        "v": 1,
        "alg": "RSA-OAEP-256+A256CBC-HS256",
        "ek": "encrypted-key",
        "iv": "nonce",
        "ct": "encrypted-task",
        "mac": "authentication-tag",
    }
    return {
        "id": comment_id,
        "user": {
            "login": pull.OWNER_LOGIN if owner else "somebody-else",
            "id": pull.OWNER_USER_ID if owner else 101,
        },
        "author_association": "OWNER" if owner else "NONE",
        "created_at": "2026-11-10T08:00:00Z",
        "updated_at": "2026-11-10T08:01:00Z" if edited else "2026-11-10T08:00:00Z",
        "body": (pull.MARKER if marker else "NOT-A-COMMAND\n")
        + json.dumps(envelope),
    }


def state(path, last_id=0, pending=None):
    pull.save_checkpoint(
        path, {"version": 1, "last_id": last_id, "pending": pending},
        create=True,
    )


def test_owner_envelope_is_eligible():
    assert json.loads(pull.eligible_envelope(comment(1)))["v"] == 1


@pytest.mark.parametrize("mutated", [
    {"user": {"login": pull.OWNER_LOGIN, "id": 333}},
    {"author_association": "CONTRIBUTOR"},
    {"created_at": "2026-11-10T07:00:00Z"},
    {"body": "ZMR-PUBLIC-KEY-V1"},
    {"body": pull.MARKER + "{}"},
])
def test_forged_edited_or_malformed_commands_rejected(mutated):
    candidate = comment(1)
    candidate.update(mutated)
    assert pull.eligible_envelope(candidate) is None


def test_wrong_owner_and_edited_comment_rejected():
    assert pull.eligible_envelope(comment(1, owner=False)) is None
    assert pull.eligible_envelope(comment(1, edited=True)) is None
    assert pull.eligible_envelope(comment(1, marker=False)) is None


def test_bootstrap_skips_historical_commands(tmp_path):
    checkpoint = tmp_path / "issue.state"
    with patch.object(pull, "fetch_comments", return_value=[comment(4), comment(9)]):
        assert pull.main(["--bootstrap", "--checkpoint", str(checkpoint)]) == 0
    assert pull.load_checkpoint(checkpoint)["last_id"] == 9
    calls = []
    assert pull.poll_once(checkpoint, [comment(4), comment(9)], calls.append) == "NO_NEW_AUTHORIZED_COMMAND"
    assert calls == []


def test_one_new_task_accepted_once(tmp_path):
    checkpoint = tmp_path / "issue.state"
    state(checkpoint, last_id=9)
    calls = []
    comments = [comment(10, marker=False), comment(11), comment(12)]
    assert pull.poll_once(checkpoint, comments, calls.append) == "ONE_COMMAND_ACCEPTED"
    assert len(calls) == 1
    assert pull.load_checkpoint(checkpoint) == {"version": 1, "last_id": 11, "pending": None}
    assert pull.poll_once(checkpoint, comments, calls.append) == "ONE_COMMAND_ACCEPTED"
    assert len(calls) == 2  # New comment 12, not a replay of 11.


def test_write_ahead_state_blocks_replay_after_import_failure(tmp_path):
    checkpoint = tmp_path / "issue.state"
    state(checkpoint)

    def fail(_):
        pending = pull.load_checkpoint(checkpoint)["pending"]
        assert pending["id"] == 1
        raise RuntimeError("simulated interruption")

    with pytest.raises(RuntimeError):
        pull.poll_once(checkpoint, [comment(1)], fail)
    with pytest.raises(pull.PullError, match="PENDING_REQUIRES_MANUAL_RECONCILIATION"):
        pull.poll_once(checkpoint, [comment(1)], lambda _: None)


def test_no_checkpoint_means_no_execution(tmp_path):
    calls = []
    with pytest.raises(pull.PullError, match="CHECKPOINT_NOT_PRIVATE_OR_MISSING"):
        pull.poll_once(tmp_path / "missing.state", [comment(1)], calls.append)
    assert calls == []


def test_public_issue_url_is_pinned():
    assert pull.ENDPOINT.startswith("https://api.github.com/")
    assert pull.ENDPOINT.endswith("/issues/1600/comments")
    assert "remote" not in pull.ENDPOINT


def test_invalid_page_and_duplicate_comment_fail_closed():
    with patch.object(pull, "_fetch_page", return_value=[comment(1), comment(1)]):
        with pytest.raises(pull.PullError, match="GITHUB_DUPLICATE_OR_INVALID_ID"):
            pull.fetch_comments()
    with patch.object(
        pull, "_fetch_page",
        side_effect=lambda page: [comment(page * 100 + i) for i in range(100)],
    ):
        with pytest.raises(pull.PullError, match="GITHUB_PAGE_LIMIT_REACHED"):
            pull.fetch_comments()


def test_checkpoint_permissions_are_strict(tmp_path):
    checkpoint = tmp_path / "issue.state"
    state(checkpoint)
    assert checkpoint.stat().st_mode & 0o777 == 0o600
    checkpoint.chmod(0o644)
    with pytest.raises(pull.PullError, match="CHECKPOINT_NOT_PRIVATE_OR_MISSING"):
        pull.load_checkpoint(checkpoint)


def test_probe_never_invokes_ingress(tmp_path):
    with (
        patch.object(pull, "fetch_comments", return_value=[comment(1)]),
        patch.object(pull, "accept_envelope", side_effect=AssertionError("must not run")),
    ):
        assert pull.main(["--probe"]) == 0
    assert not list(tmp_path.iterdir())
