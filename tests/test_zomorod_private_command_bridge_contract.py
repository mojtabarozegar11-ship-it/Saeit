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
    assert "github.event.comment.body == 'ZMR-CPANEL-READONLY-V1'" in source
    assert "github.event.comment.body == 'ZMR-CUTOVER-RECORD-V1'" in source
    assert "github.event.comment.body == 'ZMR-SEALED-SCHEMA-V1'" in source
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
        ("cpanel_readonly", None, True),
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
        (_owner_comment("ZMR-CPANEL-READONLY-V1"), True, "cpanel_readonly"),
        (_owner_comment("ZMR-CUTOVER-RECORD-V1"), True, "cutover_record"),
        (_owner_comment("ZMR-SEALED-SCHEMA-V1"), True, "sealed_schema"),
        (_owner_comment("ZMR-SEALED-SCHEMA-V1\\nsecret"), False, None),
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


def test_cpanel_readonly_command_is_exact_and_never_receives_plaintext(tmp_path):
    for body in ("ZMR-CPANEL-READONLY-V1", "ZMR-CPANEL-READONLY-V1\\nsecret", "ZMR-CPANEL-READONLY-V2"):
        result, output, encrypted = _run_gate(_owner_comment(body), "issue_comment", tmp_path)
        if body == "ZMR-CPANEL-READONLY-V1":
            assert result.returncode == 0
            assert "operation=cpanel_readonly" in output.read_text(encoding="utf-8")
            assert not encrypted.exists()
        else:
            assert result.returncode != 0
            assert not encrypted.exists()


def test_readonly_remote_commands_are_bounded_and_do_not_mutate():
    source = _source()
    step = source.split("- name: Read only cPanel inventory for the authenticated chat owner", 1)[1].split("- name: Read the current recipient public key", 1)[0]
    assert "if: steps.gate.outputs.operation == 'cpanel_readonly'" in step
    assert 'pwd.getpwuid(os.geteuid()).pw_name != "zomorod2"' in step
    for command in ("list_domains", "list_applications", "get_local_quota_info", "list_backups"):
        assert command in step
    assert "subprocess.run(" in step
    assert '[command, "--output=json", module, operation]' in step
    assert "shell=True" not in step
    assert "CPANEL_SITE_MUTATIONS=NONE" in step
    assert "CPANEL_FACTORY_OPERATIONS=NONE" in step



def test_cpanel_quota_evidence_is_bounded_sanitized_and_local_only():
    source = _source()
    step = source.split(
        "- name: Read only cPanel inventory for the authenticated chat owner", 1
    )[1].split("- name: Read the current recipient public key", 1)[0]
    assert "CPANEL_LOCAL_QUOTA_DATA=VERIFIED" in step
    assert "CPANEL_LOCAL_QUOTA_DATA=UNVERIFIED" in step
    assert 'detail.get("byte_limit")' in step
    assert 'detail.get("bytes_used")' in step
    assert "0 <= raw <= 10**15" in step
    assert "max(0, limit - used)" in step
    assert "CPANEL_LOCAL_QUOTA_HEADROOM_GIB_FLOOR=" in step
    assert "print(document)" not in step
    assert "print(result)" not in step
    assert "shell=True" not in step
    body = step.split("<<'CPANEL_READONLY_PY'\n", 1)[1].split(
        "\n          CPANEL_READONLY_PY", 1
    )[0]
    lines = body.splitlines()
    assert all(not line.strip() or line.startswith(" " * 10) for line in lines)
    ast.parse("\n".join(line[10:] for line in lines))


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


def test_emergency_direct_cpanel_path_never_lowers_identity_or_host_key_pins():
    source = _source()
    assert "Host saeit-cpanel-direct" in source
    direct = source.split("Host saeit-cpanel-direct", 1)[1].split("Host *", 1)[0]
    for line in (
        "HostName 178.239.147.125",
        "User zomorod2",
        "Port 1396",
        "IdentityFile $d/host.key",
        "UserKnownHostsFile $d/host.known",
        "ProxyJump none",
    ):
        assert line in direct
    assert "StrictHostKeyChecking yes" in source
    assert "if test \"$session_ready\" = 1; then" in source
    assert "command_host=saeit-cpanel" in source
    assert "command_host=saeit-cpanel-direct" in source
    assert "PINNED_DIRECT_CPANEL_FALLBACK=AUTHENTICATED" in source
    assert "PINNED_DIRECT_CPANEL_FALLBACK=UNAVAILABLE" in source
    assert 'printf \'command_host=%s\\n\' "$command_host" >> "$GITHUB_OUTPUT"' in source
    assert source.count('case "$COMMAND_HOST" in saeit-cpanel|saeit-cpanel-direct)') == 5
    assert source.count('COMMAND_HOST: ${{ steps.link.outputs.command_host }}') == 5
    assert 'ssh -F "$RUNNER_TEMP/zomorod-command-channel/config" "$COMMAND_HOST"' in source
    assert 'ssh -F "$d/config" "$COMMAND_HOST"' in source
    assert "UserKnownHostsFile /dev/null" not in source
    assert "StrictHostKeyChecking no" not in source


def test_ssh_control_socket_paths_fit_github_runner_unix_limit():
    source = _source()
    assert "ControlPath $d/control-%C" not in source
    assert "ControlPath $d/cpanel.sock" in source
    assert "ControlPath $d/direct.sock" in source
    assert source.count("ControlMaster auto") == 2
    assert 'install -d -m 700 "$d"' in source
    assert "ControlPath /tmp/" not in source

