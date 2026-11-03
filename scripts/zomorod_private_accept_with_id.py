#!/usr/bin/env python3
"""Private ingress adapter: bind one authenticated accepted task to its exact ID.

Executed only on the pinned cPanel identity. Encrypted input arrives through
stdin; no decrypted task, keys, or environment data are printed.
"""
import importlib.util
import os
from pathlib import Path
import pwd
import re
import sys

PRIVATE = Path("/home/zomorod2/.private/zomorod-business")
INGRESS = PRIVATE / "company_ingress.py"
DATABASE = PRIVATE / "command-center.sqlite3"
HMAC_KEY = PRIVATE / ".company-bridge.key"
RECIPIENT = PRIVATE / ".chat-command-rsa.key"


def main():
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise RuntimeError("IDENTITY_REJECTED")
    if PRIVATE.is_symlink() or not PRIVATE.is_dir() or INGRESS.is_symlink() or not INGRESS.is_file():
        raise RuntimeError("INGRESS_SOURCE_REJECTED")
    spec = importlib.util.spec_from_file_location("zmr_private_ingress", INGRESS)
    if spec is None or spec.loader is None:
        raise RuntimeError("INGRESS_MODULE_REJECTED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw = sys.stdin.buffer.read(24001)
    if not 2 <= len(raw) <= 24000:
        raise RuntimeError("ENVELOPE_SIZE_REJECTED")
    command_id, _ = module.decrypt(raw, RECIPIENT, module.load_bridge())
    if not isinstance(command_id, str) or not re.fullmatch(r"[0-9a-f]{32}", command_id):
        raise RuntimeError("COMMAND_ID_REJECTED")
    result = module.accept(raw, DATABASE, HMAC_KEY, RECIPIENT)
    if result != "ACCEPTED":
        raise RuntimeError("COMMAND_NOT_ACCEPTED")
    print("COMMAND_RECEIPT=ACCEPTED")
    print("COMMAND_QUEUE=UPDATED")
    # Only a random opaque command ID; no decrypted task or plaintext secrets.
    print("PRIVATE_COMMAND_ID=" + command_id)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("PRIVATE_COMMAND_INGRESS=REJECTED", file=sys.stderr)
        sys.exit(2)
