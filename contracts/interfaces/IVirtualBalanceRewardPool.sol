// SPDX-License-Identifier: MIT
pragma solidity 0.8.11;
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

interface IVirtualBalanceRewardPool {
    function deposit(address, uint256) external returns (bool);

    function withdraw(address, uint256) external returns (bool);

    function getReward(address) external returns (bool);

    function queueNewRewards(uint256) external returns (bool);

    function rewardToken() external view returns (IERC20);

    function earned(address account) external view returns (uint256);

    function initialize(
        address deposit_,
        address reward_,
        address op_
    ) external;
}
