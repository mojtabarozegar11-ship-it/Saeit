// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;

import {ITRC20} from "@openzeppelin/tron-contracts/token/TRC20/ITRC20.sol";
import {SafeTRC20} from "@openzeppelin/tron-contracts/token/TRC20/utils/SafeTRC20.sol";
import {MerkleProof} from "@openzeppelin/tron-contracts/utils/cryptography/MerkleProof.sol";

/// @notice TESTNET PILOT ONLY. An escrow for rewards already vested and received.
/// @dev Governance publishes immutable per-epoch Merkle roots. Eligibility and Sybil checks
///      must happen OFF CHAIN before the root is created; this contract cannot prove identity.
///      No live MOJ1 funds or reward distribution is authorized by this experimental source.
contract MojRewardClaimsPilot {
    using SafeTRC20 for ITRC20;

    struct Epoch {
        bytes32 root;
        uint256 budget;
        uint256 claimed;
        bool published;
        bool cancelled;
    }

    ITRC20 public immutable token;
    address public immutable governance;
    uint256 public outstandingCommitments;

    mapping(uint256 => Epoch) public epochs;
    mapping(uint256 => mapping(uint256 => bool)) public claimedIndex;
    mapping(uint256 => mapping(address => bool)) public claimedAccount;

    event EpochPublished(uint256 indexed epoch, bytes32 indexed root, uint256 budget);
    event EpochCancelled(uint256 indexed epoch, uint256 releasedCommitment);
    event RewardClaimed(uint256 indexed epoch, uint256 indexed index, address indexed beneficiary, uint256 amount);

    constructor(address tokenAddress, address governanceAddress) {
        require(tokenAddress != address(0) && tokenAddress.code.length > 0, "Contract token required");
        require(governanceAddress != address(0) && governanceAddress.code.length > 0, "Contract governance required");
        token = ITRC20(tokenAddress);
        governance = governanceAddress;
    }

    modifier onlyGovernance() {
        require(msg.sender == governance, "Governance only");
        _;
    }

    /// @notice Uncommitted *already received* tokens, excluding outstanding epoch liabilities.
    function availableToCommit() public view returns (uint256) {
        uint256 current = token.balanceOf(address(this));
        return current > outstandingCommitments ? current - outstandingCommitments : 0;
    }

    /// @notice Domain-bound double-hashed leaf to prevent reuse across contracts/chains/epochs.
    /// @dev Build off-chain Merkle trees using sorted-pair Keccak nodes and this exact leaf.
    function claimLeaf(uint256 epoch, uint256 index, address account, uint256 amount)
        public view returns (bytes32)
    {
        bytes32 inner = keccak256(abi.encode(block.chainid, address(this), epoch, index, account, amount));
        return keccak256(abi.encodePacked(inner));
    }

    function publishEpoch(uint256 epoch, bytes32 root, uint256 budget) external onlyGovernance {
        Epoch storage record = epochs[epoch];
        require(!record.published, "Epoch already used");
        require(root != bytes32(0) && budget > 0, "Invalid epoch");
        require(budget <= availableToCommit(), "Unfunded epoch");
        record.root = root;
        record.budget = budget;
        record.published = true;
        outstandingCommitments += budget;
        emit EpochPublished(epoch, root, budget);
    }

    /// @notice Cancel only before the first successful claim; root and epoch ID stay consumed.
    function cancelEmptyEpoch(uint256 epoch) external onlyGovernance {
        Epoch storage record = epochs[epoch];
        require(record.published && !record.cancelled, "Inactive epoch");
        require(record.claimed == 0, "Claims already paid");
        record.cancelled = true;
        outstandingCommitments -= record.budget;
        emit EpochCancelled(epoch, record.budget);
    }

    /// @notice Anyone may submit a proof, but payout goes only to the proven beneficiary.
    function claim(uint256 epoch, uint256 index, address account, uint256 amount, bytes32[] calldata proof)
        external
    {
        Epoch storage record = epochs[epoch];
        require(record.published && !record.cancelled, "Inactive epoch");
        require(account != address(0) && amount > 0, "Invalid claim");
        require(!claimedIndex[epoch][index], "Index already claimed");
        require(!claimedAccount[epoch][account], "Account already claimed");
        require(amount <= record.budget - record.claimed, "Epoch budget exceeded");
        bytes32 leaf = claimLeaf(epoch, index, account, amount);
        require(MerkleProof.verifyCalldata(proof, record.root, leaf), "Invalid proof");

        claimedIndex[epoch][index] = true;
        claimedAccount[epoch][account] = true;
        record.claimed += amount;
        outstandingCommitments -= amount;
        token.safeTransfer(account, amount);
        emit RewardClaimed(epoch, index, account, amount);
    }
}
