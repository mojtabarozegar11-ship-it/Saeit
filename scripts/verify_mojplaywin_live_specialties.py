#!/usr/bin/env python3
"""Read-only release verification: all 40 MojPlayWin editorial URLs.

Usage: python scripts/verify_mojplaywin_live_specialties.py
No credentials required; never changes production.
"""
import ast
import pathlib
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "core" / "mojplaywin_specialties.py"
BASE = "https://mojplaywin.com"
tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
assignment = next(
    n for n in tree.body
    if isinstance(n, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == "SPECIALTIES" for t in n.targets
    )
)
specialties = ast.literal_eval(assignment.value)
assert len(specialties) == 40
assert sum(v["kind"] == "products" for v in specialties.values()) == 25
assert sum(v["kind"] == "services" for v in specialties.values()) == 15

failed = []
for key, item in specialties.items():
    url = f"{BASE}/{key}/"
    request = urllib.request.Request(url, headers={"User-Agent": "MojPlayWin-Release-Verification/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read(1_000_000).decode("utf-8", "replace")
            status = response.status
            robots = response.headers.get("X-Robots-Tag", "")
            if status != 200 or item["title"] not in body or "noindex" not in robots.lower():
                failed.append((url, f"status={status}, title_present={item['title'] in body}, robots={robots}"))
                print("FAIL", url)
            else:
                print("PASS", url)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        failed.append((url, type(exc).__name__))
        print("FAIL", url, type(exc).__name__)
for hub in ("products", "services"):
    url = f"{BASE}/{hub}/"
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            body = response.read(1_000_000).decode("utf-8", "replace")
            expected = [f"/{key}/" for key in specialties if key.startswith(hub + "/")]
            if response.status != 200 or not all(link in body for link in expected):
                failed.append((url, "hub missing links or bad status"))
                print("FAIL", url)
            else:
                print("PASS", url)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        failed.append((url, type(exc).__name__))
        print("FAIL", url, type(exc).__name__)
print(f"VERDICT: {42-len(failed)}/42 endpoints passed")
if failed:
    for url, reason in failed:
        print("ISSUE", url, reason)
sys.exit(bool(failed))
