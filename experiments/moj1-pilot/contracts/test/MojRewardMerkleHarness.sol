// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;

import {Hashes} from "@openzeppelin/tron-contracts/utils/cryptography/Hashes.sol";

/// @notice Test-only Merkle node oracle for disposable local TVM tests; not a production dependency.
contract MojRewardMerkleHarness {
    function pair(bytes32 a, bytes32 b) external pure returns (bytes32) {
        return Hashes.commutativeKeccak256(a, b);
    }
}
