# @version 0.3.7

from vyper.interfaces import ERC20
import interfaces.AggregatorV3Interface as AggregatorV3Interface

interface IOYFI:
    def burn(owner: address, amount: uint256): nonpayable

interface CurvePoolInterface:
    def price_oracle() -> uint256: view

PRICE_DENOMINATOR: constant(uint256) = 10**18
SLIPPAGE_TOLERANCE: constant(uint256) = 3
SLIPPAGE_DENOMINATOR: constant(uint256) = 1000
DISCOUNT: constant(uint256) = 2

OYFI: immutable(ERC20)
YFI: immutable(ERC20)
CURVE_POOL: immutable(CurvePoolInterface)
PRICE_FEED: immutable(AggregatorV3Interface)

# @dev Returns the address of the current owner.
owner: public(address)
# @dev Returns the address of the pending owner.
pending_owner: public(address)
# @dev when the contrac is killed, exercising options isn't possible
killed: public(bool)
# @dev recipient of the ETH used to exercise options
payee: public(address)

# @dev Emitted when contract is killed
event Killed:
    yfi_recovered: uint256

event Sweep:
    token: address
    amount: uint256

# @dev Emitted when the ownership transfer from
# `previous_owner` to `new_owner` is initiated.
event OwnershipTransferStarted:
    previous_owner: indexed(address)
    new_owner: indexed(address)


# @dev Emitted when the ownership is transferred
# from `previous_owner` to `new_owner`.
event OwnershipTransferred:
    previous_owner: indexed(address)
    new_owner: indexed(address)


@external
def __init__(yfi: address, o_yfi: address, owner: address, price_feed: address, curve_pool: address):
    YFI = ERC20(yfi)
    OYFI = ERC20(o_yfi)
    PRICE_FEED = AggregatorV3Interface(price_feed)
    CURVE_POOL = CurvePoolInterface(curve_pool)
    self._transfer_ownership(owner)


@payable
@external
def exercise(amount: uint256, recipient: address = msg.sender) -> uint256:
    """
    @dev Exercise your oYFI for YFI using ETH.
    @notice Exercise tolerates a 0.3% negative or positive slippage.
    @param amount amount of oYFI to spend
    @param recipient of the exercised YFI
    """
    self._check_killed()
    assert YFI.balanceOf(self) >= amount, "not enough YFI"
    eth_required: uint256 = self._eth_required(amount)
    tolerance: uint256 = eth_required * SLIPPAGE_TOLERANCE / SLIPPAGE_DENOMINATOR
    if msg.value < (eth_required - tolerance) or msg.value > (eth_required + tolerance):
        raise "price out of tolerance"
    IOYFI(OYFI.address).burn(msg.sender, amount)
    send(self.payee, msg.value)
    YFI.transfer(recipient, amount)
    return amount


@external
@view
def eth_required(amount: uint256) -> uint256:
    """
    @dev estimate the required amount of ETH to excerice the amount of oYFI.
    @param amount of oYFI
    @return amount of ETH required
    """
    return self._eth_required(amount)


@internal
@view
def _eth_required(amount: uint256) -> uint256:
    eth_per_yfi: uint256 = self._get_latest_price()
    
    return amount * eth_per_yfi / PRICE_DENOMINATOR / DISCOUNT


@internal
@view
def _get_latest_price() -> uint256:
    oracle_price: uint256 = convert(self._get_oracle_price(), uint256)
    pool_price: uint256 = CURVE_POOL.price_oracle()
    if pool_price < oracle_price:
        return oracle_price
    return pool_price


@internal
@view
def _get_oracle_price() -> int256:
    round_id: uint80 = 0
    price: int256 = 0
    started_at: uint256 = 0
    updated_at: uint256 = 0
    answered_in_round: uint80 = 0
    (round_id, price, started_at, updated_at, answered_in_round) = PRICE_FEED.latestRoundData()
    return price


@external
def kill():
    """
    @dev stop the contract from being used and reclaim YFI
    """
    self._check_killed()
    self._check_owner()
    self.killed = True
    yfi_balance: uint256 = YFI.balanceOf(self)
    YFI.transfer(self.owner, yfi_balance)

    log Killed(yfi_balance)

@internal
def _check_killed():
    """
    @dev Throws if contract was killed
    """
    assert self.killed == False, "killed"

@external
def sweep(token: ERC20) -> uint256:
    assert self.killed or token != YFI, "protected token"
    amount: uint256 = token.balanceOf(self)
    token.transfer(self.owner, amount)
    log Sweep(token.address, amount)
    return amount

### Ownable2Step ###
@external
def transfer_ownership(new_owner: address):
    """
    @dev Starts the ownership transfer of the contract
         to a new account `new_owner`.
    @notice Note that this function can only be
            called by the current `owner`. Also, there is
            no security risk in setting `new_owner` to the
            zero address as the default value of `pending_owner`
            is in fact already the zero address and the zero
            address cannot call `accept_ownership`. Eventually,
            the function replaces the pending transfer if
            there is one.
    @param new_owner The 20-byte address of the new owner.
    """
    self._check_owner()
    self.pending_owner = new_owner
    log OwnershipTransferStarted(self.owner, new_owner)


@external
def accept_ownership():
    """
    @dev The new owner accepts the ownership transfer.
    @notice Note that this function can only be
            called by the current `pending_owner`.
    """
    assert self.pending_owner == msg.sender, "Ownable2Step: caller is not the new owner"
    self._transfer_ownership(msg.sender)


@internal
def _check_owner():
    """
    @dev Throws if the sender is not the owner.
    """
    assert msg.sender == self.owner, "Ownable2Step: caller is not the owner"


@internal
def _transfer_ownership(new_owner: address):
    """
    @dev Transfers the ownership of the contract
         to a new account `new_owner` and deletes
         any pending owner.
    @notice This is an `internal` function without
            access restriction.
    @param new_owner The 20-byte address of the new owner.
    """
    self.pending_owner = empty(address)
    old_owner: address = self.owner
    self.owner = new_owner
    log OwnershipTransferred(old_owner, new_owner)
