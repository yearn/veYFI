// SPDX-License-Identifier: MIT
pragma solidity 0.8.11;

interface IVeYfiRewardPool {
    function donate(uint256) external returns (bool);
}
