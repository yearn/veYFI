// SPDX-License-Identifier: MIT
pragma solidity 0.8.11;

interface IExtraReward {
    function initialize(address gauge_, address reward_) external;
}
