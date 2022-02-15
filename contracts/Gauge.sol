// SPDX-License-Identifier: MIT
pragma solidity 0.8.11;

import "./interfaces/IExtraReward.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";
import "./interfaces/IGauge.sol";
import "./interfaces/IVeYfiRewardPool.sol";

import "./interfaces/IVotingEscrow.sol";

/** @title  Gauge stake vault token get YFI rewards
    @notice Deposit your vault token (one gauge per vault). 
    YFI are paid based on the amount of vault tokens, the veYFI balance and the duration of the lock.
    @dev this contract is used behind multiple delegate proxies.
 */

contract Gauge is IGauge {
    using SafeERC20 for IERC20;

    IERC20 public rewardToken;
    IERC20 public stakingToken;
    //// @notice veYFI
    address public veToken;
    //// @notice the veYFI YFI reward pool, penalty are sent to this contract.
    address public veYfiRewardPool;
    //// @notice rewards are distributed during 7 days when queued.
    uint256 public constant DURATION = 7 days;
    //// @notice a copy of the veYFI max lock duration
    uint256 public constant MAX_LOCK = 4 * 365 * 86400;
    uint256 public constant PRECISON_FACTOR = 10**6;
    //// @notice Penalty do not apply for locks expiring after 3y11m
    uint256 public constant GRACE_PERIOD = 30 days;

    //// @notice gov can sweep token airdrop
    address public gov;
    //// @notice rewardManager is in charge of adding/removing aditional rewards
    address public rewardManager;

    uint256 public periodFinish;
    uint256 public rewardRate;
    uint256 public lastUpdateTime;
    uint256 public rewardPerTokenStored;
    /** 
    @notice that are queueud to be distributed on a `queueNewRewards` call
    @dev rewards are queeud using `donate`.
    @dev rewards are queeud when an account `_updateReward`.
    */
    uint256 public queuedRewards;
    /** 
    @notice penalty queued to be transfer later to veYfiRewardPool using `transferQueuedPenalty`
\    @dev rewards are queeud when an account `_updateReward`.
    */
    uint256 public queuedPenalty;
    uint256 public currentRewards;
    uint256 public historicalRewards;
    uint256 private _totalSupply;
    mapping(address => uint256) public userRewardPerTokenPaid;
    mapping(address => uint256) public rewards;
    mapping(address => uint256) private _balances;

    //// @notice list of extraRewards pool.
    address[] public extraRewards;

    event RewardAdded(uint256 reward);
    event Staked(address indexed user, uint256 amount);
    event Withdrawn(address indexed user, uint256 amount);
    event RewardPaid(address indexed user, uint256 reward);
    event AddedExtraReward(address reward);
    event DeletedExtraRewards();
    event UpdatedRewardManager(address rewardManaager);
    event UpdatedGov(address gov);

    /** @notice initialize the contract
     *  @dev Initialize called after contract is cloned.
     *  @param stakingToken_ The vault token to stake
     *  @param rewardToken_ the reward token YFI
     *  @param gov_ goverance address
     *  @param rewardManager_ reward manager address
     *  @param ve_ veYFI address
     *  @param veYfiRewardPool_ veYfiRewardPool address
     */
    function initialize(
        address stakingToken_,
        address rewardToken_,
        address gov_,
        address rewardManager_,
        address ve_,
        address veYfiRewardPool_
    ) public {
        assert(address(rewardToken) == address(0x0));
        stakingToken = IERC20(stakingToken_);
        rewardToken = IERC20(rewardToken_);
        rewardManager = rewardManager_;
        veToken = ve_;
        gov = gov_;
        veYfiRewardPool = veYfiRewardPool_;
    }

    /** @return total of the staked vault token
     */

    function totalSupply() public view returns (uint256) {
        return _totalSupply;
    }

    /** @param account to look bakance for
     *  @return amount of staked token for an account
     */
    function balanceOf(address account) public view override returns (uint256) {
        return _balances[account];
    }

    /** @return the number of extra rewards pool
     */
    function extraRewardsLength() external view returns (uint256) {
        return extraRewards.length;
    }

    /** @notice add extra rewards to the gauge
     *  @dev can only be done by rewardManager
     *  @param _extraReward the ExtraReward contract address
     *  @return true
     */
    function addExtraReward(address _extraReward) external returns (bool) {
        require(msg.sender == rewardManager, "!authorized");
        require(_extraReward != address(0), "!reward setting");
        emit AddedExtraReward(_extraReward);
        extraRewards.push(_extraReward);
        return true;
    }

    /** @notice remove extra rewards
     *  @dev can only be done by rewardManager
     */
    function clearExtraRewards() external {
        require(msg.sender == rewardManager, "!authorized");
        emit DeletedExtraRewards();
        delete extraRewards;
    }

    /** @notice update reward manager
     *  @dev can only be done by rewardManager
     */
    function updateRewardManager(address _rewardManager) external {
        require(msg.sender == rewardManager, "!authorized");
        rewardManager = _rewardManager;
    }

    modifier updateReward(address account) {
        _updateReward(account);
        _;
    }

    function _updateReward(address account) internal {
        rewardPerTokenStored = _rewardPerToken();
        lastUpdateTime = lastTimeRewardApplicable();
        if (account != address(0)) {
            if (_balances[account] != 0) {
                uint256 newEarning = _newEarning(account);
                uint256 maxEarming = _maxEarning(account);

                uint256 penalty = ((PRECISON_FACTOR - _lockingRatio(account)) *
                    newEarning) / PRECISON_FACTOR;

                rewards[account] += (newEarning - penalty);
                queuedPenalty += penalty;

                // If rewards aren't boosted at max, loss rewards are queued to be redistributed to the gauge.
                queuedRewards += (maxEarming - newEarning);
            }
            userRewardPerTokenPaid[account] = rewardPerTokenStored;
        }
    }

    /** @notice give the lockingRatio
     * @dev locking ratio is expressed in PRECISON_FACTOR, it's used to calculate the penalty due to the lock duration.
     * @return lockingRatio
     */
    function lockingRatio(address account) external view returns (uint256) {
        return _lockingRatio(account);
    }

    function _lockingRatio(address acccount) internal view returns (uint256) {
        uint256 lockedUntil = IVotingEscrow(veToken).locked(acccount).end;
        if (lockedUntil == 0) return 0;

        uint256 timeLeft = lockedUntil - block.timestamp;
        if (MAX_LOCK - timeLeft < GRACE_PERIOD) {
            return PRECISON_FACTOR;
        }

        return (PRECISON_FACTOR * timeLeft) / MAX_LOCK;
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

    /** @notice earning for an account
     *  @dev earning are based on lock duration and boost
     *  @return amount of tokens earned
     */
    function earned(address account) public view returns (uint256) {
        uint256 newEarning = _newEarning(account);

        return
            (_lockingRatio(account) * newEarning) /
            PRECISON_FACTOR +
            rewards[account];
    }

    function _newEarning(address account) internal view returns (uint256) {
        return
            (_boostedBalanceOf(account) *
                (_rewardPerToken() - userRewardPerTokenPaid[account])) / 1e18;
    }

    function _maxEarning(address account) internal view returns (uint256) {
        return
            (_balances[account] *
                (_rewardPerToken() - userRewardPerTokenPaid[account])) / 1e18;
    }

    /** @notice boosted balance of based on veYFI balance
     *  @dev min(balance * 0.4 + totalSupply * veYFIBalance / veYFITotalSypply * 0.6, balance)
     *  @return boosted balance
     */
    function boostedBalanceOf(address account) public view returns (uint256) {
        return _boostedBalanceOf(account);
    }

    function _boostedBalanceOf(address account)
        internal
        view
        returns (uint256)
    {
        uint256 veTotalSupply = IVotingEscrow(veToken).totalSupply();
        if (veTotalSupply == 0) return _balances[account];

        return
            Math.min(
                ((_balances[account] * 40) +
                    (((_totalSupply *
                        IVotingEscrow(veToken).balanceOf(account)) /
                        veTotalSupply) * 60)) / 100,
                _balances[account]
            );
    }

    /** @notice deposit vault tokens into the gauge
     * @dev a user without a veYFI should not lock.
     * @dev This call update claimable rewards
     * @param _amount of vault token
     * @return true
     */
    function deposit(uint256 _amount)
        public
        updateReward(msg.sender)
        returns (bool)
    {
        require(_amount > 0, "RewardPool : Cannot deposit 0");

        //also deposit to linked rewards
        for (uint256 i = 0; i < extraRewards.length; i++) {
            IExtraReward(extraRewards[i]).rewardCheckpoint(msg.sender);
        }

        _totalSupply = _totalSupply + _amount;
        _balances[msg.sender] = _balances[msg.sender] + _amount;

        stakingToken.safeTransferFrom(msg.sender, address(this), _amount);
        emit Staked(msg.sender, _amount);

        return true;
    }

    /** @notice deposit vault tokens into the gauge
     *   @dev a user without a veYFI should not lock.
     *   @dev will deposit the min betwwen user balance and user approval
     *   @dev This call update claimable rewards
     *   @return true
     */
    function deposit() external returns (bool) {
        uint256 balance = Math.min(
            stakingToken.balanceOf(msg.sender),
            stakingToken.allowance(msg.sender, address(this))
        );
        deposit(balance);
        return true;
    }

    /** @notice deposit vault tokens into the gauge for a user
     *   @dev vault token is taken from msg.sender
     *   @dev This call update  `_for` claimable rewards
     *   @param _for account to deposit to
     *    @param _amount to deposit
     *    @return true
     */
    function depositFor(address _for, uint256 _amount)
        external
        updateReward(_for)
        returns (bool)
    {
        require(_amount > 0, "RewardPool : Cannot deposit 0");

        //also deposit to linked rewards
        for (uint256 i = 0; i < extraRewards.length; i++) {
            IExtraReward(extraRewards[i]).rewardCheckpoint(_for);
        }

        //give to _for
        _totalSupply = _totalSupply + _amount;
        _balances[_for] = _balances[_for] + _amount;

        //take away from sender
        stakingToken.safeTransferFrom(msg.sender, address(this), _amount);
        emit Staked(_for, _amount);
        return true;
    }

    /** @notice withdraw vault token from the gauge
     * @dev This call update claimable rewards
     *  @param _amount amount to withdraw
     *   @param _claim claimm veYFI and aditional reward
     *   @param _lock should the claimed rewards be locked in veYFI for the user
     *   @return true
     */
    function withdraw(
        uint256 _amount,
        bool _claim,
        bool _lock
    ) public updateReward(msg.sender) returns (bool) {
        require(_amount > 0, "RewardPool : Cannot withdraw 0");

        //also withdraw from linked rewards
        for (uint256 i = 0; i < extraRewards.length; i++) {
            IExtraReward(extraRewards[i]).rewardCheckpoint(msg.sender);
        }

        _totalSupply = _totalSupply - _amount;
        _balances[msg.sender] = _balances[msg.sender] - _amount;

        if (_claim) {
            _getReward(msg.sender, _lock, true);
        }

        stakingToken.safeTransfer(msg.sender, _amount);
        emit Withdrawn(msg.sender, _amount);

        return true;
    }

    /** @notice withdraw all vault token from gauge
     *   @dev This call update claimable rewards
     *   @param _claim claimm veYFI and aditional reward
     *   @param _lock should the claimed rewards be locked in veYFI for the user
     *   @return true
     */
    function withdraw(bool _claim, bool _lock) external returns (bool) {
        withdraw(_balances[msg.sender], _claim, _lock);
        return true;
    }

    /** @notice withdraw all vault token from gauge
     *  @dev This call update claimable rewards
     *  @param _claim claimm veYFI and aditional reward
     *  @return true
     */
    function withdraw(bool _claim) external returns (bool) {
        withdraw(_balances[msg.sender], _claim, false);
        return true;
    }

    /** @notice withdraw all vault token from gauge
        @dev This call update claimable rewards
        @return true
    */
    function withdraw() external returns (bool) {
        withdraw(_balances[msg.sender], false, false);
        return true;
    }

    /**
     * @notice
     *  Get rewards
     * @param _lock should the yfi be locked in veYFI
     * @param _claimExtras claim extra rewards
     * @return true
     */
    function getReward(bool _lock, bool _claimExtras)
        external
        updateReward(msg.sender)
        returns (bool)
    {
        _getReward(msg.sender, _lock, _claimExtras);
        return true;
    }

    /**
     * @notice
     *  Get rewards and claim extra rewards
     *  @param _lock should the yfi be locked in veYFI
     *  @return true
     */
    function getReward(bool _lock)
        external
        updateReward(msg.sender)
        returns (bool)
    {
        _getReward(msg.sender, _lock, true);
        return true;
    }

    /**
     * @notice
     *  Get rewards and claim extra rewards, do not lock YFI earned
     *  @return true
     */
    function getReward() external updateReward(msg.sender) returns (bool) {
        _getReward(msg.sender, false, true);
        return true;
    }

    /**
     * @notice
     *  Get rewards for an account
     * @dev rewards are transfer to _account
     * @param _account to claim reards for
     * @param _claimExtras claim extra rewards
     * @return true
     */
    function getRewardFor(address _account, bool _claimExtras)
        external
        updateReward(_account)
        returns (bool)
    {
        _getReward(_account, false, _claimExtras);
        return true;
    }

    function _getReward(
        address _account,
        bool _lock,
        bool _claimExtras
    ) internal {
        uint256 reward = rewards[_account];
        if (reward > 0) {
            rewards[_account] = 0;
            if (_lock) {
                rewardToken.safeApprove(address(veToken), reward);
                IVotingEscrow(veToken).deposit_for(msg.sender, reward);
            } else {
                rewardToken.safeTransfer(_account, reward);
            }

            emit RewardPaid(_account, reward);
        }
        //also get rewards from linked rewards
        if (_claimExtras) {
            for (uint256 i = 0; i < extraRewards.length; i++) {
                IExtraReward(extraRewards[i]).getRewardFor(msg.sender);
            }
        }
    }

    /**
     * @notice
     *  Donate tokens to distribute as rewards
     * @dev Do not trigger rewardRate recalculation
     * @param _amount token to donate
     * @return true
     */

    function donate(uint256 _amount) external returns (bool) {
        require(_amount != 0, "==0");
        IERC20(rewardToken).safeTransferFrom(
            msg.sender,
            address(this),
            _amount
        );
        queuedRewards = queuedRewards + _amount;
        return true;
    }

    /**
     * @notice
     * Add new rewards to be distributed over a week
     * @dev Triger rewardRate recalculation using _amount and queuedRewards
     * @param _amount token to add to rewards
     * @return true
     */
    function queueNewRewards(uint256 _amount) external returns (bool) {
        require(_amount != 0, "==0");
        IERC20(rewardToken).safeTransferFrom(
            msg.sender,
            address(this),
            _amount
        );
        _amount = _amount + queuedRewards;

        _notifyRewardAmount(_amount);
        queuedRewards = 0;
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

    /**
     * @notice
     * Transfer penalty to the veYFIRewardContract
     * @dev Penalty are queued in this contract.
     * @return true
     */
    function transferQueuedPenalty() external returns (bool) {
        uint256 toTransfer = queuedPenalty;
        queuedPenalty = 0;

        IERC20(rewardToken).safeApprove(veYfiRewardPool, toTransfer);
        IVeYfiRewardPool(veYfiRewardPool).donate(toTransfer);
        return true;
    }

    /**
     * @notice
     * set reward manager
     * @dev Can be called by rewardManager or gov
     * @param _rewardManager new reward manager
     * @return true
     */
    function setRewardManager(address _rewardManager) external returns (bool) {
        require(
            msg.sender == rewardManager || msg.sender == gov,
            "!authorized"
        );

        require(_rewardManager != address(0), "already set");
        rewardManager = _rewardManager;
        emit UpdatedRewardManager(rewardManager);
        return true;
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

        require(_gov != address(0), "already set");
        gov = _gov;
        emit UpdatedGov(_gov);
        return true;
    }

    /**
     * @notice
     * sweep airdroped token
     * @dev Can't sweep vault tokens nor reward token
     * @dev token are sweep to giv
     * @param _token token to sweeo
     * @return true
     */
    function sweep(address _token) external returns (bool) {
        require(msg.sender == gov, "!authorized");
        require(_token != address(stakingToken), "!stakingToken");
        require(_token != address(rewardToken), "!rewardToken");

        SafeERC20.safeTransfer(
            IERC20(_token),
            gov,
            IERC20(_token).balanceOf(address(this))
        );
        return true;
    }
}
