// SPDX-License-Identifier: MIT
pragma solidity 0.8.13;
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

contract NextVe {
    address public token;

    constructor(address _token) {
        token = _token;
    }

    function migrateLock(address, uint256 amount) external {
        SafeERC20.safeTransferFrom(
            IERC20(token),
            msg.sender,
            address(this),
            amount
        );
    }
}
