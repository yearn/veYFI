// SPDX-License-Identifier: MIT
pragma solidity 0.8.15;

interface IGaugeController {
    function claim() external returns (uint256, uint256, uint256);
}
