// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;

/// @notice 2-of-3 approval gate used only in MOJ1's isolated TVM pilot.
/// @dev Production owners must be independently secured; no owner recovery is implemented.
contract MojPilotGovernance {
    address[3] public owners;
    uint256 public nonce;
    mapping(bytes32 => uint256) public approvals;
    mapping(bytes32 => mapping(address => bool)) public hasApproved;

    event Approval(bytes32 indexed operation, address indexed owner);
    event Execution(bytes32 indexed operation, address indexed target);

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
        require(approvals[operation] >= 2, "Two approvals required");
        ++nonce; // One execution per nonce, even if an external contract calls back.
        (bool ok, bytes memory response) = target.call(data);
        if (!ok) {
            assembly { revert(add(response, 32), mload(response)) }
        }
        emit Execution(operation, target);
        return response;
    }
}
