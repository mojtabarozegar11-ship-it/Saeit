// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;

/// @notice 2-of-3 approval gate used only in MOJ1's isolated TVM pilot.
/// @dev Pilot-only. Signer rotation needs a 2-of-3 self-call. There is no 2-key-loss recovery.
contract MojPilotGovernance {
    address[3] public owners;
    uint256 public nonce;
    mapping(bytes32 => uint256) public approvals;
    mapping(bytes32 => mapping(address => bool)) public hasApproved;

    event Approval(bytes32 indexed operation, address indexed owner);
    event Execution(bytes32 indexed operation, address indexed target);
    event OwnerRotated(uint8 indexed index, address indexed previousOwner, address indexed newOwner);

    constructor(address[3] memory initialOwners) {
        for (uint256 i = 0; i < 3; ++i) {
            require(initialOwners[i] != address(0), "Invalid owner");
            for (uint256 j = 0; j < i; ++j) {
                require(initialOwners[i] != initialOwners[j], "Duplicate owner");
            }
            owners[i] = initialOwners[i];
        }
    }

    modifier onlyOwner() {
        require(
            msg.sender == owners[0] || msg.sender == owners[1] || msg.sender == owners[2],
            "Owner only"
        );
        _;
    }

    /// @notice Called only by this governance contract after two current owners approved a self-call.
    /// @dev A lost owner can be rotated while two other keys remain. Never introduces a 1-of-3 backdoor.
    function replaceOwner(uint8 index, address newOwner) external {
        require(msg.sender == address(this), "Self-call only");
        require(index < 3, "Invalid owner index");
        require(newOwner != address(0), "Invalid new owner");
        for (uint256 i = 0; i < 3; ++i) {
            require(owners[i] != newOwner, "Duplicate owner");
        }
        address previous = owners[index];
        owners[index] = newOwner;
        emit OwnerRotated(index, previous, newOwner);
    }

    /// @notice Counts live owners only; old approvals by rotated-out owners do not count.
    function currentApprovalCount(bytes32 operation) public view returns (uint256 count) {
        for (uint256 i = 0; i < 3; ++i) {
            if (hasApproved[operation][owners[i]]) ++count;
        }
    }

    function operationHash(address target, bytes calldata data, uint256 operationNonce)
        public view returns (bytes32)
    {
        return keccak256(abi.encode(address(this), block.chainid, target, keccak256(data), operationNonce));
    }

    function approve(address target, bytes calldata data, uint256 operationNonce)
        external onlyOwner
    {
        require(target != address(0) && target.code.length > 0, "Contract target required");
        require(operationNonce == nonce, "Invalid nonce");
        bytes32 operation = operationHash(target, data, operationNonce);
        require(!hasApproved[operation][msg.sender], "Already approved");
        hasApproved[operation][msg.sender] = true;
        approvals[operation] += 1;
        emit Approval(operation, msg.sender);
    }

    function execute(address target, bytes calldata data, uint256 operationNonce)
        external onlyOwner returns (bytes memory)
    {
        require(target != address(0) && target.code.length > 0, "Contract target required");
        require(operationNonce == nonce, "Invalid nonce");
        bytes32 operation = operationHash(target, data, operationNonce);
        require(currentApprovalCount(operation) >= 2, "Two current approvals required");
        ++nonce; // One execution per nonce, even if an external contract calls back.
        (bool ok, bytes memory response) = target.call(data);
        if (!ok) {
            assembly { revert(add(response, 32), mload(response)) }
        }
        emit Execution(operation, target);
        return response;
    }
}
