// SPDX-License-Identifier: MIT
pragma solidity 0.8.12;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract VaultMock is ERC20 {
    constructor() ERC20("Yearn vault", "yvault") {}

    function mint(address to, uint256 amount) public {
        _mint(to, amount);
    }
}
