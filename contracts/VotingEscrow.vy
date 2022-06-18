# @version 0.3.3
"""
@title Voting Escrow
@author Curve Finance
@license MIT
@notice Votes have a weight depending on time, so that users are
        committed to the future of (whatever they are voting for)
@dev Vote weight decays linearly over time. Lock time cannot be
     more than `MAXTIME` (4 years).
     User can unlock funds with a penalty. The unlocker can remove 
     the lock for everyone. 
"""
from vyper.interfaces import ERC20

# Voting escrow to have time-weighted votes
# Votes have a weight depending on time, so that users are committed
# to the future of (whatever they are voting for).
# The weight in this implementation is linear, and lock cannot be more than maxtime:
# w ^
# 1 +        /
#   |      /
#   |    /
#   |  /
#   |/
# 0 +--------+------> time
#       maxtime (4 years?)

struct Point:
    bias: int128
    slope: int128  # - dweight / dt
    ts: uint256
    blk: uint256  # block
# We cannot really do block numbers per se b/c slope is per time, not per block
# and per block could be fairly bad b/c Ethereum changes blocktimes.
# What we can do is to extrapolate ***At functions

struct LockedBalance:
    amount: uint256
    end: uint256


interface IVeYfiRewards:
    def queueNewRewards(_amount: uint256) -> bool: nonpayable

DEPOSIT_FOR_TYPE: constant(int128) = 0
CREATE_LOCK_TYPE: constant(int128) = 1
INCREASE_LOCK_AMOUNT: constant(int128) = 2
INCREASE_UNLOCK_TIME: constant(int128) = 3

event Deposit:
    deposit_from: indexed(address)
    provider: indexed(address)
    value: uint256
    locktime: indexed(uint256)
    type: int128
    ts: uint256

event Withdraw:
    provider: indexed(address)
    value: uint256
    ts: uint256

event Penalty:
    provider: indexed(address)
    value: uint256
    ts: uint256

event Supply:
    prevSupply: uint256
    supply: uint256

event Initialized:
    token: address
    reward_pool: address

DAY: constant(uint256) = 86400
WEEK: constant(uint256) = 7 * 86400  # all future times are rounded by week
MAXTIME: constant(uint256) = 4 * 365 * 86400  # 4 years
SCALE: constant(uint256) = 10 ** 18
MAX_PENALTY_RATIO: constant(uint256) = SCALE * 3 / 4  # 75% for early exit of max lock

token: public(address)
supply: public(uint256)

locked: public(HashMap[address, LockedBalance])

epoch: public(uint256)
point_history: public(Point[100000000000000000000000000000])  # epoch -> unsigned point
user_point_history: public(HashMap[address, Point[1000000000]])  # user -> Point[user_epoch]
user_point_epoch: public(HashMap[address, uint256])
slope_changes: public(HashMap[uint256, int128])  # time -> signed slope change
queuedPenalty: public(uint256)
lastPenaltyTranfer: public(uint256)

reward_pool: public(address)

@external
def __init__(token_addr: address, reward_pool: address):
    """
    @notice Contract constructor
    @param token_addr YFI token address
    @param reward_pool Pool for early exit penalties
    """
    self.token = token_addr
    self.point_history[0].blk = block.number
    self.point_history[0].ts = block.timestamp

    log Initialized(token_addr, reward_pool)


@view
@external
def name() -> String[10]:
    return "Voting YFI"

@view
@external
def symbol() -> String[5]:
    return "veYFI"

@view
@external
def decimals() -> uint8:
    return 18

@external
@view
def get_last_user_slope(addr: address) -> int128:
    """
    @notice Get the most recently recorded rate of voting power decrease for `addr`
    @param addr Address of the user wallet
    @return Value of the slope
    """
    uepoch: uint256 = self.user_point_epoch[addr]
    return self.user_point_history[addr][uepoch].slope


@external
@view
def user_point_history__ts(_addr: address, _idx: uint256) -> uint256:
    """
    @notice Get the timestamp for checkpoint `_idx` for `_addr`
    @param _addr User wallet address
    @param _idx User epoch number
    @return Epoch time of the checkpoint
    """
    return self.user_point_history[_addr][_idx].ts


@external
@view
def locked__end(_addr: address) -> uint256:
    """
    @notice Get timestamp when `_addr`'s lock finishes
    @param _addr User wallet
    @return Epoch time of the lock end
    """
    return self.locked[_addr].end


