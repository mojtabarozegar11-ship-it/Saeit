// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;

import {ITRC20} from "@openzeppelin/tron-contracts/token/TRC20/ITRC20.sol";
import {SafeTRC20} from "@openzeppelin/tron-contracts/token/TRC20/utils/SafeTRC20.sol";

/// @notice Irrevocable allocation reserve; governance may schedule, but not redirect, its release.
/// @dev Governance is intended to be a separately verified multisignature wallet.
contract MojApprovalReserve {
    using SafeTRC20 for ITRC20;

    uint256 public constant RELEASE_DELAY = 30 days;
    ITRC20 public immutable token;
    address public immutable beneficiary;
    address public immutable releaseController;
    uint256 public immutable allocation;

    uint256 public releaseScheduledAt;
    bool public released;

    event ReleaseScheduled(uint256 executableAt);
    event ReleaseCancelled();
    event ReserveReleased(address indexed beneficiary, uint256 amount);

    constructor(address tokenAddress, address beneficiaryAddress, address controllerAddress, uint256 amount) {
        require(tokenAddress != address(0) && beneficiaryAddress != address(0), "Invalid address");
        require(controllerAddress != address(0) && amount > 0, "Invalid controller/amount");
        token = ITRC20(tokenAddress);
        beneficiary = beneficiaryAddress;
        releaseController = controllerAddress;
        allocation = amount;
    }

    function fullyFunded() public view returns (bool) {
        return released || token.balanceOf(address(this)) >= allocation;
    }

    function scheduleRelease() external {
        require(msg.sender == releaseController, "Controller only");
        require(!released && releaseScheduledAt == 0, "Already scheduled/released");
        require(fullyFunded(), "Reserve not fully funded");
        releaseScheduledAt = block.timestamp + RELEASE_DELAY;
        emit ReleaseScheduled(releaseScheduledAt);
    }

    function cancelRelease() external {
        require(msg.sender == releaseController, "Controller only");
        require(!released && releaseScheduledAt != 0, "No pending release");
        releaseScheduledAt = 0;
        emit ReleaseCancelled();
    }

    /// @notice Once approved and delayed, anyone can deliver the entire reserve to its immutable beneficiary.
    function executeRelease() external {
        require(!released && releaseScheduledAt != 0, "No pending release");
        require(block.timestamp >= releaseScheduledAt, "Delay active");
        require(fullyFunded(), "Reserve not fully funded");
        released = true;
        token.safeTransfer(beneficiary, allocation);
        emit ReserveReleased(beneficiary, allocation);
    }
}
