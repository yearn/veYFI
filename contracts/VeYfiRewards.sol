// SPDX-License-Identifier: MIT
pragma solidity 0.8.11;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";
import "./interfaces/IVotingEscrow.sol";

contract VeYfiRewards {
    using SafeERC20 for IERC20;

    IERC20 public rewardToken; // immutable immutable are breaking coverage software should be added back after.
    IVotingEscrow public veToken; // immutable
    uint256 public constant DURATION = 7 days;
    uint256 public periodFinish = 0;
    uint256 public rewardRate = 0;
    uint256 public lastUpdateTime;
    uint256 public rewardPerTokenStored;
    uint256 public queuedRewards = 0;
    uint256 public currentRewards = 0;
    uint256 public historicalRewards = 0;
    mapping(address => uint256) public userRewardPerTokenPaid;
    mapping(address => uint256) public rewards;

    event RewardAdded(uint256 reward);
    event RewardPaid(address indexed user, uint256 reward);

    constructor(address veToken_, address rewardToken_) {
        veToken = IVotingEscrow(veToken_);
        rewardToken = IERC20(rewardToken_);
    }

    function totalSupply() public view returns (uint256) {
        return veToken.totalSupply();
    }

    function balanceOf(address account) public view returns (uint256) {
        return veToken.balanceOf(account);
    }

    modifier _updateReward(address account) {
        rewardPerTokenStored = rewardPerToken();
        lastUpdateTime = lastTimeRewardApplicable();

        if (account != address(0)) {
            rewards[account] = _earnedReward(account);
            userRewardPerTokenPaid[account] = rewardPerTokenStored;
        }
        _;
    }

    function lastTimeRewardApplicable() public view returns (uint256) {
        return Math.min(block.timestamp, periodFinish);
    }

    function rewardPerToken() public view returns (uint256) {
        uint256 supply = totalSupply();
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
            (balanceOf(account) *
                (rewardPerToken() - userRewardPerTokenPaid[account])) /
            1e18 +
            rewards[account];
    }

    function earned(address account) external view returns (uint256) {
        return _earnedReward(account);
    }

    function updateReward(address _account)
        external
        _updateReward(_account)
        returns (bool)
    {
        require(msg.sender == address(veToken), "!authorized");

        return true;
    }

    function getReward(address _account, bool _lock)
        public
        _updateReward(_account)
        returns (bool)
    {
        uint256 reward = rewards[_account];
        rewards[_account] = 0;
        if (_lock) {
            SafeERC20.safeApprove(rewardToken, address(veToken), reward);
            veToken.deposit_for(msg.sender, reward);
        } else {
            SafeERC20.safeTransfer(rewardToken, _account, reward);
        }

        emit RewardPaid(_account, reward);
        return true;
    }

    function getReward(bool _stake) external returns (bool) {
        getReward(msg.sender, _stake);
        return true;
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

    function queueNewRewards(uint256 _amount) external returns (bool) {
        require(_amount != 0, "zero");
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
        _updateReward(address(0))
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
