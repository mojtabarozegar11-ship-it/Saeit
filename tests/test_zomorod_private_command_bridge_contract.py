"""Regression contract for the public half of the private company command relay.

The recipient's private key, decryption, HMAC verification and durable database
receipt live exclusively on cPanel. These tests intentionally do not claim to
exercise that private component or submit a real command.
"""

import ast
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "zomorod-private-command-dispatch.yml"
)
VALID_ENVELOPE = {
    "v": 1,
    "alg": "RSA-OAEP-256+A256CBC-HS256",
    "ek": "synthetic-ek",
    "iv": "synthetic-iv",
    "ct": "synthetic-ct",
    "mac": "synthetic-mac",
}


def _source():
    return WORKFLOW.read_text(encoding="utf-8")


def _inline_event_scripts():
    """Extract embedded Python without requiring an optional YAML parser."""
    lines = _source().splitlines()
    scripts = []
    needle = 'python3 - "$GITHUB_EVENT_PATH" <<' + "'PY'"
    for index, line in enumerate(lines):
        if needle not in line:
            continue
        indent = len(line) - len(line.lstrip(" "))
        collected = []
        for next_line in lines[index + 1:]:
            if next_line.strip() == "PY" and (
                len(next_line) - len(next_line.lstrip(" "))
            ) == indent:
                scripts.append("\n".join(collected) + "\n")
                break
            if not next_line.strip():
                collected.append("")
                continue
            assert next_line.startswith(" " * indent)
            collected.append(next_line[indent:])
        else:
            raise AssertionError("Embedded Python heredoc was not closed")
    return scripts


def test_embedded_event_scripts_are_valid_python():
    scripts = _inline_event_scripts()
    assert len(scripts) == 2
    for script in scripts:
        ast.parse(script)


def test_dispatch_is_owner_main_only_for_manual_or_exact_issue_comment():
    source = _source()
    triggers = source.split("permissions:", 1)[0]
    assert "  workflow_dispatch:\n" in triggers
    assert "  issue_comment:\n    types: [created]\n" in triggers
    assert "github.event.issue.number == 1600" in source
    assert "github.event.comment.author_association == 'OWNER'" in source
    assert "github.event.comment.user.login == 'mojtabarozegar11-ship-it'" in source
    assert "github.event.comment.body == 'ZMR-PUBLIC-KEY-V1'" in source
    assert "startsWith(github.event.comment.body, 'ZMR-SEALED-COMMAND-V1')" in source
    for forbidden in (
        "\n  push:", "\n  pull_request:", "\n  schedule:",
        "\n  repository_dispatch:", "\n  workflow_run:",
    ):
        assert forbidden not in triggers
    assert "github.actor == 'mojtabarozegar11-ship-it'" in source
    assert "github.actor == 'chatgpt-codex-connector[bot]'" in source
    assert "github.event_name == 'workflow_dispatch'" in source
    assert "github.event_name == 'issue_comment'" in source
    assert "github.ref == 'refs/heads/main'" in source
    assert 'test "$GITHUB_ACTOR" = "$EXPECTED_ACTOR"' in source
    assert 'test "$GITHUB_ACTOR" = "$EXPECTED_APP_ACTOR"' in source
    assert 'test "$GITHUB_EVENT_NAME" = "workflow_dispatch"' in source
    assert 'test "$GITHUB_REF" = "$EXPECTED_REF"' in source
    assert "contents: read" in source
    assert "    concurrency:\n      group: zomorod-private-chat-command-inbox" in source
    assert "for attempt in 1 2 3 4 5; do" in source
    assert "if test \"$attempt\" -lt 5; then sleep 12; fi" in source


def test_ssh_is_pinned_to_current_relay_and_new_host():
    source = _source()
    assert "HostName 178.239.147.150" in source
    assert "HostName 178.239.147.125" in source
    assert "Port 1396" in source
    assert "ProxyJump saeit-vps" in source
    assert "StrictHostKeyChecking yes" in source
    assert "IdentitiesOnly yes" in source
    assert "ForwardAgent no" in source
    assert "SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs" in source
    assert "SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04" in source
    assert "178.239.147.124" not in source
    assert "zohal.pws-dns.net" not in source


