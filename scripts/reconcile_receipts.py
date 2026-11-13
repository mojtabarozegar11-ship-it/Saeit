"""Offline reconciliation of order, settlement and refund claims; never certifies bank receipts."""
import json
from decimal import Decimal, InvalidOperation

def amount(value):
    if not isinstance(value, str) or 'e' in value.lower():
        raise ValueError("plain decimal string required")
    try: n = Decimal(value)
    except InvalidOperation as exc: raise ValueError("invalid decimal") from exc
    if not n.is_finite() or n < 0 or n.as_tuple().exponent < -2:
        raise ValueError("invalid nonnegative amount or precision")
    return n

def reconcile(data):
    if not isinstance(data, dict):
        raise ValueError("reconciliation input must be a JSON object")
    for key in ("orders", "settlements", "refunds"):
        if key not in data:
            raise ValueError(f"missing required collection: {key}")
    currency = data.get("currency")
    if not isinstance(currency, str) or len(currency) != 3 or not currency.isascii() or not currency.isalpha():
        raise ValueError("explicit ISO-style currency required")
    orders, settlements, refunds = (data.get(k, []) for k in ("orders", "settlements", "refunds"))
    for records in (orders, settlements, refunds):
        if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
            raise ValueError("records must be objects")
        ids = [r.get("id") for r in records]
        if any(not isinstance(i, str) or not i.strip() for i in ids) or len(set(ids)) != len(ids):
            raise ValueError("duplicate or missing ids")
    # Reject any explicit per-record currency that disagrees with the report currency.
    # Legacy records without currency remain unverified claims, not bank evidence.
    for records in (orders, settlements, refunds):
        for record in records:
            record_currency = record.get("currency")
            if record_currency is not None and (not isinstance(record_currency, str) or record_currency.upper() != currency.upper()):
                raise ValueError("record currency differs from report currency")
    # Validate all monetary claims, including pending/failed rows, before any totals.
    # Otherwise malformed records can silently become counted after a status change.
    for kind, records in (("order", orders), ("settlement", settlements), ("refund", refunds)):
        for record in records:
            if "amount" not in record:
                raise ValueError(f"{kind} amount missing")
            amount(record["amount"])
    by_order = {r["id"]: r for r in orders}
    by_settlement = {r["id"]: r for r in settlements}
    paid = {}
    returned = {}
    eligible_settlements = set()
    seen_external_references = set()
    issues = []
    for s in settlements:
        if s.get("status") != "settled": continue
        value = amount(s["amount"])
        if s.get("order_id") not in by_order or not isinstance(s.get("reference"), str) or not s["reference"].strip():
            issues.append({"settlement":s["id"],"issue":"missing_order_or_external_reference"})
            continue
        reference = s["reference"].strip()
        if reference in seen_external_references:
            issues.append({"settlement":s["id"],"issue":"duplicate_external_reference"})
            continue
        # Fail closed: do not recognize a settlement that would overpay its order.
        if paid.get(s["order_id"], Decimal(0)) + value > amount(by_order[s["order_id"]]["amount"]):
            issues.append({"settlement":s["id"],"issue":"settlements_exceed_order"})
            continue
        seen_external_references.add(reference)
        eligible_settlements.add(s["id"])
        paid[s["order_id"]] = paid.get(s["order_id"], Decimal(0)) + value
    for r in refunds:
        if r.get("status") != "completed": continue
        value = amount(r["amount"])
        s = by_settlement.get(r.get("settlement_id"))
        if s is None or s["id"] not in eligible_settlements:
            issues.append({"refund":r["id"],"issue":"unmatched_settlement"})
            continue
        sid = s["id"]
        candidate = returned.get(sid, Decimal(0)) + value
        if candidate > amount(s["amount"]):
            issues.append({"refund":r["id"],"issue":"refund_exceeds_settlement"})
            continue
        returned[sid] = candidate
    for oid, value in paid.items():
        if value > amount(by_order[oid]["amount"]):
            issues.append({"order":oid,"issue":"settlements_exceed_order"})
    for sid, value in returned.items():
        if value > amount(by_settlement[sid]["amount"]):
            issues.append({"settlement":sid,"issue":"refund_exceeds_settlement"})
    for order in orders:
        if order.get("status") == "paid" and paid.get(order["id"], Decimal(0)) < amount(order["amount"]):
            issues.append({"order":order["id"],"issue":"paid_claim_not_fully_settled"})
    gross = sum(paid.values(), Decimal(0))
    refunds_total = sum(returned.values(), Decimal(0))
    return {"currency":currency.upper(),"gross_settled_unverified":str(gross),
            "completed_refunds_unverified":str(refunds_total),
            "net_settled_unverified":str(gross-refunds_total),
            "delivered_order_claims":sum(o.get("delivery_confirmed") is True for o in orders),
            "issues":issues,"bank_verified":False,"revenue_certified":False}

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("input")
    args = p.parse_args()
    with open(args.input, encoding="utf-8") as f: data = json.load(f)
    result = reconcile(data)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(2 if result["issues"] else 0)
