// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;

import {ITRC20} from "@openzeppelin/tron-contracts/token/TRC20/ITRC20.sol";
import {SafeTRC20} from "@openzeppelin/tron-contracts/token/TRC20/utils/SafeTRC20.sol";
import {Math} from "@openzeppelin/tron-contracts/utils/math/Math.sol";

/// @notice Non-revocable, non-upgradeable vesting vault for one MOJ1 allocation.
/// @dev Must be funded with the entire allocation before any release is possible.
///      The cliff and linear-release duration are measured in seconds, not calendar months.
contract MojVestingVault {
    using SafeTRC20 for ITRC20;

    ITRC20 public immutable token;
    address public immutable beneficiary;
    uint256 public immutable allocation;
    uint256 public immutable start;
    uint256 public immutable cliff;
    uint256 public immutable duration;
    uint256 public released;

    event Released(address indexed beneficiary, uint256 amount);

    constructor(
        address tokenAddress,
        address beneficiaryAddress,
        uint256 totalAllocation,
        uint256 startTimestamp,
        uint256 cliffSeconds,
        uint256 linearDurationSeconds
    ) {
        require(tokenAddress != address(0) && beneficiaryAddress != address(0), "Invalid address");
        require(totalAllocation > 0, "Invalid allocation");
        require(linearDurationSeconds > 0, "Invalid duration");
        require(startTimestamp <= type(uint256).max - cliffSeconds, "Cliff overflow");
        require(startTimestamp + cliffSeconds <= type(uint256).max - linearDurationSeconds, "End overflow");

        token = ITRC20(tokenAddress);
        beneficiary = beneficiaryAddress;
        allocation = totalAllocation;
        start = startTimestamp;
        cliff = cliffSeconds;
        duration = linearDurationSeconds;
    }

    function fullyFunded() public view returns (bool) {
        return token.balanceOf(address(this)) >= allocation - released;
    }

    function vestedAt(uint256 timestamp) public view returns (uint256) {
        uint256 cliffEnd = start + cliff;
        if (timestamp <= cliffEnd) return 0;
        uint256 elapsed = timestamp - cliffEnd;
        if (elapsed >= duration) return allocation;
        return Math.mulDiv(allocation, elapsed, duration);
    }

    function releasable() public view returns (uint256) {
        return vestedAt(block.timestamp) - released;
    }

    /// @notice Anyone may trigger release, but payment can only go to beneficiary.
    function release() external {
        require(fullyFunded(), "Vault not fully funded");
        uint256 amount = releasable();
        require(amount > 0, "Nothing releasable");
        released += amount;
        token.safeTransfer(beneficiary, amount);
        emit Released(beneficiary, amount);
    }
}
