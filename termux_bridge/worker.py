#!/usr/bin/env python3
"""Saeit Termux pull bridge: fixed read-only operations; no arbitrary shell.

Repo Saeit is public. Results deliberately omit usernames, paths, hostnames,
device IDs, raw stdout and environment variables. No key is uploaded.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone

REPO = "git@github.com:mojtabarozegar11-ship-it/Saeit.git"
BRANCH = "feature/termux-safe-command-bridge-20261014"
PROTOCOL_VERSION = 1
VALID_ACTIONS = frozenset({"ping", "whoami_check", "python_check"})
COMMAND_PATH = "bridge/command.json"
RESULT_PATH = "bridge/result.json"
STATUS_PATH = "bridge/status.json"
ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}$")

class BridgeError(RuntimeError):
    pass

def timestamp(dt=None):
    dt = dt if dt is not None else datetime.now(timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def parse_time(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise BridgeError("timestamp must be UTC ISO-8601 ending in Z")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise BridgeError("malformed timestamp") from exc
    return dt.astimezone(timezone.utc)

def validate_command(raw, now=None):
    if len(raw) > 4096:
        raise BridgeError("command too large")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise BridgeError("invalid command JSON") from exc
    required = {"protocol_version", "command_id", "action", "issued_at", "expires_at"}
    if not isinstance(data, dict) or set(data) != required:
        raise BridgeError("unknown or missing command fields")
    if type(data["protocol_version"]) is not int or data["protocol_version"] != 1:
        raise BridgeError("unsupported protocol")
    if not isinstance(data["command_id"], str) or not ID_RE.fullmatch(data["command_id"]):
        raise BridgeError("invalid command id")
    if data["action"] not in VALID_ACTIONS:
        raise BridgeError("action not allowlisted")
    issued, expires = parse_time(data["issued_at"]), parse_time(data["expires_at"])
    current = now if now is not None else datetime.now(timezone.utc)
    if issued > current + timedelta(minutes=2):
        raise BridgeError("command issued in future")
    if expires <= current:
        raise BridgeError("command expired")
    if expires <= issued or expires - issued > timedelta(days=7):
        raise BridgeError("invalid command lifetime")
    return data

def run_allowlisted(action, runner=subprocess.run):
    """Fixed operations only; stdout never leaves the phone."""
    if action == "ping":
        return {"ok": True, "code": "pong"}
    if action == "python_check":
        return {"ok": sys.version_info.major >= 3, "code": "python_available"}
    if action == "whoami_check":
        try:
            p = runner(["id", "-un"], shell=False, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                       timeout=5, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return {"ok": False, "code": "whoami_check_failed"}
        ok = p.returncode == 0 and bool(p.stdout.strip())
        return {"ok": ok, "code": "whoami_check_passed" if ok else "whoami_check_failed"}
    raise BridgeError("action not allowlisted")

def read_json(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BridgeError("bridge state unavailable") from exc
    if not isinstance(value, dict):
        raise BridgeError("invalid bridge state")
    return value

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, sort_keys=True, ensure_ascii=True, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".pending-", delete=False) as file:
        temp = Path(file.name)
        file.write(content)
    os.replace(temp, path)

def git(repo_dir, *args, timeout=40):
    cmd = ["git"]
    if repo_dir is not None:
        cmd.extend(["-C", str(repo_dir)])
    cmd.extend(args)
    env = os.environ.copy()
    env["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=10"
    try:
        p = subprocess.run(cmd, check=False, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True,
                           timeout=timeout, env=env)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise BridgeError("git command unavailable or timed out") from exc
    if p.returncode != 0:
        raise BridgeError("git operation failed: " + args[0])
    return p.stdout.strip()

class Bridge:
    def __init__(self, checkout, remote=REPO, branch=BRANCH, clock=None):
        self.checkout = Path(checkout).expanduser()
        self.remote = remote
        self.branch = branch
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def prepare(self):
        if not self.checkout.exists():
            self.checkout.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            git(None, "clone", "--depth", "1", "--single-branch", "--no-tags",
                "--branch", self.branch, self.remote, str(self.checkout), timeout=90)
        if not (self.checkout / ".git").is_dir():
            raise BridgeError("dedicated checkout is not a Git repository")
        if git(self.checkout, "branch", "--show-current") != self.branch:
            raise BridgeError("unexpected working branch")
        if git(self.checkout, "status", "--porcelain"):
            raise BridgeError("dedicated checkout has local changes; refusing overwrite")
        git(self.checkout, "pull", "--ff-only", "origin", self.branch, timeout=60)

    def once(self):
        self.prepare()
        command_file = self.checkout / COMMAND_PATH
        if not command_file.is_file():
            return "NO_COMMAND"
        command = validate_command(command_file.read_bytes(), self.clock())
        result_file = self.checkout / RESULT_PATH
        prev = read_json(result_file) if result_file.is_file() else {}
        if prev.get("command_id") == command["command_id"]:
            return "ALREADY_HANDLED"
        outcome = run_allowlisted(command["action"])
        result = {
            "protocol_version": 1,
            "command_id": command["command_id"],
            "action": command["action"],
            "ok": outcome["ok"],
            "code": outcome["code"],
            "completed_at": timestamp(self.clock()),
        }
        status = {
            "protocol_version": 1,
            "state": "idle",
            "last_command_id": command["command_id"],
            "last_result": outcome["code"],
        }
        write_json(result_file, result)
        write_json(self.checkout / STATUS_PATH, status)
        git(self.checkout, "add", "--", RESULT_PATH, STATUS_PATH)
        git(self.checkout, "-c", "user.name=Saeit Termux Bridge",
            "-c", "user.email=bridge@users.noreply.github.com",
            "commit", "-m", "bridge: safe receipt " + command["command_id"])
        git(self.checkout, "push", "origin", "HEAD:" + self.branch, timeout=60)
        return "SAFE_COMMAND_RECEIPT_PUSHED"

def main(argv=None):
    parser = argparse.ArgumentParser(description="Safe GitHub pull bridge for Termux")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=120)
    args = parser.parse_args(argv)
    if not args.once and not args.loop:
        parser.error("Choose --once or --loop")
    if not 60 <= args.interval <= 3600:
        parser.error("--interval must be 60..3600")
    bridge = Bridge(Path.home() / ".saeit-termux-bridge" / "repo")
    while True:
        try:
            print(bridge.once(), flush=True)
        except BridgeError as exc:
            print("BRIDGE_ERROR: " + str(exc), file=sys.stderr, flush=True)
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
