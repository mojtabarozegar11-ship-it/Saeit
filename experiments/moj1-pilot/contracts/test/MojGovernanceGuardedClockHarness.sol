// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;

import {MojGovernanceGuarded} from "../MojGovernanceGuarded.sol";

/// @dev DISPOSABLE LOCAL TVM TEST ONLY. Never use as a production governor:
///      any caller can advance its clock and bypass a real-world waiting period.
contract MojGovernanceGuardedClockHarness is MojGovernanceGuarded {
    uint256 private testTime;

    constructor(address[3] memory initialOwners, uint256 initialTime)
        MojGovernanceGuarded(initialOwners)
    {
        testTime = initialTime;
    }

    function setTestClock(uint256 nextTime) external {
        require(nextTime >= testTime, "Clock cannot go backward");
        testTime = nextTime;
    }

    function currentTime() external view returns (uint256) {
        return testTime;
    }

    function _clock() internal view override returns (uint256) {
        return testTime;
    }
}
