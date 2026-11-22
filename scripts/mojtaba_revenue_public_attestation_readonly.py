#!/usr/bin/env python3
"""Read-only GET attestation of two service pages and the canonical bot domain.

No form submission, no tokens, no logins, no financial actions.
A public HTML keyword is evidence of visibility, NOT a deployed-code hash
attestation, completed sale, or a live bot-worker acceptance receipt.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

TARGETS = (
    ("zomorod_services", "https://zomorodmelal.ir/services/",
     "farm-break-even-inquiry"),
    ("mojplaywin_services", "https://mojplaywin.com/services/",
     "website-checkout-inquiry"),
    ("canonical_bot", "https://mojtaba.bot.ai/",
     "mojtaba.bot.ai"),
)
MAX_BODY = 524288

class BlockCrossDomainRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old = urlsplit(req.full_url)
        new = urlsplit(newurl)
        if new.scheme != "https" or new.hostname != old.hostname:
            raise ValueError("CROSS_DOMAIN_OR_INSECURE_REDIRECT")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def observe(name: str, url: str, marker: str, *, opener=None) -> dict:
    if (name, url, marker) not in TARGETS:
        raise ValueError("UNKNOWN_TARGET")
    original = urlsplit(url)
    result = {
        "target": name, "method": "GET", "site_writes": 0,
        "form_submissions": 0, "email_sent": 0, "payments": 0,
        "source_file_identity_proven": False,
        "live_bot_execution_proven": False,
        "collected_revenue_proven": False,
    }
    opener = opener if opener is not None else build_opener(BlockCrossDomainRedirect())
    req = Request(url, headers={
        "User-Agent": "MojtabaBotAI-RevenueReadOnly/20261114",
        "Accept": "text/html",
    }, method="GET")
    try:
        with opener.open(req, timeout=12) as response:
            http = response.status
            final_url = response.url
            content_type = response.headers.get("Content-Type", "")
            body = response.read(MAX_BODY + 1)
        final = urlsplit(final_url)
        result["http"] = http
        if final.scheme != "https" or final.hostname != original.hostname:
            result["state"] = "WRONG_ORIGIN"
            return result
        if final.path != original.path:
            result["state"] = "WRONG_PATH"
            return result
        if http != 200 or "text/html" not in content_type.lower():
            result["state"] = "UNVERIFIED_RESPONSE"
            return result
        if len(body) > MAX_BODY:
            result["state"] = "BODY_TOO_LARGE"
            return result
        result["html_sha256"] = hashlib.sha256(body).hexdigest()
        result["bytes_seen"] = len(body)
        html = body.decode("utf8", "replace")
        result["marker_visible"] = marker in html
        result["state"] = "VISIBLE_MARKER_NOT_DEPLOYMENT_PROOF" if result[
            "marker_visible"] else "HTML200_MARKER_NOT_OBSERVED"
        return result
    except HTTPError as exc:
        result.update({"http": exc.code, "state": "HTTP_NOT_200"})
    except (URLError, TimeoutError, ValueError, OSError) as exc:
        result["state"] = "UNKNOWN_FETCH_OR_REDIRECT_FAILURE"
    return result


def main() -> None:
    rows = [observe(*target) for target in TARGETS]
    report = {
        "schema": "mojtaba.bot.ai.public-readonly-revenue.v1",
        "canonical_bot": "mojtaba.bot.ai",
        "read_only": True,
        "records": rows,
        "no_actual_revenue_attestation": True,
        "no_automatic_deploy": True,
    }
    dest = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "mojtaba-revenue-attestation"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "public-readonly.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    for item in rows:
        print("MOJTABA_REVENUE_PUBLIC " + json.dumps(item, ensure_ascii=False))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf8") as f:
            f.write("\n### Canonical revenue public GET-only attestation\n")
            for x in rows:
                f.write("- " + x["target"] + ": " + x["state"] + "\n")
            f.write("No customer POST, deployment, payment or revenue asserted.\n")


if __name__ == "__main__":
    main()
