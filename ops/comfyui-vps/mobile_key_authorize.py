#!/usr/bin/env python3
"""Authorize only a dedicated mobile SSH *public* key for local ComfyUI forwarding.

Installed under githubops on VPS, never run as root. No factory, firewall,
sshd configuration, or ComfyUI process is modified.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

MARKER = "saeit-comfyui-mobile-v1"
LIMIT = 'restrict,port-forwarding,permitopen="127.0.0.1:18188",command="/bin/false"'
KEY_RE = re.compile(r"^ssh-ed25519 ([A-Za-z0-9+/]+={0,2})$")
MAX_SIZE = 1024 * 1024


def parse_key(raw: str) -> str:
    if len(raw) > 1000 or "\n" in raw.strip("\n") or "\r" in raw:
        raise ValueError("invalid public key format")
    words = raw.strip().split()
    if len(words) < 2 or words[0] != "ssh-ed25519":
        raise ValueError("only ssh-ed25519 public keys accepted")
    key = words[0] + " " + words[1]
    if not KEY_RE.fullmatch(key):
        raise ValueError("invalid public key encoding")
    # Validate the actual SSH key binary via OpenSSH, not just a regex.
    with tempfile.NamedTemporaryFile("w", prefix="saeit-pub-", delete=False) as tmp:
        path = Path(tmp.name)
        tmp.write(key + "\n")
    try:
        if subprocess.run(
            ["ssh-keygen", "-l", "-f", str(path)],
            capture_output=True, timeout=8, check=False,
        ).returncode:
            raise ValueError("ssh-keygen rejected supplied key")
    finally:
        path.unlink(missing_ok=True)
    return key


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) == 2 else ""
    if mode not in {"status", "authorize", "revoke"}:
        print("INVALID_MODE")
        return 2
    if os.geteuid() == 0:
        print("ROOT_UNSUPPORTED")
        return 3
    home = Path.home()
    ssh_dir = home / ".ssh"
    keys_file = ssh_dir / "authorized_keys"
    if ssh_dir.is_symlink() or (keys_file.exists() and keys_file.is_symlink()):
        print("SYMLINK_NOT_ALLOWED")
        return 4
    if mode == "status" and not keys_file.is_file():
        print("COMFYUI_MOBILE_KEY_NOT_AUTHORIZED")
        return 0
    ssh_dir.mkdir(mode=0o700, exist_ok=True)
    if not ssh_dir.is_dir():
        print("SSH_DIRECTORY_INVALID")
        return 5
    ssh_dir.chmod(0o700)
    if keys_file.exists() and (not keys_file.is_file() or keys_file.stat().st_size > MAX_SIZE):
        print("AUTHORIZED_KEYS_UNSAFE")
        return 6
    old = keys_file.read_text(encoding="utf-8") if keys_file.exists() else ""
    rows = old.splitlines(keepends=True)
    ours = [line for line in rows if line.rstrip("\r\n").endswith(" " + MARKER)]
    if mode == "status":
        print("COMFYUI_MOBILE_KEY_AUTHORIZED" if ours else "COMFYUI_MOBILE_KEY_NOT_AUTHORIZED")
        return 0
    if mode == "authorize":
        try:
            key = parse_key(sys.stdin.read(1024))
        except (ValueError, OSError, subprocess.TimeoutExpired):
            print("INVALID_SSH_PUBLIC_KEY")
            return 7
        replacement = LIMIT + " " + key + " " + MARKER + "\n"
    else:
        replacement = ""
    # Do not change any unrelated SSH keys.
    retained = [line for line in rows if not line.rstrip("\r\n").endswith(" " + MARKER)]
    content = "".join(retained)
    if content and not content.endswith("\n"):
        content += "\n"
    content += replacement
    fd, tmp_name = tempfile.mkstemp(dir=ssh_dir, prefix=".authorized-")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(content)
        os.replace(tmp_name, keys_file)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    print("COMFYUI_MOBILE_KEY_AUTHORIZED" if mode == "authorize" else "COMFYUI_MOBILE_KEY_REVOKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
