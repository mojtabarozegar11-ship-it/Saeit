// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;

/// @notice Candidate 2-of-3 TRON governance with delayed execution and signer rotation.
/// @dev Not a deployed or independently audited production multisig. No recovery is
///      possible if fewer than two independent owner keys remain available.
contract MojGovernanceGuarded {
    uint256 public constant OPERATION_DELAY = 48 hours;
    uint256 public constant OWNER_CHANGE_DELAY = 7 days;

    struct Operation {
        uint8 approvals;
        uint64 executableAt;
    }

    address[3] public owners;
    uint256 public nonce;
    mapping(bytes32 => Operation) public operations;
    mapping(bytes32 => mapping(address => bool)) public hasApproved;

    event Approved(bytes32 indexed operation, address indexed owner, uint256 approvals);
    event Scheduled(bytes32 indexed operation, uint256 executableAt);
    event Executed(bytes32 indexed operation, address indexed target, uint256 nonce);
    event OwnerReplaced(uint256 indexed slot, address indexed previousOwner, address indexed newOwner);
    event NonceCancelled(uint256 indexed nonce);

    constructor(address[3] memory initialOwners) {
        for (uint256 i; i < initialOwners.length; ++i) {
            require(initialOwners[i] != address(0), "Zero owner");
            for (uint256 j; j < i; ++j) {
                require(initialOwners[i] != initialOwners[j], "Duplicate owner");
            }
            owners[i] = initialOwners[i];
        }
    }

    modifier onlyOwner() {
        require(_isOwner(msg.sender), "Owner only");
        _;
    }

    modifier onlySelf() {
        require(msg.sender == address(this), "Governance call required");
        _;
    }

    function _clock() internal view virtual returns (uint256) {
        return block.timestamp;
    }

    function _isOwner(address account) internal view returns (bool) {
        return account == owners[0] || account == owners[1] || account == owners[2];
    }

    function operationHash(address target, bytes calldata data, uint256 operationNonce)
        public view returns (bytes32)
    {
        return keccak256(abi.encode(address(this), block.chainid, target, keccak256(data), operationNonce));
    }

    function approve(address target, bytes calldata data, uint256 operationNonce) external onlyOwner {
        require(target != address(0) && target.code.length > 0, "Contract target required");
        require(data.length >= 4, "Function selector required");
        require(operationNonce == nonce, "Invalid nonce");

        bytes32 digest = operationHash(target, data, operationNonce);
        require(!hasApproved[digest][msg.sender], "Duplicate approval");
        Operation storage operation = operations[digest];
        require(operation.approvals < 3, "All owners approved");
        hasApproved[digest][msg.sender] = true;
        ++operation.approvals;
        emit Approved(digest, msg.sender, operation.approvals);

        if (operation.approvals == 2) {
            uint256 delay = target == address(this) ? OWNER_CHANGE_DELAY : OPERATION_DELAY;
            uint256 executableAt = _clock() + delay;
            require(executableAt <= type(uint64).max, "Timestamp overflow");
            operation.executableAt = uint64(executableAt);
            emit Scheduled(digest, executableAt);
        }
    }

    function execute(address target, bytes calldata data, uint256 operationNonce)
        external onlyOwner returns (bytes memory)
    {
        require(target != address(0) && target.code.length > 0, "Contract target required");
        require(data.length >= 4, "Function selector required");
        require(operationNonce == nonce, "Invalid nonce");
        bytes32 digest = operationHash(target, data, operationNonce);
        Operation storage operation = operations[digest];
        require(operation.approvals >= 2 && operation.executableAt != 0, "Not scheduled");
        require(_clock() >= operation.executableAt, "Timelock active");

        ++nonce; // Prevent replay and reentrancy before external execution.
        (bool ok, bytes memory result) = target.call(data);
        if (!ok) {
            assembly { revert(add(result, 32), mload(result)) }
        }
        emit Executed(digest, target, operationNonce);
        return result;
    }

    /// @notice Change one signer through a delayed 2-of-3 call to this contract.
    function replaceOwner(uint256 slot, address replacement) external onlySelf {
        require(slot < owners.length, "Invalid slot");
        require(replacement != address(0), "Zero owner");
        for (uint256 i; i < owners.length; ++i) {
            if (i != slot) require(replacement != owners[i], "Duplicate owner");
        }
        address previousOwner = owners[slot];
        require(replacement != previousOwner, "Owner unchanged");
        owners[slot] = replacement;
        emit OwnerReplaced(slot, previousOwner, replacement);
    }

    /// @notice Advance the nonce without calling an external target, via delayed 2-of-3 approval.
    function cancelCurrentNonce() external onlySelf {
        emit NonceCancelled(nonce - 1);
    }
}
