// SPDX-License-Identifier: MIT
pragma solidity 0.8.13;
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "./IBaseGauge.sol";

interface IExtraReward is IBaseGauge {
    function initialize(
        address gauge_,
        address reward_,
        address owner_
    ) external;

    function rewardCheckpoint(address _account) external returns (bool);

    function getRewardFor(address) external returns (bool);

    function getReward() external returns (bool);
}
