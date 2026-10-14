#!/usr/bin/env python3
"""Issue-based safe receipt transport for Termux with read-only Git access.

Only the pre-allowlisted diagnostic operations in worker.py can execute.
Never posts raw command stdout, usernames, paths, keys or tokens. GitHub
Issues are PUBLIC because Saeit is public. Requires a separately authenticated
GitHub CLI on the actual phone; the connected chat GitHub account is not
automatically available to Termux.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from termux_bridge.worker import (
    Bridge, BridgeError, COMMAND_PATH, REPO, BRANCH,
    read_json, run_allowlisted, timestamp, validate_command, write_json,
)

ISSUE_REPO = "mojtabarozegar11-ship-it/Saeit"
ISSUE_NUMBER = 98
SAFE_CODES = frozenset({
    "pong", "whoami_check_passed", "whoami_check_failed", "python_available",
})


def classify_gh_error(stderr):
    """Return only a non-sensitive category, never GitHub stderr itself."""
    message = (stderr or "").lower()
    if "resource not accessible by personal access token" in message:
        return "ISSUES_TOKEN_MISSING_WRITE_PERMISSION"
    if "403" in message or "forbidden" in message:
        return "ISSUES_PERMISSION_DENIED_403"
    if "401" in message or "bad credentials" in message:
        return "GITHUB_AUTHORIZATION_EXPIRED_401"
    if "404" in message or "not found" in message:
        return "GITHUB_ISSUE_NOT_FOUND_OR_INACCESSIBLE_404"
    if "could not resolve host" in message or "network is unreachable" in message:
        return "GITHUB_NETWORK_UNAVAILABLE"
    if "rate limit" in message:
        return "GITHUB_RATE_LIMIT"
    if "prompt" in message or "terminal" in message:
        return "GITHUB_CLI_INTERACTIVE_ERROR"
    return "GITHUB_ISSUES_REJECTED_UNCLASSIFIED"


def default_gh(args):
    """Run a fixed GitHub CLI operation; report sanitized errors only."""
    if not args or args[0] not in {"auth", "issue"}:
        raise BridgeError("unexpected GitHub CLI operation")
    try:
        completed = subprocess.run(
            ["gh", *args], shell=False, check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )
    except FileNotFoundError:
        print("GITHUB_ISSUE_DIAGNOSTIC=GH_CLI_NOT_INSTALLED", file=sys.stderr)
        return False
    except subprocess.TimeoutExpired:
        print("GITHUB_ISSUE_DIAGNOSTIC=GH_CLI_TIMEOUT", file=sys.stderr)
        return False
    if completed.returncode != 0 and args[0] == "issue":
        print("GITHUB_ISSUE_DIAGNOSTIC=" + classify_gh_error(
            completed.stderr), file=sys.stderr)
    return completed.returncode == 0


class IssuesBridge(Bridge):
    def __init__(self, checkout, state_dir, remote=REPO, branch=BRANCH,
                 clock=None, gh=default_gh):
        super().__init__(checkout=checkout, remote=remote,
                         branch=branch, clock=clock)
        self.state_dir = Path(state_dir).expanduser()
        self.state_file = self.state_dir / "issue-receipt-state.json"
        self.gh = gh

    def gh_ready(self):
        if not self.gh(["auth", "status", "--hostname", "github.com"]):
            raise BridgeError("GitHub Issues authentication unavailable on phone")

    def _post(self, receipt):
        if receipt.get("code") not in SAFE_CODES:
            raise BridgeError("unexpected result code")
        allowed = {
            "type", "protocol_version", "command_id", "action",
            "ok", "code", "completed_at",
        }
        if set(receipt) != allowed or receipt.get("type") != "saeit_termux_receipt_v1":
            raise BridgeError("invalid receipt schema")
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=self.state_dir,
            prefix=".issue-body-", delete=False,
        ) as file:
            tmp = Path(file.name)
            file.write(json.dumps(receipt, sort_keys=True,
                                  separators=(",", ":")) + "\n")
        try:
            tmp.chmod(0o600)
            if not self.gh([
                "issue", "comment", str(ISSUE_NUMBER),
                "--repo", ISSUE_REPO, "--body-file", str(tmp),
            ]):
                raise BridgeError("GitHub Issues receipt submission failed")
        finally:
            tmp.unlink(missing_ok=True)

    def once(self):
        self.prepare()
        command_file = self.checkout / COMMAND_PATH
        if not command_file.is_file():
            return "NO_COMMAND"
        command = validate_command(command_file.read_bytes(), self.clock())
        state = read_json(self.state_file) if self.state_file.is_file() else {}
        handled = state.get("handled", [])
        if not isinstance(handled, list) or not all(
            isinstance(x, str) for x in handled
        ):
            raise BridgeError("invalid local receipt history")
        pending = state.get("pending")
        if pending is not None:
            if not isinstance(pending, dict):
                raise BridgeError("invalid pending receipt")
            self.gh_ready()
            self._post(pending)
            # A past receipt gets posted before accepting any new command.
            handled.append(pending["command_id"])
            state = {"handled": list(dict.fromkeys(handled))[-1000:],
                     "pending": None}
            write_json(self.state_file, state)
            if pending["command_id"] == command["command_id"]:
                return "ISSUE_RECEIPT_POSTED"
            handled = state["handled"]
        if command["command_id"] in handled:
            return "ALREADY_HANDLED"
        # Never run any operation unless the phone can first authenticate
        # to the Issues receipt channel.
        self.gh_ready()
        outcome = run_allowlisted(command["action"])
        if outcome["code"] not in SAFE_CODES:
            raise BridgeError("unexpected action result")
        receipt = {
            "type": "saeit_termux_receipt_v1",
            "protocol_version": 1,
            "command_id": command["command_id"],
            "action": command["action"],
            "ok": outcome["ok"],
            "code": outcome["code"],
            "completed_at": timestamp(self.clock()),
        }
        # Save pending first: network errors must not cause re-execution.
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        write_json(self.state_file, {"handled": handled, "pending": receipt})
        self._post(receipt)
        handled.append(receipt["command_id"])
        write_json(self.state_file, {
            "handled": list(dict.fromkeys(handled))[-1000:], "pending": None,
        })
        return "ISSUE_RECEIPT_POSTED"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Termux safe read-only Git + GitHub Issues reply bridge"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=300,
                        help="Poll every 60..3600 seconds (default: 300)")
    args = parser.parse_args(argv)
    if not 60 <= args.interval <= 3600:
        parser.error("--interval must be 60..3600")
    home = Path.home() / ".saeit-termux-bridge"
    bridge = IssuesBridge(home / "repo", home / "state")
    while True:
        try:
            result = bridge.once()
            print(result, flush=True)
        except BridgeError as exc:
            print("TERMUX_BRIDGE_ERROR: " + str(exc), file=sys.stderr,
                  flush=True)
            if args.once:
                return 1
        if args.once:
            return 0
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
