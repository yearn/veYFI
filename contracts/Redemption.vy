# @version 0.3.7

from vyper.interfaces import ERC20
import interfaces.AggregatorV3Interface as AggregatorV3Interface

interface IDYFI:
    def burn(owner: address, amount: uint256): nonpayable

interface CurvePoolInterface:
    def price_oracle() -> uint256: view

UNIT: constant(uint256) = 10**18
SLIPPAGE_TOLERANCE: constant(uint256) = 3
SLIPPAGE_DENOMINATOR: constant(uint256) = 1000

DYFI: immutable(IDYFI)
YFI: immutable(ERC20)
VEYFI: immutable(ERC20)
CURVE_POOL: immutable(CurvePoolInterface)
PRICE_FEED: immutable(AggregatorV3Interface)

# @dev Returns the address of the current owner.
owner: public(address)
# @dev Returns the address of the pending owner.
pending_owner: public(address)
# @dev when the contract is killed, redemptions aren't possible
killed: public(bool)
# @dev recipient of the ETH used for redemptions
payee: public(address)
# @dev scaling factor parameters packed into a single slot
packed_scaling_factor: uint256

# @dev Emitted when contract is killed
event Killed:
    yfi_recovered: uint256

event Sweep:
    token: indexed(address)
    amount: uint256

# @dev Emitted when the ownership transfer from
# `previous_owner` to `pending_owner` is initiated.
event PendingOwnershipTransfer:
    previous_owner: indexed(address)
    pending_owner: indexed(address)


# @dev Emitted when the ownership is transferred
# from `previous_owner` to `new_owner`.
event OwnershipTransferred:
    previous_owner: indexed(address)
    new_owner: indexed(address)

event SetPayee:
    payee: indexed(address)


MASK: constant(uint256) = 2**64 - 1

# powers of 10
E3: constant(int256)               = 1_000
E6: constant(int256)               = E3 * E3
E9: constant(int256)               = E3 * E6
E12: constant(int256)              = E3 * E9
E15: constant(int256)              = E3 * E12
E17: constant(int256)              = 100 * E15
E18: constant(int256)              = E3 * E15
E20: constant(int256)              = 100 * E18
MIN_NAT_EXP: constant(int256)      = -41 * E18
MAX_NAT_EXP: constant(int256)      = 130 * E18

# x_n = 2^(7-n), a_n = exp(x_n)
# in 20 decimals for n >= 2
X0: constant(int256)  = 128 * E18 # 18 decimals
A0: constant(int256)  = 38_877_084_059_945_950_922_200 * E15 * E18 # no decimals
X1: constant(int256)  = X0 / 2 # 18 decimals
A1: constant(int256)  = 6_235_149_080_811_616_882_910 * E6 # no decimals
X2: constant(int256)  = X1 * 100 / 2
A2: constant(int256)  = 7_896_296_018_268_069_516_100 * E12
X3: constant(int256)  = X2 / 2
A3: constant(int256)  = 888_611_052_050_787_263_676 * E6
X4: constant(int256)  = X3 / 2
A4: constant(int256)  = 298_095_798_704_172_827_474 * E3
X5: constant(int256)  = X4 / 2
A5: constant(int256)  = 5_459_815_003_314_423_907_810
X6: constant(int256)  = X5 / 2
A6: constant(int256)  = 738_905_609_893_065_022_723
X7: constant(int256)  = X6 / 2
A7: constant(int256)  = 271_828_182_845_904_523_536
X8: constant(int256)  = X7 / 2
A8: constant(int256)  = 164_872_127_070_012_814_685
X9: constant(int256)  = X8 / 2
A9: constant(int256)  = 128_402_541_668_774_148_407
X10: constant(int256) = X9 / 2
A10: constant(int256) = 11_331_4845_306_682_631_683
X11: constant(int256) = X10 / 2
A11: constant(int256) = 1_064_49_445_891_785_942_956

@external
def __init__(
    yfi: address, d_yfi: address, ve_yfi: address, owner: address, 
    price_feed: address, curve_pool: address, scaling_factor: uint256,
):
    YFI = ERC20(yfi)
    DYFI = IDYFI(d_yfi)
    VEYFI = ERC20(ve_yfi)
    PRICE_FEED = AggregatorV3Interface(price_feed)
    CURVE_POOL = CurvePoolInterface(curve_pool)
    self._transfer_ownership(owner)
    self.payee = owner
    self.packed_scaling_factor = shift(scaling_factor, 128) | shift(scaling_factor, 192)


@payable
@external
def redeem(amount: uint256, recipient: address = msg.sender) -> uint256:
    """
    @notice Redeem your dYFI for YFI using ETH.
    @dev Redemption tolerates a 0.3% negative or positive slippage.
    @param amount amount of dYFI to spend
    @param recipient of the exercised YFI
    """
    self._check_killed()
    assert YFI.balanceOf(self) >= amount, "not enough YFI"
    eth_required: uint256 = self._eth_required(amount)
    assert eth_required > 0
    tolerance: uint256 = eth_required * SLIPPAGE_TOLERANCE / SLIPPAGE_DENOMINATOR
    if msg.value < (eth_required - tolerance) or msg.value > (eth_required + tolerance):
        raise "price out of tolerance"
    DYFI.burn(msg.sender, amount)
    raw_call(self.payee, b"", value=msg.value)
    YFI.transfer(recipient, amount)
    return amount


