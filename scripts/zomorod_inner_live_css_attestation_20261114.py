#!/usr/bin/env python3
"""Read-only HTML CSS marker census for existing Zomorod inner pages.

Public GET only. Never logs in, posts, changes production, or asserts host-file identity.
A source-only CSS fix is NOT a production fix until verified on the live page.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

BASE = "https://zomorodmelal.ir"
TARGETS = (
    ("/ghanadi/", "ZM_INTERIOR_OLIVE_SCOPED_20261114"),
    ("/ghanadi/cafe-shiraz/", "ZM_INTERIOR_OLIVE_CAFE_20261114"),
    ("/auctions/", "zm-auctions-inner-olive-20261114"),
)
OLIVE = "#252b19"
OUT = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "zm-interior-css-attestation"
USER_AGENT = "Zomorod-ReadOnly-Palette-Attestation/20261114"


def inspect_path(route: str, marker: str) -> dict:
    assert route.startswith("/") and route != "/" and ".." not in route
    result = {"route": route, "expected_css_marker": marker, "method": "GET",
              "production_writes": 0, "deployment_claim": False}
    req = urllib.request.Request(BASE + route, headers={"User-Agent": USER_AGENT},
                                 method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            data = response.read(1024 * 1024 + 1)
            result["http_status"] = response.status
            result["content_type"] = response.headers.get("Content-Type", "")
            result["truncated"] = len(data) > 1024 * 1024
        data = data[:1024 * 1024]
        html = data.decode("utf-8", errors="replace")
        found = re.search(r'<meta\\s+name=["\\\']theme-color["\\\']\\s+content=["\\\']([^"\\\']+)', html, re.I)
        result.update({
            "html_sha256": hashlib.sha256(data).hexdigest(),
            "bytes_seen": len(data),
            "theme_color": found.group(1) if found else None,
            "marker_live": marker in html,
            "olive_color_literal_live": OLIVE in html,
            "live_css_status": "MARKER_VISIBLE" if marker in html
                               else "NOT_PROVEN_FROM_PUBLIC_HTML",
            "host_file_identity_proven": False
        })
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        result.update({"live_css_status": "UNKNOWN_FETCH_FAILED",
                       "error": str(err)[:140],
                       "host_file_identity_proven": False})
    return result


def main() -> None:
    assert len(TARGETS) == len({p for p, _ in TARGETS}) == 3
    assert all(p != "/" for p, _ in TARGETS)
    entries = [inspect_path(route, marker) for route, marker in TARGETS]
    report = {"site": BASE, "homepage_excluded": True, "get_only": True,
              "production_writes": 0, "forms_submitted": 0,
              "no_release_or_host_identity_inferred": True, "results": entries}
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / "report.json"
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for row in entries:
        print("ZM_INNER_ATTESTATION " + json.dumps(row, ensure_ascii=False))
    print("ZM_INNER_ATTESTATION_PATH " + str(dest))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
            handle.write("\\n### Read-only live CSS marker attestation (not deployment verification)\\n")
            for row in entries:
                handle.write(f"- {row['route']}: {row['live_css_status']}\\n")


if __name__ == "__main__":
    main()
