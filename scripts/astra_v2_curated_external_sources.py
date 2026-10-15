#!/usr/bin/env python3
"""Strictly curated, bounded HTTPS source observations for Astra R&D.

Never crawls arbitrary URLs, follows redirects, fetches on customer request,
copies article text, treats website reachability as expertise/market proof,
or touches either the original factory database or storefront.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import ssl
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, HTTPRedirectHandler, build_opener, HTTPSHandler

SOURCES = (
    ("water_multi_year_optimization", "https://waterlandcrop.ucdavis.edu/Help.html",
     "UC Davis multi-year crop/water optimization: free tool benchmark"),
    ("commodity_cost_method", "https://ers.usda.gov/data-products/commodity-costs-and-returns/documentation",
     "USDA ERS cost-accounting methodology, not willingness to pay"),
    ("farm_income_method", "https://ers.usda.gov/data-products/farm-income-and-wealth-statistics/general-documentation",
     "USDA ERS farm income accounting methodology and limits"),
    ("farm_balance_sheet_method", "https://ers.usda.gov/data-products/farm-income-and-wealth-statistics/documentation-for-the-farm-sector-balance-sheet",
     "USDA ERS assets, capital and financial risk framework"),
    ("farm_budget_alternatives", "https://ucanr.edu/site/agricultural-economics/publications",
     "University of California extension decision aids and budget alternatives"),
)
MAX_RESPONSE_BYTES = 192 * 1024
PER_SOURCE_TIMEOUT = 10
SCHEMA_VERSION = 1


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _opener():
    return build_opener(NoRedirect, HTTPSHandler(context=ssl.create_default_context()))


def _observe(source, opener):
    key, url, competitive_note = source
    result = {
        "key": key, "url": url,
        "competitive_capability_noted": competitive_note,
        "publisher_source_class": "public_university_or_government_research",
        "observed_at_utc": _utc(),
        "http_status": None,
        "transport_state": "UNKNOWN",
        "content_prefix_sha256": None,
        "bounded_bytes_observed": 0,
        "body_is_truncated_or_partial": None,
        "independent_expert_verification": False,
        "customer_problem_verified": False,
        "demand_verified": False,
        "willingness_to_pay_verified": False,
        "copy_or_republication_rights_verified": False,
    }
    assert url.startswith("https://")
    if url not in {src[1] for src in SOURCES}:
        raise ValueError("URL_NOT_CURATED")
    try:
        request = Request(url, headers={
            "User-Agent": "AstraResearchEvidenceMonitor/1.0 (bounded academic-source verification)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Encoding": "identity",
        }, method="GET")
        with opener.open(request, timeout=PER_SOURCE_TIMEOUT) as response:
            result["http_status"] = response.status
            if response.status != 200:
                result["transport_state"] = "NON_200"
                return result
            mime = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if mime not in ("text/html", "application/xhtml+xml"):
                result["transport_state"] = "NON_HTML"
                return result
            if (response.headers.get("Content-Encoding","identity").lower()
                    not in ("identity","")):
                result["transport_state"] = "COMPRESSED_REJECTED"
                return result
            sample = response.read(MAX_RESPONSE_BYTES + 1)
            prefix = sample[:MAX_RESPONSE_BYTES]
            result["bounded_bytes_observed"] = len(prefix)
            result["body_is_truncated_or_partial"] = len(sample)>MAX_RESPONSE_BYTES
            if not prefix or b"\x00" in prefix:
                result["transport_state"] = "EMPTY_OR_BINARY"
            else:
                result["content_prefix_sha256"] = hashlib.sha256(prefix).hexdigest()
                result["transport_state"] = "RETRIEVED_UNVERIFIED"
    except HTTPError as error:
        result["http_status"] = int(error.code)
        result["transport_state"] = "HTTP_ERROR"
    except (URLError, TimeoutError, ConnectionError, OSError, ValueError) as error:
        result["transport_state"] = "NETWORK_FAILURE"
        result["error_type"] = type(error).__name__
    return result


def _atomic_json(path, data):
    p=Path(path).expanduser()
    if p.is_symlink() or p.suffix!=".json" or not p.parent.is_dir() or p.parent.is_symlink():
        raise ValueError("OUTPUT_PATH_NOT_PRIVATE")
    folder=p.parent.resolve(strict=True)
    if folder.stat().st_mode & 0o077:
        raise ValueError("OUTPUT_DIRECTORY_NOT_PRIVATE")
    fd,temporary=tempfile.mkstemp(prefix=".astra-public-source-",suffix=".tmp",dir=str(folder))
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as file:
            json.dump(data,file,indent=2,sort_keys=True)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temporary,0o600)
        os.replace(temporary,str(p))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run(output_file, *, opener=None, sources=SOURCES):
    if len(sources)!=5 or len({x[0] for x in sources})!=5 or len({x[1] for x in sources})!=5:
        raise ValueError("FIVE_DISTINCT_CURATED_URLS_REQUIRED")
    if any(x not in SOURCES for x in sources):
        raise ValueError("UNKNOWN_SOURCE_NOT_ALLOWED")
    external=[_observe(x,opener or _opener()) for x in sources]
    summary={
        "schema_version": SCHEMA_VERSION,
        "mode":"FIVE_CURATED_EXTERNAL_SOURCE_OBSERVATIONS_PLUS_ONE_INTERNAL_AUDIT",
        "observed_at_utc":_utc(),
        "external_observations": external,
        "attempted": len(external),
        "retrieved_unverified":sum(x["transport_state"]=="RETRIEVED_UNVERIFIED" for x in external),
        "failed_or_inaccessible":sum(x["transport_state"]!="RETRIEVED_UNVERIFIED" for x in external),
        "internal_audit":{
            "id":"independent_quality_and_demand_gate",
            "classification":"internal_policy_review",
            "real_buyer_demand_attested":False,
            "value_above_existing_free_tools_proven":False,
            "domain_scientific_correctness_attested":False,
            "retail_release_authorized":False,
            "reason":"A successful HTTPS observation, source count or content hash is not market validation.",
        },
        "number_of_salable_products_created":0,
        "customer_orders_needed":False,
        "network_requests_to_unknown_hosts":0,
        "source_article_text_saved":False,
        "site_or_payment_mutations":0,
    }
    _atomic_json(output_file,summary)
    return {
        "mode": summary["mode"],
        "attempted":summary["attempted"],
        "retrieved_unverified":summary["retrieved_unverified"],
        "failed_or_inaccessible":summary["failed_or_inaccessible"],
        "real_buyer_demand_attested":False,
        "number_of_salable_products_created":0,
        "site_or_payment_mutations":0,
    }


def verify(file):
    path=Path(file).expanduser()
    if path.is_symlink() or not path.is_file():
        raise ValueError("SNAPSHOT_UNAVAILABLE")
    data=json.loads(path.read_text(encoding="utf-8"))
    if data["schema_version"]!=SCHEMA_VERSION or len(data["external_observations"])!=5:
        raise ValueError("SNAPSHOT_SCHEMA_MISMATCH")
    for src,observed in zip(SOURCES,data["external_observations"]):
        if observed["key"]!=src[0] or observed["url"]!=src[1]:
            raise ValueError("SNAPSHOT_SOURCE_MISMATCH")
        if observed["independent_expert_verification"] or observed["demand_verified"] or observed["willingness_to_pay_verified"]:
            raise ValueError("SNAPSHOT_FABRICATED_VERIFICATION")
    if data["internal_audit"]["retail_release_authorized"]:
        raise ValueError("SNAPSHOT_UNAPPROVED_RELEASE")
    if data["number_of_salable_products_created"]!=0 or data["site_or_payment_mutations"]!=0:
        raise ValueError("SNAPSHOT_COMMERCIAL_SCOPE_INVALID")
    return {"mode":"STRICT_READ_ONLY_VERIFICATION",
            "sources":5,"retrieved_unverified":data["retrieved_unverified"],
            "real_buyer_demand_attested":False,"sale_ready":False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",required=True)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once",action="store_true")
    group.add_argument("--check",action="store_true")
    args=parser.parse_args()
    print(json.dumps(verify(args.output) if args.check else run(args.output),
                     sort_keys=True))


if __name__=="__main__":
    main()