def _run_gate(event, event_name, tmp_path, actor="mojtabarozegar11-ship-it"):
    script = _inline_event_scripts()[0]
    event_path = tmp_path / "workflow-event.json"
    event_path.write_text(json.dumps(event), encoding="utf-8")
    output_path = tmp_path / "github-output.txt"
    env = os.environ.copy()
    env.update({
        "GITHUB_EVENT_NAME": event_name,
        "GITHUB_ACTOR": actor,
        "GITHUB_OUTPUT": str(output_path),
        "RUNNER_TEMP": str(tmp_path),
    })
    result = subprocess.run(
        [sys.executable, "-c", script, str(event_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
        env=env,
    )
    return result, output_path, tmp_path / "zomorod-sealed-command.txt"


def _owner_comment(body, *, issue_number=1600, user="mojtabarozegar11-ship-it",
                   association="OWNER", action="created", pr=False, app=None):
    issue = {"number": issue_number}
    if pr:
        issue["pull_request"] = {"url": "https://example.invalid/pr"}
    comment = {
        "body": body,
        "user": {"login": user},
        "author_association": association,
    }
    if app is not None:
        comment["performed_via_github_app"] = {"slug": app}
    return {"action": action, "issue": issue, "comment": comment}


@pytest.mark.parametrize(
    ("operation", "envelope", "allowed"),
    [
        ("show_public_key", None, True),
        ("accept", json.dumps(VALID_ENVELOPE), True),
        ("accept", None, False),
        ("accept", "", False),
        ("accept", "not-json", False),
        ("accept", "[]", False),
        ("accept", "{}", False),
        ("accept", json.dumps({**VALID_ENVELOPE, "v": 2}), False),
        ("accept", json.dumps({**VALID_ENVELOPE, "alg": "none"}), False),
        ("accept", json.dumps({**VALID_ENVELOPE, "unexpected": "x"}), False),
        ("accept", "x" * 24001, False),
        ("unexpected", None, False),
    ],
)
def test_manual_input_gate_rejects_bad_envelopes(
    operation, envelope, allowed, tmp_path
):
    # Runner-side *structure* only, never decryption or private queue mutation.
    inputs = {"operation": operation}
    if envelope is not None:
        inputs["sealed_envelope"] = envelope
    result, outputs, encrypted = _run_gate(
        {"inputs": inputs}, "workflow_dispatch", tmp_path
    )
    assert (result.returncode == 0) is allowed, (operation, result.stderr)
    if allowed:
        assert f"operation={operation}\n" in outputs.read_text(encoding="utf-8")
        assert encrypted.exists() is (operation == "accept")
    else:
        assert not encrypted.exists()


@pytest.mark.parametrize(
    ("event", "allowed", "operation"),
    [
        (_owner_comment("ZMR-PUBLIC-KEY-V1"), True, "show_public_key"),
        (_owner_comment("ZMR-SEALED-COMMAND-V1\n" + json.dumps(VALID_ENVELOPE)), True, "accept"),
        (_owner_comment("ZMR-PUBLIC-KEY-V1", issue_number=1601), False, None),
        (_owner_comment("ZMR-PUBLIC-KEY-V1", user="another-user"), False, None),
        (_owner_comment("ZMR-PUBLIC-KEY-V1", association="CONTRIBUTOR"), False, None),
        (_owner_comment("ZMR-PUBLIC-KEY-V1", action="edited"), False, None),
        (_owner_comment("ZMR-PUBLIC-KEY-V1", pr=True), False, None),
        (_owner_comment(" ZMR-PUBLIC-KEY-V1"), False, None),
        (_owner_comment("ZMR-PUBLIC-KEY-V1\nextra"), False, None),
        (_owner_comment("ZMR-SEALED-COMMAND-V1\n{}"), False, None),
        (_owner_comment("ZMR-SEALED-COMMAND-V1\nnot-json"), False, None),
        (_owner_comment("ZMR-SEALED-COMMAND-V1" + json.dumps(VALID_ENVELOPE)), False, None),
        (_owner_comment("ZMR-SEALED-COMMAND-V1\n" + "x" * 24001), False, None),
    ],
)
def test_comment_gate_accepts_only_owner_and_bounded_encrypted_envelope(
    event, allowed, operation, tmp_path
):
    result, outputs, encrypted = _run_gate(event, "issue_comment", tmp_path)
    assert (result.returncode == 0) is allowed, result.stderr
    if allowed:
        assert f"operation={operation}\n" in outputs.read_text(encoding="utf-8")
        if operation == "accept":
            raw = event["comment"]["body"].split("\n", 1)[1]
            assert encrypted.read_text(encoding="utf-8") == raw
            assert (encrypted.stat().st_mode & 0o777) == 0o600
            assert raw not in result.stdout + result.stderr
        else:
            assert not encrypted.exists()
    else:
        assert not encrypted.exists()


def test_unexpected_event_type_is_rejected(tmp_path):
    event = _owner_comment("ZMR-PUBLIC-KEY-V1")
    result, _, _ = _run_gate(event, "push", tmp_path)
    assert result.returncode != 0


def test_queue_receipt_is_required_and_execution_is_not_claimed():
    source = _source()
    assert 'grep -Fq "COMMAND_RECEIPT=ACCEPTED"' in source
    assert 'grep -Fq "COMMAND_QUEUE=UPDATED"' in source
    assert 'echo "COMPANY_WORK_EXECUTION=NOT_PERFORMED"' in source
    assert "if: steps.gate.outputs.operation == 'accept'" in source
    assert "if: steps.gate.outputs.operation == 'show_public_key'" in source
    assert "if: always()" in source
    assert 'rm -rf "$RUNNER_TEMP/zomorod-command-channel"' in source


def test_action_actor_identity_is_checked_for_manual_and_app_comments(tmp_path):
    owner = "mojtabarozegar11-ship-it"
    bot = "chatgpt-codex-connector[bot]"
    comment = _owner_comment("ZMR-PUBLIC-KEY-V1", app="chatgpt-codex-connector")
    for event_name, event, actor, permitted in [
        ("workflow_dispatch", {"inputs": {"operation": "show_public_key"}}, owner, True),
        ("workflow_dispatch", {"inputs": {"operation": "show_public_key"}}, bot, False),
        ("issue_comment", comment, owner, True),
        ("issue_comment", comment, bot, True),
        ("issue_comment", comment, "unrelated-bot[bot]", False),
        ("issue_comment", _owner_comment("ZMR-PUBLIC-KEY-V1", app="unrelated-app"), bot, False),
        ("issue_comment", _owner_comment("ZMR-PUBLIC-KEY-V1", user="unrelated"), bot, False),
    ]:
        result, _, _ = _run_gate(event, event_name, tmp_path, actor=actor)
        assert (result.returncode == 0) is permitted, (event_name, actor, result.stderr)
