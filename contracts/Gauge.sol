// SPDX-License-Identifier: MIT
pragma solidity 0.8.13;

import "./interfaces/IExtraReward.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";
import "./interfaces/IGauge.sol";
import "./BaseGauge.sol";

import "./interfaces/IVotingEscrow.sol";

/** @title  Gauge stake vault token get YFI rewards
    @notice Deposit your vault token (one gauge per vault).
    YFI are paid based on the amount of vault tokens, the veYFI balance and the duration of the lock.
    @dev this contract is used behind multiple delegate proxies.
 */

contract Gauge is BaseGauge, IGauge {
    using SafeERC20 for IERC20;

    IERC20 public stakingToken;
    //// @notice veYFI
    address public veToken;
    //// @notice the veYFI YFI reward pool, penalty are sent to this contract.
    address public veYfiRewardPool;
    //// @notice a copy of the veYFI max lock duration
    uint256 public constant MAX_LOCK = 4 * 365 * 86400;
    uint256 public constant PRECISON_FACTOR = 10**6;
    //// @notice Penalty do not apply for locks expiring after 3y11m
    uint256 public constant GRACE_PERIOD = 30 days;

    //// @notice rewardManager is in charge of adding/removing additional rewards
    address public rewardManager;

    /**
    @notice penalty queued to be transfer later to veYfiRewardPool using `transferQueuedPenalty`
    @dev rewards are queued when an account `_updateReward`.
    */
    uint256 public queuedPenalty;
    uint256 private _totalSupply;
    mapping(address => uint256) private _balances;

    //// @notice list of extraRewards pool.
    address[] public extraRewards;

    event Staked(address indexed user, uint256 amount);
    event Withdrawn(address indexed user, uint256 amount);
    event AddedExtraReward(address indexed reward);
    event DeletedExtraRewards(address[] rewards);
    event RemovedExtraReward(address indexed reward);
    event UpdatedRewardManager(address indexed rewardManager);
    event UpdatedVeToken(address indexed ve);
    event TransferedQueuedPenalty(uint256 transfered);

    event Initialized(
        address indexed stakingToken,
        address indexed rewardToken,
        address indexed owner,
        address rewardManager,
        address ve,
        address veYfiRewardPool
    );

    /** @notice initialize the contract
     *  @dev Initialize called after contract is cloned.
     *  @param _stakingToken The vault token to stake
     *  @param _rewardToken the reward token YFI
     *  @param _owner owner address
     *  @param _rewardManager reward manager address
     *  @param _ve veYFI address
     *  @param _veYfiRewardPool veYfiRewardPool address
     */
    function initialize(
        address _stakingToken,
        address _rewardToken,
        address _owner,
        address _rewardManager,
        address _ve,
        address _veYfiRewardPool
    ) external initializer {
        require(
            address(_stakingToken) != address(0x0),
            "_stakingToken 0x0 address"
        );
        require(address(_ve) != address(0x0), "_ve 0x0 address");
        require(
            address(_veYfiRewardPool) != address(0x0),
            "_veYfiRewardPool 0x0 address"
        );

        require(_rewardManager != address(0), "_rewardManager 0x0 address");

        __initialize(_rewardToken, _owner);
        stakingToken = IERC20(_stakingToken);
        veToken = _ve;
        rewardManager = _rewardManager;
        veYfiRewardPool = _veYfiRewardPool;

        emit Initialized(
            _stakingToken,
            _rewardToken,
            _owner,
            _rewardManager,
            _ve,
            _veYfiRewardPool
        );
    }

    function setVe(address _veToken) external onlyOwner {
        require(address(_veToken) != address(0x0), "_veToken 0x0 address");
        veToken = _veToken;
        emit UpdatedVeToken(_veToken);
    }

    /** @return total of the staked vault token
     */
    function totalSupply() public view returns (uint256) {
        return _totalSupply;
    }

    /** @param account to look balance for
     *  @return amount of staked token for an account
     */
    function balanceOf(address account)
        external
        view
        override
        returns (uint256)
    {
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

    /** @notice remove extra rewards from the gauge
     *  @dev can only be done by rewardManager
     *  @param _extraReward the ExtraReward contract address
     */
    function removeExtraReward(address _extraReward) external returns (bool) {
        require(msg.sender == rewardManager, "!authorized");
        uint256 index = type(uint256).max;
        uint256 length = extraRewards.length;
        for (uint256 i = 0; i < length; i++) {
            if (extraRewards[i] == _extraReward) {
                index = i;
                break;
            }
        }
        require(index != type(uint256).max, "extra reward not found");
        emit RemovedExtraReward(_extraReward);
        extraRewards[index] = extraRewards[extraRewards.length - 1];
        extraRewards.pop();
        return true;
    }

    /** @notice remove extra rewards
     *  @dev can only be done by rewardManager
     */
    function clearExtraRewards() external {
        require(msg.sender == rewardManager, "!authorized");
        emit DeletedExtraRewards(extraRewards);
        delete extraRewards;
    }

    function _updateReward(address account) internal override {
        rewardPerTokenStored = _rewardPerToken();
        lastUpdateTime = lastTimeRewardApplicable();
        if (account != address(0)) {
            if (_balances[account] != 0) {
                uint256 newEarning = _newEarning(account);
                uint256 maxEarning = _maxEarning(account);

                uint256 penalty = ((PRECISON_FACTOR - _lockingRatio(account)) *
                    newEarning) / PRECISON_FACTOR;

                rewards[account] += (newEarning - penalty);
                queuedPenalty += penalty;

                // If rewards aren't boosted at max, loss rewards are queued to be redistributed to the gauge.
                queuedRewards += (maxEarning - newEarning);
            }
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

    /** @notice give the lockingRatio
     * @dev locking ratio is expressed in PRECISON_FACTOR, it's used to calculate the penalty due to the lock duration.
     * @return lockingRatio
     */
    function lockingRatio(address account) external view returns (uint256) {
        return _lockingRatio(account);
    }

    function _lockingRatio(address acccount) internal view returns (uint256) {
        if (IVotingEscrow(veToken).migration()) {
            return PRECISON_FACTOR;
        }

        uint256 lockedUntil = IVotingEscrow(veToken).locked__end(acccount);
        if (lockedUntil == 0 || lockedUntil <= block.timestamp) {
            return 0;
        }

        uint256 timeLeft = lockedUntil - block.timestamp;
        if (MAX_LOCK - timeLeft < GRACE_PERIOD) {
            return PRECISON_FACTOR;
        }

        return (PRECISON_FACTOR * timeLeft) / MAX_LOCK;
    }

    function _rewardPerToken() internal view override returns (uint256) {
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
    function earned(address account)
        external
        view
        override(BaseGauge, IBaseGauge)
        returns (uint256)
    {
        uint256 newEarning = _newEarning(account);

        return
            (_lockingRatio(account) * newEarning) /
            PRECISON_FACTOR +
            rewards[account];
    }

    function _newEarning(address account)
        internal
        view
        override
        returns (uint256)
    {
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
        if (veTotalSupply == 0) {
            return _balances[account];
        }

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
    function deposit(uint256 _amount) public returns (bool) {
        _deposit(msg.sender, _amount);
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
        _deposit(msg.sender, balance);
        return true;
    }

    /** @notice deposit vault tokens into the gauge for a user
     *   @dev vault token is taken from msg.sender
     *   @dev This call update  `_for` claimable rewards
     *   @param _for account to deposit to
     *    @param _amount to deposit
     *    @return true
     */
    function depositFor(address _for, uint256 _amount) external returns (bool) {
        _deposit(_for, _amount);
        return true;
    }

    function _deposit(address _for, uint256 _amount)
        internal
        updateReward(_for)
    {
        require(_amount > 0, "RewardPool : Cannot deposit 0");

        //also deposit to linked rewards
        uint256 length = extraRewards.length;
        for (uint256 i = 0; i < length; i++) {
            IExtraReward(extraRewards[i]).rewardCheckpoint(_for);
        }

        //give to _for
        _totalSupply = _totalSupply + _amount;
        _balances[_for] = _balances[_for] + _amount;

        //take away from sender
        stakingToken.safeTransferFrom(msg.sender, address(this), _amount);
        emit Staked(_for, _amount);
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
        uint256 length = extraRewards.length;
        for (uint256 i = 0; i < length; i++) {
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
     *   @param _claim claim veYFI and additional reward
     *   @param _lock should the claimed rewards be locked in veYFI for the user
     *   @return true
     */
    function withdraw(bool _claim, bool _lock) external returns (bool) {
        withdraw(_balances[msg.sender], _claim, _lock);
        return true;
    }

    /** @notice withdraw all vault token from gauge
     *  @dev This call update claimable rewards
     *  @param _claim claim veYFI and additional reward
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
     * @param _account to claim rewards for
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
                rewardToken.approve(address(veToken), reward);
                IVotingEscrow(veToken).deposit_for(msg.sender, reward);
            } else {
                rewardToken.safeTransfer(_account, reward);
            }

            emit RewardPaid(_account, reward);
        }
        //also get rewards from linked rewards
        if (_claimExtras) {
            uint256 length = extraRewards.length;
            for (uint256 i = 0; i < length; i++) {
                IExtraReward(extraRewards[i]).getRewardFor(msg.sender);
            }
        }
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

        IERC20(rewardToken).approve(veYfiRewardPool, toTransfer);
        BaseGauge(veYfiRewardPool).queueNewRewards(toTransfer);
        emit TransferedQueuedPenalty(toTransfer);
        return true;
    }

    /**
     * @notice
     * set reward manager
     * @dev Can be called by rewardManager or owner
     * @param _rewardManager new reward manager
     * @return true
     */
    function setRewardManager(address _rewardManager) external returns (bool) {
        require(
            msg.sender == rewardManager || msg.sender == owner(),
            "!authorized"
        );

        require(_rewardManager != address(0), "_rewardManager 0x0 address");
        rewardManager = _rewardManager;
        emit UpdatedRewardManager(rewardManager);
        return true;
    }

    function _notProtectedTokens(address _token)
        internal
        view
        override
        returns (bool)
    {
        return
            _token != address(rewardToken) && _token != address(stakingToken);
    }
}
