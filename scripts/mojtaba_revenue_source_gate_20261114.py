#!/usr/bin/env python3
"""Evidence-bound revenue SOURCE audit for the ONE canonical mojtaba.bot.ai.

Reads only allowlisted repository sources. It does not inspect customer records,
send requests, send email, create orders, charge funds, deploy or change files.
SOURCE PASS IS NEVER A CLAIM OF LIVE COMMERCE OR RECEIVED REVENUE.
"""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_BOT = "mojtaba.bot.ai"
SCHEMA = "mojtaba.bot.ai.revenue-source-readiness.v1"

SERVICES = (
    "website-doctor", "landing-page-studio", "ai-automation",
    "business-spreadsheets", "website-templates", "social-media-kits",
    "resume-builder", "logo-studio", "browser-games", "marketing-ai",
    "business-calculators", "website-care",
)
SKU = (72, 225, 879)
SOURCE_ROOT = "mpw_revenue_20261020/earn"
INQUIRY = SOURCE_ROOT + "/inquiry.php"
HUB = SOURCE_ROOT + "/index.html"
BOT_MANIFEST = "runtime/mojtaba_bot_disposition_sources_v1.json"
BOT_EVIDENCE = "runtime/mojtaba_readonly_evidence_20261112_154350Z.json"
STORE = "core/templates/mojplaywin/store.html"
FARM = "product_recipes/farm_enterprise_economics/README.md"


