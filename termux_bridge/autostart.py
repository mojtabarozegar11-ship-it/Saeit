#!/usr/bin/env python3
"""Minimal Android Termux:Boot launcher for the Saeit allowlisted Git worker.

Never starts a listener, performs sudo, requests Android permissions, or
accepts arbitrary commands. Termux:Boot must be installed/opened separately.
"""
from __future__ import annotations

import argparse
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import time

from .worker import Bridge, BridgeError, BRANCH, REPO

INTERVAL = 300
SCRIPT_NAME = "50-saeit-termux-bridge"
SIGNATURE = "# Managed by Saeit Termux Safe Bridge v1"
EXPECTED_PREFIX = "/data/data/com.termux/files/usr"


def paths(home: Path):
    home = Path(home).expanduser().resolve()
    state = home / ".saeit-termux-bridge"
    return state, state / "repo", home / ".termux" / "boot" / SCRIPT_NAME


def boot_script():
    # No untrusted interpolation, no private data, all paths within Termux $HOME.
    return (
        "#!/data/data/com.termux/files/usr/bin/sh\n"
        + SIGNATURE + "\n"
        + 'cd "$HOME/.saeit-termux-bridge/repo" || exit 1\n'
        + 'test -f "termux_bridge/autostart.py" || exit 1\n'
        + 'command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock || true\n'
        + 'exec python -m termux_bridge.autostart --start\n'
    )


def install(home: Path, *, check_termux=True):
    state, checkout, script = paths(home)
    if check_termux and not os.environ.get("PREFIX", "").startswith(EXPECTED_PREFIX):
        raise BridgeError("Termux installation environment not detected")
    if not (checkout / "termux_bridge" / "worker.py").is_file():
        raise BridgeError("existing Saeit Termux checkout missing")
    if not (checkout / "termux_bridge" / "autostart.py").is_file():
        raise BridgeError("boot launcher source missing in checkout")
    if (checkout / "bridge" / "command.json").is_symlink():
        raise BridgeError("unexpected command symlink")
    script.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    script.parent.chmod(0o700)
    if script.is_symlink():
        raise BridgeError("refusing boot script symlink")
    if script.exists():
        existing = script.read_text(encoding="utf-8")
        if SIGNATURE not in existing:
            raise BridgeError("refusing to replace another boot launcher")
        if existing == boot_script():
            script.chmod(0o700)
            return "BOOT_HOOK_ALREADY_INSTALLED"
    # Atomic within boot folder; no modification of unrelated user files.
    import tempfile
    with tempfile.NamedTemporaryFile(
        dir=script.parent, mode="w", encoding="utf-8",
        prefix=".saeit-", delete=False
    ) as out:
        tmp = Path(out.name)
        out.write(boot_script())
    try:
        tmp.chmod(0o700)
        os.replace(tmp, script)
    finally:
        tmp.unlink(missing_ok=True)
    return "BOOT_HOOK_INSTALLED"


def is_locked(file):
    """Check the boot-runner lock, not unrelated foreground Termux processes."""
    file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with file.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        return False


def run_forever(home: Path, interval=INTERVAL, *, bridge=None,
                snooze=time.sleep, limit=None):
    state, checkout, _ = paths(home)
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    lockpath = state / "autostart.lock"
    with lockpath.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("SAEIT_WORKER_ALREADY_RUNNING", flush=True)
            return 0
        instance = bridge or Bridge(checkout)
        completed = 0
        print("SAEIT_WORKER_STARTED_INTERVAL_300", flush=True)
        while limit is None or completed < limit:
            try:
                result = instance.once()
                if result not in {"ALREADY_HANDLED", "NO_COMMAND"}:
                    print("SAEIT_WORKER_RESULT=" + result, flush=True)
            except BridgeError as exc:
                # All external Git errors are sanitized by Bridge.git.
                print("SAEIT_WORKER_RECOVERABLE_ERROR=" + str(exc), flush=True)
            except OSError:
                print("SAEIT_WORKER_RECOVERABLE_OS_ERROR", flush=True)
            completed += 1
            if limit is None or completed < limit:
                try:
                    snooze(interval)
                except KeyboardInterrupt:
                    return 0
    return 0


def start(home: Path, python=None, *, spawner=None):
    state, checkout, _ = paths(home)
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    if is_locked(state / "autostart.lock"):
        return "SAEIT_WORKER_ALREADY_RUNNING"
    if not (checkout / "termux_bridge" / "autostart.py").is_file():
        raise BridgeError("autostart module missing")
    log = state / "autostart.log"
    interpreter = python or sys.executable
    launch = spawner or subprocess.Popen
    with log.open("a", encoding="utf-8") as stream:
        launch(
            [interpreter, "-m", "termux_bridge.autostart", "--run"],
            cwd=str(checkout),
            stdin=subprocess.DEVNULL, stdout=stream, stderr=stream,
            start_new_session=True, close_fds=True,
        )
    return "SAEIT_BACKGROUND_WORKER_LAUNCHED"


def boot_addon_status():
    """Does not install Android applications or modify Android settings."""
    try:
        p = subprocess.run(
            ["pm", "path", "com.termux.boot"],
            shell=False, text=True, capture_output=True, timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "TERMUX_BOOT_APP_STATUS_UNKNOWN"
    if p.returncode == 0 and "package:" in p.stdout:
        return "TERMUX_BOOT_APP_INSTALLED"
    return "TERMUX_BOOT_APP_NOT_CONFIRMED"


def main(argv=None):
    parser = argparse.ArgumentParser()
    options = parser.add_mutually_exclusive_group(required=True)
    options.add_argument("--install", action="store_true")
    options.add_argument("--start", action="store_true")
    options.add_argument("--run", action="store_true")
    options.add_argument("--status", action="store_true")
    args = parser.parse_args(argv)
    home = Path.home()
    try:
        if args.install:
            print(install(home))
            print(boot_addon_status())
            return 0
        if args.status:
            state, _, script = paths(home)
            print("BOOT_HOOK_PRESENT" if script.is_file() and
                  SIGNATURE in script.read_text(encoding="utf-8")
                  else "BOOT_HOOK_NOT_INSTALLED")
            print("SAEIT_BACKGROUND_ACTIVE" if is_locked(
                state / "autostart.lock") else "SAEIT_BACKGROUND_NOT_ACTIVE")
            print(boot_addon_status())
            return 0
        if args.start:
            print(start(home))
            return 0
        if args.run:
            return run_forever(home)
    except BridgeError as exc:
        print("SAEIT_AUTOSTART_ERROR=" + str(exc), file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