@internal
def _checkpoint(addr: address, old_locked: LockedBalance, new_locked: LockedBalance):
    """
    @notice Record global and per-user data to checkpoint
    @param addr User's wallet address. No user checkpoint if 0x0
    @param old_locked Pevious locked amount / end lock time for the user
    @param new_locked New locked amount / end lock time for the user
    """
    u_old: Point = empty(Point)
    u_new: Point = empty(Point)
    old_dslope: int128 = 0
    new_dslope: int128 = 0
    _epoch: uint256 = self.epoch

    if addr != ZERO_ADDRESS:
        # Calculate slopes and biases
        # Kept at zero when they have to
        if old_locked.end > block.timestamp and old_locked.amount > 0:
            u_old.slope = convert(old_locked.amount / MAXTIME, int128)
            u_old.bias = u_old.slope * convert(old_locked.end - block.timestamp, int128)
        if new_locked.end > block.timestamp and new_locked.amount > 0:
            u_new.slope = convert(new_locked.amount / MAXTIME, int128)
            u_new.bias = u_new.slope * convert(new_locked.end - block.timestamp, int128)

        # Read values of scheduled changes in the slope
        # old_locked.end can be in the past and in the future
        # new_locked.end can ONLY by in the FUTURE unless everything expired: than zeros
        old_dslope = self.slope_changes[old_locked.end]
        if new_locked.end != 0:
            if new_locked.end == old_locked.end:
                new_dslope = old_dslope
            else:
                new_dslope = self.slope_changes[new_locked.end]

    last_point: Point = Point({bias: 0, slope: 0, ts: block.timestamp, blk: block.number})
    if _epoch > 0:
        last_point = self.point_history[_epoch]
    last_checkpoint: uint256 = last_point.ts
    # initial_last_point is used for extrapolation to calculate block number
    # (approximately, for *At methods) and save them
    # as we cannot figure that out exactly from inside the contract
    initial_last_point: Point = last_point
    block_slope: uint256 = 0  # dblock/dt
    if block.timestamp > last_point.ts:
        block_slope = SCALE * (block.number - last_point.blk) / (block.timestamp - last_point.ts)
    # If last point is already recorded in this block, slope=0
    # But that's ok b/c we know the block in such case

    # Go over weeks to fill history and calculate what the current point is
    t_i: uint256 = (last_checkpoint / WEEK) * WEEK
    for i in range(255):
        # Hopefully it won't happen that this won't get used in 5 years!
        # If it does, users will be able to withdraw but vote weight will be broken
        t_i += WEEK
        d_slope: int128 = 0
        if t_i > block.timestamp:
            t_i = block.timestamp
        else:
            d_slope = self.slope_changes[t_i]
        last_point.bias -= last_point.slope * convert(t_i - last_checkpoint, int128)
        last_point.slope += d_slope
        if last_point.bias < 0:  # This can happen
            last_point.bias = 0
        if last_point.slope < 0:  # This cannot happen - just in case
            last_point.slope = 0
        last_checkpoint = t_i
        last_point.ts = t_i
        last_point.blk = initial_last_point.blk + block_slope * (t_i - initial_last_point.ts) / SCALE
        _epoch += 1
        if t_i == block.timestamp:
            last_point.blk = block.number
            break
        else:
            self.point_history[_epoch] = last_point

    self.epoch = _epoch
    # Now point_history is filled until t=now

    if addr != ZERO_ADDRESS:
        # If last point was in this block, the slope change has been applied already
        # But in such case we have 0 slope(s)
        last_point.slope += (u_new.slope - u_old.slope)
        last_point.bias += (u_new.bias - u_old.bias)
        if last_point.slope < 0:
            last_point.slope = 0
        if last_point.bias < 0:
            last_point.bias = 0

    # Record the changed point into history
    self.point_history[_epoch] = last_point

    if addr != ZERO_ADDRESS:
        # Schedule the slope changes (slope is going down)
        # We subtract new_user_slope from [new_locked.end]
        # and add old_user_slope to [old_locked.end]
        if old_locked.end > block.timestamp:
            # old_dslope was <something> - u_old.slope, so we cancel that
            old_dslope += u_old.slope
            if new_locked.end == old_locked.end:
                old_dslope -= u_new.slope  # It was a new deposit, not extension
            self.slope_changes[old_locked.end] = old_dslope

        if new_locked.end > block.timestamp:
            if new_locked.end > old_locked.end:
                new_dslope -= u_new.slope  # old slope disappeared at this point
                self.slope_changes[new_locked.end] = new_dslope
            # else: we recorded it already in old_dslope

        # Now handle user history
        user_epoch: uint256 = self.user_point_epoch[addr] + 1

        self.user_point_epoch[addr] = user_epoch
        u_new.ts = block.timestamp
        u_new.blk = block.number
        self.user_point_history[addr][user_epoch] = u_new


