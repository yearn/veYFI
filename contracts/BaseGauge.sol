// SPDX-License-Identifier: MIT
pragma solidity 0.8.12;
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "./interfaces/IBaseGauge.sol";

abstract contract BaseGauge is IBaseGauge {
    IERC20 public override rewardToken;
    //// @notice rewards are distributed during 7 days when queued.
    uint256 public constant DURATION = 7 days;
    uint256 public periodFinish;
    uint256 public rewardRate;
    uint256 public lastUpdateTime;
    uint256 public rewardPerTokenStored;
    /**
    @notice that are queued to be distributed on a `queueNewRewards` call
    @dev rewards are queued using `donate`.
    @dev rewards are queued when an account `_updateReward`.
    */
    uint256 public queuedRewards;
    uint256 public currentRewards;
    uint256 public historicalRewards;
    //// @notice gov can sweep token airdrop
    address public gov;

    mapping(address => uint256) public userRewardPerTokenPaid;
    mapping(address => uint256) public rewards;

    event RewardAdded(uint256 reward);
    event RewardPaid(address indexed user, uint256 reward);
    event UpdatedGov(address gov);

    function _newEarning(address) internal view virtual returns (uint256);

    function _updateReward(address) internal virtual;

    function _rewardPerToken() internal view virtual returns (uint256);

    modifier updateReward(address account) {
        _updateReward(account);
        _;
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

    /**
     * @notice
     * set gov
     * @dev Can be called by gov
     * @param _gov new gov
     * @return true
     */
    function setGov(address _gov) external returns (bool) {
        require(msg.sender == gov, "!authorized");

        require(_gov != address(0), "0x0 address");
        gov = _gov;
        emit UpdatedGov(_gov);
        return true;
    }

    function _notProtectedTokens(address _token)
        internal
        view
        virtual
        returns (bool)
    {
        return _token != address(rewardToken);
    }

    function sweep(address _token) external returns (bool) {
        require(msg.sender == gov, "!authorized");
        require(_notProtectedTokens(_token), "protected token");

        SafeERC20.safeTransfer(
            IERC20(_token),
            gov,
            IERC20(_token).balanceOf(address(this))
        );
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
        _amount = _amount + queuedRewards;

        if (block.timestamp >= periodFinish) {
            _notifyRewardAmount(_amount);
            queuedRewards = 0;
            return true;
        }
        uint256 elapsedSinceBeginingOfPeriod = block.timestamp -
            (periodFinish - DURATION);
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
