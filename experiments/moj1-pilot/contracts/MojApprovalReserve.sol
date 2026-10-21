// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;

import {ITRC20} from "@openzeppelin/tron-contracts/token/TRC20/ITRC20.sol";
import {SafeTRC20} from "@openzeppelin/tron-contracts/token/TRC20/utils/SafeTRC20.sol";

/// @notice Non-revocable, pre-funded reserve with a strict tranche ceiling and cooldown.
/// @dev Liquidity and contingency share one implementation with fixed, allocation-bound caps.
///      Governance may schedule/cancel but never redirect the immutable beneficiary.
contract MojApprovalReserve {
    using SafeTRC20 for ITRC20;

    uint256 public constant RELEASE_DELAY = 30 days;
    uint256 public constant RELEASE_INTERVAL = 90 days;
    uint256 public constant LIQUIDITY_ALLOCATION = 15_000_000_000 * 10 ** 18;
    uint256 public constant CONTINGENCY_ALLOCATION = 5_000_000_000 * 10 ** 18;
    uint256 public constant LIQUIDITY_TRANCHE_CAP = 1_000_000_000 * 10 ** 18;
    uint256 public constant CONTINGENCY_TRANCHE_CAP = 250_000_000 * 10 ** 18;

    ITRC20 public immutable token;
    address public immutable beneficiary;
    address public immutable releaseController;
    uint256 public immutable allocation;
    uint256 public immutable trancheCap;

    uint256 public releaseScheduledAt;
    uint256 public scheduledAmount;
    uint256 public releasedAmount;
    uint256 public nextReleaseAt;
    uint256 public trancheNonce;
    bool public released;

    event ReleaseScheduled(uint256 indexed nonce, uint256 amount, uint256 executableAt);
    event ReleaseCancelled(uint256 indexed nonce, uint256 amount);
    event ReserveReleased(address indexed beneficiary, uint256 indexed nonce, uint256 amount, uint256 cumulative);

    constructor(address tokenAddress, address beneficiaryAddress, address controllerAddress, uint256 amount) {
        require(tokenAddress != address(0) && beneficiaryAddress != address(0), "Invalid address");
        require(controllerAddress != address(0), "Invalid controller");
        uint256 cap;
        if (amount == LIQUIDITY_ALLOCATION) {
            cap = LIQUIDITY_TRANCHE_CAP;
        } else if (amount == CONTINGENCY_ALLOCATION) {
            cap = CONTINGENCY_TRANCHE_CAP;
        } else {
            revert("Unsupported allocation");
        }
        token = ITRC20(tokenAddress);
        beneficiary = beneficiaryAddress;
        releaseController = controllerAddress;
        allocation = amount;
        trancheCap = cap;
    }

    function fullyFunded() public view returns (bool) {
        return token.balanceOf(address(this)) >= allocation - releasedAmount;
    }

    /// @dev The production implementation always uses the chain clock.
    ///      A test-only subclass overrides this method to verify multiple months locally.
    function _clock() internal view virtual returns (uint256) {
        return block.timestamp;
    }

    function scheduleRelease(uint256 amount) external {
        require(msg.sender == releaseController, "Controller only");
        require(!released && releaseScheduledAt == 0, "Already scheduled/released");
        require(amount > 0 && amount <= trancheCap, "Invalid tranche amount");
        require(amount <= allocation - releasedAmount, "Exceeds remaining allocation");
        require(fullyFunded(), "Reserve not fully funded");

        uint256 executableAt = _clock() + RELEASE_DELAY;
        if (executableAt < nextReleaseAt) executableAt = nextReleaseAt;

        scheduledAmount = amount;
        releaseScheduledAt = executableAt;
        ++trancheNonce;
        emit ReleaseScheduled(trancheNonce, amount, executableAt);
    }

    function cancelRelease() external {
        require(msg.sender == releaseController, "Controller only");
        require(releaseScheduledAt != 0 && !released, "No pending release");
        uint256 amount = scheduledAmount;
        releaseScheduledAt = 0;
        scheduledAmount = 0;
        emit ReleaseCancelled(trancheNonce, amount);
    }

    /// @notice Anyone can trigger a matured tranche, but payment goes ONLY to immutable beneficiary.
    function executeRelease() external {
        require(!released && releaseScheduledAt != 0, "No pending release");
        require(_clock() >= releaseScheduledAt, "Delay active");
        require(fullyFunded(), "Reserve not fully funded");
        uint256 amount = scheduledAmount;
        require(amount > 0 && amount <= trancheCap, "Invalid tranche");
        require(amount <= allocation - releasedAmount, "Exceeds remaining allocation");

        // State is committed before external TRC-20 token transfer.
        releaseScheduledAt = 0;
        scheduledAmount = 0;
        releasedAmount += amount;
        released = releasedAmount == allocation;
        nextReleaseAt = _clock() + RELEASE_INTERVAL;
        token.safeTransfer(beneficiary, amount);
        emit ReserveReleased(beneficiary, trancheNonce, amount, releasedAmount);
    }
}
