// SPDX-License-Identifier: MIT
pragma solidity 0.8.14;
import "./IBaseGauge.sol";
import "@openzeppelin-upgradeable/contracts/token/ERC20/IERC20Upgradeable.sol";

interface IGauge is IBaseGauge, IERC20Upgradeable {
    function initialize(
        address _stakingToken,
        address _rewardToken,
        address _owner,
        address _rewardManager,
        address _ve,
        address _veYfiRewardPool
    ) external;

    function boostedBalanceOf(address _account) external view returns (uint256);

    function getRewardFor(
        address _account,
        bool _lock,
        bool _claimExtras
    ) external returns (bool);
}
