// SPDX-License-Identifier: MIT
pragma solidity 0.8.15;
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

interface IBaseGauge {
    function earned(address _account) external view returns (uint256);
}
