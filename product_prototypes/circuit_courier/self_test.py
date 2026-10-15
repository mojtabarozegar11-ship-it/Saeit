#!/usr/bin/env python3
"""Standalone offline game integrity check, included inside private product ZIP."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
FILES = ("engine.js", "app.js", "index.html", "style.css", "test_engine.js", "README.md")
for name in FILES:
    asset = ROOT / name
    assert asset.is_file() and not asset.is_symlink(), name
    assert 100 < asset.stat().st_size < 200000, name
html = (ROOT / "index.html").read_text(encoding="utf-8")
assert 'src="engine.js"' in html and 'src="app.js"' in html
assert 'href="style.css"' in html
assert 'https://' not in html and '<iframe' not in html.lower()
assert 'COMMERCIAL_RELEASE_ALLOWED' not in html
print("ASTRA_CIRCUIT_OFFLINE_BUNDLE_INTEGRITY=PASS")
if shutil.which("node"):
    result = subprocess.run(
        ["node", str(ROOT / "test_engine.js")],
        cwd=str(ROOT), timeout=30, text=True, capture_output=True,
        check=False)
    if result.returncode != 0:
        raise RuntimeError("independent puzzle QA failed: " + result.stderr[-1500:])
    print(result.stdout, end="")
else:
    print("ASTRA_CIRCUIT_NODE_MATH_TEST=NOT_RUN_NODE_UNAVAILABLE")
print("ASTRA_CIRCUIT_PRODUCT_SALE_READY=false")
