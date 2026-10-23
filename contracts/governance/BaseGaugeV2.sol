// SPDX-License-Identifier: MIT
pragma solidity 0.8.15;
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import "../interfaces/IBaseGauge.sol";

abstract contract BaseGaugeV2 is IBaseGauge, OwnableUpgradeable {
    IERC20 public constant REWARD_TOKEN = IERC20(0x41252E8691e964f7DE35156B68493bAb6797a275);
    uint256 constant DURATION = 14 days;
    uint256 public periodFinish;
    uint256 public rewardRate;
    uint256 public lastUpdateTime;
    uint256 public rewardPerTokenStored;
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

    function _newEarning(address) internal view virtual returns (uint256);

    function _updateReward(address) internal virtual;

    function _rewardPerToken() internal view virtual returns (uint256);

    modifier updateReward(address account) {
        _updateReward(account);
        _;
    }

    function __initialize(address _owner) internal {
        require(_owner != address(0), "_owner 0x0 address");
        _transferOwnership(_owner);
    }

    /**
     *  @return timestamp until rewards are distributed
     */
    function lastTimeRewardApplicable() public view returns (uint256) {
        return Math.min(block.timestamp, periodFinish);
    }

    /** @notice reward per token deposited
     *  @dev gives the total amount of rewards distributed since the inception of the pool.
     *  @return rewardPerToken
     */
    function rewardPerToken() external view returns (uint256) {
        return _rewardPerToken();
    }

    function _protectedTokens(
        address _token
    ) internal view virtual returns (bool) {
        return _token == address(REWARD_TOKEN);
    }

    /** @notice sweep tokens that are airdropped/transferred into the gauge.
     *  @dev sweep can only be done on non-protected tokens.
     *  @return _token to sweep
     */
    function sweep(address _token) external onlyOwner returns (bool) {
        require(_protectedTokens(_token) == false, "protected token");
        uint256 amount = IERC20(_token).balanceOf(address(this));

        SafeERC20.safeTransfer(IERC20(_token), owner(), amount);
        emit Sweep(_token, amount);
        return true;
    }

    /** @notice earnings for an account
     *  @dev earnings are based on lock duration and boost
     *  @return amount of tokens earned
     */
    function earned(address _account) external view virtual returns (uint256) {
        return _newEarning(_account);
    }
}
