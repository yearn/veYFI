// SPDX-License-Identifier: MIT
pragma solidity 0.8.13;

import "./interfaces/IGauge.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";
import "./interfaces/IExtraReward.sol";
import "./BaseGauge.sol";

/** @title Extra Rewards for a Gauge
    @notice An ExtraReward is associated with a gauge and a token.
    Balances are managed by the associated Gauge. Gauge will
    @dev this contract is used behind multiple delegate proxies.
 */
contract ExtraReward is IExtraReward, BaseGauge {
    using SafeERC20 for IERC20;
    IGauge public gauge;

    event Initialized(
        address indexed _gauge,
        address indexed rewardToken,
        address indexed owner
    );

    /**
    @notice Initialize the contract after a clone.
    @param _gauge the associated Gauge address
    @param _rewardToken the reward token to be distributed
    @param _owner owner
    */
    function initialize(
        address _gauge,
        address _rewardToken,
        address _owner
    ) external initializer {
        __initialize(_rewardToken, _owner);
        require(address(_gauge) != address(0x0), "_gauge 0x0 address");
        gauge = IGauge(_gauge);
        rewardToken = IERC20(_rewardToken);
        emit Initialized(_gauge, _rewardToken, _owner);
    }

    function _updateReward(address account) internal override {
        rewardPerTokenStored = _rewardPerToken();
        lastUpdateTime = lastTimeRewardApplicable();
        if (account != address(0)) {
            uint256 newEarning = _newEarning(account);
            uint256 maxEarning = _maxEarning(account);

            rewards[account] += newEarning;

            // If rewards aren't boosted at max, loss rewards are queued to be redistributed to the gauge.
            queuedRewards += (maxEarning - newEarning);

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
        if (gauge.totalSupply() == 0) {
            return rewardPerTokenStored;
        }
        return
            rewardPerTokenStored +
            (((lastTimeRewardApplicable() - lastUpdateTime) *
                rewardRate *
                1e18) / gauge.totalSupply());
    }

    function _newEarning(address account)
        internal
        view
        override
        returns (uint256)
    {
        return
            (gauge.boostedBalanceOf(account) *
                (_rewardPerToken() - userRewardPerTokenPaid[account])) / 1e18;
    }

    function _maxEarning(address account) internal view returns (uint256) {
        return
            (gauge.balanceOf(account) *
                (_rewardPerToken() - userRewardPerTokenPaid[account])) / 1e18;
    }

    /** @notice update reward for an account
     *  @dev called by the underlying gauge
     *  @param _account to update
     *  @return true
     */
    function rewardCheckpoint(address _account)
        external
        override
        updateReward(_account)
        returns (bool)
    {
        require(msg.sender == address(gauge), "!authorized");
        return true;
    }

    /**
     * @notice
     *  Get rewards
     * @param _account claim extra rewards
     * @return true
     */
    function getRewardFor(address _account)
        public
        override
        updateReward(_account)
        returns (bool)
    {
        uint256 reward = rewards[_account];
        if (reward > 0) {
            rewards[_account] = 0;
            rewardToken.safeTransfer(_account, reward);
            emit RewardPaid(_account, reward);
        }
        return true;
    }

    function getReward() external override returns (bool) {
        getRewardFor(msg.sender);
        return true;
    }
}
