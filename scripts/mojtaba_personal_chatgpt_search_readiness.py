#!/usr/bin/env python3
"""Read-only ChatGPT Search discovery readiness audit of the personal site.

Checks the *domain root* robots.txt, not a nested robots.txt, and simulates
requests using OpenAI's published user-agent strings. A spoofed UA from a GitHub
runner is NOT proof that the real OpenAI IP address ranges are allowed; confirm
that separately with firewall rules or server logs.

Only public GET requests; no deploy, file writes, authentication or data changes.
"""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree as ET

ROOT = "https://mojplaywin.com/"
PERSONAL = ROOT + "mojtaba.roozegar/"
ROBOTS = ROOT + "robots.txt"
SEARCHBOT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
             "AppleWebKit/537.36 (KHTML, like Gecko) "
             "Chrome/131.0.0.0 Safari/537.36; compatible; "
             "OAI-SearchBot/1.4; +https://openai.com/searchbot")
CHATGPT_USER = ("Mozilla/5.0 AppleWebKit/537.36 "
                "(KHTML, like Gecko); compatible; ChatGPT-User/1.0; "
                "+https://openai.com/bot")
NORMAL = "MojtabaPersonalPublicReadOnlySEOAudit/2.0"
BOTS = {"normal": NORMAL, "oai_searchbot_ua": SEARCHBOT,
        "chatgpt_user_ua": CHATGPT_USER}
PATHS = ("", "about/", "blog/")
MIN_ARTICLE_URLS = 93
FAQ_MARKER = "mpw-public-personal-faq-20261016"

class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.in_script = False
        self.title = []
        self.scripts = []
        self.parts = []
        self.meta = {}
        self.canonicals = []
        self.headings = []
        self.heading_active = False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag in ("h1", "h2", "h3"):
            self.heading_active = True
        if tag == "meta" and a.get("name", "").lower() in ("robots", "description"):
            self.meta[a["name"].lower()] = a.get("content", "")
        if tag == "link" and "canonical" in a.get("rel", "").lower().split():
            self.canonicals.append(a.get("href", ""))
        if tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self.in_script = True
            self.parts = []
    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        if self.heading_active and data.strip():
            self.headings.append(data.strip())
        if self.in_script:
            self.parts.append(data)
    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag in ("h1", "h2", "h3"):
            self.heading_active = False
        if tag == "script" and self.in_script:
            self.scripts.append("".join(self.parts))
            self.in_script = False

def fetch(url, ua, timeout=12):
    start = time.monotonic()
    req = Request(url, headers={
        "User-Agent": ua, "Accept": "text/html,application/xml,text/plain,*/*",
    })
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read(2_500_000)
            info = {"status": resp.status, "seconds": round(time.monotonic()-start,2),
                    "type": resp.headers.get("Content-Type", "").split(";")[0],
                    "x_robots_tag": resp.headers.get("X-Robots-Tag", ""),
                    "final_url": resp.url}
            return body, info
    except HTTPError as e:
        return None, {"status": e.code, "seconds": round(time.monotonic()-start,2),
                      "error": "HTTPError"}
    except (URLError, TimeoutError, OSError) as e:
        return None, {"status": None, "seconds": round(time.monotonic()-start,2),
                      "error": type(e).__name__}

def parse_policy(raw):
    robots = RobotFileParser()
    robots.parse(raw.decode("utf-8", "replace").splitlines())
    routes = [PERSONAL, PERSONAL + "about/", PERSONAL + "blog/"]
    return {
        "oai_searchbot": {url: robots.can_fetch("OAI-SearchBot", url) for url in routes},
        "gptbot_training": {url: robots.can_fetch("GPTBot", url) for url in routes},
        "chatgpt_user": {url: robots.can_fetch("ChatGPT-User", url) for url in routes},
    }

def collect_objects(value):
    if isinstance(value, list):
        for child in value:
            yield from collect_objects(child)
    elif isinstance(value, dict):
        yield value
        for child in value.values():
            yield from collect_objects(child)

def summarize_page(raw, expected):
    p = Page()
    p.feed(raw.decode("utf-8", "replace"))
    json_objects = []
    for script in p.scripts:
        try:
            json_objects.extend(collect_objects(json.loads(script)))
        except json.JSONDecodeError:
            continue
    person = [o for o in json_objects if o.get("@type") == "Person"
              and o.get("name") == "Mojtaba Roozegar"]
    same_as = []
    for o in person:
        same_as.extend(o.get("sameAs") or [])
    text = raw.decode("utf-8", "replace")
    return {
        "title": " ".join(p.title).strip()[:200],
        "description": p.meta.get("description", "")[:240],
        "robots": p.meta.get("robots", ""),
        "canonicals": p.canonicals,
        "canonical_matches": p.canonicals == [expected],
        "person_jsonld": bool(person),
        "person_same_as": sorted(set(v for v in same_as if isinstance(v, str))),
        "english_person_name_visible": "Mojtaba Roozegar" in text,
        "persian_person_name_visible": "مجتبی روزگار" in text,
        "faq_markup_present": FAQ_MARKER in text,
        "faq_english_question_present": "Who is Mojtaba Roozegar?" in text,
        "faq_persian_question_present": "مجتبی روزگار کیست؟" in text,
    }

