#!/usr/bin/env python3
"""Read-only HTTP smoke test for deployed agricultural SEO pages.

Usage: python scripts/seo_http_smoke.py https://staging.example.org
Only GET requests are issued. Does not deploy, publish or alter the server.
"""
import argparse
import sys
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

PATHS = (
    "/", "/agriculture/",
    "/agricultural-topics/agricultural-services/",
    "/agricultural-topics/agro-industry/",
    "/agricultural-topics/agricultural-company/",
    "/agricultural-topics/agricultural-research/",
    "/agricultural-topics/breeding/",
    "/agricultural-topics/agricultural-technology/",
)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url", help="Explicit staging URL, e.g. https://staging.example.org")
    args = parser.parse_args()
    base = args.base_url.rstrip("/") + "/"
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        parser.error("Only HTTPS base URLs without embedded credentials are accepted")
    failures = 0
    for path in PATHS:
        url = urljoin(base, path.lstrip("/"))
        try:
            with urlopen(Request(url, headers={"User-Agent": "ZomorodSEOStagingSmoke/1.0"}), timeout=12) as response:
                final = urlparse(response.geturl())
                if final.hostname != parsed.hostname or final.scheme != "https":
                    raise ValueError("Redirected outside the configured HTTPS staging host")
                body = response.read(2_000_000).decode("utf-8", "replace").lower()
                checks = {
                    "status": response.status == 200,
                    "title": "<title" in body and "</title>" in body,
                    "description": 'name="description"' in body or "name='description'" in body,
                    "canonical": 'rel="canonical"' in body or "rel='canonical'" in body,
                }
                failed = [key for key, ok in checks.items() if not ok]
                if failed:
                    failures += 1
                    print(f"FAIL {path}: {', '.join(failed)}")
                else:
                    print(f"PASS {path}")
        except (HTTPError, URLError, ValueError, TimeoutError) as exc:
            failures += 1
            print(f"FAIL {path}: {type(exc).__name__}: {exc}")
    print(f"RESULT: {len(PATHS)-failures}/{len(PATHS)} passed")
    return 1 if failures else 0

if __name__ == "__main__":
    sys.exit(main())
