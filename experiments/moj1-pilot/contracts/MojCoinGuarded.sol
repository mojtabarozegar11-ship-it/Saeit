// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;

import {TRC20} from "@openzeppelin/tron-contracts/token/TRC20/TRC20.sol";
import {MojGenesisFactoryGuarded} from "./MojGenesisFactoryGuarded.sol";

/// @notice LOCAL TVM ONLY: V2 reference coin for factory-created vesting/reserve vaults.
/// @dev Existing Shasta MOJ1 code and immutable escrow are intentionally unchanged.
contract MojCoinGuarded is TRC20 {
    uint256 public constant MAX_SUPPLY = 100_000_000_000 * 10 ** 18;
    MojGenesisFactoryGuarded public immutable distributor;

    constructor(address governance) TRC20("Moj 1", "MOJ1") {
        require(governance != address(0), "Invalid governance");
        distributor = new MojGenesisFactoryGuarded(governance);
        _mint(address(distributor), MAX_SUPPLY);
    }
}
