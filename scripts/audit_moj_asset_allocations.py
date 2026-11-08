"""Offline cross-check for Moj asset proposals and allocation math.

This is a pre-issuance audit, not a contract security audit or a chain action.
"""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from moj_asset_registry import generate_program, validate_program, MOJONER_SUPPLY

ALLOCATION_BPS = {
    "game_rewards": 3000,
    "player_ecosystem_reserve": 2500,
    "unfunded_liquidity_reserve": 1500,
    "development_treasury": 1500,
    "community_creators": 1000,
    "security_contingency": 500,
}

def allocation_for_supply(supply):
    if type(supply) is not int or supply <= 0:
        raise ValueError("invalid_supply")
    if sum(ALLOCATION_BPS.values()) != 10000:
        raise ValueError("allocation_basis_points_not_10000")
    result = {name: supply * bps // 10000
              for name, bps in ALLOCATION_BPS.items()}
    # Assign rounding dust deterministically to the reserve, not rewards.
    result["security_contingency"] += supply - sum(result.values())
    if sum(result.values()) != supply:
        raise ValueError("allocation_sum_mismatch")
    return result

def audit():
    program = generate_program()
    validate_program(program)
    assets = {}
    for item in program["assets"]:
        supply = int(item["supply_tokens"])
        assets[item["id"]] = {
            "supply": str(supply),
            "allocation": {k: str(v) for k, v in allocation_for_supply(supply).items()},
            "issued": False,
            "liquidity_funded": False,
        }
    assert int(assets["mojoner"]["supply"]) == MOJONER_SUPPLY
    assert len(assets) == 51
    return {"schema": "moj.asset-allocation-audit.v1",
            "allocation_status": "revisable_unapproved_proposal",
            "chain_transactions": 0, "verified_revenue": "0",
            "assets": assets}

if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