def sitemap_summary(raw):
    root = ET.fromstring(raw)
    locs = [node.text or "" for node in root.iter() if node.tag.endswith("loc")]
    personal_urls = sorted(set(u for u in locs if u.startswith(PERSONAL)))
    articles = [url for url in personal_urls if "/blog/" in url and url != PERSONAL+"blog/"]
    return {"total": len(personal_urls), "blog_articles": len(articles),
            "home": PERSONAL in personal_urls, "about": PERSONAL+"about/" in personal_urls,
            "one_article": articles[0] if articles else None}

def audit(timeout):
    report = {"scope": PERSONAL, "mode": "read_only", "bot_identity_verified": False,
              "notes": ["UA simulation is NOT verification of crawler IP allowlisting.",
                        "GPTBot training choice does NOT control ChatGPT Search inclusion."],
              "checks": {}, "findings": [], "warnings": []}
    robots_raw, robots_status = fetch(ROBOTS, NORMAL, timeout)
    report["checks"]["domain_root_robots"] = robots_status
    if robots_raw is None or robots_status.get("status") != 200:
        report["findings"].append("domain_root_robots_unavailable")
        return report
    policy = parse_policy(robots_raw)
    report["policy"] = policy
    if not all(policy["oai_searchbot"].values()):
        report["findings"].append("oai_searchbot_blocked_by_domain_root_robots")
    if not all(policy["chatgpt_user"].values()):
        report["warnings"].append("chatgpt_user_policy_restricted")
    for path in PATHS:
        url = PERSONAL + path
        report["checks"][path or "home"] = {}
        for key, agent in BOTS.items():
            body, check = fetch(url, agent, timeout)
            report["checks"][path or "home"][key] = check
            if key == "oai_searchbot_ua":
                if body is None or check.get("status") != 200:
                    report["findings"].append("searchbot_ua_http_not_200:"+path)
                elif check["final_url"] != url:
                    report["warnings"].append("redirect_on_searchbot_request:"+path)
                elif "noindex" in check["x_robots_tag"].lower():
                    report["findings"].append("searchbot_x_robots_noindex:"+path)
                else:
                    summary = summarize_page(body, url)
                    report["checks"][path or "home"]["meta"] = summary
                    if not summary["canonical_matches"]:
                        report["findings"].append("wrong_canonical:"+path)
                    if "noindex" in summary["robots"].lower():
                        report["findings"].append("noindex_meta:"+path)
                    if path == "" and not summary["person_jsonld"]:
                        report["findings"].append("person_jsonld_missing")
                    if path == "about/" and not (summary["faq_markup_present"] and
                                                summary["faq_english_question_present"] and
                                                summary["faq_persian_question_present"]):
                        report["findings"].append("published_bilingual_faq_missing")
            if key == "normal" and check.get("status") != 200:
                report["warnings"].append("ordinary_client_non200:"+path)
            # Healthy site should not be loaded with needless retries.
    sitemap_raw, sitemap_status = fetch(PERSONAL+"sitemap.xml", NORMAL, timeout)
    report["checks"]["sitemap"] = sitemap_status
    if sitemap_raw is None or sitemap_status.get("status") != 200:
        report["findings"].append("personal_sitemap_unavailable")
    else:
        try:
            summary = sitemap_summary(sitemap_raw)
            report["sitemap"] = summary
            if summary["blog_articles"] < MIN_ARTICLE_URLS:
                report["findings"].append("article_sitemap_less_than_93")
            if not (summary["home"] and summary["about"]):
                report["findings"].append("identity_pages_missing_from_sitemap")
        except ET.ParseError:
            report["findings"].append("sitemap_xml_invalid")
    return report

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, default=12)
    args = ap.parse_args()
    if not 5 <= args.timeout <= 20:
        ap.error("timeout must be between 5 and 20 seconds")
    report = audit(args.timeout)
    print("CHATGPT_DISCOVERABILITY_REPORT=" + json.dumps(report, ensure_ascii=False,
          separators=(",", ":"), sort_keys=True))
    if report["findings"]:
        print("CHATGPT_DISCOVERABILITY_STATUS=needs_review")
        raise SystemExit(1)
    print("CHATGPT_DISCOVERABILITY_STATUS=passed")
    print("CHATGPT_DISCOVERABILITY_LIMITATION=real_searchbot_IP_not_verified")

if __name__ == "__main__":
    main()
