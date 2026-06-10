// SPDX-License-Identifier: MIT
pragma solidity 0.8.15;
import "./IBaseGauge.sol";
import "./IERC4626.sol";

interface IGaugeV2 is IBaseGauge, IERC4626 {
    function initialize(address _stakingToken, address _owner, address _controller, bytes memory _data) external;

    function boostedBalanceOf(address _account) external view returns (uint256);

    function getReward(address _account) external returns (bool);
}
