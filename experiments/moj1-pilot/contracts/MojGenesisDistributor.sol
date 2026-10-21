// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;

import {ITRC20} from "@openzeppelin/tron-contracts/token/TRC20/ITRC20.sol";
import {SafeTRC20} from "@openzeppelin/tron-contracts/token/TRC20/utils/SafeTRC20.sol";
import {MojVestingVault} from "./MojVestingVault.sol";
import {MojApprovalReserve} from "./MojApprovalReserve.sol";

/// @notice Non-upgradeable genesis escrow for six owner-approved allocation PERCENTAGES.
/// @dev Created exclusively by the MOJ1 constructor: all initial supply is held here until
///      all six independently deployed, policy-conforming vaults can be funded atomically.
///      The governance address must be a separately approved multisig before real deployment.
contract MojGenesisDistributor {
    using SafeTRC20 for ITRC20;

    uint256 public constant GENESIS_SUPPLY = 100_000_000_000 * 10 ** 18;
    ITRC20 public immutable token;
    address public immutable governance;
    bool public distributed;
    address[6] public vaults;

    event BucketFunded(uint8 indexed bucket, address indexed vault, uint256 amount);
    event GenesisDistributed(uint256 timestamp, uint256 total);

    constructor(address governanceAddress) {
        require(governanceAddress != address(0), "Invalid governance");
        // The deploying contract is MOJ1, so there is no token-address circular dependency.
        token = ITRC20(msg.sender);
        governance = governanceAddress;
    }

    function bucketAmount(uint256 index) public pure returns (uint256) {
        if (index == 0) return 35_000_000_000 * 10 ** 18; // player rewards and ecosystem
        if (index == 1) return 20_000_000_000 * 10 ** 18; // product and security development
        if (index == 2) return 15_000_000_000 * 10 ** 18; // future liquidity (approval reserve)
        if (index == 3) return 10_000_000_000 * 10 ** 18; // team (cliff + vesting)
        if (index == 4) return 15_000_000_000 * 10 ** 18; // partners and creators
        if (index == 5) return  5_000_000_000 * 10 ** 18; // contingency (approval reserve)
        revert("Invalid bucket");
    }

    function distribute(address[6] calldata destinations, uint256 startTimestamp) external {
        require(msg.sender == governance, "Governance only");
        require(!distributed, "Already distributed");
        require(startTimestamp >= block.timestamp, "Retroactive start prohibited");
        require(token.totalSupply() == GENESIS_SUPPLY, "Wrong supply");
        require(token.balanceOf(address(this)) == GENESIS_SUPPLY, "Escrow not fully funded");

        for (uint256 i; i < destinations.length; ++i) {
            require(destinations[i].code.length > 0, "Vault must be contract");
            for (uint256 j; j < i; ++j) {
                require(destinations[i] != destinations[j], "Duplicate vault");
            }

            if (i == 2 || i == 5) {
                MojApprovalReserve reserve = MojApprovalReserve(destinations[i]);
                require(address(reserve.token()) == address(token), "Wrong reserve token");
                require(reserve.allocation() == bucketAmount(i), "Wrong reserve allocation");
                require(reserve.beneficiary() != address(0), "Missing beneficiary");
                require(reserve.releaseController() == governance, "Wrong reserve controller");
                uint256 cap = i == 2 ? 1_000_000_000 * 10 ** 18 : 250_000_000 * 10 ** 18;
                require(reserve.trancheCap() == cap, "Wrong tranche cap");
                require(reserve.RELEASE_DELAY() == 30 days && reserve.RELEASE_INTERVAL() == 90 days, "Wrong tranche timing");
                require(!reserve.released() && reserve.releaseScheduledAt() == 0 && reserve.scheduledAmount() == 0, "Reserve scheduled");
                require(reserve.releasedAmount() == 0 && reserve.nextReleaseAt() == 0, "Reserve already used");
            } else {
                MojVestingVault vesting = MojVestingVault(destinations[i]);
                require(address(vesting.token()) == address(token), "Wrong vesting token");
                require(vesting.allocation() == bucketAmount(i), "Wrong vesting allocation");
                require(vesting.beneficiary() != address(0), "Missing beneficiary");
                require(vesting.start() == startTimestamp, "Wrong vesting start");
                uint256 cliff = i == 3 ? 365 days : 0;
                uint256 duration = i == 0 ? 1825 days : i == 3 ? 1095 days : 1460 days;
                require(vesting.cliff() == cliff && vesting.duration() == duration, "Wrong vesting schedule");
                require(vesting.released() == 0, "Vesting already active");
            }
        }

        // Commit state before external transfers. Any failed transfer reverts the entire split.
        distributed = true;
        for (uint256 i; i < destinations.length; ++i) {
            vaults[i] = destinations[i];
            token.safeTransfer(destinations[i], bucketAmount(i));
            emit BucketFunded(uint8(i), destinations[i], bucketAmount(i));
        }
        require(token.balanceOf(address(this)) == 0, "Unallocated tokens");
        emit GenesisDistributed(block.timestamp, GENESIS_SUPPLY);
    }
}
