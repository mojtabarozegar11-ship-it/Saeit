#!/usr/bin/env python3
"""Read-only public SEO and response-time audit for Mojtaba Roozegar's personal site.

Makes GET requests only. Never authenticates, deploys, crawls private URLs or writes
to any website. Exits 1 when a repeatable public availability / SEO error exists.
"""
from __future__ import annotations
import argparse
import json
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

ROOT = "https://mojplaywin.com/mojtaba.roozegar/"
ROUTES = ("", "about/", "blog/", "resume/", "projects/", "contact/",
          "robots.txt", "sitemap.xml", "feed.xml")
EXPECTED_CANONICAL = ROOT

class Metadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title_on = False
        self.title = []
        self.description = ""
        self.robots = ""
        self.canonicals = []
        self.json_scripts = []
        self.script_on = False
        self.script_parts = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self.title_on = True
        if tag == "meta":
            key = attrs.get("name", "").lower()
            if key == "description":
                self.description = attrs.get("content", "")
            if key == "robots":
                self.robots = attrs.get("content", "")
        if tag == "link" and "canonical" in attrs.get("rel", "").lower().split():
            self.canonicals.append(attrs.get("href", ""))
        if tag == "script" and attrs.get("type", "").lower() == "application/ld+json":
            self.script_on = True
            self.script_parts = []
    def handle_data(self, data):
        if self.title_on:
            self.title.append(data)
        if self.script_on:
            self.script_parts.append(data)
    def handle_endtag(self, tag):
        if tag == "title":
            self.title_on = False
        if tag == "script" and self.script_on:
            self.json_scripts.append("".join(self.script_parts))
            self.script_on = False

def fetch(url, attempts=3, timeout=12):
    samples = []
    for number in range(attempts):
        started = time.monotonic()
        try:
            request = urllib.request.Request(url, headers={
                "User-Agent": "MojtabaPersonalPublicSEOReadOnlyAudit/1.0",
                "Accept": "text/html,application/xml,text/plain,*/*",
            })
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read(2_500_000)
                code = response.status
                content_type = response.headers.get("Content-Type", "")
            elapsed = round(time.monotonic() - started, 2)
            samples.append({"code": code, "seconds": elapsed, "bytes": len(payload)})
            if code == 200:
                return payload, content_type, samples
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            elapsed = round(time.monotonic() - started, 2)
            samples.append({"error": type(exc).__name__, "seconds": elapsed})
        # Retry only failed attempts; never create load on a healthy site.
        if number + 1 < attempts:
            time.sleep(1)
    return None, "", samples

def evaluate_home(document):
    p = Metadata()
    p.feed(document.decode("utf-8", "replace"))
    errors = []
    title = " ".join(p.title).strip()
    if "Mojtaba Roozegar" not in title:
        errors.append("home_title_missing_name")
    if not p.description or "Mojtaba Roozegar" not in p.description:
        errors.append("home_meta_description_missing_name")
    if p.canonicals != [EXPECTED_CANONICAL]:
        errors.append("home_canonical_missing_or_incorrect")
    if "noindex" in p.robots.lower() or "index" not in p.robots.lower():
        errors.append("home_not_explicitly_indexable")
    structured = []
    for script in p.json_scripts:
        try:
            obj = json.loads(script)
        except json.JSONDecodeError:
            errors.append("invalid_jsonld")
            continue
        structured.append(obj)
    def contains_person(obj):
        if isinstance(obj, dict):
            typ = obj.get("@type")
            if typ == "Person" and obj.get("name") == "Mojtaba Roozegar":
                return True
            return any(contains_person(value) for value in obj.values())
        if isinstance(obj, list):
            return any(contains_person(value) for value in obj)
        return False
    if not any(contains_person(obj) for obj in structured):
        errors.append("person_jsonld_missing")
    return {"title": title, "canonical": p.canonicals,
            "robots": p.robots, "person_jsonld": any(contains_person(x) for x in structured),
            "errors": errors}

def check_sitemap(document):
    errors = []
    try:
        root = ET.fromstring(document)
        locs = [x.text or "" for x in root.iter() if x.tag.endswith("loc")]
    except ET.ParseError:
        return {"errors": ["sitemap_invalid_xml"], "total_urls": 0}
    personal = [url for url in locs if url.startswith(ROOT)]
    if ROOT not in personal:
        errors.append("personal_home_missing_from_sitemap")
    if len(personal) < 100:
        errors.append("personal_sitemap_below_protected_page_floor")
    return {"total_urls": len(locs), "personal_urls": len(personal),
            "home_present": ROOT in personal, "errors": errors}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=12)
    args = parser.parse_args()
    if not 1 <= args.attempts <= 3 or not 4 <= args.timeout <= 30:
        parser.error("Unsafe sampling settings")
    report = {"site": ROOT, "mode": "read_only", "responses": {}, "findings": []}
    for route in ROUTES:
        payload, ctype, samples = fetch(ROOT + route, args.attempts, args.timeout)
        report["responses"][route or "home"] = samples
        if payload is None:
            report["findings"].append((route or "home") + "_unavailable_after_retries")
            continue
        if route == "":
            report["home_seo"] = evaluate_home(payload)
            report["findings"].extend(report["home_seo"]["errors"])
        if route == "sitemap.xml":
            report["sitemap"] = check_sitemap(payload)
            report["findings"].extend(report["sitemap"]["errors"])
    print("PERSONAL_SEO_HEALTH_AUDIT=" + json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    if report["findings"]:
        print("PERSONAL_SEO_HEALTH_STATUS=needs_review")
        raise SystemExit(1)
    print("PERSONAL_SEO_HEALTH_STATUS=passed")

if __name__ == "__main__":
    main()
