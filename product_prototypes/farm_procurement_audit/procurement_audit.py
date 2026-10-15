#!/usr/bin/env python3
"""Procurement Quote Audit: offline landed-cost comparison for agricultural inputs.

Distinct product from orchard investment NPV. Buyer-supplied quantities, prices,
taxes, lead times and supplier quality information only. No online scraping,
market forecasts, paid APIs, supplier due-diligence or public product publishing.
"""
from decimal import Decimal, InvalidOperation, localcontext, ROUND_HALF_EVEN, ROUND_CEILING
from datetime import date
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import tempfile

MAX_MONEY=Decimal("1000000000000")
MAX_QTY=Decimal("1000000000")
CENT=Decimal("0.01")


class AuditInputError(ValueError):
    pass


def dec(x,name,limit=MAX_MONEY,positive=False):
    if type(x) not in (str,int):
        raise AuditInputError(name+" must be decimal string/integer")
    try:
        val=Decimal(str(x))
    except InvalidOperation as exc:
        raise AuditInputError(name+" must be a finite decimal") from exc
    if not val.is_finite() or val<0 or val>limit or (positive and val==0):
        raise AuditInputError(name+" outside supported range")
    return val


def shown(v):
    return str(v.quantize(CENT,rounding=ROUND_HALF_EVEN))


def _iso_date(value, field):
    if not isinstance(value,str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}",value):
        raise AuditInputError(field+" requires YYYY-MM-DD")
    try:
        obj=date.fromisoformat(value)
    except ValueError as exc:
        raise AuditInputError(field+" is not a valid calendar date") from exc
    if obj.isoformat()!=value:
        raise AuditInputError(field+" requires canonical YYYY-MM-DD")
    return obj


