"""Read-only public HTTP evidence for Zomorod's news and weather delivery.

This is a negative release gate, not a publication command: a passing report
does not prove editorial accuracy, Passenger configuration, or cron operation.
"""

import argparse
from collections import Counter
from datetime import date, timedelta
from html.parser import HTMLParser
import json
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


ORIGIN = "https://zomorodmelal.ir"
MAX_HTML_BYTES = 2_000_000
SIGNATURE = "#مجتبی_روزگار"
DAILY_LINE = re.compile(r"(?m)^\s*•\s*(\d{4}-\d{2}-\d{2}):")
PROVINCE_HEADER = re.compile(r"(?m)^(?P<province>[^\n•|]+?)\s+—\s+[^\n|]+\|\s*دامنه دمای ۷ روز")
VOID_ELEMENTS = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"})


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ValueError("Public HTTP check must not follow redirects")


class _VisibleText(HTMLParser):
    """Extract visible text, never script, style or invisible head elements."""

    def __init__(self, *, report_section_only=False):
        super().__init__(convert_charrefs=True)
        self.report_section_only = report_section_only
        self.depth = 0
        self.found = False
        self.hidden_depth = 0
        self.output = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head", "template", "noscript"):
            self.hidden_depth += 1
        if self.report_section_only:
            if self.depth:
                if tag not in VOID_ELEMENTS:
                    self.depth += 1
            elif tag == "section" and "newsletter-original-report" in dict(attrs).get("class", "").split():
                self.depth = 1
                self.found = True
        if (not self.report_section_only or self.depth) and not self.hidden_depth:
            if tag in ("p", "div", "section", "h1", "h2", "h3", "br", "li"):
                self.output.append("\n")

    def handle_endtag(self, tag):
        if (not self.report_section_only or self.depth) and not self.hidden_depth:
            if tag in ("p", "div", "section", "h1", "h2", "h3", "li"):
                self.output.append("\n")
        if self.report_section_only and self.depth:
            self.depth -= 1
        if tag in ("script", "style", "head", "template", "noscript") and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_ELEMENTS:
            self.handle_endtag(tag)

    def handle_data(self, data):
        if not self.hidden_depth and (not self.report_section_only or self.depth):
            self.output.append(data)

    def visible_text(self):
        return "\n".join(line.strip() for line in "".join(self.output).splitlines() if line.strip())


def _parse(html: str, *, report_section_only=False) -> tuple[str, bool]:
    parser = _VisibleText(report_section_only=report_section_only)
    parser.feed(html)
    parser.close()
    return parser.visible_text(), parser.found


def inspect_delivery(weather_html: str, news_html: str, story_html: str, *, report_date: str) -> dict:
    """Count *published* per-day forecast lines, not API/database rows."""
    start = date.fromisoformat(report_date)
    expected_dates = [(start + timedelta(days=offset)).isoformat() for offset in range(7)]
    weather_text, _ = _parse(weather_html)
    news_text, _ = _parse(news_html)
    story_text, body_found = _parse(story_html, report_section_only=True)
    observed_dates = Counter(DAILY_LINE.findall(story_text))
    lines = [line.strip() for line in story_text.splitlines() if line.strip()]
    exact_final_signature = bool(lines) and lines[-1] == SIGNATURE
    province_dates = {}
    current_province = None
    duplicate_province = False
    orphan_daily_row = False
    for line in lines:
        header = PROVINCE_HEADER.match(line)
        if header:
            current_province = header.group("province").strip()
            if current_province in province_dates:
                duplicate_province = True
            else:
                province_dates[current_province] = []
        daily_row = DAILY_LINE.match(line)
        if daily_row:
            if current_province is None:
                orphan_daily_row = True
            else:
                province_dates[current_province].append(daily_row.group(1))
    seven_day_complete = (
        body_found and len(DAILY_LINE.findall(story_text)) == 217
        and all(observed_dates[item] == 31 for item in expected_dates)
        and set(observed_dates) == set(expected_dates)
        and len(PROVINCE_HEADER.findall(story_text)) == 31
        and len(province_dates) == 31 and not duplicate_province and not orphan_daily_row
        and all(days == expected_dates for days in province_dates.values())
    )
    weather_disclaimer = "این صفحه فعلاً پیش‌بینی زنده منتشر نمی‌کند" in weather_text
    news_disclaimer = "در این صفحه خبر فوری یا دستاورد تأییدنشده درج نشده است" in news_text
    return {
        "mode": "READ_ONLY_PUBLIC_DELIVERY_AUDIT",
        "evidence_scope": "HTTP_response_HTML_only_not_backend_or_runtime_proof",
        "report_date": report_date,
        "weather_page_disclaims_live_forecast": weather_disclaimer,
        "news_page_is_company_information": news_disclaimer,
        "story_original_report_found": body_found,
        "story_daily_rows": sum(observed_dates.values()),
        "story_daily_rows_by_date": dict(sorted(observed_dates.items())),
        "story_province_headers": len(PROVINCE_HEADER.findall(story_text)),
        "story_unique_provinces": len(province_dates),
        "story_seven_days_31_provinces": seven_day_complete,
        "story_exact_final_signature": exact_final_signature,
        "public_delivery_gate_passed": (
            not weather_disclaimer and not news_disclaimer
            and seven_day_complete and exact_final_signature
        ),
        "safe_to_deploy_automatically": False,
    }


def _fetch_fixed_path(path: str) -> str:
    """Only GET fixed paths on the pinned host; never follow redirects."""
    if not re.fullmatch(r"/(?:news|weather)/|/newsletter/weather-iran-\d{4}-\d{2}-\d{2}/", path):
        raise ValueError("Unapproved public audit path")
    opener = build_opener(_NoRedirect())
    request = Request(ORIGIN + path, headers={"User-Agent": "ZomorodNewsroomReadOnlyAudit/1.0"})
    with opener.open(request, timeout=15) as response:
        if response.status != 200:
            raise ValueError(f"Unexpected HTTP status {response.status} for {path}")
        if "text/html" not in response.headers.get("Content-Type", "").lower():
            raise ValueError(f"Expected HTML response for {path}")
        data = response.read(MAX_HTML_BYTES + 1)
        if len(data) > MAX_HTML_BYTES:
            raise ValueError(f"Oversize response for {path}")
        return data.decode("utf-8", errors="strict")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Read-only audit of Zomorod public newsroom delivery")
    parser.add_argument("--story-date", default="2026-11-08", help="ISO date of the published weather bulletin")
    args = parser.parse_args(argv)
    try:
        report_date = date.fromisoformat(args.story_date).isoformat()
        result = inspect_delivery(
            _fetch_fixed_path("/weather/"),
            _fetch_fixed_path("/news/"),
            _fetch_fixed_path(f"/newsletter/weather-iran-{report_date}/"),
            report_date=report_date,
        )
    except (ValueError, UnicodeError, HTTPError, URLError, TimeoutError, OSError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["public_delivery_gate_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
