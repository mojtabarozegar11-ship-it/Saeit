"""Read-only filesystem evidence for Zomorod's /news/ and /weather/ routes.

This does not determine which document root a live web server uses; nor does it
authorize installing files, changing Apache rules, Passenger, or cron.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROUTES = ("news", "weather")
MAX_HTML_BYTES = 2_000_000


def inspect_static_routes(public_root: Path) -> dict:
    """Report static-page file evidence while preserving every target byte."""
    if public_root.is_symlink() or not public_root.is_dir() or public_root.resolve() == Path("/"):
        raise ValueError("Public root must be a specific existing non-symlink directory")

    entries = []
    for route in ROUTES:
        directory = public_root / route
        index = directory / "index.html"
        observed = {"route": f"/{route}/", "index": f"{route}/index.html"}
        if directory.is_symlink() or index.is_symlink():
            observed["state"] = "unsafe_symlink"
        elif not directory.is_dir():
            observed["state"] = "no_static_route_directory"
        elif not index.exists():
            observed["state"] = "no_static_index"
        elif not index.is_file():
            observed["state"] = "unsafe_not_regular_file"
        else:
            try:
                if index.stat().st_size > MAX_HTML_BYTES:
                    observed["state"] = "oversize_static_index"
                else:
                    payload = index.read_bytes()
                    observed.update({
                        "state": "static_index_present",
                        "bytes": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "mentions_inpage_loader": b"zm-inpage-editorial-2026.js" in payload,
                        "mentions_direct_loader": b"data-zm-editorial-loader" in payload,
                    })
            except OSError:
                observed["state"] = "unreadable"
        entries.append(observed)

    return {
        "mode": "READ_ONLY_STATIC_ROUTE_AUDIT",
        "evidence_scope": "filesystem_only_not_http_routing",
        "web_server_route_verified": False,
        "safe_to_deploy_automatically": False,
        "entries": entries,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Inspect static newsroom routes without writing")
    parser.add_argument("--public-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = inspect_static_routes(args.public_root)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
