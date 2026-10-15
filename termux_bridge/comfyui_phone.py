"""One fixed, local-only Android Termux operation: prepare ComfyUI SSH identity.

The private key stays in the phone home directory. Only its PUBLIC key
can be placed in the repository's public sanitized receipt.
This module does not open listeners, connect, install packages or change VPS.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess

KEY_COMMENT = "saeit-comfyui-mobile-v1"
PUBLIC_RE = re.compile(r"^ssh-ed25519 ([A-Za-z0-9+/]+={0,2}) saeit-comfyui-mobile-v1$")
TERMUX_PREFIX = "/data/data/com.termux/files/usr"


def prepare_key(home=None, prefix=None, runner=subprocess.run):
    """Idempotent prepare; never return private key material or raw stderr."""
    active_prefix = os.environ.get("PREFIX", "") if prefix is None else prefix
    if active_prefix != TERMUX_PREFIX:
        return {"ok": False, "code": "comfyui_not_termux"}
    root = (Path(home) if home is not None else Path.home()) / ".saeit-comfyui-phone"
    key = root / "comfyui_ed25519"
    pub = root / "comfyui_ed25519.pub"
    try:
        if root.is_symlink() or key.is_symlink() or pub.is_symlink():
            return {"ok": False, "code": "comfyui_unsafe_key_path"}
        root.mkdir(mode=0o700, exist_ok=True)
        root.chmod(0o700)
        if (key.exists() or pub.exists()) and not (key.is_file() and pub.is_file()):
            return {"ok": False, "code": "comfyui_incomplete_key_pair"}
        if key.exists() and key.stat().st_size > 4096:
            return {"ok": False, "code": "comfyui_invalid_key_pair"}
        if not key.exists():
            p = runner(["ssh-keygen", "-q", "-t", "ed25519", "-N", "",
                        "-C", KEY_COMMENT, "-f", str(key)],
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=20, check=False)
            if p.returncode != 0:
                return {"ok": False, "code": "comfyui_keygen_failed"}
        key.chmod(0o600)
        pub.chmod(0o644)
        public = pub.read_text(encoding="ascii").strip()
        match = PUBLIC_RE.fullmatch(public)
        if not match or len(public) > 240:
            return {"ok": False, "code": "comfyui_invalid_key_pair"}
        # Check the public key really corresponds to the private identity.
        derived = runner(["ssh-keygen", "-y", "-P", "", "-f", str(key)],
                         stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, timeout=12, check=False)
        if derived.returncode != 0:
            return {"ok": False, "code": "comfyui_invalid_key_pair"}
        comparison = derived.stdout.decode("ascii", "strict").split()
        if len(comparison) < 2 or comparison[:2] != public.split()[:2]:
            return {"ok": False, "code": "comfyui_mismatched_key_pair"}
        return {"ok": True, "code": "comfyui_public_key_ready",
                "public_key": public}
    except (OSError, UnicodeError, subprocess.TimeoutExpired):
        return {"ok": False, "code": "comfyui_key_prepare_failed"}
