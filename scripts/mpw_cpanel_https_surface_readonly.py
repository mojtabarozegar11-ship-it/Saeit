#!/usr/bin/env python3
"""Unauthenticated, TLS-verified, no-redirect cPanel 2083 UAPI surface check.

GET exact allowlisted UAPI path with no token, cookie, password, credentials,
file paths, query strings or request body. Only observe HTTP status and SSL
validation. 401/403 is EXPECTED and means authentication is required;
never mistake it for a failed network link or a signed-in cPanel user.
"""
from __future__ import annotations
import json
import ssl
import sys
from urllib.error import HTTPError, URLError
from urllib.request import build_opener, HTTPSHandler, HTTPRedirectHandler, ProxyHandler, Request

URL = "https://zohal.pws-dns.net:2083/execute/PassengerApps/list_applications"
TIMEOUT = 8

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def run(opener=None):
    data={"method":"unauthenticated_tls_verified_get","user_authenticated":False,
          "api_token_used":False,"operations_modified":0,
          "remote_data_read":False,"status":"unobserved"}
    try:
        browser=opener or build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()), NoRedirect())
        request=Request(URL, headers={"Accept":"application/json"}, method="GET")
        with browser.open(request, timeout=TIMEOUT) as response:
            status=response.getcode()
        data.update(http_status=int(status), status=("unexpected_unauthenticated_success" if status==200 else "unexpected_status"))
    except HTTPError as exc:
        data.update(http_status=int(exc.code),status=("auth_challenge_expected" if exc.code in (401,403) else "http_error"))
    except (URLError, OSError, ValueError, ssl.SSLError) as exc:
        data.update(status="tls_or_network_error",error_class=type(exc).__name__)
    return data

if __name__=="__main__":
    print("MPW_CPANEL_HTTPS_UAPI_UNAUTHENTICATED="+json.dumps(run(),sort_keys=True))
    sys.exit(0)
