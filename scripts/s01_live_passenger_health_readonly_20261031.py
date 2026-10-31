#!/usr/bin/env python3
"""GET-only check for the live unauthenticated Passenger health endpoint."""
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

HEALTH_URL = "https://mojplaywin.com/api/health/"
ALLOWED_HOSTS = {"mojplaywin.com", "www.mojplaywin.com"}
MAX_BODY = 4096


def classify_response(http_status, final_url, body):
    result = {
        "http_status": http_status,
        "same_site_https": False,
        "application_status": "unverified",
        "database_status": "unverified",
        "live_passenger_db_select1_verified": False,
        "passenger_worker_db_authority_verified": False,
        "response_body_bytes": len(body) if isinstance(body, bytes) else 0,
        "customer_rows_read": 0,
        "business_rows_read": 0,
        "database_modified": False,
        "orders_created": 0,
        "payments_created": 0,
    }
    try:
        parsed = urlsplit(final_url)
        result["same_site_https"] = (
            parsed.scheme == "https" and parsed.hostname in ALLOWED_HOSTS
        )
        if not result["same_site_https"] or not isinstance(body, bytes) or len(body) > MAX_BODY:
            return result
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("service") != "saeit":
            return result
        status = payload.get("status")
        database = payload.get("database")
        if status in {"ok", "degraded"}:
            result["application_status"] = status
        if database in {"ok", "unavailable"}:
            result["database_status"] = database
        verified = (
            http_status == 200 and status == "ok" and database == "ok"
        )
        result["live_passenger_db_select1_verified"] = verified
        result["passenger_worker_db_authority_verified"] = verified
        return result
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
        return result


def check_live_endpoint():
    request = Request(
        HEALTH_URL,
        method="GET",
        headers={
            "User-Agent": "S01-Live-Passenger-Health-ReadOnly/20261031",
            "Cache-Control": "no-cache",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=14) as response:
            status = response.status
            final_url = response.geturl()
            body = response.read(MAX_BODY + 1)
    except HTTPError as exc:
        status = exc.code
        final_url = exc.geturl()
        body = exc.read(MAX_BODY + 1)
    except Exception as exc:
        result = classify_response(0, HEALTH_URL, b"")
        result["failure_class"] = type(exc).__name__
        return result
    return classify_response(status, final_url, body)


if __name__ == "__main__":
    print("S01_LIVE_PASSENGER_HEALTH_READONLY=" + json.dumps(check_live_endpoint(), sort_keys=True))