def test_owner_only_cutover_record_is_a_fixed_private_write_with_independent_readback(tmp_path):
    result, outputs, encrypted = _run_gate(
        _owner_comment("ZMR-CUTOVER-RECORD-V1"), "issue_comment", tmp_path
    )
    assert result.returncode == 0
    assert "operation=cutover_record" in outputs.read_text(encoding="utf-8")
    assert not encrypted.exists()
    source = _source()
    step = source.split(
        "- name: Record private owner cutover decision and verify durable write", 1
    )[1].split("- name: Read the current recipient public key", 1)[0]
    assert "if: steps.gate.outputs.operation == 'cutover_record'" in step
    assert 'case "$COMMAND_HOST" in saeit-cpanel|saeit-cpanel-direct)' in step
    assert "os.O_EXCL" in step and "O_NOFOLLOW" in step
    assert "CHAT_MUTATING_COMMAND_EXECUTED=YES" in step
    assert "PRIVATE_RECEIPT_VERIFIED=YES" in step
    assert "REMOTE_DISABLED=NO" in step
    assert "shell=True" not in step
    for marker in ("CUTOVER_WRITE_PY", "CUTOVER_VERIFY_PY"):
        body = step.split("<<'" + marker + "'\n", 1)[1].split(
            "\n          " + marker, 1
        )[0]
        ast.parse("\n".join(line[10:] for line in body.splitlines()) + "\n")



def test_private_queue_capability_audit_is_metadata_only_and_valid_python():
    source = _source()
    body = source.split("<<'CPANEL_READONLY_PY'\n", 1)[1].split(
        "\n          CPANEL_READONLY_PY", 1
    )[0]
    parsed = "\n".join(line[10:] for line in body.splitlines()) + "\n"
    ast.parse(parsed)
    for marker in (
        "PRIVATE_INGRESS_AST_AUDIT=OK",
        "PRIVATE_INGRESS_STATIC_PARSER_VERBS=",
        "PRIVATE_INGRESS_EXECUTOR_SUBCOMMAND_DETECTED=",
        "PRIVATE_QUEUE_SCHEMA_AUDIT=OK",
        "PRIVATE_QUEUE_TABLES_DETECTED=",
        "PRIVATE_QUEUE_STATE_FIELD_DETECTED=",
        "PRIVATE_QUEUE_RESULT_FIELD_DETECTED=",
        "PRIVATE_INGRESS_KNOWN_CLI_LITERALS=",
        "PRIVATE_INGRESS_EXECUTION_LITERAL_DETECTED=",
        "PRIVATE_INGRESS_WORKER_FUNCTION_CANDIDATE=",
        "PRIVATE_SCHEMA_RESULT_MARKER_ANY_TABLE=",
        "PRIVATE_QUEUE_KEYED_PAYLOAD_TABLES=",
        "PRIVATE_QUEUE_INTEGRITY_FIELD_TABLES=",
        "PRIVATE_QUEUE_TIMESTAMP_FIELD_TABLES=",
        "PRIVATE_QUEUE_LEASE_FIELD_TABLES=",
        "PRIVATE_QUEUE_WORKER_CONTRACT_TABLES=",
    ):
        assert marker in parsed
    assert "ast.parse(ingress_path.read_text" in parsed
    assert "mode=ro&immutable=1" in parsed
    assert "SELECT name FROM sqlite_master WHERE type = 'table'" in parsed
    assert "PRAGMA table_info" in parsed
    assert "SELECT *" not in parsed
    assert "shell=True" not in parsed
    assert "private_db.unlink" not in parsed
    assert "node.value in safe_verbs" in parsed
    assert "print(table_name" not in parsed
    assert "print(ingress_path.read_text" not in parsed
    assert "SELECT payload" not in parsed
    assert "db.execute(\"UPDATE" not in parsed
    for private_data in (
        "print(columns)", "print(table_name)", "print(table_rows)",
        "SELECT *", "SELECT payload", "SELECT command",
        "print(ingress_path.read_text",
    ):
        assert private_data not in parsed
    assert "worker_contract_tables += int(" in parsed
    assert "identifiers and payload and integrity and state and created" in parsed


def test_owner_sealed_schema_contract_is_encrypted_before_log_output(tmp_path):
    result, outputs, encrypted = _run_gate(
        _owner_comment("ZMR-SEALED-SCHEMA-V1"), "issue_comment", tmp_path
    )
    assert result.returncode == 0
    assert "operation=sealed_schema" in outputs.read_text(encoding="utf-8")
    assert not encrypted.exists()
    source = _source()
    step = source.split(
        "- name: Return private queue contract as sealed owner-only receipt", 1
    )[1].split(
        "- name: Record private owner cutover decision and verify durable write", 1
    )[0]
    assert "if: steps.gate.outputs.operation == 'sealed_schema'" in step
    assert "<<'ZMR_PRIVATE_SCHEMA' > \"$d/private-queue-schema.json\"" in step
    assert 'mode=ro&immutable=1' in step
    assert 'node.name in {"accept", "decrypt", "load_bridge", "main"}' in step
    assert '"selected_function_source": selected_functions' in step
    assert "ZMR_SEALED_SCHEMA=ENCRYPTED_ONLY" in step
    assert "openssl\", \"pkeyutl\", \"-encrypt" in step
    assert "rsa_padding_mode:oaep" in step
    assert "rsa_oaep_md:sha256" in step
    assert "shell=True" not in step
    assert "set -x" not in step
    assert "echo \"$d/private-queue-schema.json\"" not in step
    assert "-----BEGIN PUBLIC KEY-----" in step
    for marker in ("ZMR_PRIVATE_SCHEMA", "ZMR_ENCRYPT_SCHEMA"):
        body = step.split("<<'" + marker + "'", 1)[1].split("\n", 1)[1].split(
            "\n          " + marker, 1
        )[0]
        ast.parse("\n".join(line[10:] for line in body.splitlines()) + "\n")
