// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;

import {ITRC20} from "@openzeppelin/tron-contracts/token/TRC20/ITRC20.sol";
import {SafeTRC20} from "@openzeppelin/tron-contracts/token/TRC20/utils/SafeTRC20.sol";
import {MojVestingVault} from "./MojVestingVault.sol";
import {MojApprovalReserve} from "./MojApprovalReserve.sol";

/// @notice Candidate V2: genesis vaults are constructed by this trusted factory,
///         not supplied as arbitrary addresses with forgeable view methods.
/// @dev NOT DEPLOYED, NOT INDEPENDENTLY AUDITED, NOT MAINNET APPROVED.
///      The six beneficiaries and T0 require separate independent owner review.
contract MojGenesisFactoryGuarded {
    using SafeTRC20 for ITRC20;

    uint256 public constant GENESIS_SUPPLY = 100_000_000_000 * 10 ** 18;
    ITRC20 public immutable token;
    address public immutable governance;
    bool public distributed;
    address[6] public vaults;

    event VaultCreated(uint8 indexed bucket, address indexed vault, address indexed beneficiary, uint256 amount);
    event GenesisDistributed(uint256 timestamp, uint256 total);

    constructor(address governanceAddress) {
        require(governanceAddress != address(0), "Invalid governance");
        token = ITRC20(msg.sender);
        governance = governanceAddress;
    }

    function bucketAmount(uint256 index) public pure returns (uint256) {
        if (index == 0) return 35_000_000_000 * 10 ** 18;
        if (index == 1) return 20_000_000_000 * 10 ** 18;
        if (index == 2) return 15_000_000_000 * 10 ** 18;
        if (index == 3) return 10_000_000_000 * 10 ** 18;
        if (index == 4) return 15_000_000_000 * 10 ** 18;
        if (index == 5) return  5_000_000_000 * 10 ** 18;
        revert("Invalid bucket");
    }

    /// @notice A governance-authorized, one-shot, atomic six-vault split.
    ///         The provided addresses are BENEFICIARIES, never predeployed vault code.
    /// @dev Deploying six contracts within one tx can be energy-expensive on TRON.
    ///      Measure TVM/Shasta fees before considering this candidate for real funds.
    function distribute(address[6] calldata beneficiaries, uint256 startTimestamp) external {
        require(msg.sender == governance, "Governance only");
        require(!distributed, "Already distributed");
        require(startTimestamp >= block.timestamp, "Retroactive start prohibited");
        require(token.totalSupply() == GENESIS_SUPPLY, "Wrong supply");
        require(token.balanceOf(address(this)) == GENESIS_SUPPLY, "Escrow not fully funded");

        for (uint256 i; i < beneficiaries.length; ++i) {
            require(beneficiaries[i] != address(0), "Missing beneficiary");
            for (uint256 j; j < i; ++j) {
                require(beneficiaries[i] != beneficiaries[j], "Duplicate beneficiary");
            }
        }

        distributed = true;
        for (uint256 i; i < beneficiaries.length; ++i) {
            uint256 amount = bucketAmount(i);
            address vault;
            if (i == 2 || i == 5) {
                vault = address(new MojApprovalReserve(
                    address(token), beneficiaries[i], governance, amount
                ));
            } else {
                uint256 cliffSeconds = i == 3 ? 365 days : 0;
                uint256 durationSeconds = i == 0 ? 1825 days : i == 3 ? 1095 days : 1460 days;
                vault = address(new MojVestingVault(
                    address(token), beneficiaries[i], amount, startTimestamp, cliffSeconds, durationSeconds
                ));
            }
            vaults[i] = vault;
            token.safeTransfer(vault, amount);
            emit VaultCreated(uint8(i), vault, beneficiaries[i], amount);
        }
        require(token.balanceOf(address(this)) == 0, "Unallocated tokens");
        emit GenesisDistributed(block.timestamp, GENESIS_SUPPLY);
    }
}
