#!/usr/bin/env python3
"""Public, read-only, bounded verification of the existing 102 localized finance URLs."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from collections import Counter
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request

SLUGS = (
    "saman", "zahra", "zhila", "marzieh", "maryam", "marjan", "faremah",
    "farnaz", "taniya", "raham", "mojtaba", "mohammad", "mostafa",
    "17", "21", "206", "108",
)
BRAND_LABELS = {
    "saman": ("سمن", "SAMAN", "سمن"),
    "zahra": ("زهرا", "ZAHRA", "زهرة"),
    "zhila": ("ژیلا", "ZHILA", "جيلا"),
    "marzieh": ("مرضیه", "MARZIEH", "مرضية"),
    "maryam": ("مریم", "MARYAM", "مريم"),
    "marjan": ("مرجان", "MARJAN", "مرجان"),
    "faremah": ("فریماه", "FAREMAH", "فريماه"),
    "farnaz": ("فرناز", "FARNAZ", "فرناز"),
    "taniya": ("تانیا", "TANIYA", "تانيا"),
    "raham": ("رهام", "RAHAM", "رهام"),
    "mojtaba": ("مجتبی", "MOJTABA", "مجتبى"),
    "mohammad": ("محمد", "MOHAMMAD", "محمد"),
    "mostafa": ("مصطفی", "MOSTAFA", "مصطفى"),
    "17": ("۱۷", "17", "١٧"),
    "21": ("۲۱", "21", "٢١"),
    "206": ("۲۰۶", "206", "٢٠٦"),
    "108": ("۱۰۸", "108", "١٠٨"),
}
LOCALE_INDEX = {"fa": 0, "en": 1, "ar": 2}

TARGETS = [
    (host, lang, slug, kind, "/" + prefix + slug + "/" + kind + "/")
    for host, lang, prefix in [
        ("zomorodmelal.ir", "fa", ""),
        ("mojplaywin.com", "en", ""),
        ("mojplaywin.com", "ar", "ar/"),
    ]
    for slug in SLUGS
    for kind in ("market-signals", "digital-products")
]
assert len(TARGETS) == 102 and len(set((h, p) for h, _, _, _, p in TARGETS)) == 102

class BasicHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.lang = None
        self.title_depth = 0
        self.title = ""
    def handle_starttag(self, tag, attrs):
        if tag == "html":
            self.lang = dict(attrs).get("lang")
        if tag == "title":
            self.title_depth += 1
    def handle_endtag(self, tag):
        if tag == "title":
            self.title_depth = max(0, self.title_depth - 1)
    def handle_data(self, data):
        if self.title_depth:
            self.title += data

class LocalOnlyRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, host):
        self.host = host
        super().__init__()
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if target.scheme != "https" or target.hostname not in (self.host, "www." + self.host) or target.username or target.password or target.query:
            raise ValueError("redirect_rejected")
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def probe(target):
    host, lang, slug, kind, path = target
    url = "https://" + host + path
    result = {"host": host, "lang": lang, "slug": slug, "type": kind, "path": path,
              "http": None, "content_ok": False, "title": "", "error": None}
    try:
        opener = urllib.request.build_opener(LocalOnlyRedirect(host))
        req = urllib.request.Request(url, method="GET", headers={
            "Accept": "text/html", "User-Agent": "Saeit-Finance102-ReadOnly-20261113/1.0",
            "Cache-Control": "no-cache"
        })
        with opener.open(req, timeout=9) as resp:
            data = resp.read(90_000)
            result["http"] = resp.status
            if resp.status != 200 or "html" not in resp.headers.get("Content-Type","").lower():
                result["error"] = "not_html_200"
            else:
                html = data.decode("utf-8", errors="replace")
                parsed = BasicHTML()
                parsed.feed(html)
                result["title"] = parsed.title[:130]
                result["content_ok"] = (
                    parsed.lang == lang
                    and "MojPlayWin / Zomorod Melal" in html
                    and parsed.title.startswith(BRAND_LABELS[slug][LOCALE_INDEX[lang]] + " | ")
                    and (("market" in html.lower() or "بازار" in html or "الأسواق" in html)
                         if kind == "market-signals"
                         else ("digital" in html.lower() or "دیجیتال" in html or "رقمية" in html))
                )
                if not result["content_ok"]:
                    result["error"] = "wrong_or_incomplete_page_content"
    except urllib.error.HTTPError as ex:
        result["http"] = ex.code
        result["error"] = "http_" + str(ex.code)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, ssl.SSLError) as ex:
        result["error"] = type(ex).__name__
    return result

def main():
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = sorted((future.result() for future in as_completed(
            [pool.submit(probe, target) for target in TARGETS])),
            key=lambda x: (x["host"], x["lang"], x["slug"], x["type"]))
    by_group = {}
    for host, lang, _, _, _ in [("zomorodmelal.ir", "fa", "", "", ""),
                                 ("mojplaywin.com", "en", "", "", ""),
                                 ("mojplaywin.com", "ar", "", "", "")]:
        subset = [r for r in results if r["host"] == host and r["lang"] == lang]
        by_group[f"{host}:{lang}"] = {
            "count": len(subset),
            "http_200": sum(r["http"] == 200 for r in subset),
            "content_verified": sum(r["content_ok"] for r in subset),
            "codes": dict(Counter(str(r["http"]) if r["http"] is not None else "connection_failure" for r in subset))
        }
    report = {"classification": "PUBLIC_READ_ONLY_NO_DEPLOY",
              "target_count": len(results), "verified": sum(r["content_ok"] for r in results),
              "groups": by_group, "failures": [r for r in results if not r["content_ok"]]}
    print("FINANCE102_RESULT=" + json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["verified"] == 102 else 2

if __name__ == "__main__":
    raise SystemExit(main())
