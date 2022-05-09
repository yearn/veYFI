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
    YFI are paid based on the number of vault tokens, the veYFI balance, and the duration of the lock.
    @dev this contract is used behind multiple delegate proxies.
 */

contract Gauge is BaseGauge, IGauge {
    using SafeERC20 for IERC20;

    struct Balance {
        uint256 realBalance;
        uint256 boostedBalance;
        uint256 lastDeposit;
        uint256 integrateCheckpointOf;
    }

    struct Appoved {
        bool deposit;
        bool claim;
        bool lock;
    }

    uint256 public boostingFactor = 100;
    uint256 private constant BOOST_DENOMINATOR = 1000;

    IERC20 public stakingToken;
    //// @notice veYFI
    address public veToken;
    //// @notice the veYFI YFI reward pool, penalty are sent to this contract.
    address public veYfiRewardPool;
    //// @notice a copy of the veYFI max lock duration
    uint256 public constant MAX_LOCK = 4 * 365 * 86400;
    uint256 public constant PRECISON_FACTOR = 10**6;
    //// @notice Penalty does not apply for locks expiring after 3y11m

    //// @notice rewardManager is in charge of adding/removing additional rewards
    address public rewardManager;

    /**
    @notice penalty queued to be transferred later to veYfiRewardPool using `transferQueuedPenalty`
    @dev rewards are queued when an account `_updateReward`.
    */
    uint256 public queuedVeYfiRewards;
    uint256 private _totalSupply;
    mapping(address => Balance) private _balances;
    mapping(address => mapping(address => Appoved)) public approvedTo;

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
    event UpdatedBoostingFactor(uint256 boostingFactor);

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
        boostingFactor = 100;
    }

    /**
    @notice Set the veYFI token address.
    @param _veToken the new address of the veYFI token
    */
    function setVe(address _veToken) external onlyOwner {
        require(address(_veToken) != address(0x0), "_veToken 0x0 address");
        veToken = _veToken;
        emit UpdatedVeToken(_veToken);
    }

    /**
    @notice Set the boosting factor.
    @dev the boosting factor is used to calculate your boosting balance using the curve boosting formula adjusted with the boostingFactor
    @param _boostingFactor the value should be between 20 and 500
    */
    function setBoostingFactor(uint256 _boostingFactor) external onlyOwner {
        require(_boostingFactor <= BOOST_DENOMINATOR / 2, "value too high");
        require(_boostingFactor >= BOOST_DENOMINATOR / 50, "value too low");

        boostingFactor = _boostingFactor;
        emit UpdatedBoostingFactor(_boostingFactor);
    }

    /** @return total of the staked vault token
     */
    function totalSupply() public view returns (uint256) {
        return _totalSupply;
    }

    /** @param _account to look balance for
     *  @return amount of staked token for an account
     */
    function balanceOf(address _account)
        external
        view
        override
        returns (uint256)
    {
        return _balances[_account].realBalance;
    }

    /** @param _account to look balance for
     *  @return amount of staked token for an account
     */
    function snapshotBalanceOf(address _account)
        external
        view
        returns (uint256)
    {
        return _balances[_account].boostedBalance;
    }

    /** @param _account integrateCheckpointOf
     *  @return block number
     */
    function integrateCheckpointOf(address _account)
        external
        view
        returns (uint256)
    {
        return _balances[_account].integrateCheckpointOf;
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
        for (uint256 i = 0; i < extraRewards.length; ++i) {
            require(extraRewards[i] != _extraReward, "exists");
        }
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
        for (uint256 i = 0; i < length; ++i) {
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

    function _updateReward(address _account) internal override {
        rewardPerTokenStored = _rewardPerToken();
        lastUpdateTime = lastTimeRewardApplicable();
        if (_account != address(0)) {
            if (_balances[_account].boostedBalance != 0) {
                uint256 newEarning = _newEarning(_account);
                uint256 maxEarning = _maxEarning(_account);

                rewards[_account] += newEarning;
                queuedVeYfiRewards += (maxEarning - newEarning);
            }
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
        if (totalSupply() == 0) {
            return rewardPerTokenStored;
        }
        return
            rewardPerTokenStored +
            (((lastTimeRewardApplicable() - lastUpdateTime) *
                rewardRate *
                PRECISION_FACTOR) / totalSupply());
    }

    /** @notice earnings for an account
     *  @dev earnings are based on lock duration and boost
     *  @return amount of tokens earned
     */
    function earned(address _account)
        external
        view
        override(BaseGauge, IBaseGauge)
        returns (uint256)
    {
        uint256 newEarning = _newEarning(_account);

        return newEarning + rewards[_account];
    }

    function _newEarning(address _account)
        internal
        view
        override
        returns (uint256)
    {
        return
            (_balances[_account].boostedBalance *
                (_rewardPerToken() - userRewardPerTokenPaid[_account])) /
            PRECISION_FACTOR;
    }

    function _maxEarning(address _account) internal view returns (uint256) {
        return
            (_balances[_account].realBalance *
                (_rewardPerToken() - userRewardPerTokenPaid[_account])) /
            PRECISION_FACTOR;
    }

    /** @notice boosted balance of based on veYFI balance
     *  @return boosted balance
     */
    function boostedBalanceOf(address _account)
        external
        view
        returns (uint256)
    {
        return _boostedBalanceOf(_account);
    }

    function _boostedBalanceOf(address _account)
        internal
        view
        returns (uint256)
    {
        return _boostedBalanceOf(_account, _balances[_account].realBalance);
    }

    function _boostedBalanceOf(address _account, uint256 _realBalance)
        internal
        view
        returns (uint256)
    {
        uint256 veTotalSupply = IVotingEscrow(veToken).totalSupply();
        if (veTotalSupply == 0) {
            return _realBalance;
        }
        return
            Math.min(
                ((_realBalance * boostingFactor) +
                    (((_totalSupply *
                        IVotingEscrow(veToken).balanceOf(_account)) /
                        veTotalSupply) *
                        (BOOST_DENOMINATOR - boostingFactor))) /
                    BOOST_DENOMINATOR,
                _realBalance
            );
    }

    /** @notice deposit vault tokens into the gauge
     * @dev a user without a veYFI should not lock.
     * @dev This call updates claimable rewards
     * @param _amount of vault token
     * @return true
     */
    function deposit(uint256 _amount) external returns (bool) {
        _deposit(msg.sender, _amount);
        return true;
    }

    /** @notice deposit vault tokens into the gauge
     *   @dev a user without a veYFI should not lock.
     *   @dev will deposit the min between user balance and user approval
     *   @dev This call updates claimable rewards
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
     *   @param _for the account to deposit to
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
        require(_amount != 0, "RewardPool : Cannot deposit 0");
        if (_for != msg.sender) {
            require(approvedTo[msg.sender][_for].deposit, "not allowed");
        }

        //also deposit to linked rewards
        uint256 length = extraRewards.length;
        for (uint256 i = 0; i < length; ++i) {
            IExtraReward(extraRewards[i]).rewardCheckpoint(_for);
        }

        //give to _for
        Balance storage balance = _balances[_for];
        balance.lastDeposit = block.number;

        _totalSupply += _amount;
        uint256 newBalance = balance.realBalance + _amount;
        balance.realBalance = newBalance;
        balance.boostedBalance = _boostedBalanceOf(_for, newBalance);
        balance.integrateCheckpointOf = block.number;

        //take away from sender
        stakingToken.safeTransferFrom(msg.sender, address(this), _amount);
        emit Staked(_for, _amount);
    }

    /** @notice allow an address to deposit on your behalf
     *  @param _addr address to change approval for
     *  @param _canDeposit can deposit
     *  @param _canClaim can deposit
     *  @return true
     */
    function setApprovals(
        address _addr,
        bool _canDeposit,
        bool _canClaim,
        bool _canLock
    ) external returns (bool) {
        approvedTo[_addr][msg.sender].deposit = _canDeposit;
        approvedTo[_addr][msg.sender].claim = _canClaim;
        approvedTo[_addr][msg.sender].lock = _canLock;

        return true;
    }

    /** @notice withdraw vault token from the gauge
     * @dev This call updates claimable rewards
     *  @param _amount amount to withdraw
     *   @param _claim claim veYFI and additional reward
     *   @param _lock should the claimed rewards be locked in veYFI for the user
     *   @return true
     */
    function withdraw(
        uint256 _amount,
        bool _claim,
        bool _lock
    ) public updateReward(msg.sender) returns (bool) {
        require(_amount != 0, "RewardPool : Cannot withdraw 0");
        Balance storage balance = _balances[msg.sender];
        require(
            balance.lastDeposit < block.number,
            "no withdraw on the deposit block"
        );

        //also withdraw from linked rewards
        uint256 length = extraRewards.length;
        for (uint256 i = 0; i < length; ++i) {
            IExtraReward(extraRewards[i]).rewardCheckpoint(msg.sender);
        }

        _totalSupply -= _amount;
        uint256 newBalance = balance.realBalance - _amount;
        balance.realBalance = newBalance;
        balance.boostedBalance = _boostedBalanceOf(msg.sender, newBalance);
        balance.integrateCheckpointOf = block.number;

        if (_claim) {
            _getReward(msg.sender, _lock, true);
        }

        stakingToken.safeTransfer(msg.sender, _amount);
        emit Withdrawn(msg.sender, _amount);

        return true;
    }

    /** @notice withdraw all vault tokens from gauge
     *   @dev This call updates claimable rewards
     *   @param _claim claim veYFI and additional reward
     *   @param _lock should the claimed rewards be locked in veYFI for the user
     *   @return true
     */
    function withdraw(bool _claim, bool _lock) external returns (bool) {
        withdraw(_balances[msg.sender].realBalance, _claim, _lock);
        return true;
    }

    /** @notice withdraw all vault token from gauge
     *  @dev This call update claimable rewards
     *  @param _claim claim veYFI and additional reward
     *  @return true
     */
    function withdraw(bool _claim) external returns (bool) {
        withdraw(_balances[msg.sender].realBalance, _claim, false);
        return true;
    }

    /** @notice withdraw all vault token from gauge
        @dev This call update claimable rewards
        @return true
    */
    function withdraw() external returns (bool) {
        withdraw(_balances[msg.sender].realBalance, false, false);
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
        _balances[msg.sender].boostedBalance = _boostedBalanceOf(msg.sender);
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
     * @dev rewards are transferred to _account
     * @param _account to claim rewards for
     * @param _claimExtras claim extra rewards
     * @return true
     */
    function getRewardFor(
        address _account,
        bool _lock,
        bool _claimExtras
    ) external updateReward(_account) returns (bool) {
        if (_account != msg.sender) {
            require(
                approvedTo[msg.sender][_account].claim,
                "not allowed to claim"
            );
            require(
                _lock == false || approvedTo[msg.sender][_account].lock,
                "not allowed to lock"
            );
        }

        _getReward(_account, _lock, _claimExtras);

        return true;
    }

    function _getReward(
        address _account,
        bool _lock,
        bool _claimExtras
    ) internal {
        _balances[_account].boostedBalance = _boostedBalanceOf(_account);
        _balances[_account].integrateCheckpointOf = block.number;

        uint256 reward = rewards[_account];
        if (reward != 0) {
            rewards[_account] = 0;
            if (_lock) {
                rewardToken.approve(address(veToken), reward);
                IVotingEscrow(veToken).deposit_for(_account, reward);
            } else {
                rewardToken.safeTransfer(_account, reward);
            }

            emit RewardPaid(_account, reward);
        }
        //also get rewards from linked rewards
        if (_claimExtras) {
            uint256 length = extraRewards.length;
            for (uint256 i = 0; i < length; ++i) {
                IExtraReward(extraRewards[i]).getRewardFor(_account);
            }
        }
    }

    /**
     * @notice
     * Transfer penalty to the veYFIRewardContract
     * @dev Penalty are queued in this contract.
     * @return true
     */
    function transferVeYfiRewards() external returns (bool) {
        uint256 toTransfer = queuedVeYfiRewards;
        queuedVeYfiRewards = 0;

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

    /**
    @notice Kick `addr` for abusing their boost
    @param _account Address to kick
    */
    function kick(address _account) external updateReward(_account) {
        Balance storage balance = _balances[_account];

        require(
            balance.boostedBalance >
                (balance.realBalance * boostingFactor) / BOOST_DENOMINATOR,
            "min boosted balance"
        );

        balance.boostedBalance = _boostedBalanceOf(
            _account,
            balance.realBalance
        );
        balance.integrateCheckpointOf = block.number;
    }
}
