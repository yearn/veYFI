// SPDX-License-Identifier: MIT
pragma solidity 0.8.13;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract Token is ERC20 {
    constructor(string memory name) ERC20(name, name) {}

    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }
}
