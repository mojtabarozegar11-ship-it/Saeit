#!/usr/bin/env python3
"""Standalone post-extraction QA of the published private reference prototype."""
import json
from pathlib import Path
from decimal import Decimal
from procurement_audit import evaluate

DATA=Path(__file__).resolve().parent/"example_synthetic.json"


def verify():
    payload=json.loads(DATA.read_text(encoding="utf-8"))
    result=evaluate(payload)
    base=result["scenarios"]["base"]
    assert base["lowest_cost_eligible_supplier_under_inputs"]=="Synthetic Provider North"
    assert not base["all_offers_ineligible"]
    by={o["supplier"]:o for o in base["offers"]}
    assert by["Synthetic Provider Late"]["eligible_for_cost_comparison"] is False
    assert "DELIVERY_AFTER_DEADLINE" in by["Synthetic Provider Late"]["reasons"]
    first=by["Synthetic Provider North"]
    expected=(Decimal(100)/Decimal("0.95"))*Decimal(5)*Decimal("0.95")+Decimal(45)
    assert Decimal(first["total_landed_cost"])==expected.quantize(Decimal(".01"))
    assert result["market_demand_verified"] is False
    assert result["commercial_release_allowed"] is False
    assert result["quality_score"] is None
    print("PROCUREMENT_SELF_TEST=PASS")
    print("PROCUREMENT_FOR_SALE=false")


if __name__=="__main__":
    verify()
