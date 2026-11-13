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

RELEASE_REVISION = "finance102-20261113-v2"
LEGACY_STATUS_DISCLOSURES = {
    "market-signals": {
        "fa": "سیگنال زنده یا سابقهٔ عملکردِ راستی‌آزمایی‌شده",
        "en": "No live signal or independently verified performance history",
        "ar": "إشارات مباشرة أو نتائج أداء موثقة مستقلة",
    },
    "digital-products": {
        "fa": "فهرست محصولات و پرداخت این زیردسته هنوز فعال نشده",
        "en": "product listing and checkout are not active yet",
        "ar": "قائمة المنتجات والدفع لهذا المتجر الفرعي غير مفعّلين",
    },
}

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
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == "html":
            self.lang = dict(attrs).get("lang")
        if tag == "title":
            self.title_depth += 1
        if tag == "a":
            href = dict(attrs).get("href")
            if isinstance(href, str):
                self.links.append(href)
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
              "http": None, "content_ok": False, "title": "",
              "expected_shop_link_present": False, "editorial_revision_live": False,
              "canonical_header_correct": False, "content_language_header_correct": False,
              "honest_legacy_disclosure_present": False, "error": None}
    try:
        opener = urllib.request.build_opener(LocalOnlyRedirect(host))
        req = urllib.request.Request(url, method="GET", headers={
            "Accept": "text/html", "User-Agent": "Saeit-Finance102-ReadOnly-20261113/1.0",
            "Cache-Control": "no-cache"
        })
        with opener.open(req, timeout=9) as resp:
            data = resp.read(90_000)
            result["http"] = resp.status
            result["editorial_revision_live"] = (
                resp.headers.get("X-Finance102-Editorial-Revision") == RELEASE_REVISION
            )
            result["canonical_header_correct"] = (
                "<" + url + '>; rel="canonical"' in resp.headers.get("Link", "")
            )
            result["content_language_header_correct"] = (
                resp.headers.get("Content-Language") == lang
            )
            if resp.status != 200 or "html" not in resp.headers.get("Content-Type","").lower():
                result["error"] = "not_html_200"
            else:
                html = data.decode("utf-8", errors="replace")
                parsed = BasicHTML()
                parsed.feed(html)
                result["honest_legacy_disclosure_present"] = (
                    LEGACY_STATUS_DISCLOSURES[kind][lang] in html
                )
                result["title"] = parsed.title[:130]
                expected_shop_path = "/store/" if lang == "fa" else "/commerce/"
                result["expected_shop_link_present"] = expected_shop_path in parsed.links
                result["content_ok"] = (
                    parsed.lang == lang
                    and result["expected_shop_link_present"]
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

def check_shop_link(host, path):
    """GET only one allowed main-shop destination, never follow off-host redirects."""
    try:
        opener = urllib.request.build_opener(LocalOnlyRedirect(host))
        request = urllib.request.Request("https://" + host + path, method="GET", headers={
            "User-Agent": "Saeit-Finance102-ReadOnly-20261113/1.0", "Accept": "text/html"
        })
        with opener.open(request, timeout=9) as response:
            kind = response.headers.get("Content-Type", "").lower()
            snippet = response.read(2048)
            return {"host": host, "path": path, "http": response.status,
                    "content_type_html": "html" in kind, "nonempty": bool(snippet),
                    "valid": response.status == 200 and "html" in kind and bool(snippet)}
    except urllib.error.HTTPError as ex:
        return {"host": host, "path": path, "http": ex.code, "valid": False, "error": "HTTPError"}
    except (urllib.error.URLError, OSError, TimeoutError, ValueError, ssl.SSLError) as ex:
        return {"host": host, "path": path, "http": None, "valid": False, "error": type(ex).__name__}

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
    shops = [check_shop_link(host, path) for host, path in (
        ("zomorodmelal.ir", "/store/"), ("mojplaywin.com", "/commerce/"))]
    release_ready = sum(
        r["content_ok"] and r["editorial_revision_live"]
        and r["canonical_header_correct"] and r["content_language_header_correct"]
        for r in results
    )
    report = {"classification": "PUBLIC_READ_ONLY_NO_DEPLOY",
              "editorial_revision": RELEASE_REVISION,
              "new_editorial_release_verified": release_ready,
              "canonical_headers_verified": sum(r["canonical_header_correct"] for r in results),
              "language_headers_verified": sum(r["content_language_header_correct"] for r in results),
              "noncommercial_status_disclosures": {
                  "signal_pages_declaring_no_live_signal": sum(
                      r["honest_legacy_disclosure_present"]
                      for r in results if r["type"] == "market-signals"),
                  "substores_declaring_no_active_checkout": sum(
                      r["honest_legacy_disclosure_present"]
                      for r in results if r["type"] == "digital-products"),
              },
              "shop_destinations": shops,
              "cta_links_present": sum(r["expected_shop_link_present"] for r in results),
              "target_count": len(results), "verified": sum(r["content_ok"] for r in results),
              "groups": by_group, "failures": [r for r in results if not r["content_ok"]]}
    print("FINANCE102_RESULT=" + json.dumps(report, ensure_ascii=False, sort_keys=True))
    import sys
    strict_release_check = "--require-release" in sys.argv[1:]
    return 0 if (report["verified"] == 102 and all(x["valid"] for x in shops)
                 and (not strict_release_check or release_ready == 102)) else 2

if __name__ == "__main__":
    raise SystemExit(main())
