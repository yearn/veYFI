// SPDX-License-Identifier: MIT
pragma solidity 0.8.11;

import "./interfaces/IGauge.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";
import "./interfaces/IExtraReward.sol";

/** @title Extra Rewards for a Gauge
    @notice An ExtraReward is associated with a gauge and a token.
    Balances are managed by the associated Gauge. Gauge will 
    @dev this contract is used behind multiple delegate proxies.
 */
contract ExtraReward is IExtraReward {
    using SafeERC20 for IERC20;

    IERC20 public rewardToken;
    uint256 public constant DURATION = 7 days;
    IGauge public gauge;

    uint256 public periodFinish = 0;
    uint256 public rewardRate = 0;
    uint256 public lastUpdateTime;
    uint256 public rewardPerTokenStored;
    uint256 public queuedRewards = 0;
    uint256 public currentRewards = 0;
    uint256 public historicalRewards = 0;
    uint256 public constant NEW_REWARD_RATIO = 830;
    mapping(address => uint256) public userRewardPerTokenPaid;
    mapping(address => uint256) public rewards;

    event RewardAdded(uint256 reward);
    event Deposited(address indexed user, uint256 amount);
    event Withdrawn(address indexed user, uint256 amount);
    event RewardPaid(address indexed user, uint256 reward);

    /**
    @notice Initialize the contract after a clone.
    @param gauge_ the associated Gauge address
    @param reward_ the reward token to be ditributed
    */
    function initialize(address gauge_, address reward_) public {
        assert(address(gauge) == address(0x0));
        gauge = IGauge(gauge_);
        rewardToken = IERC20(reward_);
    }

    /**
    @notice The Gauge total supply
    @return total supply
    */
    function totalSupply() public view returns (uint256) {
        return gauge.totalSupply();
    }

    /**
    @notice The Gauge balance of an account
    @return balance of an account
    */
    function balanceOf(address account) public view returns (uint256) {
        return gauge.balanceOf(account);
    }

    /**
    @notice The Gauge boosted balance of an account
    @return boosted balance of an account
    */
    function boostedBalanceOf(address account) public view returns (uint256) {
        return gauge.boostedBalanceOf(account);
    }

    modifier updateReward(address account) {
        _updateReward(account);
        _;
    }

    function _updateReward(address account) internal {
        rewardPerTokenStored = _rewardPerToken();
        lastUpdateTime = lastTimeRewardApplicable();
        if (account != address(0)) {
            uint256 newEarning = _newEarning(account);
            uint256 maxEarming = _maxEarning(account);

            rewards[account] += newEarning;

            // If rewards aren't boosted at max, loss rewards are queued to be redistributed to the gauge.
            queuedRewards += (maxEarming - newEarning);

            userRewardPerTokenPaid[account] = rewardPerTokenStored;
        }
    }

    /**
     *  @return timestamp untill rewards are distributed
     */
    function lastTimeRewardApplicable() public view returns (uint256) {
        return Math.min(block.timestamp, periodFinish);
    }

    /** @notice reward per token deposited
     *  @dev gives the total amount of rewards distributed since inception of the pool per vault token
     *  @return rewardPerToken
     */
    function rewardPerToken() public view returns (uint256) {
        return _rewardPerToken();
    }

    function _rewardPerToken() internal view returns (uint256) {
        if (totalSupply() == 0) {
            return rewardPerTokenStored;
        }
        return
            rewardPerTokenStored +
            (((lastTimeRewardApplicable() - lastUpdateTime) *
                rewardRate *
                1e18) / totalSupply());
    }

    function _newEarning(address account) internal view returns (uint256) {
        return
            (boostedBalanceOf(account) *
                (_rewardPerToken() - userRewardPerTokenPaid[account])) / 1e18;
    }

    function _maxEarning(address account) internal view returns (uint256) {
        return
            (balanceOf(account) *
                (_rewardPerToken() - userRewardPerTokenPaid[account])) / 1e18;
    }

    /** @notice earning for an account
     *  @dev earning are based on lock duration and boost
     *  @return amount of tokens earned
     */
    function earned(address account) public view returns (uint256) {
        return _newEarning(account);
    }

    /** @notice update reward for an account
     *  @dev called by the underlying gauge
     *  @param _account to udpdate
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

    function getReward(address _account)
        public
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

    function getReward() external {
        getReward(msg.sender);
    }

    function donate(uint256 _amount) external {
        IERC20(rewardToken).safeTransferFrom(
            msg.sender,
            address(this),
            _amount
        );
        queuedRewards = queuedRewards + _amount;
    }

    function queueNewRewards(uint256 _rewards) external returns (bool) {
        require(_rewards > 0);
        IERC20(rewardToken).safeTransferFrom(
            msg.sender,
            address(this),
            _rewards
        );
        _rewards = _rewards + queuedRewards;

        if (block.timestamp >= periodFinish) {
            _notifyRewardAmount(_rewards);
            queuedRewards = 0;
            return true;
        }

        //et = now - (finish-DURATION)
        uint256 elapsedTime = block.timestamp - (periodFinish - DURATION);
        //current at now: rewardRate * elapsedTime
        uint256 currentAtNow = rewardRate * elapsedTime;
        uint256 queuedRatio = (currentAtNow * 1000) / _rewards;
        if (queuedRatio < NEW_REWARD_RATIO) {
            _notifyRewardAmount(_rewards);
            queuedRewards = 0;
        } else {
            queuedRewards = _rewards;
        }
        return true;
    }

    function _notifyRewardAmount(uint256 reward)
        internal
        updateReward(address(0))
    {
        historicalRewards = historicalRewards + reward;
        if (block.timestamp >= periodFinish) {
            rewardRate = reward / DURATION;
        } else {
            uint256 remaining = periodFinish - block.timestamp;
            uint256 leftover = remaining * rewardRate;
            reward = reward + leftover;
            rewardRate = reward / DURATION;
        }
        currentRewards = reward;
        lastUpdateTime = block.timestamp;
        periodFinish = block.timestamp + DURATION;
        emit RewardAdded(reward);
    }
}
