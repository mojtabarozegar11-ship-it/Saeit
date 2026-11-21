// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;

import {TRC20} from "@openzeppelin/tron-contracts/token/TRC20/TRC20.sol";

/// @notice Disposable local-TVM test token. Never deploy or use as MOJ1 itself.
contract MojRewardTestToken is TRC20 {
    constructor() TRC20("Disposable reward test", "TTEST") {
        _mint(msg.sender, 1_000_000 * 10 ** 18);
    }
}
