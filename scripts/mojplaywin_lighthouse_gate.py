#!/usr/bin/env python3
"""Strict 100/100 Lighthouse acceptance for offline MojPlayWin preview pages.

Run ONLY against generated local HTML snapshots served on 127.0.0.1.
Never deploys, edits production, requests protected child sites or touches payments.
A result is acceptable only if every audited Lighthouse category is 1.0
(performance, accessibility, best practices, SEO) on both desktop and mobile.
"""
from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import threading

CATEGORIES = ("performance", "accessibility", "best-practices", "seo")
PAGES = ("home", "store", "research", "agents", "ai", "blockchain", "support", "web_engineering")
DEVICES = ("mobile", "desktop")


def check_report(report: dict) -> dict:
    categories = report.get("categories", {})
    scores = {key: (categories.get(key) or {}).get("score") for key in CATEGORIES}
    # Missing/null scores count as failure: never round 99.5 up to 100.
    failed = {key: score for key, score in scores.items()
              if not isinstance(score, (int, float)) or isinstance(score, bool) or score != 1.0}
    return {"scores": scores, "passes_100_out_of_100": not failed, "failed": failed}


def make_handler(root: Path):
    class LocalFileHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)
        def log_message(self, format, *args):
            pass
    return LocalFileHandler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("mojplaywin-v4-visual-preview"))
    parser.add_argument("--pages", nargs="+", choices=PAGES, default=list(PAGES))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--output", type=Path, default=Path("mojplaywin-lighthouse-results"))
    args = parser.parse_args()

    root = args.root.resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if not manifest.get("preview_only") or not manifest.get("production_routes_unchanged"):
        raise SystemExit("Refusing to score a non-isolated or unverified preview.")
    if any(key not in manifest["routes"] for key in args.pages):
        raise SystemExit("Requested snapshot not found in offline preview manifest.")
    args.output.mkdir(parents=True, exist_ok=True)
    with ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(root)) as server:
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        results = {}
        try:
            for page in args.pages:
                for device in DEVICES:
                    label = f"{page}-{device}"
                    report_path = args.output / f"{label}.json"
                    url = f"http://127.0.0.1:{args.port}/{manifest['routes'][page]['filename']}"
                    command = [
                        "npx", "--yes", "lighthouse@12.8.2", url,
                        "--only-categories=" + ",".join(CATEGORIES),
                        "--output=json", "--output-path=" + str(report_path.resolve()),
                        "--chrome-flags=--headless --no-sandbox --disable-dev-shm-usage",
                        "--quiet",
                    ]
                    if device == "desktop":
                        command.append("--preset=desktop")
                    result = subprocess.run(command, capture_output=True, text=True, timeout=160)
                    if result.returncode != 0 or not report_path.is_file():
                        results[label] = {"passes_100_out_of_100": False,
                                          "error": (result.stderr or result.stdout)[-1400:]}
                        continue
                    report = json.loads(report_path.read_text(encoding="utf-8"))
                    results[label] = check_report(report)
                    print(f"{label}: {results[label]}", flush=True)
        finally:
            server.shutdown()
        summary = {
            "condition": "Every score must equal 100/100 on each audited page and device.",
            "production_audited": False,
            "local_preview_only": True,
            "results": results,
            "accepted": all(v["passes_100_out_of_100"] for v in results.values())
                        and len(results) == len(args.pages) * len(DEVICES),
        }
        (args.output / "summary.json").write_text(json.dumps(summary, indent=2),
                                                    encoding="utf-8")
        print(f"MOJPLAYWIN_LIGHTHOUSE_ACCEPTED={summary['accepted']}", flush=True)
        if not summary["accepted"]:
            raise SystemExit("Lighthouse 100/100 acceptance gate FAILED.")


if __name__ == "__main__":
    main()
