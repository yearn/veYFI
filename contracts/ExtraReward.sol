// SPDX-License-Identifier: MIT
pragma solidity 0.8.15;

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

    event Initialize(
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
        emit Initialize(_gauge, _rewardToken, _owner);
    }

    function _updateReward(address _account) internal override {
        rewardPerTokenStored = _rewardPerToken();
        lastUpdateTime = lastTimeRewardApplicable();
        if (_account != address(0)) {
            rewards[_account] += _newEarning(_account);

            userRewardPerTokenPaid[_account] = rewardPerTokenStored;
            emit UpdatedRewards(
                _account,
                rewardPerTokenStored,
                lastUpdateTime,
                rewards[_account],
                userRewardPerTokenPaid[_account]
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
                PRECISION_FACTOR) / gauge.totalSupply());
    }

    function _newEarning(address _account)
        internal
        view
        override
        returns (uint256)
    {
        return
            (gauge.balanceOf(_account) *
                (_rewardPerToken() - userRewardPerTokenPaid[_account])) /
            PRECISION_FACTOR;
    }

    /** @notice update reward for an account
     *  @dev called by the gauge holding vaults tokens
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
     * @param _account claim rewards on the behalf of an account.
     * @return true
     */
    function getRewardFor(address _account)
        public
        override
        updateReward(_account)
        returns (bool)
    {
        uint256 reward = rewards[_account];
        if (reward != 0) {
            rewards[_account] = 0;
            rewardToken.safeTransfer(_account, reward);
            emit RewardPaid(_account, reward);
        }
        return true;
    }

    /**
     * @notice
     *  Get rewards
     * @return true
     */
    function getReward() external override returns (bool) {
        getRewardFor(msg.sender);
        return true;
    }
}
