// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;

import {ITRC20} from "@openzeppelin/tron-contracts/token/TRC20/ITRC20.sol";
import {SafeTRC20} from "@openzeppelin/tron-contracts/token/TRC20/utils/SafeTRC20.sol";

/// @notice Immutable, pre-funded reward escrow using a domain-bound Merkle-sum tree.
/// @dev Unmerged candidate, not independently audited and not approved for real rewards.
///      Unclaimed verified entitlements never expire or become treasury sweepable.
///      Root composition alone cannot prove real-world eligibility or global uniqueness.
contract MojRewardClaimsSumGuarded {
    using SafeTRC20 for ITRC20;

    uint256 public constant MAX_PROOF_DEPTH = 32;
    uint256 public constant MAX_CLAIMS_PER_EPOCH = 1_000_000;

    struct Epoch {
        bytes32 root;
        bytes32 manifestDigest;
        uint256 budget;
        uint256 leafCount;
        uint256 claimed;
        uint256 claimCount;
        bool published;
    }

    struct Node {
        bytes32 hash;
        uint256 sum;
        uint256 count;
    }

    /// @dev Single calldata object avoids TRON Solidity's narrow stack limits.
    struct ClaimProof {
        uint256 epoch;
        uint256 index;
        address account;
        uint256 amount;
        bytes32[] siblingHashes;
        uint256[] siblingSums;
        uint256[] siblingCounts;
    }

    ITRC20 public immutable token;
    address public immutable governance;
    uint256 public outstandingCommitments;
    mapping(uint256 => Epoch) public epochs;
    mapping(uint256 => mapping(uint256 => bool)) public claimedIndex;
    mapping(uint256 => mapping(address => bool)) public claimedAccount;

    event EpochPublished(
        uint256 indexed epoch, bytes32 indexed root, bytes32 indexed manifestDigest,
        uint256 budget, uint256 leafCount
    );
    event RewardClaimed(uint256 indexed epoch, uint256 indexed index, address indexed beneficiary, uint256 amount);
    event EpochFullyClaimed(uint256 indexed epoch, uint256 totalPaid);
    event EpochManifestMismatch(uint256 indexed epoch, uint256 paidClaims, uint256 declaredLeaves);

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

    function availableToCommit() public view returns (uint256) {
        uint256 balance = token.balanceOf(address(this));
        return balance > outstandingCommitments ? balance - outstandingCommitments : 0;
    }

    /// @notice Read the effective TVM chain ID used in the leaf's domain separator.
    function chainId() external view returns (uint256) {
        return block.chainid;
    }

    /// @notice Leaf binds the exact beneficiary and amount to this chain, contract and epoch.
    /// @dev Different prefix bytes distinguish leaves from internal tree nodes.
    function claimLeaf(uint256 epoch, uint256 index, address account, uint256 amount)
        public view returns (bytes32)
    {
        return keccak256(abi.encode(bytes1(0x00), block.chainid, address(this), epoch, index, account, amount));
    }

    /// @notice Order by hash; commit to each child hash, sum and count.
    /// @dev Every genuine leaf has a positive amount and count exactly one.
    function combineNodes(
        bytes32 leftHash, uint256 leftSum, uint256 leftCount,
        bytes32 rightHash, uint256 rightSum, uint256 rightCount
    ) public pure returns (bytes32 parentHash, uint256 parentSum, uint256 parentCount) {
        Node memory result = _combine(
            Node(leftHash, leftSum, leftCount), Node(rightHash, rightSum, rightCount)
        );
        return (result.hash, result.sum, result.count);
    }

    function _combine(Node memory a, Node memory b) internal pure returns (Node memory result) {
        require(a.hash != bytes32(0) && b.hash != bytes32(0), "Zero node");
        require(a.sum > 0 && b.sum > 0 && a.count > 0 && b.count > 0, "Empty node");
        result.sum = a.sum + b.sum;
        result.count = a.count + b.count;
        if (uint256(a.hash) <= uint256(b.hash)) {
            result.hash = keccak256(abi.encode(
                bytes1(0x01), a.hash, a.sum, a.count, b.hash, b.sum, b.count
            ));
        } else {
            result.hash = keccak256(abi.encode(
                bytes1(0x01), b.hash, b.sum, b.count, a.hash, a.sum, a.count
            ));
        }
    }

    /// @notice The approved tree root must cryptographically commit to its budget and leaf count.
    /// @dev A verified off-chain source ledger and independent approval are still mandatory.
    function publishEpoch(
        uint256 epoch, bytes32 root, uint256 budget, uint256 leafCount, bytes32 manifestDigest
    ) external onlyGovernance {
        require(!epochs[epoch].published, "Epoch already used");
        require(root != bytes32(0) && manifestDigest != bytes32(0), "Missing commitment");
        require(budget > 0 && leafCount > 0 && leafCount <= MAX_CLAIMS_PER_EPOCH, "Invalid liability");
        require(budget <= availableToCommit(), "Unfunded liability");
        Epoch storage record = epochs[epoch];
        record.root = root;
        record.manifestDigest = manifestDigest;
        record.budget = budget;
        record.leafCount = leafCount;
        record.published = true;
        outstandingCommitments += budget;
        emit EpochPublished(epoch, root, manifestDigest, budget, leafCount);
    }

    function verifyClaim(ClaimProof calldata proof) public view returns (bool) {
        Epoch storage record = epochs[proof.epoch];
        if (!record.published || proof.account == address(0) || proof.amount == 0) return false;
        uint256 length = proof.siblingHashes.length;
        if (length > MAX_PROOF_DEPTH || length != proof.siblingSums.length || length != proof.siblingCounts.length) return false;

        Node memory cursor = Node(claimLeaf(proof.epoch, proof.index, proof.account, proof.amount), proof.amount, 1);
        for (uint256 i; i < length; ++i) {
            cursor = _combine(
                cursor, Node(proof.siblingHashes[i], proof.siblingSums[i], proof.siblingCounts[i])
            );
        }
        return cursor.hash == record.root && cursor.sum == record.budget && cursor.count == record.leafCount;
    }

    /// @notice Anyone may relay a valid claim. Payment always goes to the proven account.
    function claim(ClaimProof calldata proof) external {
        Epoch storage record = epochs[proof.epoch];
        require(record.published && proof.account != address(0) && proof.amount > 0, "Invalid claim");
        require(!claimedIndex[proof.epoch][proof.index] && !claimedAccount[proof.epoch][proof.account], "Already claimed");
        require(proof.amount <= record.budget - record.claimed, "Budget exceeded");
        require(verifyClaim(proof), "Invalid sum proof");

        // Commit accounting and replay protection before the external token call.
        claimedIndex[proof.epoch][proof.index] = true;
        claimedAccount[proof.epoch][proof.account] = true;
        record.claimed += proof.amount;
        ++record.claimCount;
        require(record.claimCount <= record.leafCount, "Claim count exceeded");
        outstandingCommitments -= proof.amount;
        token.safeTransfer(proof.account, proof.amount);
        emit RewardClaimed(proof.epoch, proof.index, proof.account, proof.amount);
        if (record.claimed == record.budget) {
            // Never deny a valid final payout because the publisher lied about count.
            if (record.claimCount == record.leafCount) {
                emit EpochFullyClaimed(proof.epoch, record.claimed);
            } else {
                emit EpochManifestMismatch(proof.epoch, record.claimCount, record.leafCount);
            }
        }
    }
}
