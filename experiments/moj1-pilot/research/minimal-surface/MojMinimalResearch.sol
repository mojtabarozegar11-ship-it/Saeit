// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;

import {TRC20} from "@openzeppelin/tron-contracts/token/TRC20/TRC20.sol";

/// @title MOJ1 Minimal Research Prototype - NOT the MOJ1 token.
/// @notice A comparison-only, isolated research example; never deploy or market.
/// @dev It deliberately omits six on-chain allocations, vesting, reserve delays,
///      reward claims and governed distribution. It is NOT equivalent to the
///      approved MOJ1 V2 design and must not bypass issue #853 release gates.
///      Use only a pinned independently audited OZ Tron package for review.
contract MojMinimalResearch is TRC20 {
    uint256 public constant FIXED_SUPPLY = 100_000_000_000 * 10 ** 18;
    address public immutable initialCustodian;

    /// @param custodian Research comparison recipient only. No real wallet
    ///        address, production key, or mainnet deployment is authorized.
    constructor(address custodian) TRC20("MOJ1 Research - Not for Release", "MOJ1R") {
        require(custodian != address(0), "Zero custodian");
        initialCustodian = custodian;
        _mint(custodian, FIXED_SUPPLY);
    }
}