@external
def checkpoint():
    """
    @notice Record global data to checkpoint
    """
    self._checkpoint(ZERO_ADDRESS, empty(LockedBalance), empty(LockedBalance))


@internal
def _deposit_for(_from: address, _addr: address, _value: uint256, unlock_time: uint256, locked_balance: LockedBalance, type: int128):
    """
    @notice Deposit and lock tokens for a user
    @param _from Address to take funds from 
    @param _addr User's wallet address
    @param _value Amount to deposit
    @param unlock_time New time when to unlock the tokens, or 0 if unchanged
    @param locked_balance Previous locked amount / timestamp
    """
    _locked: LockedBalance = locked_balance
    supply_before: uint256 = self.supply

    self.supply = supply_before + _value
    old_locked: LockedBalance = _locked
    # Adding to existing lock, or if a lock is expired - creating a new one
    _locked.amount += _value
    if unlock_time != 0:
        _locked.end = unlock_time
    self.locked[_addr] = _locked

    # Possibilities:
    # Both old_locked.end could be current or expired (>/< block.timestamp)
    # value == 0 (extend lock) or value > 0 (add to lock or extend lock)
    # _locked.end > block.timestamp (always)
    self._checkpoint(_addr, old_locked, _locked)

    if _value != 0:
        assert ERC20(self.token).transferFrom(_from, self, _value)

    log Deposit(_from, _addr, _value, _locked.end, type, block.timestamp)
    log Supply(supply_before, supply_before + _value)


@external
@nonreentrant('lock')
def deposit_for(_addr: address, _value: uint256):
    """
    @notice Deposit `_value` tokens for `_addr` and add to the lock
    @dev Anyone (even a smart contract) can deposit for someone else, but
         cannot extend their locktime and deposit for a brand new user
    @param _addr User's wallet address
    @param _value Amount to add to user's lock
    """
    _locked: LockedBalance = self.locked[_addr]

    assert _value > 0  # dev: need non-zero value
    assert _locked.amount > 0  # dev: no existing lock found
    assert _locked.end > block.timestamp  # dev: lock expired, call withdraw

    self._deposit_for(msg.sender, _addr, _value, 0, _locked, DEPOSIT_FOR_TYPE)

@external
@nonreentrant('lock')
def create_lock(_value: uint256, _unlock_time: uint256):
    """
    @notice Deposit `_value` tokens for `msg.sender` and lock until `_unlock_time`
    @param _value Amount to deposit
    @param _unlock_time Epoch time when tokens unlock, rounded down to whole weeks
    """
    unlock_time: uint256 = (_unlock_time / WEEK) * WEEK  # locktime is rounded down to weeks
    _locked: LockedBalance = self.locked[msg.sender]

    assert _value > 0  # dev: need non-zero value
    assert _locked.amount == 0  # dev: withdraw old tokens first
    assert unlock_time > block.timestamp  #  dev: unlock time must be in the future
    assert unlock_time <= block.timestamp + MAXTIME  # dev: voting lock can be 4 years max

    self._deposit_for(msg.sender, msg.sender, _value, unlock_time, _locked, CREATE_LOCK_TYPE)

@external
@nonreentrant('lock')
def increase_amount(_value: uint256):
    """
    @notice Deposit `_value` additional tokens for `msg.sender`
            without modifying the unlock time
    @param _value Amount of tokens to deposit and add to the lock
    """
    _locked: LockedBalance = self.locked[msg.sender]

    assert _value > 0  # dev: need non-zero value
    assert _locked.amount > 0  # dev: no existing lock found
    assert _locked.end > block.timestamp  # dev: lock expired, call withdraw

    self._deposit_for(msg.sender, msg.sender, _value, 0, _locked, INCREASE_LOCK_AMOUNT)


