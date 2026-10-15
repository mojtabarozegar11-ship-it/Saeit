#!/usr/bin/env python3
"""Run independent arithmetic smoke checks after unzipping the private prototype."""
from decimal import Decimal
import json
from pathlib import Path
from decision_audit import analyze, InputError


def verify():
    home=Path(__file__).resolve().parent
    payload=json.loads((home/"example_synthetic.json").read_text(encoding="utf-8"))
    data=analyze(payload)
    assert data["tool"] == "orchard_decision_audit_private_reference_mvp"
    assert not data["sources_independently_verified"]
    assert not data["market_demand_verified"]
    assert not data["store_listing_authorized"]
    base={item["option"]:item for item in data["scenarios"]["base"]}
    ref=sum(Decimal(40)/(Decimal("1.1")**y) for y in (1,2,3))
    invest=Decimal(-100)+sum(Decimal(90)/(Decimal("1.1")**y) for y in (1,2,3))
    assert Decimal(base["Maintain Existing Trees"]["npv"])==ref.quantize(Decimal(".01"))
    assert Decimal(base["Replace Orchard Block"]["npv"])==invest.quantize(Decimal(".01"))
    assert data["scenarios"]["downside"][0]["option"]=="Maintain Existing Trees"
    print("ORCHARD_PRODUCT_SELF_TEST=PASS")
    print("ORCHARD_PRODUCT_MARKET_DEMAND_VERIFIED=false")


if __name__ == "__main__":
    verify()
