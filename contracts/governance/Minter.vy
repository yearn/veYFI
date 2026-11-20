# @version 0.3.10
"""
@title Minter
@author 0xkorin, Yearn Finance
@license GNU AGPLv3
@notice
    Mints reward tokens for the gauge controller according to a predefined formula.
    Annualized emission is `c * sqrt(ve_supply)` and is recalculated every epoch.
"""

interface Token:
    def mint(_account: address, _amount: uint256): nonpayable
    def transferOwnership(_owner: address): nonpayable

interface VotingEscrow:
    def totalSupply(_ts: uint256) -> uint256: view

interface Minter:
    def mint(_epoch: uint256) -> uint256: nonpayable

implements: Minter

genesis: public(immutable(uint256))
token: public(immutable(Token))
voting_escrow: public(immutable(VotingEscrow))
management: public(address)
pending_management: public(address)
controller: public(address)
scaling_factor: public(uint256)
last_epoch: public(uint256)

event Mint:
    epoch: indexed(uint256)
    amount: uint256

event SetController:
    controller: indexed(address)

event SetScalingFactor:
    scaling_factor: uint256

event TransferTokenOwnership:
    owner: indexed(address)

event PendingManagement:
    management: indexed(address)

event SetManagement:
    management: indexed(address)

UNIT: constant(uint256) = 10**18
SCALE: constant(uint256) = 10_000
WEEK_LENGTH: constant(uint256) = 7 * 24 * 60 * 60
EPOCH_LENGTH: constant(uint256) = 2 * WEEK_LENGTH

@external
def __init__(_genesis: uint256, _token: address, _voting_escrow: address, _last_epoch: uint256):
    """
    @notice Constructor
    @param _genesis Genesis timestamp
    @param _token Address of token to be minted
    @param _voting_escrow Voting escrow address
    @param _last_epoch Last completed epoch prior to activation
    """
    genesis = _genesis
    token = Token(_token)
    voting_escrow = VotingEscrow(_voting_escrow)
    self.management = msg.sender
    self.last_epoch = _last_epoch
    self.scaling_factor = 12 * SCALE

@external
@view
def epoch() -> uint256:
    """
    @notice Get the current epoch
    @return Current epoch
    """
    return self._epoch()

@internal
@view
def _epoch() -> uint256:
    return (block.timestamp - genesis) / EPOCH_LENGTH

@external
@view
def preview(_epoch: uint256) -> uint256:
    """
    @notice Estimate tokens minted in a future epoch
    @param _epoch Epoch number
    @return Estimated tokens minted
    """
    assert _epoch > self.last_epoch
    return self._mintable(_epoch)

@external
def mint(_epoch: uint256) -> uint256:
    """
    @notice Mint tokens for a specific epoch
    @param _epoch Epoch number
    @return Amount of tokens minted
    @dev Only callable by gauge controller
    @dev Should only be called for a finished epoch
    @dev Should only be called in sequence
    """
    controller: address = self.controller
    assert msg.sender == controller
    assert _epoch == self.last_epoch + 1
    assert _epoch < self._epoch()

    self.last_epoch = _epoch
    minted: uint256 = self._mintable(_epoch)
    token.mint(controller, minted)
    log Mint(_epoch, minted)
    return minted

@internal
@view
def _mintable(_epoch: uint256) -> uint256:
    """
    @notice 
        Rewards for an epoch. Annual emission of `c * sqrt(ve_supply)`, 
        where `ve_supply` is evaluated at the end of the epoch
    """
    supply: uint256 = voting_escrow.totalSupply(genesis + (_epoch + 1) * EPOCH_LENGTH)
    return self.scaling_factor * self._sqrt(supply) * 14 / 365 / SCALE

@external
def set_controller(_controller: address):
    """
    @notice Set the new gauge controller
    @param _controller New gauge controller
    @dev Only callable by management
    """
    assert msg.sender == self.management
    assert _controller != empty(address)
    self.controller = _controller
    log SetController(_controller)

@external
def set_scaling_factor(_scaling_factor: uint256):
    """
    @notice Set the new scaling factor
    @param _scaling_factor New scaling factor
    @dev Should be between 4 and 64, inclusive
    @dev Only callable by management
    """
    assert msg.sender == self.management
    assert _scaling_factor >= 4 * SCALE and _scaling_factor <= 64 * SCALE
    assert self._epoch() == self.last_epoch + 1
    self.scaling_factor = _scaling_factor
    log SetScalingFactor(_scaling_factor)

@external
def transfer_token_ownership(_new: address):
    """
    @notice Transfer ownership of token ownership
    @param _new New token owner
    @dev Once this has been called, this contract will no longer be
        able to mint additional tokens
    @dev Only callable by management
    """
    assert msg.sender == self.management
    assert _new != empty(address)
    token.transferOwnership(_new)
    log TransferTokenOwnership(_new)

@external
def set_management(_management: address):
    """
    @notice 
        Set the pending management address.
        Needs to be accepted by that account separately to transfer management over
    @param _management New pending management address
    """
    assert msg.sender == self.management
    self.pending_management = _management
    log PendingManagement(_management)

@external
def accept_management():
    """
    @notice 
        Accept management role.
        Can only be called by account previously marked as pending management by current management
    """
    assert msg.sender == self.pending_management
    self.pending_management = empty(address)
    self.management = msg.sender
    log SetManagement(msg.sender)

@internal
@pure
def _sqrt(_x: uint256) -> uint256:
    """
    @notice 
        Calculate square root of a 18 decimal number, rounding down.
        Uses the Babylonian method: iteratively calculate `(r_i + x / r_i) / 2`, 
        which converges quadratically to `r = sqrt(x)`.
        Based on implementation in https://github.com/PaulRBerg/prb-math
    """
    if _x == 0:
        return 0

    # sqrt(x * 10**18 * 10**18) = sqrt(x) * 10**18
    x: uint256 = unsafe_mul(_x, UNIT)

    # find first bit
    r: uint256 = 1
    if x >= 1 << 128:
        x = x >> 128
        r = r << 64
    if x >= 1 << 64:
        x = x >> 64
        r = r << 32
    if x >= 1 << 32:
        x = x >> 32
        r = r << 16
    if x >= 1 << 16:
        x = x >> 16
        r = r << 8
    if x >= 1 << 8:
        x = x >> 8
        r = r << 4
    if x >= 1 << 4:
        x = x >> 4
        r = r << 2
    if x >= 1 << 2:
        r = r << 1
    
    # iterate 7 times to get 2**7 = 128 bit accuracy
    x = unsafe_mul(_x, UNIT)
    r = unsafe_add(r, unsafe_div(x, r)) >> 1
    r = unsafe_add(r, unsafe_div(x, r)) >> 1
    r = unsafe_add(r, unsafe_div(x, r)) >> 1
    r = unsafe_add(r, unsafe_div(x, r)) >> 1
    r = unsafe_add(r, unsafe_div(x, r)) >> 1
    r = unsafe_add(r, unsafe_div(x, r)) >> 1
    r = unsafe_add(r, unsafe_div(x, r)) >> 1

    d: uint256 = x / r
    if r >= d:
        return d
    return r