@external
@view
def discount() -> uint256:
    """
    @notice Get the current dYFI redemption discount
    @return Redemption discount (18 decimals)
    """
    return self._discount()


@internal
@view
def _discount() -> uint256:
    yfi_supply: uint256 = YFI.totalSupply()
    veyfi_supply: uint256 = VEYFI.totalSupply()
    x: int256 = convert(veyfi_supply * UNIT / yfi_supply, int256)
    x = self._exp(47 * (self._scaling_factor()[0] * x / E18 - E18) / 10)
    return convert(E18 * E18 / (E18 + 10 * x), uint256)


@external
@view
def eth_required(amount: uint256) -> uint256:
    """
    @notice Estimate the required amount of ETH to redeem the amount of dYFI for YFI
    @param amount Amount of dYFI
    @return Amount of ETH required
    """
    return self._eth_required(amount)


@internal
@view
def _eth_required(amount: uint256) -> uint256:
    return amount * self._get_latest_price() / UNIT * (UNIT - self._discount()) / UNIT


@external
@view
def get_latest_price() -> uint256:
    """
    @notice Get the latest price of YFI in ETH
    @return Price of YFI in ETH (18 decimals)
    """
    return self._get_latest_price()


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
    assert updated_at + 86400 > block.timestamp, "price too old"
    return price


@external
@view
def scaling_factor() -> uint256:
    """
    @notice Get the current discount curve scaling factor
    @return Scaling factor (18 decimals)
    """
    return convert(self._scaling_factor()[0], uint256)

@external
@view
def scaling_factor_ramp() -> (uint256, uint256, uint256, uint256):
    """
    @notice Get the current discount curve scaling factor ramp parameters
    @return Tuple of ramp start timestamp, ramp end timestamp, ramp start scaling factor, ramp end scaling factor
    """
    ramp_start: uint256 = 0
    ramp_end: uint256 = 0
    old: int256 = 0
    new: int256 = 0
    ramp_start, ramp_end, old, new = self._unpack_scaling_factor(self.packed_scaling_factor)
    return ramp_start, ramp_end, convert(old, uint256), convert(new, uint256)


@internal
@view
def _scaling_factor() -> (int256, bool):
    ramp_start: uint256 = 0
    ramp_end: uint256 = 0
    old: int256 = 0
    new: int256 = 0
    ramp_start, ramp_end, old, new = self._unpack_scaling_factor(self.packed_scaling_factor)
    if ramp_end <= block.timestamp:
        return new, False
    if ramp_start > block.timestamp:
        return old, False
    
    duration: int256 = convert(ramp_end - ramp_start, int256)
    time: int256 = convert(block.timestamp - ramp_start, int256)
    return old + (new - old) * time / duration, True


@external
def set_payee(new_payee: address):
    """
    @dev set the payee of the ETH used for redemptions
    @param new_payee the new payee
    """
    self._check_owner()
    assert new_payee != empty(address)
    self.payee = new_payee
    log SetPayee(new_payee)


@external
def start_ramp(new: uint256, duration: uint256 = 604_800, start: uint256 = block.timestamp):
    """
    @notice Start ramping of scaling factor
    @param new New scaling factor (18 decimals)
    @param duration Ramp duration (seconds)
    @param start Ramp start timestamp
    """
    self._check_owner()
    assert new >= UNIT and new <= 12 * UNIT
    assert start >= block.timestamp
    scaling_factor: int256 = 0
    active: bool = False
    scaling_factor, active = self._scaling_factor()
    assert not active
    self.packed_scaling_factor = self._pack_scaling_factor(
        start, start + duration, scaling_factor, convert(new, int256)
    )

@external
def stop_ramp():
    """
    @notice Stop a currently active ramp
    """
    self._check_owner()
    scaling_factor: int256 = 0
    active: bool = False
    scaling_factor, active = self._scaling_factor()
    assert active
    self.packed_scaling_factor = self._pack_scaling_factor(0, 0, scaling_factor, scaling_factor)


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
def sweep(token: address) -> uint256:
    assert self.killed or token != YFI.address, "protected token"
    amount: uint256 = 0
    if token == empty(address):
        amount = self.balance
        raw_call(self.owner, b"", value=amount)
    else:
        amount = ERC20(token).balanceOf(self)
        assert ERC20(token).transfer(self.owner, amount, default_return_value=True)
    log Sweep(token, amount)
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
    log PendingOwnershipTransfer(self.owner, new_owner)


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


