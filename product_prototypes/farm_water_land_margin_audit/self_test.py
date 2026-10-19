#!/usr/bin/env python3
"""Standalone zero-dependency verification included inside the product ZIP."""
from pathlib import Path
import json
from water_margin_audit import audit

def main():
    doc=json.loads((Path(__file__).parent/"example_synthetic.json").read_text())
    result=audit(doc)
    assert result["baseline"]["optimal_for_given_linear_model"]
    assert result["water_scarcity"]["optimal_for_given_linear_model"]
    assert result["sale_ready"] is False
    assert result["market_demand_verified"] is False
    assert result["quality_score"] is None
    assert float(result["baseline"]["total_gross_margin"])>=float(result["water_scarcity"]["total_gross_margin"])
    for key in ("baseline","water_scarcity"):
        scenario=result[key]
        assert float(scenario["unused_land_hectares"])>=-0.0001
        assert float(scenario["unused_water_m3"])>=-0.01
    print("ASTRA_WATER_LAND_INDEPENDENT_SELF_TEST=PASS")
    print("ASTRA_WATER_LAND_RETAIL_READY=false")

if __name__=="__main__":
    main()
