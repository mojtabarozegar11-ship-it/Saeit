// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;

import {ITRC20} from "@openzeppelin/tron-contracts/token/TRC20/ITRC20.sol";
import {SafeTRC20} from "@openzeppelin/tron-contracts/token/TRC20/utils/SafeTRC20.sol";

/// @notice ADVERSARIAL LOCAL TEST FIXTURE ONLY. NEVER USE WITH REAL TOKENS.
///         It presents the same public parameters as a legitimate vesting vault,
///         but does not enforce any vesting before forwarding all funds.
contract MojVestingLookalike {
    using SafeTRC20 for ITRC20;

    ITRC20 public immutable token;
    address public immutable beneficiary;
    uint256 public immutable allocation;
    uint256 public immutable start;
    uint256 public immutable cliff;
    uint256 public immutable duration;
    uint256 public released;

    constructor(address coin, address target, uint256 amount, uint256 t0, uint256 cliffSeconds, uint256 durationSeconds) {
        token = ITRC20(coin);
        beneficiary = target;
        allocation = amount;
        start = t0;
        cliff = cliffSeconds;
        duration = durationSeconds;
    }

    function drain(address recipient) external {
        token.safeTransfer(recipient, token.balanceOf(address(this)));
    }
}
