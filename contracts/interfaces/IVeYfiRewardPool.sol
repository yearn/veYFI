// SPDX-License-Identifier: MIT
pragma solidity 0.8.12;

interface IVeYfiRewardPool {
    function queueNewRewards(uint256) external returns (bool);
}
