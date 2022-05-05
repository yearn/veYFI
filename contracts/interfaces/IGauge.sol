// SPDX-License-Identifier: MIT
pragma solidity 0.8.13;
import "./IBaseGauge.sol";

interface IGauge is IBaseGauge {
    function initialize(
        address _stakingToken,
        address _rewardToken,
        address _owner,
        address _rewardManager,
        address _ve,
        address _veYfiRewardPool
    ) external;

    function totalSupply() external view returns (uint256);

    function balanceOf(address _account) external view returns (uint256);

    function boostedBalanceOf(address _account) external view returns (uint256);
}
