// SPDX-License-Identifier: MIT
pragma solidity 0.8.11;

interface IGauge {
    function initialize(
        address stakingToken_,
        address rewardToken_,
        address gov,
        address rewardManager_,
        address ve_,
        address veYfiRewardPool_
    ) external;

    function totalSupply() external view returns (uint256);

    function balanceOf(address account) external view returns (uint256);

    function boostedBalanceOf(address account) external view returns (uint256);
}