class _Links(HTMLParser):
    """Collect real HTML href attributes, not text, scripts or HTML comments."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.invalid = False
        self._ignore = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "template"):
            self._ignore += 1
            return
        if self._ignore:
            return
        if tag == "base":
            self.invalid = True
        if tag != "a":
            return
        values = [value for key, value in attrs if key.lower() == "href"]
        if len(values) != 1 or not isinstance(values[0], str):
            self.invalid = True
        else:
            self.links.append(values[0])

    def handle_endtag(self, tag):
        if tag in ("script", "style", "template") and self._ignore:
            self._ignore -= 1


def _read(root: Path, relative: str) -> str:
    """Restrict inspection to local UTF-8 regular files with no symlink hops."""
    if (not isinstance(relative, str) or relative.startswith("/")
            or relative.startswith("./") or "/./" in relative):
        raise ValueError("UNSAFE_SOURCE_PATH")
    pieces = Path(relative).parts
    if not pieces or any(part in (".", "..") for part in pieces):
        raise ValueError("UNSAFE_SOURCE_PATH")
    base = root.resolve(strict=True)
    candidate = base
    for item in pieces:
        candidate = candidate / item
        if candidate.is_symlink():
            raise ValueError("SYMLINK_SOURCE_DENIED")
    if not candidate.is_file():
        raise FileNotFoundError("SOURCE_MISSING:" + relative)
    if candidate.stat().st_size > 256_000:
        raise ValueError("SOURCE_TOO_LARGE")
    return candidate.read_text(encoding="utf-8", errors="strict")


def _links(html: str) -> _Links:
    inspector = _Links()
    inspector.feed(html)
    inspector.close()
    return inspector


def _php_offer_ids(text: str) -> set[str]:
    match = re.search(r"\$allowed\s*=\s*\[(.*?)\];", text, flags=re.DOTALL)
    if not match:
        return set()
    allowed = re.findall(r"'([a-z0-9-]+)'\s*=>", match.group(1))
    if len(allowed) != len(set(allowed)):
        return set()
    return set(allowed)


def audit(root: Path = ROOT) -> dict:
    """Produce a source-only report; unknown live fields must remain null."""
    checks = []
    def check(code: str, ok: bool, detail: str):
        checks.append({"code": code, "passed": bool(ok), "detail": detail})

    hub = _read(root, HUB)
    php = _read(root, INQUIRY)
    store = _read(root, STORE)
    farm = _read(root, FARM)
    manifest = json.loads(_read(root, BOT_MANIFEST))
    historical = json.loads(_read(root, BOT_EVIDENCE))
    hub_links = _links(hub)
    php_ids = _php_offer_ids(php)

    check("single_bot_identity", manifest.get("canonical_bot_id") == CANONICAL_BOT,
          "Canonical single-agent identity is declared in source")
    check("source_only_manifest", manifest.get("evidence_scope") ==
          "verified_repository_source_not_live_runtime",
          "Manifest must not claim the repository is the active host")
    check("historical_not_deployment", historical.get("production_deployment_attested") is False,
          "Historical read-only observation is not deployment attestation")
    check("historical_runtime_unknown", historical.get("whole_company_consolidation_pct") is None
          and historical.get("host_observations", {}).get("cpanel", {}).get(
              "verified_live_agent_count") is None,
          "Actual consolidation cannot be reported as 100 percent")
    check("php_all_services_and_general", php_ids == set(SERVICES) | {"general"},
          "PHP allowlist must match exactly the twelve offered service slugs")
    for key, needle in (
        ("php_csrf_check", "hash_equals("),
        ("php_valid_email", "FILTER_VALIDATE_EMAIL"),
        ("php_encrypted_storage", "aes-256-gcm"),
        ("php_private_storage", "safe_private_dir("),
        ("php_honeypot", "fax_number"),
        ("php_no_guaranteed_quote", "Request is too large."),
    ):
        check(key, needle in php, "Verify static intake control is declared")

    offers = []
    for slug in SERVICES:
        html = _read(root, SOURCE_ROOT + "/" + slug + "/index.html")
        links = _links(html)
        offer_url = "/earn/" + slug + "/"
        inquiry = "/earn/inquiry.php?service=" + slug
        detail_ok = inquiry in links.links and not links.invalid
        hub_ok = offer_url in hub_links.links and not hub_links.invalid
        php_ok = slug in php_ids
        check("service_page:" + slug, detail_ok,
              "Detail HTML links to its own public inquiry URL")
        check("hub_link:" + slug, hub_ok,
              "Revenue hub links to exact service detail")
        check("php_slug:" + slug, php_ok,
              "Intake PHP permits exactly this service slug")
        offers.append({
            "slug": slug,
            "detail_route": offer_url,
            "inquiry_route": inquiry,
            "source_link_verified": bool(detail_ok and hub_ok and php_ok),
            "live_intake_verified": None,
            "quote_accepted": None,
            "paid_and_fulfilled": None,
        })

    check("store_source_identity", "MojPlayWin" in store and "TRX" in store,
          "Existing main store template is inspected but not published")
    for product in (72, 225):
        check("store_checkout_link:" + str(product),
              ('href="/store/product/' + str(product) + '/checkout/"') in store,
              "Static source only; guest email and on-chain finality are unverified")
    check("store_879_details_only",
          'href="/store/product/879/"' in store,
          "SKU879 remains gated on rights, package, QA and delivery")
    check("farm_economics_source",
          "break-even" in farm.lower() and "offline" in farm.lower(),
          "Existing farm-economics toolkit is documented in source")
    check("bot_sources_exist",
          isinstance(manifest.get("sources"), list) and len(manifest["sources"]) > 0,
          "Source-defined roles are not proof of independently running bots")

    passed = sum(item["passed"] for item in checks)
    source_routes = sum(offer["source_link_verified"] for offer in offers)
    return {
        "schema": SCHEMA,
        "canonical_bot_id": CANONICAL_BOT,
        "mode": "REPOSITORY_READ_ONLY",
        "source_checks": {"passed": passed, "total": len(checks)},
        "source_gate_passed": passed == len(checks),
        "service_source_routes": {"linked": source_routes, "total": len(SERVICES)},
        "service_offers": offers,
        "product_ids": list(SKU),
        "live_cpanel_checkout_verified": None,
        "live_inquiries_verified": None,
        "settled_paid_orders": None,
        "settled_revenue": None,
        "private_deliveries_verified": None,
        "canonical_bot_live_verified": None,
        "one_bot_cutover_verified": None,
        "live_commercial_ready": False,
        "live_deployment_authorized": False,
        "writes_performed": 0,
        "emails_sent": 0,
        "payments_initiated": 0,
        "new_agents_created": 0,
        "checks": checks,
    }


def markdown(result: dict) -> str:
    """Printable management summary. No customer data is included."""
    a = result["source_checks"]
    b = result["service_source_routes"]
    state = "PASS" if result["source_gate_passed"] else "FAIL"
    return "\n".join((
        "# Mojtaba.bot.ai — revenue source gate",
        "",
        "- Canonical agent: " + result["canonical_bot_id"],
        "- Source-only gate: " + state + " (" + str(a["passed"]) +
        "/" + str(a["total"]) + " checks)",
        "- Service links: " + str(b["linked"]) + "/" + str(b["total"]),
        "- Paid orders / cash received / delivery: UNKNOWN (no live evidence)",
        "- Live bot cutover: UNKNOWN; no agents created",
        "- Deploy and payments: NOT AUTHORIZED",
        "",
        "A green repository gate never authorizes production publication.",
    ))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    try:
        result = audit()
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        # Error category only: no filesystem path, secret, body or PII.
        print(json.dumps({"schema": SCHEMA, "source_gate_passed": False,
                          "error_class": type(exc).__name__}, sort_keys=True))
        return 1
    if args.format == "markdown":
        print(markdown(result))
    else:
        print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0 if result["source_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
