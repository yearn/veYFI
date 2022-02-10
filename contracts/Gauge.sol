// SPDX-License-Identifier: MIT
pragma solidity 0.8.11;

import "./interfaces/IVirtualBalanceRewardPool.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";
import "./interfaces/IGauge.sol";
import "./interfaces/IVeYfiRewardPool.sol";

import "./interfaces/IVotingEscrow.sol";

contract Gauge is IGauge {
    using SafeERC20 for IERC20;

    IERC20 public rewardToken;
    IERC20 public stakingToken;
    address public veToken;
    address public veYfiRewardPool;
    uint256 public constant DURATION = 7 days;
    uint256 constant MAX_LOCK = 4 * 365 * 86400;
    uint256 constant PRECISON_FACTOR = 10**6;
    uint256 constant GRACE_PERIOD = 30 days; // No penalty for a max lock for 30 days.

    address public rewardManager;
    address public gov;

    uint256 public pid;
    uint256 public periodFinish;
    uint256 public rewardRate;
    uint256 public lastUpdateTime;
    uint256 public rewardPerTokenStored;
    uint256 public queuedRewards;
    uint256 public queuedPenalty;
    uint256 public currentRewards;
    uint256 public historicalRewards;
    uint256 private _totalSupply;
    mapping(address => uint256) public userRewardPerTokenPaid;
    mapping(address => uint256) public rewards;
    mapping(address => uint256) private _balances;

    address[] public extraRewards;

    event RewardAdded(uint256 reward);
    event Staked(address indexed user, uint256 amount);
    event Withdrawn(address indexed user, uint256 amount);
    event RewardPaid(address indexed user, uint256 reward);
    event AddedExtraReward(address reward);
    event deletedExtraRewards();
    event UpdatedRewardManager(address rewardManaager);
    event UpdatedGov(address gov);

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

    function totalSupply() public view returns (uint256) {
        return _totalSupply;
    }

    function balanceOf(address account) public view override returns (uint256) {
        return _balances[account];
    }

    function extraRewardsLength() external view returns (uint256) {
        return extraRewards.length;
    }

    function addExtraReward(address _extraReward) external returns (bool) {
        require(msg.sender == rewardManager, "!authorized");
        require(_extraReward != address(0), "!reward setting");
        emit AddedExtraReward(_extraReward);
        extraRewards.push(_extraReward);
        return true;
    }

    function clearExtraRewards() external {
        require(msg.sender == rewardManager, "!authorized");
        emit deletedExtraRewards();
        delete extraRewards;
    }

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

    function lastTimeRewardApplicable() public view returns (uint256) {
        return Math.min(block.timestamp, periodFinish);
    }

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

    function earned(address account) public view returns (uint256) {
        uint256 newEarning = _newEarning(account);

        return
            (_lockingRatio(account) * newEarning) /
            PRECISON_FACTOR +
            rewards[account];
    }

    function _newEarning(address account) internal view returns (uint256) {
        return
            (boostedBalanceOf(account) *
                (_rewardPerToken() - userRewardPerTokenPaid[account])) / 1e18;
    }

    function _maxEarning(address account) internal view returns (uint256) {
        return
            (_balances[account] *
                (_rewardPerToken() - userRewardPerTokenPaid[account])) / 1e18;
    }

    function boostedBalanceOf(address account) public view returns (uint256) {
        uint256 veTotalSupply = IVotingEscrow(veToken).totalSupply();
        if (veTotalSupply == 0) return _balances[account];

        return
            Math.min(
                ((_balances[account] * 40) /
                    100 +
                    (((_totalSupply *
                        IVotingEscrow(veToken).balanceOf(account)) /
                        veTotalSupply) * 60) /
                    100),
                _balances[account]
            );
    }

    function deposit(uint256 _amount)
        public
        updateReward(msg.sender)
        returns (bool)
    {
        require(_amount > 0, "RewardPool : Cannot deposit 0");

        //also deposit to linked rewards
        for (uint256 i = 0; i < extraRewards.length; i++) {
            IVirtualBalanceRewardPool(extraRewards[i]).deposit(
                msg.sender,
                _amount
            );
        }

        _totalSupply = _totalSupply + _amount;
        _balances[msg.sender] = _balances[msg.sender] + _amount;

        stakingToken.safeTransferFrom(msg.sender, address(this), _amount);
        emit Staked(msg.sender, _amount);

        return true;
    }

    function deposit() external returns (bool) {
        uint256 balance = Math.min(
            stakingToken.balanceOf(msg.sender),
            stakingToken.allowance(msg.sender, address(this))
        );
        deposit(balance);
        return true;
    }

    function depositFor(address _for, uint256 _amount)
        external
        updateReward(_for)
        returns (bool)
    {
        require(_amount > 0, "RewardPool : Cannot deposit 0");

        //also deposit to linked rewards
        for (uint256 i = 0; i < extraRewards.length; i++) {
            IVirtualBalanceRewardPool(extraRewards[i]).deposit(_for, _amount);
        }

        //give to _for
        _totalSupply = _totalSupply + _amount;
        _balances[_for] = _balances[_for] + _amount;

        //take away from sender
        stakingToken.safeTransferFrom(msg.sender, address(this), _amount);
        emit Staked(_for, _amount);
        return true;
    }

    function withdraw(
        uint256 amount,
        bool claim,
        bool lock
    ) public updateReward(msg.sender) returns (bool) {
        require(amount > 0, "RewardPool : Cannot withdraw 0");

        //also withdraw from linked rewards
        for (uint256 i = 0; i < extraRewards.length; i++) {
            IVirtualBalanceRewardPool(extraRewards[i]).withdraw(
                msg.sender,
                amount
            );
        }

        _totalSupply = _totalSupply - amount;
        _balances[msg.sender] = _balances[msg.sender] - amount;

        if (claim) {
            _getReward(msg.sender, lock, true);
        }

        stakingToken.safeTransfer(msg.sender, amount);
        emit Withdrawn(msg.sender, amount);

        return true;
    }

    function withdraw(bool _claim, bool _lock) external {
        withdraw(_balances[msg.sender], _claim, _lock);
    }

    function withdraw(bool _claim) external {
        withdraw(_balances[msg.sender], _claim, false);
    }

    function withdraw() external {
        withdraw(_balances[msg.sender], false, false);
    }

    /**
     * @notice
     *  Get rewards
     * @param _lock should the yfi be locked in veYFI
     * @param _claimExtras claim extra rewards
     */
    function getReward(bool _lock, bool _claimExtras)
        external
        updateReward(msg.sender)
        returns (bool)
    {
        _getReward(msg.sender, _lock, _claimExtras);
        return true;
    }

    function getReward(bool lock)
        external
        updateReward(msg.sender)
        returns (bool)
    {
        _getReward(msg.sender, lock, true);
        return true;
    }

    function getReward() external updateReward(msg.sender) returns (bool) {
        _getReward(msg.sender, false, true);
        return true;
    }

    function getRewardFor(address account, bool _claimExtras)
        external
        updateReward(account)
        returns (bool)
    {
        _getReward(account, false, _claimExtras);
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
                IVirtualBalanceRewardPool(extraRewards[i]).getReward(
                    msg.sender
                );
            }
        }
    }

    function donate(uint256 _amount) external returns (bool) {
        require(_amount != 0);
        IERC20(rewardToken).safeTransferFrom(
            msg.sender,
            address(this),
            _amount
        );
        queuedRewards = queuedRewards + _amount;
        return true;
    }

    function queueNewRewards(uint256 _rewards) external returns (bool) {
        require(_rewards != 0);
        IERC20(rewardToken).safeTransferFrom(
            msg.sender,
            address(this),
            _rewards
        );
        _rewards = _rewards + queuedRewards;

        _notifyRewardAmount(_rewards);
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

    function transferQueuedPenalty() public {
        uint256 toTransfer = queuedPenalty;
        queuedPenalty = 0;

        IERC20(rewardToken).safeApprove(veYfiRewardPool, toTransfer);
        IVeYfiRewardPool(veYfiRewardPool).donate(toTransfer);
    }

    function setRewardManager(address _rewardManager) external {
        require(
            msg.sender == rewardManager || msg.sender == gov,
            "!authorized"
        );

        require(_rewardManager != address(0));
        rewardManager = _rewardManager;
        emit UpdatedRewardManager(rewardManager);
    }

    function setGov(address _gov) external {
        require(msg.sender == gov, "!authorized");

        require(_gov != address(0));
        gov = _gov;
        emit UpdatedGov(_gov);
    }

    function sweep(address _token) external {
        require(msg.sender == gov, "!authorized");
        require(_token != address(stakingToken), "!stakingToken");
        require(_token != address(rewardToken), "!rewardToken");

        SafeERC20.safeTransfer(
            IERC20(_token),
            rewardManager,
            IERC20(_token).balanceOf(address(this))
        );
    }
}
