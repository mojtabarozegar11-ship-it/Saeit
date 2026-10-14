#!/usr/bin/env python3
"""Recover an already-executed Termux diagnostic using Git-over-SSH.

Migrates a pending receipt left by issue_worker.py after its GitHub Issues
token was refused. Does NOT execute the action again. Publishes only fixed,
redacted status fields in the isolated Saeit feature branch.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

from .worker import (
    BRANCH, COMMAND_PATH, REPO, RESULT_PATH, STATUS_PATH,
    Bridge, BridgeError, git, parse_time, read_json, validate_command,
    write_json,
)

EXPECTED_CODES = {
    "ping": {"pong": True},
    "whoami_check": {"whoami_check_passed": True,
                     "whoami_check_failed": False},
    "python_check": {"python_available": True},
}
RECEIPT_FIELDS = frozenset({
    "type", "protocol_version", "command_id", "action",
    "ok", "code", "completed_at",
})


class PendingGitBridge(Bridge):
    """One-shot delivery of an existing, locally persisted receipt."""

    def __init__(self, checkout, state_dir, remote=REPO,
                 branch=BRANCH, clock=None):
        super().__init__(checkout, remote=remote, branch=branch, clock=clock)
        self.state_file = Path(state_dir).expanduser() / "issue-receipt-state.json"

    def once(self):
        # Never run an action here: delivery only.
        self.prepare()
        if not self.state_file.is_file():
            return "NO_SAVED_RECEIPT"
        state = read_json(self.state_file)
        pending = state.get("pending")
        if pending is None:
            return "NO_PENDING_RECEIPT"
        if not isinstance(pending, dict) or set(pending) != RECEIPT_FIELDS:
            raise BridgeError("saved receipt schema invalid")
        if pending.get("type") != "saeit_termux_receipt_v1":
            raise BridgeError("invalid receipt type")
        if type(pending.get("protocol_version")) is not int or pending["protocol_version"] != 1:
            raise BridgeError("invalid receipt version")
        if type(pending.get("ok")) is not bool:
            raise BridgeError("invalid result boolean")

        command_file = self.checkout / COMMAND_PATH
        if not command_file.is_file():
            raise BridgeError("command file unavailable")
        command = validate_command(command_file.read_bytes(), self.clock())
        if (pending["command_id"] != command["command_id"]
                or pending["action"] != command["action"]):
            raise BridgeError("saved receipt does not match current command")
        if pending.get("code") not in EXPECTED_CODES.get(command["action"], {}):
            raise BridgeError("unrecognized receipt result")
        if pending["ok"] is not EXPECTED_CODES[command["action"]][pending["code"]]:
            raise BridgeError("inconsistent receipt result")
        completed = parse_time(pending.get("completed_at"))
        if not (parse_time(command["issued_at"]) - timedelta(minutes=2)
                <= completed <= self.clock() + timedelta(minutes=2)):
            raise BridgeError("receipt completion time invalid")
        handled = state.get("handled", [])
        if not isinstance(handled, list) or not all(isinstance(x, str) for x in handled):
            raise BridgeError("invalid saved handled IDs")

        result_file = self.checkout / RESULT_PATH
        result_prev = read_json(result_file) if result_file.is_file() else {}
        result = {
            "protocol_version": 1,
            "command_id": command["command_id"],
            "action": command["action"],
            "ok": pending["ok"],
            "code": pending["code"],
            "completed_at": pending["completed_at"],
        }

        # If Git already contains this receipt, do not make a second commit.
        if result_prev.get("command_id") == command["command_id"]:
            if result_prev != result:
                raise BridgeError("conflicting existing Git receipt")
            write_json(self.state_file, {
                "handled": list(dict.fromkeys([*handled, command["command_id"]]))[-1000:],
                "pending": None,
            })
            return "SAVED_RECEIPT_ALREADY_DELIVERED"

        status = {
            "protocol_version": 1,
            "state": "idle",
            "last_command_id": command["command_id"],
            "last_result": pending["code"],
        }
        write_json(result_file, result)
        write_json(self.checkout / STATUS_PATH, status)
        git(self.checkout, "add", "--", RESULT_PATH, STATUS_PATH)
        git(self.checkout, "-c", "user.name=Saeit Termux Bridge",
            "-c", "user.email=bridge@users.noreply.github.com",
            "commit", "-m", "bridge: deliver stored safe receipt "
            + command["command_id"])
        git(self.checkout, "push", "origin", "HEAD:" + self.branch, timeout=60)

        # Clear pending ONLY after Git confirms the real push.
        write_json(self.state_file, {
            "handled": list(dict.fromkeys([*handled, command["command_id"]]))[-1000:],
            "pending": None,
        })
        return "SAVED_RECEIPT_PUSHED_WITHOUT_REEXECUTION"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Deliver already-executed safe Termux receipt over Git SSH"
    )
    parser.add_argument("--once", action="store_true", required=True)
    parser.parse_args(argv)
    home = Path.home() / ".saeit-termux-bridge"
    bridge = PendingGitBridge(home / "repo", home / "state")
    try:
        print(bridge.once(), flush=True)
        return 0
    except BridgeError as exc:
        print("TERMUX_GIT_RECEIPT_ERROR: " + str(exc),
              file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