@external
@nonreentrant('lock')
def increase_unlock_time(_unlock_time: uint256):
    """
    @notice Extend the unlock time for `msg.sender` to `_unlock_time`
    @param _unlock_time New epoch time for unlocking
    """
    _locked: LockedBalance = self.locked[msg.sender]
    unlock_time: uint256 = (_unlock_time / WEEK) * WEEK  # Locktime is rounded down to weeks

    assert _locked.end > block.timestamp  # dev: lock expired
    assert _locked.amount > 0  # dev: nothing is locked
    assert unlock_time > _locked.end  # dev: can only increase lock duration
    assert unlock_time <= block.timestamp + MAXTIME  # dev: voting lock can be 4 years max

    self._deposit_for(msg.sender, msg.sender, 0, unlock_time, _locked, INCREASE_UNLOCK_TIME)


@external
@nonreentrant('lock')
def withdraw():
    """
    @notice Withdraw all tokens for `msg.sender`
    @dev Only possible if the lock has expired
    """
        
    old_locked: LockedBalance = self.locked[msg.sender]
    value: uint256 = convert(old_locked.amount, uint256)

    assert block.timestamp >= old_locked.end  # dev: the lock hasn't expired yet

    zero_locked: LockedBalance = LockedBalance({amount: 0, end: 0})
    self.locked[msg.sender] = zero_locked
    supply_before: uint256 = self.supply
    self.supply = supply_before - value

    # old_locked can have either expired <= timestamp or zero end
    # _locked has only 0 end
    # Both can have >= 0 amount
    self._checkpoint(msg.sender, old_locked, zero_locked)

    assert ERC20(self.token).transfer(msg.sender, value)

    log Withdraw(msg.sender, value, block.timestamp)
    log Supply(supply_before, supply_before - value)


@external
@nonreentrant('lock')
def force_withdraw():
    """
    @notice Withdraw all tokens for `msg.sender`
    @dev Will pay a penalty based on time.
    With a 4 years lock on withdraw, you pay 75% penalty during the first year.
    Penalty decrease linearly to zero starting when time left is under 3 years.
    """
    old_locked: LockedBalance = self.locked[msg.sender]
    assert block.timestamp < old_locked.end  # dev: lock expired
    
    time_left: uint256 = old_locked.end - block.timestamp

    value: uint256 = convert(old_locked.amount, uint256)

    zero_locked: LockedBalance = LockedBalance({amount: 0, end: 0})
    self.locked[msg.sender] = zero_locked
    supply_before: uint256 = self.supply
    self.supply = supply_before - value

    # old_locked can have either expired <= timestamp or zero end
    # _locked has only 0 end
    # Both can have >= 0 amount
    self._checkpoint(msg.sender, old_locked, zero_locked)
    
    penalty_ratio: uint256 = min(time_left * SCALE / MAXTIME, MAX_PENALTY_RATIO)
    penalty: uint256 = value * penalty_ratio / SCALE
    assert ERC20(self.token).transfer(msg.sender, value - penalty)
    
    # push the penalty to reward pool
    assert ERC20(self.token).approve(self.reward_pool, penalty)
    assert IVeYfiRewards(self.reward_pool).queueNewRewards(penalty)  # dev: penalty not queued
    log Penalty(msg.sender, penalty, block.timestamp)

    log Withdraw(msg.sender, value, block.timestamp)
    log Supply(supply_before, supply_before - value)

# The following ERC20/minime-compatible methods are not real balanceOf and supply!
# They measure the weights for the purpose of voting, so they don't represent
# real coins.

@internal
@view
def find_block_epoch(_block: uint256, max_epoch: uint256) -> uint256:
    """
    @notice Binary search to estimate timestamp for block number
    @param _block Block to find
    @param max_epoch Don't go beyond this epoch
    @return Approximate timestamp for block
    """
    # Binary search
    _min: uint256 = 0
    _max: uint256 = max_epoch
    for i in range(128):  # Will be always enough for 128-bit numbers
        if _min >= _max:
            break
        _mid: uint256 = (_min + _max + 1) / 2
        if self.point_history[_mid].blk <= _block:
            _min = _mid
        else:
            _max = _mid - 1
    return _min