def _spec_ref(value,field):
    if not isinstance(value,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{2,79}",value):
        raise AuditInputError(field+" requires a bounded product specification reference")
    return value


def verify(inp):
    old_keys={"currency","unit","net_units_required","deadline_days",
              "offers","stress_cases"}
    if not isinstance(inp,dict) or set(inp) not in (old_keys,old_keys|{"comparison_controls"}):
        raise AuditInputError("exact input fields required")
    control=None
    if "comparison_controls" in inp:
        raw_controls=inp["comparison_controls"]
        expected={"required_product_spec_id","delivery_basis","as_of_date"}
        if not isinstance(raw_controls,dict) or set(raw_controls)!=expected:
            raise AuditInputError("comparison_controls require exact declared fields")
        delivery=raw_controls["delivery_basis"]
        if delivery not in ("delivered_to_farm","buyer_collection"):
            raise AuditInputError("unsupported delivery basis")
        control={
            "required_product_spec_id":_spec_ref(raw_controls["required_product_spec_id"],
                                                   "required_product_spec_id"),
            "delivery_basis":delivery,
            "as_of_date":_iso_date(raw_controls["as_of_date"],"as_of_date"),
        }
    if not isinstance(inp["currency"],str) or not re.fullmatch("[A-Z]{3}",inp["currency"]):
        raise AuditInputError("currency must be three uppercase characters")
    if inp["unit"] not in ("kg","tonne","litre","piece","bag"):
        raise AuditInputError("unit must be exactly one specified commodity measurement")
    qty=dec(inp["net_units_required"],"net_units_required",MAX_QTY,True)
    deadline=inp["deadline_days"]
    if type(deadline) is not int or not 0<=deadline<=365:
        raise AuditInputError("deadline_days must be 0..365")
    offers=inp["offers"]
    if not isinstance(offers,list) or not 2<=len(offers)<=10:
        raise AuditInputError("between two and ten offers required")
    clean=[]
    names=set()
    spec={"supplier","unit_price","freight_flat","setup_flat","discount_pct",
          "tax_pct","waste_pct","lead_days","minimum_order_units",
          "available_units","source_label","quote_ref"}
    for raw in offers:
        # Optional whole-pack pricing is explicit and backward compatible.
        keys=set(raw) if isinstance(raw,dict) else set()
        pack_fields={"pricing_basis","pack_size_base_units"}
        quote_fields={"quote_controls"}
        allowed=(spec,spec|pack_fields,spec|quote_fields,spec|pack_fields|quote_fields)
        if not isinstance(raw,dict) or keys not in allowed:
            raise AuditInputError("exact base-unit, whole-pack and optional quote fields required")
        if pack_fields.issubset(keys) and raw["pricing_basis"]!="per_pack":
            raise AuditInputError("whole-pack quote must explicitly say per_pack")
        if control is None and quote_fields.issubset(keys):
            raise AuditInputError("quote_controls require top-level comparison_controls")
        name=raw["supplier"]
        if not isinstance(name,str) or not name.strip() or len(name)>70 or name in names:
            raise AuditInputError("distinct nonblank supplier names required")
        names.add(name)
        lead=raw["lead_days"]
        if type(lead) is not int or not 0<=lead<=365:
            raise AuditInputError("lead_days must be 0..365")
        src=raw["source_label"]
        if not isinstance(src,str) or len(src)>240:
            raise AuditInputError("source_label length invalid")
        ref=raw["quote_ref"]
        if not isinstance(ref,str) or len(ref)>120:
            raise AuditInputError("quote_ref length invalid")
        out={"supplier":name,"lead_days":lead,"source_label":src,"quote_ref":ref,
             "pricing_basis":"per_base_unit","pack_size_base_units":None,
             "quote_controls":None}
        if "quote_controls" in raw:
            quote=raw["quote_controls"]
            if not isinstance(quote,dict) or set(quote)!={
                "product_spec_id","delivery_basis","quoted_on","valid_until",
                "quote_document_sha256"}:
                raise AuditInputError("quote_controls exact metadata fields required")
            if quote["delivery_basis"] not in ("delivered_to_farm","buyer_collection"):
                raise AuditInputError("unsupported quoted delivery basis")
            fingerprint=quote["quote_document_sha256"]
            if not isinstance(fingerprint,str) or not re.fullmatch("[a-f0-9]{64}",fingerprint) or len(set(fingerprint))==1:
                raise AuditInputError("quote document requires a nontrivial lowercase sha256 digest")
            issued=_iso_date(quote["quoted_on"],"quoted_on")
            expires=_iso_date(quote["valid_until"],"valid_until")
            if issued>expires:
                raise AuditInputError("quote issue date after expiry")
            out["quote_controls"]={
                "product_spec_id":_spec_ref(quote["product_spec_id"],"product_spec_id"),
                "delivery_basis":quote["delivery_basis"],
                "quoted_on":issued,"valid_until":expires,
                "quote_document_sha256":fingerprint,
            }
        if pack_fields.issubset(keys):
            out["pricing_basis"]="per_pack"
            out["pack_size_base_units"]=dec(
                raw["pack_size_base_units"],"pack_size_base_units",MAX_QTY,True)
        for key in ("unit_price","freight_flat","setup_flat","minimum_order_units",
                    "available_units"):
            out[key]=dec(raw[key],key,MAX_QTY if key.endswith("_units") else MAX_MONEY)
        for key in ("discount_pct","tax_pct","waste_pct"):
            out[key]=dec(raw[key],key,Decimal("100"))
        if out["waste_pct"]>=100:
            raise AuditInputError("waste_pct must be below 100")
        clean.append(out)
    stresses=inp["stress_cases"]
    if not isinstance(stresses,dict) or set(stresses)!={"base","adverse"}:
        raise AuditInputError("must explicitly provide base and adverse stress cases")
    parsed={}
    for scenario in ("base","adverse"):
        obj=stresses[scenario]
        if not isinstance(obj,dict) or set(obj)!={"price_multiplier","freight_multiplier","waste_extra_pp"}:
            raise AuditInputError("exact price, freight, waste scenario fields required")
        parsed[scenario]={
            "price_multiplier":dec(obj["price_multiplier"],"price_multiplier",Decimal("5")),
            "freight_multiplier":dec(obj["freight_multiplier"],"freight_multiplier",Decimal("5")),
            "waste_extra_pp":dec(obj["waste_extra_pp"],"waste_extra_pp",Decimal("99")),
        }
    if parsed["base"]!={"price_multiplier":Decimal(1),
                        "freight_multiplier":Decimal(1),
                        "waste_extra_pp":Decimal(0)}:
        raise AuditInputError("base case must have neutral multipliers")
    return qty,deadline,clean,parsed,control


def evaluate(inp):
    qty,deadline,offers,stresses,control=verify(inp)
    results={}
    notes=["SUPPLIER_QUOTES_AND_QUALITY_NOT_INDEPENDENTLY_VERIFIED",
           "ESTIMATED_LANDED_COST_ONLY_NOT_PURCHASE_APPROVAL",
           "NO_PARTIAL_OR_SPLIT_SUPPLIER_ALLOCATION",
           "DELIVERY_CAPACITY_SELF_REPORTED",
           "TAX_AND_DISCOUNT_CONVENTIONS_MUST_BE_CONFIRMED",
           "WHOLE_PACK_PRICING_AND_ROUNDING_ARE_EXPLICIT_INPUTS",
           "UNUSED_PURCHASED_UNITS_ARE_NOT_ASSUMED_RESALABLE",
           "COST_SPREAD_IS_NOT_REALIZED_SAVINGS",
           "DECLARED_SPEC_MATCH_AND_DOCUMENT_HASH_DO_NOT_AUTHENTICATE_SUPPLIER",
           "NO_PROOF_OF_REAL_BUYER_DEMAND_OR_ACTUAL_SAVINGS"]
    if control is None:
        notes.append("LEGACY_MODE_DOES_NOT_CHECK_SUPPLIER_PRODUCT_SPEC_EQUIVALENCE")
    with localcontext() as ctx:
        ctx.prec=42
        for tag,scenario in stresses.items():
            rows=[]
            for offer in offers:
                waste=offer["waste_pct"]+scenario["waste_extra_pp"]
                reasons=[]
                pack_count=None
                required_gross=None
                if waste>=100:
                    reasons.append("WASTE_AT_OR_ABOVE_100_PERCENT")
                    gross=None
                else:
                    required_gross=qty/(1-waste/100)
                    gross=max(required_gross,offer["minimum_order_units"])
                    if offer["pricing_basis"]=="per_pack":
                        pack=offer["pack_size_base_units"]
                        pack_count=(gross/pack).to_integral_value(rounding=ROUND_CEILING)
                        gross=pack_count*pack
                if offer["lead_days"]>deadline:
                    reasons.append("DELIVERY_AFTER_DEADLINE")
                if gross is not None and gross>offer["available_units"]:
                    reasons.append("INSUFFICIENT_DECLARED_CAPACITY")
                if not offer["source_label"].strip() or not offer["quote_ref"].strip():
                    reasons.append("QUOTE_PROVENANCE_MISSING")
                if control is not None:
                    quote=offer["quote_controls"]
                    if quote is None:
                        reasons.append("QUOTE_COMPARABILITY_METADATA_MISSING")
                    else:
                        if quote["product_spec_id"]!=control["required_product_spec_id"]:
                            reasons.append("PRODUCT_SPECIFICATION_MISMATCH")
                        if quote["delivery_basis"]!=control["delivery_basis"]:
                            reasons.append("DELIVERY_BASIS_MISMATCH")
                        if quote["quoted_on"]>control["as_of_date"]:
                            reasons.append("QUOTE_ISSUED_AFTER_AS_OF_DATE")
                        if quote["valid_until"]<control["as_of_date"]:
                            reasons.append("QUOTE_EXPIRED_AS_OF_DATE")
                output={
                    "supplier":offer["supplier"],
                    "eligible_for_cost_comparison":not reasons,
                    "reasons":reasons,
                    "source_operator_supplied":offer["source_label"],
                    "quote_reference_operator_supplied":offer["quote_ref"],
                    "lead_days":offer["lead_days"],
                    "verified_quote":False,
                    "verified_supplier_quality":False,
                    "buyer_declared_spec_and_quote_date_gate_checked":control is not None,
                    "quote_metadata_independently_authenticated":False,
                    "quote_spec_ref_operator_supplied":(
                        offer["quote_controls"]["product_spec_id"]
                        if offer["quote_controls"] is not None else None),
                    "quote_document_digest_operator_supplied":(
                        offer["quote_controls"]["quote_document_sha256"]
                        if offer["quote_controls"] is not None else None),
                    "quote_pricing_basis":offer["pricing_basis"],
                    "price_per_quoted_unit":shown(offer["unit_price"]),
                    "pack_size_base_units":(
                        shown(offer["pack_size_base_units"])
                        if offer["pack_size_base_units"] is not None else None),
                    "whole_packs_ordered":(
                        str(pack_count) if pack_count is not None else None),
                }
                if gross is not None:
                    invoice_qty=pack_count if pack_count is not None else gross
                    material=invoice_qty*offer["unit_price"]*scenario["price_multiplier"]
                    discounted=material*(1-offer["discount_pct"]/100)
                    # Tax convention: applies to discounted material + setup, excludes freight.
                    taxable=discounted+offer["setup_flat"]
                    tax=taxable*offer["tax_pct"]/100
                    freight=offer["freight_flat"]*scenario["freight_multiplier"]
                    total=taxable+tax+freight
                    output.update({
                        "gross_order_units":shown(gross),
                        "gross_units_before_pack_rounding":shown(required_gross),
                        "net_usable_units_from_order":shown(gross*(1-waste/100)),
                        "surplus_usable_units":shown(gross*(1-waste/100)-qty),
                        "quoted_price_normalized_per_base_unit":shown(
                            offer["unit_price"]/offer["pack_size_base_units"]
                            if pack_count is not None else offer["unit_price"]),
                        "usable_fraction_pct":shown(100-waste),
                        "discounted_material_cost":shown(discounted),
                        "setup_cost":shown(offer["setup_flat"]),
                        "tax_cost":shown(tax),
                        "freight_cost":shown(freight),
                        "total_landed_cost":shown(total),
                        "landed_cost_per_net_required_unit":shown(total/qty),
                        "_exact_total":total,
                    })
                else:
                    output["total_landed_cost"]=None
                rows.append(output)
            rows.sort(key=lambda x:(not x["eligible_for_cost_comparison"],
                                     x.get("_exact_total",Decimal("Infinity")),
                                     x["supplier"]))
            valid=[x for x in rows if x["eligible_for_cost_comparison"]]
            winner=valid[0]["supplier"] if valid else None
            runner_up=valid[1]["supplier"] if len(valid)>1 else None
            arithmetic_gap=(
                shown(valid[1]["_exact_total"]-valid[0]["_exact_total"])
                if len(valid)>1 else None)
            for row in rows:
                row.pop("_exact_total",None)
            results[tag]={
                "lowest_cost_eligible_supplier_under_inputs":winner,
                "second_lowest_cost_eligible_supplier_under_inputs":runner_up,
                "arithmetic_cost_gap_to_second_eligible_not_realized_savings":arithmetic_gap,
                "offers":rows,
                "all_offers_ineligible":len(valid)==0,
            }
    canonical=json.dumps(inp,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    return {
        "schema_version":1,
        "product":"farm_input_procurement_audit_private_reference_mvp",
        "input_sha256":hashlib.sha256(canonical.encode()).hexdigest(),
        "currency":inp["currency"],"unit":inp["unit"],
        "net_units_required":shown(qty),
        "deadline_days":deadline,
        "declared_spec_comparison_mode":(
            "buyer_supplied_metadata_not_independently_authenticated"
            if control is not None else "legacy_spec_comparability_unassessed"),
        "buyer_required_product_spec_ref":(
            control["required_product_spec_id"] if control is not None else None),
        "as_of_date_operator_supplied":(
            control["as_of_date"].isoformat() if control is not None else None),
        "scenarios":results,
        "warnings":notes,
        "winner_is_not_supplier_recommendation":True,
        "sources_independently_verified":False,
        "market_demand_verified":False,
        "quality_score":None,
        "commercial_release_allowed":False,
        "payment_authorized":False,
    }


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input",required=True)
    ap.add_argument("--output",required=True)
    args=ap.parse_args(argv)
    raw=Path(args.input).expanduser()
    if raw.is_symlink() or not raw.is_file() or raw.stat().st_size>300000:
        raise AuditInputError("invalid source file")
    source=raw.resolve(strict=True)
    dest_raw=Path(args.output).expanduser()
    if dest_raw.is_symlink() or dest_raw.exists():
        raise AuditInputError("output path must be a new file")
    dest=dest_raw.resolve()
    if dest==source or not dest.parent.is_dir():
        raise AuditInputError("output path invalid")
    doc=json.loads(source.read_text(encoding="utf-8"),parse_float=str,parse_int=int)
    report=evaluate(doc)
    fd,tmp=tempfile.mkstemp(prefix=".farm-procurement-",dir=str(dest.parent))
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as h:
            json.dump(report,h,ensure_ascii=False,sort_keys=True,indent=2)
            h.write(chr(10));h.flush();os.fsync(h.fileno())
        os.chmod(tmp,0o600)
        os.link(tmp,dest)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    print("FARM_PROCUREMENT_PRIVATE_QA_ONLY=true")
    print("FARM_PROCUREMENT_SALE_READY=false")


if __name__=="__main__":
    main()
