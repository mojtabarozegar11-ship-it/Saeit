// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;
import {TRC20} from "@openzeppelin/tron-contracts/token/TRC20/TRC20.sol";

/// @notice Fixed-supply token, strictly for testnet evaluation at this stage.
contract MojCoin is TRC20 {
    uint256 public constant MAX_SUPPLY = 100_000_000_000 * 10 ** 18;

    constructor(address treasury) TRC20("Moj 1", "MOJ1") {
        require(treasury != address(0), "Invalid treasury");
        _mint(treasury, MAX_SUPPLY);
    }
}
