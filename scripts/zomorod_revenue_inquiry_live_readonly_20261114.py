#!/usr/bin/env python3
"""GET-only evidence of the existing Zomorod quote/inquiry funnel.

Never submit POST, store customer information, or log CSRF tokens.
Source readiness != deployed readiness != a lead != collected revenue.
"""
from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

ORIGIN = "https://zomorodmelal.ir"
TARGETS = (
    "/store/",
    "/ghanadi/",
    "/ghanadi/cafe-shiraz/",
    "/ask-master/index.php?service=1",
)
OUT = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "zm-revenue-inquiry-readonly"
LIMIT = 512 * 1024


class Forms(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self.current = {"method": (a.get("method") or "get").lower(),
                            "action": a.get("action") or "",
                            "fields": set()}
        elif tag in ("input", "textarea", "select") and self.current is not None:
            self.current["fields"].add(a.get("name") or "")
        if tag == "input" and a.get("name") == "csrf":
            pass  # Never record the value.

    def handle_endtag(self, tag):
        if tag == "form" and self.current is not None:
            self.forms.append(self.current)
            self.current = None


def official_contract(forms, response_url):
    for form in forms:
        target = urlsplit(urljoin(response_url, form["action"]))
        if (form["method"] == "post"
                and target.scheme == "https"
                and target.netloc == "zomorodmelal.ir"
                and target.path == "/ask-master/index.php"
                and "csrf" in form["fields"]):
            return True
    return False


def inspect(path, opener=urlopen, sleeper=time.sleep):
    if path not in TARGETS or path == "/":
        raise ValueError("not a whitelisted revenue-inquiry path")
    url = ORIGIN + path
    result = {"path": path, "method": "GET", "site_writes": 0,
              "form_submissions": 0, "attempts": [], "source_deployed_proven": False}
    request = Request(url, headers={"User-Agent": "Zomorod-Revenue-ReadOnly/20261114"}, method="GET")
    for n in (1, 2):
        try:
            with opener(request, timeout=12 if n == 1 else 8) as response:
                code = response.status
                final = response.geturl()
                data = response.read(LIMIT + 1)
            parsed = urlsplit(final)
            if parsed.scheme != "https" or parsed.netloc != "zomorodmelal.ir":
                result["status"] = "WRONG_ORIGIN"
                result["http"] = code
                result["attempts"].append({"n": n, "ok": False, "reason": "wrong_origin"})
                return result
            if parsed.path != urlsplit(url).path:
                result["status"] = "REDIRECTED_AWAY"
                result["http"] = code
                result["attempts"].append({"n": n, "ok": False, "reason": "unexpected_path"})
                return result
            result["http"] = code
            if code != 200:
                result["status"] = "HTTP_NOT_200"
                result["attempts"].append({"n": n, "ok": False, "http": code})
                if code < 500:
                    return result
                continue
            clipped = len(data) > LIMIT
            html = data[:LIMIT].decode("utf-8", "replace")
            forms = Forms()
            forms.feed(html)
            result.update({"status": "HTTP_200_READ_ONLY",
                           "sha256": hashlib.sha256(data[:LIMIT]).hexdigest(),
                           "bytes": len(data[:LIMIT]),
                           "truncated": clipped,
                           "official_form_contract": official_contract(forms.forms, final),
                           "quote_link_live": 'درخواست بررسی خرید و پیش‌فاکتور' in html,
                           "cafe_inquiry_form_live": 'id="cafeInquiry"' in html,
                           "offline_payment_notice": 'پرداخت آنلاین تا اتصال درگاه غیرفعال است' in html,
                           "attempts": result["attempts"] + [{"n": n, "ok": True, "http": code}]})
            return result
        except HTTPError as exc:
            result["http"] = exc.code
            result["status"] = "HTTP_NOT_200"
            result["attempts"].append({"n": n, "ok": False, "http": exc.code})
            if exc.code < 500:
                return result
        except (URLError, TimeoutError, OSError) as exc:
            result["status"] = "UNKNOWN_NETWORK_FAILURE"
            result["attempts"].append({"n": n, "ok": False, "kind": type(exc).__name__})
        if n == 1:
            sleeper(0.3)
    return result


def main():
    records = [inspect(p) for p in TARGETS]
    by_path = {r["path"]: r for r in records}
    official_ok = bool(by_path[TARGETS[-1]].get("official_form_contract"))
    report = {"scope": "4 existing paths; public GET only",
              "site_writes": 0, "form_submissions": 0, "payments": 0,
              "collected_revenue_verified": False,
              "official_csrf_post_contract_observed": official_ok,
              "gate": "PUBLIC_FORM_CONTRACT_OBSERVED" if official_ok else "NO_GO_FORM_CONTRACT_UNVERIFIED",
              "records": records}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "readiness.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    for row in records:
        print("ZM_REVENUE_GET " + json.dumps(row, ensure_ascii=False))
    print("ZM_REVENUE_READINESS " + json.dumps({k: v for k, v in report.items() if k != "records"},ensure_ascii=False))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf8") as output:
            output.write("\n### Existing revenue-inquiry GET-only readiness (never submits leads)\n")
            for row in records:
                output.write(f"- {row['path']}: {row['status']}, {row.get('http', 'unknown')}\n")
            output.write(f"- Official POST+CSRF contract observed: {official_ok}\n")
    # Non-mutating diagnostics: offline source CI is independent of host response.
    # An unknown or missing contract is explicitly NO_GO, never treated as success.


if __name__ == "__main__":
    main()
