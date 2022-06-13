// SPDX-License-Identifier: MIT
pragma solidity 0.8.13;

import "./interfaces/IGauge.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

interface IVeYFIRewards {
    function claim(address _addr, bool _lock) external returns (uint256);
}

interface IVeYFI {
    function deposit_for(address _addr, uint256 _amount) external;
}

/** @title  Zap
    @notice Used to claim multiple gauges rewards
 */
contract Zap {
    address immutable YFI;
    address immutable VE_YFI;
    address immutable VE_YFI_REWARDS;

    constructor(
        address _yfi,
        address _veYfi,
        address _veYFIRewards
    ) {
        YFI = _yfi;
        VE_YFI = _veYfi;
        VE_YFI_REWARDS = _veYFIRewards;
        IERC20(YFI).approve(VE_YFI, type(uint256).max);
    }

    /** 
        @notice Add a vault to the list of vaults that receives rewards.
        @param _gauges gauges to claim
        @param _lock should the rewards from the gauges be locked.
        @param _claimVeYfi should it claim veYfiRewards
    */
    function claim(
        address[] calldata _gauges,
        bool _lock,
        bool _claimVeYfi
    ) external {
        uint256 balance = IERC20(YFI).balanceOf(msg.sender);

        for (uint256 i = 0; i < _gauges.length; ++i) {
            IGauge(_gauges[i]).getRewardFor(msg.sender, false, true);
        }

        if (_claimVeYfi) {
            IVeYFIRewards(VE_YFI_REWARDS).claim(msg.sender, false);
        }

        if (_lock == false) {
            return;
        }

        uint256 balanceAfter = IERC20(YFI).balanceOf(msg.sender);
        uint256 diff = balanceAfter - balance;
        if (diff != 0) {
            IERC20(YFI).transferFrom(msg.sender, address(this), diff);
            IVeYFI(VE_YFI).deposit_for(msg.sender, diff);
        }
    }
}