@external
@view
def balanceOf(addr: address, _t: uint256 = block.timestamp) -> uint256:
    """
    @notice Get the current voting power for `msg.sender`
    @dev Adheres to the ERC20 `balanceOf` interface for Aragon compatibility
    @param addr User wallet address
    @param _t Epoch time to return voting power at
    @return User voting power
    """
    _epoch: uint256 = self.user_point_epoch[addr]
    if _epoch == 0:
        return 0

    upoint: Point = self.user_point_history[addr][_epoch]
    if upoint.ts > _t:
        # Binary search
        _min: uint256 = 0
        _max: uint256 = _epoch
        for i in range(128):  # Will be always enough for 128-bit numbers
            if _min >= _max:
                break
            _mid: uint256 = (_min + _max + 1) / 2
            if self.user_point_history[addr][_mid].ts <= _t:
                _min = _mid
            else:
                _max = _mid - 1

        upoint = self.user_point_history[addr][_min]
    upoint.bias -= upoint.slope * convert(_t - upoint.ts, int128)
    if upoint.bias < 0:
        upoint.bias = 0
    return convert(upoint.bias, uint256)

@external
@view
def balanceOfAt(addr: address, _block: uint256) -> uint256:
    """
    @notice Measure voting power of `addr` at block height `_block`
    @dev Adheres to MiniMe `balanceOfAt` interface: https://github.com/Giveth/minime
    @param addr User's wallet address
    @param _block Block to calculate the voting power at
    @return Voting power
    """
    assert _block <= block.number

    # Binary search
    _min: uint256 = 0
    _max: uint256 = self.user_point_epoch[addr]
    for i in range(128):  # Will be always enough for 128-bit numbers
        if _min >= _max:
            break
        _mid: uint256 = (_min + _max + 1) / 2
        if self.user_point_history[addr][_mid].blk <= _block:
            _min = _mid
        else:
            _max = _mid - 1

    upoint: Point = self.user_point_history[addr][_min]

    max_epoch: uint256 = self.epoch
    _epoch: uint256 = self.find_block_epoch(_block, max_epoch)
    point_0: Point = self.point_history[_epoch]
    d_block: uint256 = 0
    d_t: uint256 = 0
    if _epoch < max_epoch:
        point_1: Point = self.point_history[_epoch + 1]
        d_block = point_1.blk - point_0.blk
        d_t = point_1.ts - point_0.ts
    else:
        d_block = block.number - point_0.blk
        d_t = block.timestamp - point_0.ts
    block_time: uint256 = point_0.ts
    if d_block != 0:
        block_time += d_t * (_block - point_0.blk) / d_block

    upoint.bias -= upoint.slope * convert(block_time - upoint.ts, int128)
    if upoint.bias >= 0:
        return convert(upoint.bias, uint256)
    else:
        return 0


@internal
@view
def supply_at(point: Point, t: uint256) -> uint256:
    """
    @notice Calculate total voting power at some point in the past
    @param point The point (bias/slope) to start search from
    @param t Time to calculate the total voting power at
    @return Total voting power at that time
    """
    last_point: Point = point
    t_i: uint256 = (last_point.ts / WEEK) * WEEK
    for i in range(255):
        t_i += WEEK
        d_slope: int128 = 0
        if t_i > t:
            t_i = t
        else:
            d_slope = self.slope_changes[t_i]
        last_point.bias -= last_point.slope * convert(t_i - last_point.ts, int128)
        if t_i == t:
            break
        last_point.slope += d_slope
        last_point.ts = t_i

    if last_point.bias < 0:
        last_point.bias = 0
    return convert(last_point.bias, uint256)


@external
@view
def totalSupply(t: uint256 = block.timestamp) -> uint256:
    """
    @notice Calculate total voting power
    @dev Adheres to the ERC20 `totalSupply` interface for Aragon compatibility
    @return Total voting power
    """
    _epoch: uint256 = self.epoch
    last_point: Point = self.point_history[_epoch]
    return self.supply_at(last_point, t)


@external
@view
def totalSupplyAt(_block: uint256) -> uint256:
    """
    @notice Calculate total voting power at some point in the past
    @param _block Block to calculate the total voting power at
    @return Total voting power at `_block`
    """
    assert _block <= block.number
    _epoch: uint256 = self.epoch
    target_epoch: uint256 = self.find_block_epoch(_block, _epoch)

    point: Point = self.point_history[target_epoch]
    dt: uint256 = 0
    if target_epoch < _epoch:
        point_next: Point = self.point_history[target_epoch + 1]
        if point.blk != point_next.blk:
            dt = (_block - point.blk) * (point_next.ts - point.ts) / (point_next.blk - point.blk)
    else:
        if point.blk != block.number:
            dt = (_block - point.blk) * (block.timestamp - point.ts) / (block.number - point.blk)
    # Now dt contains info on how far are we beyond point

    return self.supply_at(point, point.ts + dt)   
