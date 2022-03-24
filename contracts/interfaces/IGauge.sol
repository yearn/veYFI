// SPDX-License-Identifier: MIT
pragma solidity 0.8.13;
import "./IBaseGauge.sol";

interface IGauge is IBaseGauge {
    function initialize(
        address stakingToken_,
        address rewardToken_,
        address owner,
        address rewardManager_,
        address ve_,
        address veYfiRewardPool_
    ) external;

    function totalSupply() external view returns (uint256);

    function balanceOf(address account) external view returns (uint256);

    function boostedBalanceOf(address account) external view returns (uint256);
}
