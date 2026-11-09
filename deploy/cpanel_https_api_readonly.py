#!/usr/bin/env python3
"""Authenticated, read-only cPanel UAPI over HTTPS 2083, without SSH or SSO.

The token must be provisioned out of band as an Actions secret.  No operation
accepts an arbitrary URL, path, function, username, or mutation parameter.
Only aggregate evidence is printed; private cPanel objects stay in memory.
"""
from __future__ import annotations

import json
import os
import ssl
import sys
from urllib import error, request


CPANEL_HOST = "zohal.pws-dns.net"
CPANEL_USER = "zomorod2"
TOKEN_ENV = "SAEIT_CPANEL_HTTPS_API_TOKEN"
ALLOWED = {
    "domains": "DomainInfo/list_domains",
    "passenger": "PassengerApps/list_applications",
}
MAX_RESPONSE = 256 * 1024


class RefuseRedirect(request.HTTPRedirectHandler):
    """Never forward an Authorization header to a redirected destination."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def make_request(operation: str, token: str) -> request.Request:
    if operation not in ALLOWED:
        raise ValueError("OPERATION_DENIED")
    if not token or len(token) > 1024 or any(ord(c) < 33 or ord(c) == 127 for c in token):
        raise ValueError("TOKEN_MISSING_OR_INVALID")
    url = f"https://{CPANEL_HOST}:2083/execute/{ALLOWED[operation]}"
    return request.Request(
        url,
        headers={
            "Authorization": f"cpanel {CPANEL_USER}:{token}",
            "Accept": "application/json",
            "User-Agent": "Saeit-ReadOnly-cPanel-HTTPS/1",
        },
        method="GET",
    )


def summarize(operation: str, document: object) -> dict[str, str | int]:
    if not isinstance(document, dict):
        raise ValueError("UAPI_INVALID_ROOT")
    result = document.get("result")
    if not isinstance(result, dict) or result.get("status") not in (1, True, "1"):
        raise ValueError("UAPI_REPORTED_FAILURE")
    data = result.get("data")
    summary: dict[str, str | int] = {
        "CPANEL_HTTPS_AUTH": "VERIFIED",
        "CPANEL_UAPI_READONLY": operation.upper(),
        "CPANEL_UAPI_RESULT": "SUCCESS",
    }
    if operation == "domains":
        if not isinstance(data, dict):
            raise ValueError("UAPI_DOMAIN_SHAPE_UNEXPECTED")
        for key in ("main_domain", "addon_domains", "sub_domains", "parked_domains"):
            value = data.get(key)
            if key == "main_domain" and isinstance(value, str):
                summary["MAIN_DOMAIN_PRESENT"] = int(bool(value))
            elif isinstance(value, list):
                summary[key.upper() + "_COUNT"] = len(value)
    elif operation == "passenger":
        if not isinstance(data, (dict, list)):
            raise ValueError("UAPI_PASSENGER_SHAPE_UNEXPECTED")
        # cPanel versions return differing nested application structures;
        # a success marker is trustworthy even when no count is available.
        if isinstance(data, list):
            summary["PASSENGER_RECORDS"] = len(data)
    return summary


def query(operation: str, token: str) -> dict[str, str | int]:
    req = make_request(operation, token)
    opener = request.build_opener(
        request.HTTPSHandler(context=ssl.create_default_context()),
        RefuseRedirect(),
    )
    try:
        with opener.open(req, timeout=20) as response:
            if response.status != 200:
                raise ValueError("UAPI_NON_200_RESPONSE")
            raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise ValueError("UAPI_RESPONSE_TOO_LARGE")
    except error.HTTPError as exc:
        raise ValueError(f"UAPI_HTTP_STATUS_{exc.code}") from None
    except (error.URLError, TimeoutError, ssl.SSLError, OSError):
        raise ValueError("UAPI_TRANSPORT_UNAVAILABLE") from None
    try:
        document = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError("UAPI_NOT_JSON") from None
    return summarize(operation, document)


def probe_transport() -> dict[str, str | int]:
    """Check the service and UAPI path without sending credentials or cookies."""
    opener = request.build_opener(
        request.HTTPSHandler(context=ssl.create_default_context()),
        RefuseRedirect(),
    )

    def check(path: str, accept: str) -> tuple[int, str]:
        req = request.Request(
            f"https://{CPANEL_HOST}:2083/{path}",
            headers={"Accept": accept, "User-Agent": "Saeit-cPanel-Transport-Probe/1"},
            method="GET",
        )
        try:
            with opener.open(req, timeout=20) as response:
                # Content type distinguishes a 200 login HTML page from an
                # API response. Never read or log private response bodies.
                media_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                return response.status, media_type
        except error.HTTPError as exc:
            # Authentication challenges and redirects prove endpoint reachability.
            # We never follow redirects and never read private response bodies.
            media_type = exc.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() if exc.headers else ""
            return exc.code, media_type
        except (error.URLError, TimeoutError, ssl.SSLError, OSError):
            raise ValueError("CPANEL_HTTPS_TRANSPORT_UNAVAILABLE") from None

    status, _ = check("", "text/html")
    api_status, api_media_type = check("execute/Version/get", "application/json")
    if not (200 <= status < 500 and 200 <= api_status < 500):
        raise ValueError("CPANEL_HTTPS_SERVICE_UNHEALTHY")
    if api_media_type == "text/html":
        api_response_kind = "HTML_NOT_API_RESULT"
    elif api_media_type == "application/json":
        api_response_kind = "JSON_AUTH_UNVERIFIED"
    else:
        api_response_kind = "OTHER_AUTH_UNVERIFIED"
    return {
        "CPANEL_HTTPS_TLS": "VERIFIED",
        "CPANEL_HTTPS_HTTP_STATUS": status,
        "CPANEL_UAPI_UNAUTH_HTTP_STATUS": api_status,
        "CPANEL_UAPI_UNAUTH_RESPONSE_KIND": api_response_kind,
        "CPANEL_HTTPS_AUTH": "NOT_ATTEMPTED",
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in (*ALLOWED, "preflight"):
        print("CPANEL_HTTPS_OPERATION_DENIED", file=sys.stderr)
        return 64
    if argv[1] == "preflight":
        try:
            result = probe_transport()
        except ValueError as exc:
            print("CPANEL_HTTPS_CHECK_FAILED=" + str(exc), file=sys.stderr)
            return 1
        for key, value in result.items():
            print(f"{key}={value}")
        if not os.environ.get(TOKEN_ENV):
            print("CPANEL_API_TOKEN_STATUS=NOT_CONFIGURED")
            return 0
        print("CPANEL_API_TOKEN_STATUS=CONFIGURED_UNVERIFIED")
        # An existing token is checked only by an explicitly selected inventory
        # operation; preflight never consumes it or claims authentication.
        return 0
    token = os.environ.get(TOKEN_ENV, "")
    if not token:
        print("CPANEL_HTTPS_TOKEN_NOT_CONFIGURED", file=sys.stderr)
        return 78
    try:
        result = query(argv[1], token)
    except ValueError as exc:
        # All error codes are deliberately fixed and contain no response body,
        # request Authorization header, hostname redirects, or token values.
        print("CPANEL_HTTPS_CHECK_FAILED=" + str(exc), file=sys.stderr)
        return 1
    for key, value in result.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
