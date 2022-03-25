// SPDX-License-Identifier: MIT
pragma solidity 0.8.13;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";
import "./interfaces/IVotingEscrow.sol";
import "./BaseGauge.sol";

/** @title VeYfiRewards
    @notice Gauge like contract that simulate veYFI stake.
 */

contract VeYfiRewards is BaseGauge {
    using SafeERC20 for IERC20;

    address public veToken;
    event UpdatedVeToken(address ve);

    constructor(
        address _veToken,
        address _rewardToken,
        address _owner
    ) {
        __initialize(_rewardToken, _owner);
        require(address(_veToken) != address(0x0), "_veToken 0x0 address");
        veToken = _veToken;
    }

    function setVe(address _veToken) external onlyOwner {
        require(address(_veToken) != address(0x0), "_veToken 0x0 address");
        veToken = _veToken;
        emit UpdatedVeToken(_veToken);
    }

    function _updateReward(address account) internal override {
        rewardPerTokenStored = _rewardPerToken();
        lastUpdateTime = lastTimeRewardApplicable();

        if (account != address(0)) {
            rewards[account] = _earnedReward(account);
            userRewardPerTokenPaid[account] = rewardPerTokenStored;
            emit UpdatedRewards(
                account,
                rewardPerTokenStored,
                lastUpdateTime,
                rewards[account],
                userRewardPerTokenPaid[account]
            );
        }
    }

    function _rewardPerToken() internal view override returns (uint256) {
        uint256 supply = IVotingEscrow(veToken).totalSupply();
        if (supply == 0) {
            return rewardPerTokenStored;
        }
        return
            rewardPerTokenStored +
            (((lastTimeRewardApplicable() - lastUpdateTime) *
                rewardRate *
                1e18) / supply);
    }

    function _earnedReward(address account) internal view returns (uint256) {
        return
            (IVotingEscrow(veToken).balanceOf(account) *
                (_rewardPerToken() - userRewardPerTokenPaid[account])) /
            1e18 +
            rewards[account];
    }

    function _newEarning(address account)
        internal
        view
        override
        returns (uint256)
    {
        return _earnedReward(account);
    }

    /** @notice use to update rewards on veYFI balance changes.
        @dev called by veYFI
     *  @return true
     */
    function rewardCheckpoint(address _account)
        external
        updateReward(_account)
        returns (bool)
    {
        require(msg.sender == address(veToken), "!authorized");

        return true;
    }

    /**
     * @notice
     *  Get rewards for an account
     * @dev rewards are transfer to _account
     * @param account to claim rewards for
     * @return true
     */
    function getRewardFor(address account) external returns (bool) {
        _getReward(account, false);
        return true;
    }

    /**
     * @notice
     *  Get rewards
     * @param _lock should it lock rewards into veYFI
     * @return true
     */
    function getReward(bool _lock) external returns (bool) {
        _getReward(msg.sender, _lock);
        return true;
    }

    /**
     * @notice
     *  Get rewards
     * @return true
     */
    function getReward() external returns (bool) {
        _getReward(msg.sender, false);
        return true;
    }

    function _getReward(address _account, bool _lock)
        internal
        updateReward(_account)
    {
        uint256 reward = rewards[_account];
        rewards[_account] = 0;
        if (reward == 0) {
            return;
        }

        if (_lock) {
            rewardToken.approve(address(veToken), reward);
            IVotingEscrow(veToken).deposit_for(msg.sender, reward);
        } else {
            SafeERC20.safeTransfer(rewardToken, _account, reward);
        }

        emit RewardPaid(_account, reward);
    }

    function _notProtectedTokens(address _token)
        internal
        view
        override
        returns (bool)
    {
        return
            _token != address(rewardToken) ||
            IVotingEscrow(veToken).migration();
    }
}
