import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from termux_bridge.recover_pending_git import PendingGitBridge
from termux_bridge.worker import BridgeError, timestamp
from test_termux_bridge import NOW, request, seed_remote, cli

BRANCH = "feature/termux-safe-command-bridge-20261014"


def pending_receipt(action="ping", code="pong", ok=True,
                    command_id="probe-20261014"):
    return {
        "type": "saeit_termux_receipt_v1",
        "protocol_version": 1,
        "command_id": command_id,
        "action": action,
        "ok": ok,
        "code": code,
        "completed_at": timestamp(NOW),
    }


def prepare(td, *, pending=True, current_command=None):
    remote = seed_remote(td, current_command or request())
    home = Path(td) / "phone-local-only"
    state_dir = home / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    if pending:
        (state_dir / "issue-receipt-state.json").write_text(
            json.dumps({"handled": [], "pending": pending_receipt()}),
            encoding="utf-8",
        )
    bridge = PendingGitBridge(
        checkout=home / "repo", state_dir=state_dir,
        remote=str(remote), clock=lambda: NOW,
    )
    return remote, bridge


class PendingGitRecoveryTests(unittest.TestCase):
    def test_deliver_existing_pending_over_git_without_action_execution(self):
        with tempfile.TemporaryDirectory() as td:
            remote, bridge = prepare(td)
            previous = cli("--git-dir", remote, "rev-parse", BRANCH)
            with patch("termux_bridge.worker.run_allowlisted") as action:
                self.assertEqual(
                    bridge.once(),
                    "SAVED_RECEIPT_PUSHED_WITHOUT_REEXECUTION",
                )
            action.assert_not_called()
            self.assertNotEqual(
                cli("--git-dir", remote, "rev-parse", BRANCH), previous
            )
            result = json.loads(cli(
                "--git-dir", remote, "show", BRANCH + ":bridge/result.json"
            ))
            self.assertEqual(result["code"], "pong")
            self.assertEqual(result["command_id"], "probe-20261014")
            self.assertNotIn("username", json.dumps(result))
            local_state = json.loads(bridge.state_file.read_text())
            self.assertIsNone(local_state["pending"])
            self.assertIn("probe-20261014", local_state["handled"])
            self.assertEqual(bridge.once(), "NO_PENDING_RECEIPT")

    def test_no_saved_state_never_executes(self):
        with tempfile.TemporaryDirectory() as td:
            _, bridge = prepare(td, pending=False)
            with patch("termux_bridge.worker.run_allowlisted") as action:
                self.assertEqual(bridge.once(), "NO_SAVED_RECEIPT")
            action.assert_not_called()

    def test_no_pending_receipt_stays_idle(self):
        with tempfile.TemporaryDirectory() as td:
            _, bridge = prepare(td)
            bridge.state_file.write_text(
                json.dumps({"handled": ["old"], "pending": None})
            )
            self.assertEqual(bridge.once(), "NO_PENDING_RECEIPT")

    def test_conflicting_pending_action_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            remote, bridge = prepare(td)
            old = cli("--git-dir", remote, "rev-parse", BRANCH)
            state = json.loads(bridge.state_file.read_text())
            state["pending"]["action"] = "whoami_check"
            bridge.state_file.write_text(json.dumps(state))
            with self.assertRaisesRegex(BridgeError, "does not match"):
                bridge.once()
            self.assertEqual(cli("--git-dir", remote, "rev-parse", BRANCH), old)

    def test_disallowed_sensitive_code_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            remote, bridge = prepare(td)
            old = cli("--git-dir", remote, "rev-parse", BRANCH)
            state = json.loads(bridge.state_file.read_text())
            state["pending"]["code"] = "phone_private_token"
            bridge.state_file.write_text(json.dumps(state))
            with self.assertRaisesRegex(BridgeError, "unrecognized"):
                bridge.once()
            self.assertEqual(cli("--git-dir", remote, "rev-parse", BRANCH), old)

    def test_inconsistent_ok_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            _, bridge = prepare(td)
            state = json.loads(bridge.state_file.read_text())
            state["pending"]["ok"] = False
            bridge.state_file.write_text(json.dumps(state))
            with self.assertRaisesRegex(BridgeError, "inconsistent"):
                bridge.once()

    def test_saved_result_already_on_git_is_not_reexecuted_or_recommitted(self):
        with tempfile.TemporaryDirectory() as td:
            remote, bridge = prepare(td)
            bridge.once()
            original_sha = cli("--git-dir", remote, "rev-parse", BRANCH)
            bridge.state_file.write_text(json.dumps(
                {"handled": [], "pending": pending_receipt()}
            ))
            self.assertEqual(bridge.once(), "SAVED_RECEIPT_ALREADY_DELIVERED")
            self.assertEqual(cli("--git-dir", remote, "rev-parse", BRANCH),
                             original_sha)

    def test_wrong_command_id_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            _, bridge = prepare(td)
            state = json.loads(bridge.state_file.read_text())
            state["pending"]["command_id"] = "unexpected-id"
            bridge.state_file.write_text(json.dumps(state))
            with self.assertRaisesRegex(BridgeError, "does not match"):
                bridge.once()


if __name__ == "__main__":
    unittest.main()
