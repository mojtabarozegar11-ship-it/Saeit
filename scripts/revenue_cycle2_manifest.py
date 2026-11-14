#!/usr/bin/env python3
"""SHA-256 manifest of predefined, public, synthetic evidence assets.

Never reads a customer-provided path or walks a home directory.
"""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_FILES = (
    "docs/revenue-p0/example-farm-model.synthetic.json",
    "docs/revenue-p0/example-checkout-intake.synthetic.json",
    "docs/revenue-p0/example-farm-intake.synthetic.json",
    "docs/revenue-p0/example-website-audit.synthetic.md",
)


def manifest():
    assets = []
    for rel in ALLOWED_FILES:
        path = ROOT / rel
        if not path.is_file() or path.is_symlink():
            raise ValueError("SYNTHETIC_ASSET_MISSING_OR_SYMLINK")
        size = path.stat().st_size
        if size > 65536:
            raise ValueError("SYNTHETIC_ASSET_SIZE_INVALID")
        content = path.read_bytes()
        if len(content) != size:
            raise ValueError("SYNTHETIC_ASSET_CHANGED")
        assets.append({"path": rel, "bytes": size,
                       "sha256": hashlib.sha256(content).hexdigest()})
    return {
        "schema": "mojtaba.bot.ai.synthetic-asset-manifest.v1",
        "canonical_bot": "mojtaba.bot.ai",
        "synthetic_only": True,
        "customer_data_included": False,
        "verified_live_delivery": False,
        "assets": assets,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(manifest(), sort_keys=True, indent=2))
