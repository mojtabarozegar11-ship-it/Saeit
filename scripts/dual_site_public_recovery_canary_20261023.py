#!/usr/bin/env python3
"""Anonymous, read-only cross-domain recovery canary.

Protects against the October 2026 regression where HTTP 200 showed a directory
listing rather than the site. No SSH, secrets, POST, payment, DB or site writes.
This is a known-route sample; it cannot certify all unknown subsites or sales.
"""
from __future__ import annotations
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SITES = {
    "zomorodmelal.ir": {
        "/": "زمرد",
        "/about/": "زمرد",
        "/research/": "پژوهش",
        "/contact/": "تماس",
        "/games/": "بازی",
        "/games/water-path/": "مسیر آب",
        "/agriculture/water-soil/irrigation-planner/": "آبیاری",
        "/agriculture/greenhouse/ventilation-estimator/": "گلخانه",
    },
    "mojplaywin.com": {
        "/": "Moj Play Win",
        "/games/": "Games",
        "/products/": "Digital Products",
        "/store/": "Digital Store",
        "/company/": "MojPlayWin",
        "/saman/": "SAMAN",
        "/farnaz/": "Farnaz",
        "/studio.Roham/": "Studio Raham",
        "/zahra$$/": "Zahra",
        "/taniya/": "Taniya",
        "/games/corwn-defender/": "CROWN DEFENDER",
        "/mpw-editorial/field-guides/20261023/index.html": "Field Studio",
        "/mpw-editorial/field-guides/20261023/prism-relay/index.html": "PRISM RELAY",
        "/mpw-editorial/field-guides/20261023/release.json": "MPW-FIELDGUIDES-20261023-01",
    },
}
MANIFEST_PATH = "/mpw-editorial/field-guides/20261023/release.json"
MAX_BODY = 550_000
MAX_REDIRECTS = 2


class RestrictedRedirect(urllib.request.HTTPRedirectHandler):
    """Allow redirects only to the same exact public path and domain."""

    def __init__(self, host: str, path: str):
        super().__init__()
        self.host, self.path, self.count = host, path, 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(urllib.parse.urljoin(req.full_url, newurl))
        if (target.scheme != "https"
                or target.hostname not in (self.host, "www." + self.host)
                or target.path != self.path
                or target.port not in (None, 443)
                or target.username or target.password
                or target.query or target.fragment):
            raise ValueError("redirect_outside_exact_site_route")
        self.count += 1
        if self.count > MAX_REDIRECTS:
            raise ValueError("redirect_loop")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def examine(host: str, path: str, code: int, data: bytes, final_url: str) -> str:
    """Return an error code, not the page body; an empty string means pass."""
    if host not in SITES or path not in SITES[host]:
        return "unapproved_route"
    final = urllib.parse.urlsplit(final_url)
    if final.scheme != "https" or final.hostname not in (host, "www." + host) or final.path != path:
        return "wrong_origin_or_route"
    if code != 200:
        return "http_" + str(code)
    if len(data) < 90:
        return "unexpected_short_body"
    if path == MANIFEST_PATH:
        try:
            manifest = json.loads(data.decode("utf-8"))
            expected = (manifest.get("release_id") == "MPW-FIELDGUIDES-20261023-01"
                        and manifest.get("guide_count") == 50
                        and manifest.get("stage_count") == 150
                        and len(manifest.get("files_sha256", {})) == 53)
        except (UnicodeError, ValueError, AttributeError, TypeError):
            expected = False
        return "" if expected else "release_manifest_mismatch"
    html = data.decode("utf-8", errors="replace")
    if re.search(r"<(?:title|h1)[^>]*>\s*Index of(?: /|<)", html, flags=re.I):
        return "directory_listing_exposed"
    if re.search(r"<title[^>]*>\s*(?:503 Service Unavailable|404 Not Found)", html, flags=re.I):
        return "http_200_error_page"
    if SITES[host][path].casefold() not in html.casefold():
        return "wrong_page_identity"
    return ""


def probe(host: str, path: str, opener_factory=None) -> dict:
    if host not in SITES or path not in SITES[host]:
        raise ValueError("route_not_allowlisted")
    url = "https://" + host + path
    handler = RestrictedRedirect(host, path)
    opener = opener_factory(handler) if opener_factory else urllib.request.build_opener(handler)
    request = urllib.request.Request(url, method="GET", headers={
        "User-Agent": "Saeit-DualSite-RecoveryReadOnly/1.0",
        "Cache-Control": "no-cache, no-store",
        "Pragma": "no-cache",
        "Accept": "text/html,application/json",
    })
    status, data, final_url, reason = 0, b"", url, ""
    try:
        with opener.open(request, timeout=14) as response:
            status = response.status
            final_url = response.geturl()
            data = response.read(MAX_BODY)
    except urllib.error.HTTPError as exc:
        status = exc.code
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        reason = type(exc).__name__
    error = reason or examine(host, path, status, data, final_url)
    return {
        "site": host, "path": path, "http_status": status,
        "checked_bytes": len(data), "body_sha256_prefix": hashlib.sha256(data).hexdigest()[:16] if data else None,
        "outcome": "pass" if not error else "fail", "reason": error or None,
    }


def report() -> dict:
    records = []
    for host, routes in SITES.items():
        for path in routes:
            result = probe(host, path)
            if result["outcome"] != "pass":
                time.sleep(1.5)
                retry = probe(host, path)
                retry["retried_after_failure"] = True
                result = retry
            records.append(result)
            print("PUBLIC_RECOVERY_CHECK", json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
    failures = [x for x in records if x["outcome"] != "pass"]
    return {
        "purpose": "read_only_dual_domain_known_route_recovery_regression",
        "method": "anonymous_GET",
        "site_count": len(SITES), "route_count": len(records),
        "failed_count": len(failures), "status": "healthy_sample" if not failures else "regression_detected",
        "files_changed": 0, "payments_tested": False,
        "unknown_subsites_certified": False,
        "deployment_authorized": False,
    }


if __name__ == "__main__":
    result = report()
    print("PUBLIC_RECOVERY_SUMMARY", json.dumps(result, sort_keys=True))
    sys.exit(0 if result["failed_count"] == 0 else 1)
