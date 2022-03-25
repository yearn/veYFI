// SPDX-License-Identifier: MIT
pragma solidity 0.8.13;
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/proxy/utils/Initializable.sol";
import "./interfaces/IBaseGauge.sol";

abstract contract BaseGauge is IBaseGauge, Ownable, Initializable {
    IERC20 public override rewardToken;
    //// @notice rewards are distributed during 7 days when queued.
    uint256 public duration;
    uint256 public periodFinish;
    uint256 public rewardRate;
    uint256 public lastUpdateTime;
    uint256 public rewardPerTokenStored;
    /**
    @notice that are queued to be distributed on a `queueNewRewards` call
    @dev rewards are queued when an account `_updateReward`.
    */
    uint256 public queuedRewards;
    uint256 public currentRewards;
    uint256 public historicalRewards;

    mapping(address => uint256) public userRewardPerTokenPaid;
    mapping(address => uint256) public rewards;

    event RewardsAdded(
        uint256 currentRewards,
        uint256 lastUpdateTime,
        uint256 periodFinish,
        uint256 rewardRate,
        uint256 historicalRewards
    );

    event RewardsQueued(address indexed from, uint256 amount);

    event RewardPaid(address indexed user, uint256 reward);
    event UpdatedRewards(
        address indexed account,
        uint256 rewardPerTokenStored,
        uint256 lastUpdateTime,
        uint256 rewards,
        uint256 userRewardPerTokenPaid
    );
    event Sweep(address indexed token, uint256 amount);

    event DurationUpdated(uint256 duration, uint256 rewardRate);

    function _newEarning(address) internal view virtual returns (uint256);

    function _updateReward(address) internal virtual;

    function _rewardPerToken() internal view virtual returns (uint256);

    modifier updateReward(address account) {
        _updateReward(account);
        _;
    }

    function __initialize(address _rewardToken, address _owner) internal {
        require(
            address(_rewardToken) != address(0x0),
            "_rewardToken 0x0 address"
        );
        require(_owner != address(0), "_owner 0x0 address");
        rewardToken = IERC20(_rewardToken);
        duration = 7 days;
        _transferOwnership(_owner);
    }

    function setDuration(uint256 newDuration)
        external
        onlyOwner
        updateReward(address(0))
    {
        if (block.timestamp < periodFinish) {
            uint256 remaining = periodFinish - block.timestamp;
            uint256 leftover = remaining * rewardRate;
            rewardRate = leftover / newDuration;
        }
        duration = newDuration;
        emit DurationUpdated(newDuration, rewardRate);
    }

    /**
     *  @return timestamp until rewards are distributed
     */
    function lastTimeRewardApplicable() public view returns (uint256) {
        return Math.min(block.timestamp, periodFinish);
    }

    /** @notice reward per token deposited
     *  @dev gives the total amount of rewards distributed since inception of the pool per vault token
     *  @return rewardPerToken
     */
    function rewardPerToken() external view returns (uint256) {
        return _rewardPerToken();
    }

    function _notProtectedTokens(address _token)
        internal
        view
        virtual
        returns (bool)
    {
        return _token != address(rewardToken);
    }

    function sweep(address _token) external onlyOwner returns (bool) {
        require(_notProtectedTokens(_token), "protected token");
        uint256 amount = IERC20(_token).balanceOf(address(this));

        SafeERC20.safeTransfer(IERC20(_token), owner(), amount);
        emit Sweep(_token, amount);
        return true;
    }

    /** @notice earning for an account
     *  @dev earning are based on lock duration and boost
     *  @return amount of tokens earned
     */
    function earned(address account) external view virtual returns (uint256) {
        return _newEarning(account);
    }

    /**
     * @notice
     * Add new rewards to be distributed over a week
     * @dev Triger rewardRate recalculation using _amount and queuedRewards
     * @param _amount token to add to rewards
     * @return true
     */
    function queueNewRewards(uint256 _amount) external override returns (bool) {
        require(_amount != 0, "==0");
        SafeERC20.safeTransferFrom(
            IERC20(rewardToken),
            msg.sender,
            address(this),
            _amount
        );
        emit RewardsQueued(msg.sender, _amount);
        _amount = _amount + queuedRewards;

        if (block.timestamp >= periodFinish) {
            _notifyRewardAmount(_amount);
            queuedRewards = 0;
            return true;
        }
        uint256 elapsedSinceBeginingOfPeriod = block.timestamp -
            (periodFinish - duration);
        uint256 distributedSoFar = elapsedSinceBeginingOfPeriod * rewardRate;
        // we only restart a new week if _amount is 120% of distributedSoFar.

        if ((distributedSoFar * 12) / 10 < _amount) {
            _notifyRewardAmount(_amount);
            queuedRewards = 0;
        } else {
            queuedRewards = _amount;
        }
        return true;
    }

    function _notifyRewardAmount(uint256 reward)
        internal
        updateReward(address(0))
    {
        historicalRewards = historicalRewards + reward;
        if (block.timestamp >= periodFinish) {
            rewardRate = reward / duration;
        } else {
            uint256 remaining = periodFinish - block.timestamp;
            uint256 leftover = remaining * rewardRate;
            reward = reward + leftover;
            rewardRate = reward / duration;
        }
        currentRewards = reward;
        lastUpdateTime = block.timestamp;
        periodFinish = block.timestamp + duration;
        emit RewardsAdded(
            currentRewards,
            lastUpdateTime,
            periodFinish,
            rewardRate,
            historicalRewards
        );
    }
}
