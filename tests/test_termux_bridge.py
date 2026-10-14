import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from termux_bridge.worker import (
    BRANCH, Bridge, BridgeError, run_allowlisted, timestamp, validate_command,
)

NOW = datetime(2026, 10, 14, 17, 0, tzinfo=timezone.utc)

def request(action="ping", ident="probe-20261014", when=NOW):
    return {
        "protocol_version": 1, "command_id": ident, "action": action,
        "issued_at": timestamp(when - timedelta(minutes=1)),
        "expires_at": timestamp(when + timedelta(days=1)),
    }

def cli(*args):
    p = subprocess.run(["git", *map(str, args)], check=True, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.stdout.strip()

def seed_remote(td, cmd=None):
    bare = Path(td) / "remote.git"
    cli("init", "--bare", bare)
    seed = Path(td) / "seed"
    cli("init", "-b", BRANCH, seed)
    (seed / "bridge").mkdir(parents=True)
    if cmd is not None:
        (seed / "bridge" / "command.json").write_text(
            json.dumps(cmd) + "\n", encoding="utf-8")
    (seed / "bridge" / "status.json").write_text(
        '{"protocol_version":1,"state":"waiting"}\n', encoding="utf-8")
    cli("-C", seed, "add", "bridge")
    cli("-C", seed, "-c", "user.name=Test",
        "-c", "user.email=test@example.invalid", "commit", "-m", "seed")
    cli("-C", seed, "remote", "add", "origin", bare)
    cli("-C", seed, "push", "-u", "origin", BRANCH)
    return bare

class TermuxBridgeTests(unittest.TestCase):
    def test_ping_protocol(self):
        self.assertEqual(validate_command(json.dumps(request()).encode(), NOW)["action"], "ping")
        self.assertEqual(run_allowlisted("ping"), {"ok": True, "code": "pong"})

    def test_whoami_executes_fixed_command_but_never_publishes_username(self):
        runner = Mock(return_value=subprocess.CompletedProcess(
            ["id", "-un"], 0, "private_android_username\n", ""))
        result = run_allowlisted("whoami_check", runner=runner)
        self.assertEqual(result, {"ok": True, "code": "whoami_check_passed"})
        self.assertNotIn("private_android_username", json.dumps(result))
        a, kw = runner.call_args
        self.assertEqual(a[0], ["id", "-un"])
        self.assertFalse(kw["shell"])

    def test_no_arbitrary_shell_or_extra_arguments(self):
        for action in ["exec", "bash", "rm -rf /", "shell", "curl", "ssh", "ping;whoami"]:
            with self.subTest(action=action), self.assertRaises(BridgeError):
                validate_command(json.dumps(request(action=action)).encode(), NOW)
        extra = request()
        extra["command"] = "print secrets"
        with self.assertRaises(BridgeError):
            validate_command(json.dumps(extra).encode(), NOW)

    def test_timestamps_must_be_current_and_bounded(self):
        with self.assertRaises(BridgeError):
            validate_command(json.dumps(request(when=NOW-timedelta(days=3))).encode(), NOW)
        with self.assertRaises(BridgeError):
            validate_command(json.dumps(request(when=NOW+timedelta(hours=2))).encode(), NOW)
        over = request()
        over["expires_at"] = timestamp(NOW + timedelta(days=8))
        with self.assertRaises(BridgeError):
            validate_command(json.dumps(over).encode(), NOW)

    def test_json_has_size_limit(self):
        with self.assertRaises(BridgeError):
            validate_command(b" " * 4100, NOW)

    def test_no_command_does_not_write_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            remote = seed_remote(td, None)
            bridge = Bridge(Path(td) / "isolated-repo", remote=str(remote), clock=lambda: NOW)
            self.assertEqual(bridge.once(), "NO_COMMAND")

    def test_real_git_roundtrip_receipt_and_no_replay(self):
        with tempfile.TemporaryDirectory() as td:
            remote = seed_remote(td, request("whoami_check"))
            bridge = Bridge(Path(td) / "isolated-repo", remote=str(remote), clock=lambda: NOW)
            self.assertEqual(bridge.once(), "SAFE_COMMAND_RECEIPT_PUSHED")
            raw = cli("--git-dir", remote, "show", BRANCH + ":bridge/result.json")
            result = json.loads(raw)
            self.assertEqual(result["command_id"], "probe-20261014")
            self.assertEqual(result["code"], "whoami_check_passed")
            self.assertEqual(result["ok"], True)
            self.assertNotIn("username", raw)
            old_sha = cli("--git-dir", remote, "rev-parse", BRANCH)
            self.assertEqual(bridge.once(), "ALREADY_HANDLED")
            self.assertEqual(cli("--git-dir", remote, "rev-parse", BRANCH), old_sha)

    def test_untrusted_action_never_executes_and_never_pushes(self):
        with tempfile.TemporaryDirectory() as td:
            remote = seed_remote(td, request("bash"))
            bridge = Bridge(Path(td) / "isolated-repo", remote=str(remote), clock=lambda: NOW)
            old_sha = cli("--git-dir", remote, "rev-parse", BRANCH)
            with self.assertRaisesRegex(BridgeError, "not allowlisted"):
                bridge.once()
            self.assertEqual(cli("--git-dir", remote, "rev-parse", BRANCH), old_sha)

    def test_does_not_touch_any_other_local_directory(self):
        with tempfile.TemporaryDirectory() as td:
            remote = seed_remote(td, request("ping"))
            untouched = Path(td) / "production"
            untouched.mkdir()
            marker = untouched / "SENTINEL"
            marker.write_text("keep me", encoding="utf-8")
            bridge = Bridge(Path(td) / "isolated-repo", remote=str(remote), clock=lambda: NOW)
            self.assertEqual(bridge.once(), "SAFE_COMMAND_RECEIPT_PUSHED")
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep me")

if __name__ == "__main__":
    unittest.main()
