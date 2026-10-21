// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;
import {TRC20} from "@openzeppelin/tron-contracts/token/TRC20/TRC20.sol";
import {MojGenesisDistributor} from "./MojGenesisDistributor.sol";

/// @notice Fixed-supply token, strictly for testnet evaluation at this stage.
contract MojCoin is TRC20 {
    uint256 public constant MAX_SUPPLY = 100_000_000_000 * 10 ** 18;
    MojGenesisDistributor public immutable distributor;

    constructor(address governance) TRC20("Moj 1", "MOJ1") {
        require(governance != address(0), "Invalid governance");
        // No externally controlled wallet receives the full supply at genesis.
        distributor = new MojGenesisDistributor(governance);
        _mint(address(distributor), MAX_SUPPLY);
    }
}
