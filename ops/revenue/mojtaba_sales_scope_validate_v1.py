#!/usr/bin/env python3
"""Pure read-only verifier for 11 private draft sales scopes; no customer or pricing data."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[2]
OFFER_FILE = "ops/revenue/mojtaba_commercial_offers_v1.json"
MANIFEST = "ops/revenue/mojtaba_sales_scope_briefs_v1.json"
INDEX = "docs/sales/mojtaba-20261114/INDEX.md"
ALLOWED_ORIGIN = "https://zomorodmelal.ir"
FORMAT = "mojtaba.bot.ai.sales-scope-briefs.v1"
CANONICAL = "mojtaba.bot.ai"
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{4,45}$")
HEADINGS = (
    "## مسئله اقتصادی و هدف مشتری",
    "## پیش‌نیاز استعلام و داده‌ای که متقاضی باید توضیح دهد",
    "## روش علمی و عملیات پیشنهادی",
    "## خروجی‌های قابل‌بررسی در پیشنهاد خدمت",
    "## معیار پذیرش و کنترل کیفیت",
    "## تعهدات خارج از دامنه و ریسک",
    "## مسیر ارجاع و گیت صدور پیشنهاد",
)


class BriefInvalid(ValueError):
    pass


def loads_unique(text):
    def strict(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise BriefInvalid("duplicate_json_key")
            result[k] = v
        return result
    return json.loads(text, object_pairs_hook=strict)


def safe_file(root: Path, path: str) -> Path:
    if not isinstance(path, str) or not re.fullmatch(r"[a-zA-Z0-9_./-]+", path):
        raise BriefInvalid("invalid_source_path")
    rel = Path(path)
    if rel.is_absolute() or not rel.parts or any(part in (".", "..") for part in rel.parts):
        raise BriefInvalid("path_traversal")
    p = root
    for part in rel.parts:
        p = p / part
        try:
            mode = p.lstat().st_mode
        except OSError as exc:
            raise BriefInvalid("missing_document") from exc
        if stat.S_ISLNK(mode):
            raise BriefInvalid("symlink_in_document_path")
    if not p.is_file() or p.stat().st_size > 45000:
        raise BriefInvalid("bad_document_file")
    return p


def check(root: Path, offers=None, manifest=None) -> dict:
    offers = offers if offers is not None else loads_unique(safe_file(root,OFFER_FILE).read_text("utf-8"))
    manifest = manifest if manifest is not None else loads_unique(safe_file(root,MANIFEST).read_text("utf-8"))
    if not isinstance(offers, dict) or offers.get("canonical_bot_id") != CANONICAL or not isinstance(offers.get("offers"),list):
        raise BriefInvalid("portfolio_not_canonical")
    if not isinstance(manifest, dict) or set(manifest) != {"schema", "canonical_bot_id", "scope", "briefs"}:
        raise BriefInvalid("manifest_schema")
    if manifest["schema"] != FORMAT or manifest["canonical_bot_id"] != CANONICAL:
        raise BriefInvalid("manifest_identity")
    if manifest["scope"] != "source_only_draft_no_live_sales":
        raise BriefInvalid("false_release_scope")
    rows = manifest["briefs"]
    if not isinstance(rows,list) or len(rows) != 11:
        raise BriefInvalid("wrong_brief_count")
    source_offers = {o["offer_id"]:o for o in offers["offers"]}
    candidates = {id for id,o in source_offers.items() if o["stage"]=="inquiry_candidate"}
    ids = [r.get("offer_id") for r in rows if isinstance(r,dict)]
    if len(ids) != len(rows) or len(ids) != len(set(ids)) or set(ids) != candidates:
        raise BriefInvalid("draft_offer_set_mismatch")
    docs = []
    for row in rows:
        if not isinstance(row,dict) or set(row) != {"offer_id","path","distinct_scope"}:
            raise BriefInvalid("invalid_brief_row")
        ident = row["offer_id"]
        if not isinstance(ident,str) or not ID_PATTERN.fullmatch(ident):
            raise BriefInvalid("bad_offer_id")
        o = source_offers[ident]
        if o["canonical_bot_id"] != CANONICAL or o["model"] not in ("consulting_quote","b2b_quote","physical_catalogue"):
            raise BriefInvalid("wrong_offer_or_bot")
        if o["payment_enabled"] is not False or o["price_irr"] is not None or o["owner_approved"] is not False:
            raise BriefInvalid("financial_approval_missing")
        if o["delivery_verified"] is not False or o["public_live_verified"] is not False:
            raise BriefInvalid("false_delivery_claim")
        expected = "docs/sales/mojtaba-20261114/" + ident + ".md"
        if row["path"] != expected:
            raise BriefInvalid("wrong_document_path")
        if not isinstance(row["distinct_scope"],str) or len(row["distinct_scope"]) < 12:
            raise BriefInvalid("generic_sales_scope")
        content = safe_file(root, expected).read_text("utf-8")
        if len(content) < 1250 or not content.startswith("# " + o["title"] + " | پرونده فروش و تعیین دامنه"):
            raise BriefInvalid("brief_incomplete")
        if content.count("mojtaba.bot.ai") != 1:
            raise BriefInvalid("bot_identity_mismatch")
        if any(content.count(h)!=1 for h in HEADINGS):
            raise BriefInvalid("missing_or_duplicate_heading")
        for value in o["required_inputs"] + o["deliverables"] + o["exclusions"] + o["source_files"]:
            if value not in content:
                raise BriefInvalid("offer_content_provenance_missing")
        if row["distinct_scope"] not in content:
            raise BriefInvalid("missing_unique_next_step")
        if f"[ثبت درخواست]({ALLOWED_ORIGIN}{o['intake_path']})" not in content:
            raise BriefInvalid("unapproved_intake_link")
        for disallowed in ("پرداخت کنید", "همین حالا وجه", "شماره کارت", "پرداخت تضمینی",
                           "فروش نهایی انجام شد", "درگاه فعال است", "mailto:", "wa.me/", "t.me/"):
            if disallowed in content:
                raise BriefInvalid("misleading_commercial_claim")
        if content.count("## ") != len(HEADINGS):
            raise BriefInvalid("unreviewed_sections")
        docs.append({"id":ident, "scope_defined":True, "intake_destination_defined":True,
                     "source_referenced":True, "verified_live_delivery":False,
                     "verified_revenue":False})
    index = safe_file(root, INDEX).read_text("utf-8")
    if not index.startswith("# بسته فروش تخصصی"):
        raise BriefInvalid("missing_index")
    for ident in ids:
        if index.count(f"./{ident}.md")!=1:
            raise BriefInvalid("index_missing_or_duplicate_link")
    if "اشتراک ربات" not in index or "مسدود" not in index or "اطلاعات مشتری در GitHub" not in index:
        raise BriefInvalid("missing_revenue_or_privacy_gate")
    return {
      "schema":"mojtaba.bot.ai.sales-scope-validation.v1",
      "canonical_bot_id":CANONICAL,
      "source_scopes_checked":len(docs),
      "source_scope_contract_pass_count":len(docs),
      "live_customer_inquiries_verified":None,
      "paid_sales_verified":None,
      "received_revenue_verified":None,
      "customer_information_accessed":False,
      "customer_messages_sent":0,
      "orders_created":0,
      "payments_triggered":0,
      "production_writes":0,
      "next_gate":"verify_real_lead_intake_and_delivery_capacity_before_price",
      "scopes":docs,
    }


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--repo-root",type=Path,default=ROOT)
    args=parser.parse_args(argv)
    try:
        result=check(args.repo_root.resolve())
    except (OSError, TypeError, ValueError, KeyError) as exc:
        print(json.dumps({"status":"BLOCKED","reason":type(exc).__name__,"scope":"source_only"},sort_keys=True))
        return 2
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return 0

if __name__=="__main__":
    sys.exit(main())
