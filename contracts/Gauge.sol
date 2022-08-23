// SPDX-License-Identifier: MIT
pragma solidity 0.8.15;

import "./interfaces/IExtraReward.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin-upgradeable/contracts/token/ERC20/ERC20Upgradeable.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";
import "./interfaces/IGauge.sol";
import "./BaseGauge.sol";

import "./interfaces/IVotingYFI.sol";

/** @title  Gauge stake vault token get YFI rewards
    @notice Deposit your vault token (one gauge per vault).
    YFI are paid based on the number of vault tokens, the veYFI balance, and the duration of the lock.
    @dev this contract is used behind multiple delegate proxies.
 */

contract Gauge is BaseGauge, ERC20Upgradeable, IGauge {
    using SafeERC20 for IERC20;

    struct Balance {
        uint256 realBalance;
        uint256 boostedBalance;
    }

    struct Approved {
        bool claim;
        bool lock;
    }

    uint256 public boostingFactor = 100;
    uint256 private constant BOOST_DENOMINATOR = 1000;

    IERC20 public asset;
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
    mapping(address => uint256) private _boostedBalances;
    mapping(address => mapping(address => Approved)) public approvedTo;

    //// @notice list of extraRewards pool.
    address[] public extraRewards;

    event AddedExtraReward(address indexed reward);
    event DeletedExtraRewards(address[] rewards);
    event UpdatedRewardManager(address indexed rewardManager);
    event UpdatedVeToken(address indexed ve);
    event TransferedQueuedPenalty(uint256 transfered);
    event UpdatedBoostingFactor(uint256 boostingFactor);
    event BoostedBalanceUpdated(address account, uint256 amount);

    event Initialize(
        address indexed asset,
        address indexed rewardToken,
        address indexed owner,
        address rewardManager,
        address ve,
        address veYfiRewardPool
    );

    /** @notice initialize the contract
     *  @dev Initialize called after contract is cloned.
     *  @param _asset The vault token to stake
     *  @param _rewardToken the reward token YFI
     *  @param _owner owner address
     *  @param _rewardManager reward manager address
     *  @param _ve veYFI address
     *  @param _veYfiRewardPool veYfiRewardPool address
     */
    function initialize(
        address _asset,
        address _rewardToken,
        address _owner,
        address _rewardManager,
        address _ve,
        address _veYfiRewardPool
    ) external initializer {
        require(address(_asset) != address(0x0), "_asset 0x0 address");
        require(address(_ve) != address(0x0), "_ve 0x0 address");
        require(
            address(_veYfiRewardPool) != address(0x0),
            "_veYfiRewardPool 0x0 address"
        );

        require(_rewardManager != address(0), "_rewardManager 0x0 address");

        __initialize(_rewardToken, _owner);
        asset = IERC20(_asset);
        __ERC20_init(
            string.concat("gauge ", IERC20Metadata(_asset).name()),
            string.concat("G", IERC20Metadata(_asset).symbol())
        );

        veToken = _ve;
        rewardManager = _rewardManager;
        veYfiRewardPool = _veYfiRewardPool;

        emit Initialize(
            _asset,
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
    function totalAssets() public view returns (uint256) {
        return totalSupply();
    }

    /**
        The amount of shares that the Vault would exchange for the amount of assets provided.
    */
    function convertToShares(uint256 _assets) public view returns (uint256) {
        return _assets;
    }

    /**
        The amount of assets that the Vault would exchange for the amount of shares provided.
    */
    function convertToAssets(uint256 _shares) public view returns (uint256) {
        return _shares;
    }

    /**
    Maximum amount of the underlying asset that can be deposited into the Vault for the receiver, through a deposit call.
    */
    function maxDeposit(address _receiver) public view returns (uint256) {
        return type(uint256).max;
    }

    /**
    Allows an on-chain or off-chain user to simulate the effects of their deposit at the current block, given current on-chain conditions.
    */
    function previewDeposit(uint256 _assets) public view returns (uint256) {
        return _assets;
    }

    /**
    Maximum amount of shares that can be minted from the Vault for the receiver, through a mint call.
    */
    function maxMint(address _receiver) public view returns (uint256) {
        return type(uint256).max;
    }

    /**
    Allows an on-chain or off-chain user to simulate the effects of their mint at the current block, given current on-chain conditions.
    */
    function previewMint(uint256 _shares) public view returns (uint256) {
        return _shares;
    }

    /** @param _account to look balance for
     *  @return amount of staked token for an account
     */
    function boostedBalanceOf(address _account)
        external
        view
        returns (uint256)
    {
        return _boostedBalances[_account];
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
        address[] memory toDelete = new address[](1);
        toDelete[0] = _extraReward;
        emit DeletedExtraRewards(toDelete);
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

    /** @notice
     *   Performs a snapshot of the account's accrued rewards since the previous update.
     *  @dev
     *   The snapshot made by this function depends on:
     *    1. The account's boosted balance
     *    2. The amount of reward emissions that have been added to the gauge since the
     *       account's rewards were last updated.
     *   Any function that mutates an account's balance, boostedBalance, userRewardPerTokenPaid,
     *   or rewards MUST call updateReward before performing the mutation.
     */
    function _updateReward(address _account) internal override {
        rewardPerTokenStored = _rewardPerToken();
        lastUpdateTime = lastTimeRewardApplicable();
        if (_account != address(0)) {
            if (_boostedBalances[_account] != 0) {
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

    function _beforeTokenTransfer(
        address _from,
        address _to,
        uint256
    ) internal override {
        if (_from != address(0)) {
            _updateReward(_from);
            //also deposit to linked rewards
            uint256 length = extraRewards.length;
            for (uint256 i = 0; i < length; ++i) {
                IExtraReward(extraRewards[i]).rewardCheckpoint(_from);
            }
        }
        if (_to != address(0)) {
            _updateReward(_to);
            //also deposit to linked rewards
            uint256 length = extraRewards.length;
            for (uint256 i = 0; i < length; ++i) {
                IExtraReward(extraRewards[i]).rewardCheckpoint(_to);
            }
        }
    }

    function _afterTokenTransfer(
        address _from,
        address _to,
        uint256
    ) internal override {
        if (_from != address(0)) {
            _boostedBalances[_from] = _boostedBalanceOf(_from);
            emit BoostedBalanceUpdated(_from, _boostedBalances[_from]);
        }
        if (_to != address(0)) {
            _boostedBalances[_to] = _boostedBalanceOf(_to);
            emit BoostedBalanceUpdated(_to, _boostedBalances[_to]);
        }
    }

    function _rewardPerToken() internal view override returns (uint256) {
        if (totalAssets() == 0) {
            return rewardPerTokenStored;
        }
        return
            rewardPerTokenStored +
            (((lastTimeRewardApplicable() - lastUpdateTime) *
                rewardRate *
                PRECISION_FACTOR) / totalAssets());
    }

    /** @notice The total undistributed earnings for an account.
     *  @dev Earnings are based on lock duration and boost
     *  @return
     *   Amount of tokens the account has earned that have yet to be distributed.
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

    /** @notice Calculates an account's earnings based on their boostedBalance.
     *   This function only reflects the accounts earnings since the last time
     *   the account's rewards were calculated via _updateReward.
     */
    function _newEarning(address _account)
        internal
        view
        override
        returns (uint256)
    {
        return
            (_boostedBalances[_account] *
                (_rewardPerToken() - userRewardPerTokenPaid[_account])) /
            PRECISION_FACTOR;
    }

    /** @notice Calculates an account's potential maximum earnings based on
     *   a maximum boost.
     *   This function only reflects the accounts earnings since the last time
     *   the account's rewards were calculated via _updateReward.
     */
    function _maxEarning(address _account) internal view returns (uint256) {
        return
            (balanceOf(_account) *
                (_rewardPerToken() - userRewardPerTokenPaid[_account])) /
            PRECISION_FACTOR;
    }

    /** @notice
     *   Calculates the boosted balance of based on veYFI balance.
     *  @dev
     *   This function expects this._totalAssets to be up to date.
     *  @return
     *   The account's boosted balance. Always lower than or equal to the
     *   account's real balance.
     */
    function nextBoostedBalanceOf(address _account)
        external
        view
        returns (uint256)
    {
        return _boostedBalanceOf(_account);
    }

    /** @notice
     *   Calculates the boosted balance of based on veYFI balance.
     *  @dev
     *    This function expects the account's _balances[_account].realBalance
     *    to be up to date.
     *  @dev This function expects this._totalAssets to be up to date.
     *  @return
     *   The account's boosted balance. Always lower than or equal to the
     *   account's real balance.
     */
    function _boostedBalanceOf(address _account)
        internal
        view
        returns (uint256)
    {
        return _boostedBalanceOf(_account, balanceOf(_account));
    }

    /** @notice
     *   Calculates the boosted balance of an account based on its gauge stake
     *   proportion & veYFI lock proportion.
     *  @dev This function expects this._totalAssets to be up to date.
     *  @param _account The account whose veYFI lock should be checked.
     *  @param _realBalance The amount of token _account has locked in the gauge.
     *  @return
     *   The account's boosted balance. Always lower than or equal to the
     *   account's real balance.
     */
    function _boostedBalanceOf(address _account, uint256 _realBalance)
        internal
        view
        returns (uint256)
    {
        uint256 veTotalSupply = IVotingYFI(veToken).totalSupply();
        if (veTotalSupply == 0) {
            return _realBalance;
        }
        return
            Math.min(
                ((_realBalance * boostingFactor) +
                    (((totalSupply() *
                        IVotingYFI(veToken).balanceOf(_account)) /
                        veTotalSupply) *
                        (BOOST_DENOMINATOR - boostingFactor))) /
                    BOOST_DENOMINATOR,
                _realBalance
            );
    }

    /** @notice deposit vault tokens into the gauge
     *  @dev a user without a veYFI should not lock.
     *  @dev will deposit the min between user balance and user approval
     *  @dev This call updates claimable rewards
     *  @return amount of assets deposited
     */
    function deposit() external returns (uint256) {
        uint256 balance = Math.min(
            asset.balanceOf(msg.sender),
            asset.allowance(msg.sender, address(this))
        );
        _deposit(balance, msg.sender);
        return balance;
    }

    /** @notice deposit vault tokens into the gauge
     *  @dev a user without a veYFI should not lock.
     *  @dev This call updates claimable rewards
     *  @param _assets of vault token
     *  @return amount  of assets deposited
     */
    function deposit(uint256 _assets) external returns (uint256) {
        _deposit(_assets, msg.sender);
        return _assets;
    }

    /** @notice deposit vault tokens into the gauge for a user
     *   @dev vault token is taken from msg.sender
     *   @dev This call update  `_for` claimable rewards
     *   @param _assets to deposit
     *   @param _receiver the account to deposit to
     *   @return true
     */
    function deposit(uint256 _assets, address _receiver)
        external
        returns (uint256)
    {
        _deposit(_assets, _receiver);
        return _assets;
    }

    /** @notice deposit vault tokens into the gauge for a user
     *   @dev vault token is taken from msg.sender
     *   @dev This call update  `_for` claimable rewards
     *   @dev shares and
     *   @param _shares to deposit
     *   @param _receiver the account to deposit to
     *   @return amount of shares transfered
     */
    function mint(uint256 _shares, address _receiver)
        external
        returns (uint256)
    {
        _deposit(_shares, _receiver);
        return _shares;
    }

    function _deposit(uint256 _assets, address _receiver) internal {
        require(_assets != 0, "Cannot deposit 0");

        //take away from sender
        asset.safeTransferFrom(msg.sender, address(this), _assets);

        // mint shares
        _mint(_receiver, _assets);

        emit Deposit(msg.sender, _receiver, _assets, _assets);
    }

    /**
      Maximum amount of the underlying asset that can be withdrawn from the owner balance in the Vault, through a withdraw call.
    */
    function maxWithdraw(address _owner) external view returns (uint256) {
        return balanceOf(_owner);
    }

    function previewWithdraw(uint256 _assets) external view returns (uint256) {
        return _assets;
    }

    /** @notice allow an address to lock and claim on your behalf
     * claim ermai
     *  @param _addr address to change approval for
     *  @param _canClaim can deposit
     *  @return true
     */
    function setApprovals(
        address _addr,
        bool _canClaim,
        bool _canLock
    ) external returns (bool) {
        approvedTo[_addr][msg.sender].claim = _canClaim;
        approvedTo[_addr][msg.sender].lock = _canLock;

        return true;
    }

    /** @notice Burns shares from owner and sends exactly assets of underlying tokens to receiver.
     *  @dev This call updates claimable rewards
     *  @param _assets amount to withdraw
     *  @param _receiver account that will recieve the shares
     *  @param _owner shares will be taken from account
     *  @param _lock should the claimed rewards be locked in veYFI for the user
     *  @param _claim claim veYFI and additional reward
     *  @return amount of shares withdrawn
     */
    function withdraw(
        uint256 _assets,
        address _receiver,
        address _owner,
        bool _claim,
        bool _lock
    ) external returns (uint256) {
        return _withdraw(_assets, _receiver, _owner, _claim, _lock);
    }

    /** @notice Burns shares from owner and sends exactly assets of underlying tokens to receiver.
     *  @dev This call updates claimable rewards
     *  @param _assets amount to withdraw
     *  @param _receiver account that will recieve the shares
     *  @param _owner shares will be taken from account
     *  @return amount of shares withdrawn
     */
    function withdraw(
        uint256 _assets,
        address _receiver,
        address _owner
    ) external returns (uint256) {
        return _withdraw(_assets, _receiver, _owner, false, false);
    }

    /** @notice withdraw all vault tokens from gauge
     *   @dev This call updates claimable rewards
     *   @param _claim claim veYFI and additional reward
     *   @param _lock should the claimed rewards be locked in veYFI for the user
     *  @return amount of shares withdrawn
     */
    function withdraw(bool _claim, bool _lock) external returns (uint256) {
        return
            _withdraw(
                balanceOf(msg.sender),
                msg.sender,
                msg.sender,
                _claim,
                _lock
            );
    }

    /** @notice withdraw all vault token from gauge
     *  @dev This call update claimable rewards
     *  @param _claim claim veYFI and additional reward
     *  @return amount of shares withdrawn
     */
    function withdraw(bool _claim) external returns (uint256) {
        return
            _withdraw(
                balanceOf(msg.sender),
                msg.sender,
                msg.sender,
                _claim,
                false
            );
    }

    /** @notice withdraw all vault token from gauge
     *  @dev This call update claimable rewards
     *  @return amount of shares withdrawn
     */
    function withdraw() external returns (uint256) {
        return
            _withdraw(
                balanceOf(msg.sender),
                msg.sender,
                msg.sender,
                false,
                false
            );
    }

    function _withdraw(
        uint256 _assets,
        address _receiver,
        address _owner,
        bool _claim,
        bool _lock
    ) internal returns (uint256) {
        require(_assets != 0, "Cannot withdraw 0");

        if (msg.sender != _owner) {
            _spendAllowance(_owner, msg.sender, _assets);
        }

        _burn(_owner, _assets);

        if (_claim) {
            if (_owner != msg.sender) {
                require(
                    approvedTo[msg.sender][_owner].claim,
                    "not allowed to claim"
                );
                require(
                    _lock == false || approvedTo[msg.sender][_owner].lock,
                    "not allowed to lock"
                );
            }

            _getReward(_owner, _lock, true);
        }

        asset.safeTransfer(_receiver, _assets);
        emit Withdraw(msg.sender, _receiver, _owner, _assets, _assets);

        return _assets;
    }

    function maxRedeem(address _owner) external view returns (uint256) {
        return balanceOf(_owner);
    }

    function previewRedeem(uint256 _assets) external view returns (uint256) {
        return _assets;
    }

    /** @notice Burns shares from owner and sends exactly assets of underlying tokens to receiver.
     *  @dev This call updates claimable rewards
     *  @param _assets amount to withdraw
     *  @param _receiver account that will recieve the shares
     *  @param _owner shares will be taken from account
     *  @return amount of shares withdrawn
     */
    function redeem(
        uint256 _assets,
        address _receiver,
        address _owner
    ) external override returns (uint256) {
        return _withdraw(_assets, _receiver, _owner, true, false);
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

    /** @notice Distributes the rewards for the specified account.
     *  @dev
     *   This function MUST NOT be called without the caller invoking
     *   updateReward(_account) first.
     */
    function _getReward(
        address _account,
        bool _lock,
        bool _claimExtras
    ) internal {
        uint256 boostedBalance = _boostedBalanceOf(_account);
        _boostedBalances[_account] = boostedBalance;
        emit BoostedBalanceUpdated(_account, boostedBalance);

        uint256 reward = rewards[_account];
        if (reward != 0) {
            rewards[_account] = 0;
            if (_lock) {
                rewardToken.approve(address(veToken), reward);
                IVotingYFI(veToken).modify_lock(reward, 0, _account);
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
        return _token != address(rewardToken) && _token != address(asset);
    }

    /**
    @notice Kick `addr` for abusing their boost
    @param _accounts Addresses to kick
    */
    function kick(address[] calldata _accounts) public {
        for (uint256 i = 0; i < _accounts.length; ++i) {
            _kick(_accounts[i]);
        }
    }

    function _kick(address _account) internal updateReward(_account) {
        uint256 balance = balanceOf(_account);
        require(
            _boostedBalances[_account] >
                (balance * boostingFactor) / BOOST_DENOMINATOR,
            "min boosted balance"
        );
        uint256 boostedBalance = _boostedBalanceOf(_account, balance);
        _boostedBalances[_account] = boostedBalance;
        emit BoostedBalanceUpdated(_account, boostedBalance);
    }
}
