"""Revisable, non-executable token allocation proposals; no issuance authority.

All values are basis points. Distribution is a *proposal* for owner review,
not a promise of liquidity, exchange listing, sale or game reward value.
"""
from moj_asset_registry import generate_program, validate_program

ALLOCATION_BPS = {
    "game_rewards": 3000,
    "player_ecosystem_reserve": 2500,
    "liquidity_reserve_unfunded": 1500,
    "development_treasury_locked": 1500,
    "community_and_creators": 1000,
    "security_and_contingency": 500,
}


EXPECTED_ALLOCATION_CATEGORIES = frozenset(ALLOCATION_BPS)


def _valid_allocation_weights():
    if set(ALLOCATION_BPS) != EXPECTED_ALLOCATION_CATEGORIES:
        raise ValueError("allocation_categories_invalid")
    if any(type(bps) is not int or not 0 <= bps <= 10_000
           for bps in ALLOCATION_BPS.values()):
        raise ValueError("allocation_weight_invalid")
    if sum(ALLOCATION_BPS.values()) != 10_000:
        raise ValueError("allocation_basis_points_must_sum_to_10000")


def candidate_allocations(program=None):
    program = generate_program() if program is None else program
    validate_program(program)
    _valid_allocation_weights()
    result = {}
    for asset in program["assets"]:
        supply = int(asset["supply_tokens"])
        allocations = {name: supply * bps // 10000
                       for name, bps in ALLOCATION_BPS.items()}
        # Allocate rounding residue to the non-distributable reserve; never
        # silently overallocate or promise fractional whole-token transfers.
        allocations["security_and_contingency"] += supply - sum(allocations.values())
        if sum(allocations.values()) != supply or any(v < 0 for v in allocations.values()):
            raise ValueError("allocation_supply_mismatch")
        result[asset["id"]] = {
            "network": asset["network"],
            "total_supply_tokens": str(supply),
            "allocations_tokens": {k: str(v) for k, v in allocations.items()},
            "status": "revisable_offline_proposal_not_issued",
            "vesting_schedule": "undecided_requires_owner_approval",
            "market_liquidity_committed": False,
            "player_rewards_transferable": False,
            "no_expected_profit_or_redemption": True,
        }
    return result


if __name__ == "__main__":
    import json
    print(json.dumps(candidate_allocations(), indent=2, sort_keys=True))
