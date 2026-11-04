// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

/// @title MOJ7
/// @notice Fixed-supply TRC-20-compatible token for TRON.
/// @dev Constructor beneficiary is explicit so a relayer/deployer cannot accidentally
///      receive the entire initial supply. No owner, mint, burn, blacklist, pause,
///      external call, or upgrade mechanism.
contract MOJ7 {
    string public constant name = "MOJ7";
    string public constant symbol = "MOJ7";
    uint8 public constant decimals = 6;
    uint256 public constant totalSupply = 1_000_000_000_000 * 1_000_000;

    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);

    /// @param initialHolder The address that receives all 1,000,000,000,000 MOJ7.
    constructor(address initialHolder) {
        require(initialHolder != address(0), "Zero initial holder");
        balanceOf[initialHolder] = totalSupply;
        emit Transfer(address(0), initialHolder, totalSupply);
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        _transfer(msg.sender, to, amount);
        return true;
    }

    /// @dev Must reset a nonzero allowance to zero before assigning a new nonzero value.
    function approve(address spender, uint256 amount) external returns (bool) {
        require(spender != address(0), "Zero spender");
        require(amount == 0 || allowance[msg.sender][spender] == 0, "Reset allowance first");
        allowance[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        uint256 permitted = allowance[from][msg.sender];
        require(permitted >= amount, "Insufficient allowance");
        if (permitted != type(uint256).max) {
            allowance[from][msg.sender] = permitted - amount;
            emit Approval(from, msg.sender, allowance[from][msg.sender]);
        }
        _transfer(from, to, amount);
        return true;
    }

    function _transfer(address from, address to, uint256 amount) internal {
        require(from != address(0), "Zero sender");
        require(to != address(0), "Zero recipient");
        uint256 available = balanceOf[from];
        require(available >= amount, "Insufficient balance");
        balanceOf[from] = available - amount;
        balanceOf[to] += amount;
        emit Transfer(from, to, amount);
    }
}
