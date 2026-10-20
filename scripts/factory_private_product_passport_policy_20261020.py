#!/usr/bin/env python3
"""Private product passport metadata policy; does not publish or grant IP rights."""
import json
from pathlib import Path

PERSON = "مجتبی روزگار"
ROLES = ("author", "researcher", "scientific_researcher", "compiler", "producer", "maker", "seller")
LABELS = ("نویسنده", "محقق", "پژوهشگر", "گردآورنده", "تهیه‌کننده", "سازنده", "فروشنده")
SCHEMA_VERSION = "1.0"

def build_passport(product_id, verified_roles=None, ownership=None, evidence=None):
    """Do not assert unverified authorship or ownership. Store claims separately."""
    if not isinstance(product_id, str) or not product_id.strip():
        raise ValueError("PRODUCT_ID_REQUIRED")
    verified_roles = verified_roles or []
    if any(role not in ROLES for role in verified_roles):
        raise ValueError("UNKNOWN_ROLE")
    if ownership is not None:
        if not isinstance(ownership, list) or not ownership or any(
            not isinstance(x, dict) or not isinstance(x.get("party"), str)
            or not isinstance(x.get("percent"), (int, float))
            or isinstance(x.get("percent"), bool)
            or not 0 <= x["percent"] <= 100 for x in ownership
        ) or abs(sum(x["percent"] for x in ownership) - 100) > 0.00001:
            raise ValueError("OWNERSHIP_SHARES_INVALID")
    return {
        "schema_version": SCHEMA_VERSION,
        "product_id": product_id,
        "visibility": "private_passport_only",
        "declared_person": PERSON,
        "declared_roles": dict(zip(ROLES, LABELS)),
        "verified_roles": verified_roles,
        "role_evidence": evidence or {},
        "economic_rights": ownership,
        "exclusive_sales_license": {
            "proposed_licensee": PERSON,
            "exclusive": True,
            "duration": "indefinite_until_contractual_termination",
            "cure_period_calendar_days": 15,
            "executed_agreement_verified": False,
        },
        "commercial_release_allowed": False,
        "public_store_role_display": False,
    }

def write_passport(path, passport):
    target = Path(path)
    if target.exists() or target.is_symlink():
        raise FileExistsError("NO_PASSPORT_OVERWRITE")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(passport, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("product_id")
    parser.add_argument("output")
    args = parser.parse_args()
    write_passport(args.output, build_passport(args.product_id))
