"""Regression contract for the public half of the private company command relay.

The recipient's private key, decryption, HMAC verification and durable database
receipt live exclusively on cPanel. These tests intentionally do not claim to
exercise that private component or submit a real command.
"""

import ast
import json
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


def test_dispatch_is_manual_owner_main_only():
    source = _source()
    triggers = source.split("permissions:", 1)[0]
    assert "  workflow_dispatch:\n" in triggers
    for forbidden in (
        "\n  push:", "\n  pull_request:", "\n  schedule:",
        "\n  repository_dispatch:", "\n  workflow_run:",
    ):
        assert forbidden not in triggers
    assert (
        "github.actor == 'mojtabarozegar11-ship-it'"
        in source
    )
    assert "github.ref == 'refs/heads/main'" in source
    assert 'test "$GITHUB_ACTOR" = "$EXPECTED_ACTOR"' in source
    assert 'test "$GITHUB_REF" = "$EXPECTED_REF"' in source
    assert "contents: read" in source


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
        (
            "accept",
            json.dumps({**VALID_ENVELOPE, "alg": "none"}),
            False,
        ),
        (
            "accept",
            json.dumps({**VALID_ENVELOPE, "unexpected": "x"}),
            False,
        ),
        ("accept", "x" * 24001, False),
        ("unexpected", None, False),
    ],
)
def test_runner_input_gate_rejects_bad_envelopes(
    operation, envelope, allowed, tmp_path
):
    # This checks *structural* input validation, not cryptographic validity.
    validation = _inline_event_scripts()[0]
    event = {"inputs": {"operation": operation}}
    if envelope is not None:
        event["inputs"]["sealed_envelope"] = envelope
    event_path = tmp_path / "workflow-event.json"
    event_path.write_text(json.dumps(event), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-c", validation, str(event_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert (result.returncode == 0) is allowed, (
        operation, envelope and envelope[:60], result.stdout, result.stderr
    )


def test_queue_receipt_is_required_and_execution_is_not_claimed():
    source = _source()
    assert 'grep -Fq "COMMAND_RECEIPT=ACCEPTED"' in source
    assert 'grep -Fq "COMMAND_QUEUE=UPDATED"' in source
    assert 'echo "COMPANY_WORK_EXECUTION=NOT_PERFORMED"' in source
    assert "if: inputs.operation == 'accept'" in source
    assert "if: inputs.operation == 'show_public_key'" in source
    assert "if: always()" in source
    assert 'rm -rf "$RUNNER_TEMP/zomorod-command-channel"' in source
