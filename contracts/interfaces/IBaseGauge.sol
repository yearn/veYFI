// SPDX-License-Identifier: MIT
pragma solidity 0.8.13;
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

interface IBaseGauge {
    function queueNewRewards(uint256) external returns (bool);

    function rewardToken() external view returns (IERC20);

    function earned(address account) external view returns (uint256);
}
