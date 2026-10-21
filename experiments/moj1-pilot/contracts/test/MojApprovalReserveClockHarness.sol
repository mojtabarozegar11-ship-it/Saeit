// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;

import {MojApprovalReserve} from "../MojApprovalReserve.sol";

/// @notice LOCAL TVM TEST FIXTURE ONLY. Public time control makes this UNSAFE for real funds.
/// @dev Never deploy, use as a real genesis vault, or change any production release policy based
///      on the fixture without separate independent contract verification.
contract MojApprovalReserveClockHarness is MojApprovalReserve {
    uint256 public mockTimestamp;

    constructor(address tokenAddress, address beneficiaryAddress, address controllerAddress, uint256 amount)
        MojApprovalReserve(tokenAddress, beneficiaryAddress, controllerAddress, amount)
    {
        mockTimestamp = block.timestamp;
    }

    function setTime(uint256 timestamp) external {
        mockTimestamp = timestamp;
    }

    function _clock() internal view override returns (uint256) {
        return mockTimestamp;
    }
}