@internal
@pure
def _pack_scaling_factor(_ramp_start: uint256, _ramp_end: uint256, _old: int256, _new: int256) -> uint256:
    assert _ramp_start <= MASK and _ramp_end <= MASK
    assert _old <= convert(MASK, int256) and _new > 0 and _new <= convert(MASK, int256)
    return _ramp_start | shift(_ramp_end, 64) | \
        shift(convert(_old, uint256), 128) | shift(convert(_new, uint256), 192)

@internal
@pure
def _unpack_scaling_factor(_packed: uint256) -> (uint256, uint256, int256, int256):
    return _packed & MASK, shift(_packed, -64) & MASK, \
        convert(shift(_packed, -128) & MASK, int256), convert(shift(_packed, -192), int256)

# From https://github.com/yearn/yETH/blob/main/contracts/Pool.vy, based on Balancer code

@internal
@pure
def _exp(_x: int256) -> int256:
    """
    @notice Calculate natural exponent `e^x`
    @param _x Exponent (18 decimals)
    @return Natural exponent in 18 decimals
    """
    assert _x >= MIN_NAT_EXP and _x <= MAX_NAT_EXP
    if _x < 0:
        # exp(-x) = 1/exp(x)
        return unsafe_mul(E18, E18) / self.__exp(-_x)
    return self.__exp(_x)

@internal
@pure
def __exp(_x: int256) -> int256:
    """
    @notice Calculate natural exponent `e^x`, assuming exponent is positive
    @param _x Exponent (18 decimals)
    @return Natural exponent in 18 decimals
    @dev Caller should perform bounds checks before calling this function
    """
    
    # e^x = e^(sum(k_n x_n) + rem)
    #     = product(e^(k_n x_n)) * e^(rem)
    #     = product(a_n^k_n) * e^(rem)
    # k_n = {0,1}, x_n = 2^(7-n), a_n = exp(x_n)
    x: int256 = _x

    # subtract out x_ns
    f: int256 = 1
    if x >= X0:
        x = unsafe_sub(x, X0)
        f = A0
    elif x >= X1:
        x = unsafe_sub(x, X1)
        f = A1

    # other terms are in 20 decimals
    x = unsafe_mul(x, 100)

    p: int256 = E20
    if x >= X2:
        x = unsafe_sub(x, X2)
        p = unsafe_div(unsafe_mul(p, A2), E20) # p * A2 / E20
    if x >= X3:
        x = unsafe_sub(x, X3)
        p = unsafe_div(unsafe_mul(p, A3), E20)
    if x >= X4:
        x = unsafe_sub(x, X4)
        p = unsafe_div(unsafe_mul(p, A4), E20)
    if x >= X5:
        x = unsafe_sub(x, X5)
        p = unsafe_div(unsafe_mul(p, A5), E20)
    if x >= X6:
        x = unsafe_sub(x, X6)
        p = unsafe_div(unsafe_mul(p, A6), E20)
    if x >= X7:
        x = unsafe_sub(x, X7)
        p = unsafe_div(unsafe_mul(p, A7), E20)
    if x >= X8:
        x = unsafe_sub(x, X8)
        p = unsafe_div(unsafe_mul(p, A8), E20)
    if x >= X9:
        x = unsafe_sub(x, X9)
        p = unsafe_div(unsafe_mul(p, A9), E20)
    
    # x < X9 (0.25), taylor series for remainder
    # c = e^x = sum(x^n / n!)
    n: int256 = x
    c: int256 = unsafe_add(E20, x)

    n = unsafe_div(unsafe_div(unsafe_mul(n, x), E20), 2) # n * x / E20 / 2
    c = unsafe_add(c, n)
    n = unsafe_div(unsafe_div(unsafe_mul(n, x), E20), 3)
    c = unsafe_add(c, n)
    n = unsafe_div(unsafe_div(unsafe_mul(n, x), E20), 4)
    c = unsafe_add(c, n)
    n = unsafe_div(unsafe_div(unsafe_mul(n, x), E20), 5)
    c = unsafe_add(c, n)
    n = unsafe_div(unsafe_div(unsafe_mul(n, x), E20), 6)
    c = unsafe_add(c, n)
    n = unsafe_div(unsafe_div(unsafe_mul(n, x), E20), 7)
    c = unsafe_add(c, n)
    n = unsafe_div(unsafe_div(unsafe_mul(n, x), E20), 8)
    c = unsafe_add(c, n)
    n = unsafe_div(unsafe_div(unsafe_mul(n, x), E20), 9)
    c = unsafe_add(c, n)
    n = unsafe_div(unsafe_div(unsafe_mul(n, x), E20), 10)
    c = unsafe_add(c, n)
    n = unsafe_div(unsafe_div(unsafe_mul(n, x), E20), 11)
    c = unsafe_add(c, n)
    n = unsafe_div(unsafe_div(unsafe_mul(n, x), E20), 12)
    c = unsafe_add(c, n)

    # p * c / E20 * f / 100
    return unsafe_div(unsafe_mul(unsafe_div(unsafe_mul(p, c), E20), f), 100)
