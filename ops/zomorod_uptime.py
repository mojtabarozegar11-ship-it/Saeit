#!/usr/bin/env python3
"""Independent, read-only HTTPS probes for the Zomorod root application."""
import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://zomorodmelal.ir"
ROUTES = (
    ("/", "html", True),
    ("/api/health/", "django", True),
    ("/api/bridge/health/", "bridge", False),
    ("/agriculture/", "html", False),
    ("/company/", "html", False),
    ("/amozeshgah/", "html", False),
    ("/ghanadi/", "html", False),
    ("/tala/", "html", False),
)


def probe(path, kind, critical):
    req = urllib.request.Request(BASE + path, headers={
        "User-Agent": "ZomorodUptimeMonitor/1.0",
        "Cache-Control": "no-cache",
    })
    start = time.monotonic()
    code, mime, body = 0, "", b""
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            code = response.status
            mime = response.headers.get("Content-Type", "")
            body = response.read(4096)
    except urllib.error.HTTPError as exc:
        code = exc.code
        mime = exc.headers.get("Content-Type", "")
        body = exc.read(4096)
    except (OSError, ValueError, TimeoutError):
        pass
    good = code == 200 if kind in ("django", "bridge") else code in (200, 301, 302, 307, 308)
    if good and kind in ("django", "bridge"):
        try:
            payload = json.loads(body)
            good = "json" in mime.lower() and payload.get("status") == "ok"
            if kind == "django":
                good = good and payload.get("database") == "ok"
        except (ValueError, TypeError, AttributeError):
            good = False
    return {
        "path": path, "code": code, "ok": good, "critical": critical,
        "duration_ms": round((time.monotonic() - start) * 1000),
    }


def assess(probes, confirmation):
    """Only two explicit critical failures justify a confirmed outage.

    Incomplete or malformed samples must not crash the watchdog or trigger
    an automatic Passenger recovery on missing evidence.
    """
    def indexed(rows):
        return {row["path"]: row for row in rows
                if isinstance(row, dict) and isinstance(row.get("path"), str)}

    first = indexed(probes)
    second = indexed(confirmation)
    failed = [key for key in ("/", "/api/health/")
              if first.get(key, {}).get("ok") is False
              and second.get(key, {}).get("ok") is False]
    return bool(failed), failed


def run():
    primary = [probe(*item) for item in ROUTES]
    if any(not row["ok"] and row["critical"] for row in primary):
        time.sleep(3)
        confirmation = [probe(*item) for item in ROUTES if item[2]]
    else:
        confirmation = [row for row in primary if row["critical"]]
    failed, failed_paths = assess(primary, confirmation)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "captured_at": now,
        "status": "failed" if failed else ("degraded" if any(not p["ok"] for p in primary) else "healthy"),
        "confirmed_root_failure": failed,
        "failed_paths": failed_paths,
        "public": primary,
        "confirmation": confirmation,
        "passenger": {"mapping": "unverified", "processes": None, "recovery": "not_attempted"},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = run()
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    print("ZOMOROD_ROOT=" + report["status"])
    for item in report["public"]:
        print(f"ZOMOROD_PROBE={item['path']} code={item['code']} ok={str(item['ok']).lower()}")
    return 1 if report["confirmed_root_failure"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
