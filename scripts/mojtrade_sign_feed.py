#!/usr/bin/env python3
"""Sign an existing research snapshot; never query markets or place an order.

Usage: MOJTRADE_PUBLIC_FEED_HMAC_KEY=... python scripts/mojtrade_sign_feed.py
       --input /private/validated-payload.json --output /private/signed-feed.json
"""

import argparse
import hashlib
import hmac
import json
import os
import tempfile
from pathlib import Path


def sign(payload, secret):
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("Versioned JSON payload required")
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return {
        "payload": payload,
        "signature": hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description="Sign a MojTrade research feed without executing trades")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    secret = os.getenv("MOJTRADE_PUBLIC_FEED_HMAC_KEY", "")
    if len(secret) < 32:
        parser.error("MOJTRADE_PUBLIC_FEED_HMAC_KEY must be a private random key of at least 32 characters")
    if not args.input.is_file() or args.input.is_symlink():
        parser.error("Input must be a regular file")
    if not args.output.is_absolute() or not args.output.parent.is_dir() or args.output.is_symlink():
        parser.error("Output must be an absolute path in an existing private directory")
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    document = (json.dumps(sign(payload, secret), ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(document) > 96_000:
        parser.error("Feed exceeds 96 KB limit")
    with tempfile.NamedTemporaryFile(dir=args.output.parent, prefix=".mojtrade-", delete=False) as temp:
        temp_path = Path(temp.name)
        os.chmod(temp_path, 0o600)
        try:
            temp.write(document)
            temp.flush()
            os.fsync(temp.fileno())
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
    os.replace(temp_path, args.output)
    print("SIGNED_FEED_WRITTEN (no market query, financial action or publication performed)")


if __name__ == "__main__":
    main()
