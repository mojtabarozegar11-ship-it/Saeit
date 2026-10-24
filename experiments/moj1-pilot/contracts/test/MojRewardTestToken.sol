// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;

import {TRC20} from "@openzeppelin/tron-contracts/token/TRC20/TRC20.sol";

/// @notice Disposable local-TVM and separately authorized Shasta-only test token. Never MOJ1 or production.
contract MojRewardTestToken is TRC20 {
    constructor() TRC20("Disposable reward test", "TTEST") {
        _mint(msg.sender, 1_000_000 * 10 ** 18);
    }
}
