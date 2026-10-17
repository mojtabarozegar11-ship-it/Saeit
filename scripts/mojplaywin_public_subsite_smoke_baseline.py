#!/usr/bin/env python3
"""Read-only HTTP GET health baseline for known public MojPlayWin routes.

No auth, cookies, POST, staff/admin paths, download links, payment requests,
private user data, broad discovery or write access. One GET per known URL.
This limited sampling NEVER proves safety of UNKNOWN or dynamic child sites.
"""
from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request

HOST = "mojplaywin.com"
ALLOWED_HOSTS = frozenset({"mojplaywin.com", "www.mojplaywin.com"})
PUBLIC_PATHS = (
    "/",
    "/store/",
    "/about/",
    "/mojtaba.roozegar/",
    "/mojtaba.roozegar/about/",
    "/picm/login/",
    "/studio.Roham/",
    "/saman/",
    "/farnaz/",
    "/zahra$$/",
    "/taniya/",
)
BODY_LIMIT = 65_536


class UnsafeRedirect(Exception):
    pass


class StrictRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self):
        super().__init__()
        self.redirect_count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if target.scheme != "https" or target.hostname not in ALLOWED_HOSTS or target.port not in (None, 443):
            raise UnsafeRedirect("external_or_insecure_redirect")
        self.redirect_count += 1
        if self.redirect_count > 2:
            raise UnsafeRedirect("more_than_two_redirects")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def probe(path: str, opener_factory=None) -> dict:
    if path not in PUBLIC_PATHS:
        raise ValueError("unapproved_public_route")
    redirect = StrictRedirect()
    opener = opener_factory(redirect) if opener_factory else urllib.request.build_opener(redirect)
    url = "https://" + HOST + urllib.parse.quote(path, safe="/$.-")
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": "MojPlayWin-ReadOnly-IntegrityAudit/1.0",
                 "Accept": "text/html",
                 "Cache-Control": "no-cache"},
    )
    result = {"path": path, "status": None, "redirects": 0,
              "body_prefix_sha256": None, "response_bytes_sampled": 0,
              "error_class": None}
    try:
        with opener.open(request, timeout=12) as response:
            body = response.read(BODY_LIMIT)
            result["status"] = response.status
            result["body_prefix_sha256"] = hashlib.sha256(body).hexdigest()[:16]
            result["response_bytes_sampled"] = len(body)
    except urllib.error.HTTPError as err:
        result["status"] = err.code
        # Do not read private-looking error pages; status alone suffices.
        result["error_class"] = "http_status"
    except UnsafeRedirect:
        result["error_class"] = "unsafe_redirect_blocked"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        result["error_class"] = "connection_or_protocol_error"
    result["redirects"] = redirect.redirect_count
    return result


def report(probe_function=probe) -> dict:
    records = [probe_function(path) for path in PUBLIC_PATHS]
    return {
        "classification": "KNOWN_PUBLIC_ROUTES_READ_ONLY_GET_BASELINE",
        "request_method": "GET",
        "authenticated": False,
        "approved_path_count": len(PUBLIC_PATHS),
        "responses": records,
        "unknown_subsites_inventoried": False,
        "complete_content_parity_verified": False,
        "all_protected_sites_verified": False,
        "payments_or_login_tested": False,
        "backup_restore_verified": False,
        "release_permitted": False,
    }


if __name__ == "__main__":
    print(json.dumps(report(), sort_keys=True, ensure_ascii=False))
