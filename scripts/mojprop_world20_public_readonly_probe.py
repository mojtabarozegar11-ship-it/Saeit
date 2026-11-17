#!/usr/bin/env python3
"""Fixed public-only MojPlayWin availability probe; no credentials, no POST.

Designed to run on an unprivileged GitHub-hosted runner. It never examines
private URLs, submits buyer data, or interprets a passing CI as deployment.
All printed paths are constant literals; only statuses and boolean markers
are emitted. External redirects are never followed.
"""
from __future__ import annotations

import json
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

_ORIGIN = "https://mojplaywin.com"
_CASES = (
    ("/", "GET", b""),
    ("/moj-prop/", "GET", b""),
    ("/world/", "GET", b""),
    ("/world/fa/", "GET", b""),
    ("/world/fa/moj-prop-interest/", "GET", b'name="csrfmiddlewaretoken"'),
    ("/moj-prop-intake/?format=html", "GET", b'name="csrfmiddlewaretoken"'),
)


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def scan_one(path, method, marker, *, opener):
    if path not in [item[0] for item in _CASES] or method != "GET":
        raise ValueError("Only preapproved read-only public pages may be probed")
    request = Request(
        _ORIGIN + path,
        headers={
            "User-Agent": "MojProp-OwnerReadOnly-HTTP/1.0",
            "Cache-Control": "no-cache",
            "Accept": "text/html",
        },
        method=method,
    )
    status = None
    match = False
    try:
        with opener.open(request, timeout=10) as response:
            status = response.status
            # Bounded public HTML, no output, no user credentials, no PII.
            body = response.read(128 * 1024)
            match = bool(marker and marker in body)
    except HTTPError as exc:
        status = exc.code
        exc.close()
    except (URLError, TimeoutError, OSError, ssl.SSLError):
        pass
    return {"path": path, "http_status": status, "public_form_csrf_marker": match}


def snapshot(*, opener=None):
    client = opener or build_opener(
        NoRedirects, HTTPSHandler(context=ssl.create_default_context()),
    )
    observations = [scan_one(path, method, marker, opener=client)
                    for path, method, marker in _CASES]
    statuses = {x["path"]: x for x in observations}
    return {
        "schema": "mojprop.world20.public_readonly_probe.v1",
        "read_only": True,
        "fixed_public_origin": _ORIGIN,
        "observations": observations,
        "world20_publicly_reachable": statuses["/world/"]["http_status"] == 200,
        "crm_html_form_publicly_reachable":
            statuses["/moj-prop-intake/?format=html"]["http_status"] == 200
            and statuses["/moj-prop-intake/?format=html"]["public_form_csrf_marker"],
        "proof_of_submission": False,
        "buyer_data_accessed": False,
        "payment_verified": False,
        "publication_authorized": False,
    }


if __name__ == "__main__":
    print("MOJPROP_PUBLIC_READONLY_PROBE=" +
          json.dumps(snapshot(), sort_keys=True, separators=(",", ":")))
