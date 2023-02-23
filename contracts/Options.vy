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
VEYFI: immutable(address)
CURVE_POOL: immutable(CurvePoolInterface)
PRICE_FEED: immutable(AggregatorV3Interface)
DISCOUNT_TABLE: constant(uint16[500]) = [9156, 9149, 9142, 9134, 9127, 9119, 9112, 9104, 9096, 9089, 9081, 9073, 9065, 9057, 9049, 9041, 9033, 9024, 9016, 9008, 8999, 8991, 8982, 8974, 8965, 8956, 8947, 8939, 8930, 8921, 8912, 8902, 8893, 8884, 8875, 8865, 8856, 8846, 8837, 8827, 8817, 8807, 8797, 8787, 8777, 8767, 8757, 8747, 8736, 8726, 8716, 8705, 8694, 8684, 8673, 8662, 8651, 8640, 8629, 8618, 8607, 8595, 8584, 8573, 8561, 8549, 8538, 8526, 8514, 8502, 8490, 8478, 8466, 8454, 8441, 8429, 8417, 8404, 8391, 8379, 8366, 8353, 8340, 8327, 8314, 8301, 8287, 8274, 8261, 8247, 8233, 8220, 8206, 8192, 8178, 8164, 8150, 8136, 8121, 8107, 8093, 8078, 8063, 8049, 8034, 8019, 8004, 7989, 7974, 7959, 7943, 7928, 7913, 7897, 7881, 7866, 7850, 7834, 7818, 7802, 7786, 7770, 7753, 7737, 7720, 7704, 7687, 7670, 7654, 7637, 7620, 7603, 7585, 7568, 7551, 7533, 7516, 7498, 7481, 7463, 7445, 7427, 7409, 7391, 7373, 7355, 7336, 7318, 7300, 7281, 7262, 7244, 7225, 7206, 7187, 7168, 7149, 7130, 7110, 7091, 7072, 7052, 7033, 7013, 6993, 6974, 6954, 6934, 6914, 6894, 6873, 6853, 6833, 6813, 6792, 6772, 6751, 6730, 6710, 6689, 6668, 6647, 6626, 6605, 6584, 6563, 6542, 6521, 6499, 6478, 6456, 6435, 6413, 6392, 6370, 6348, 6326, 6304, 6283, 6261, 6239, 6217, 6194, 6172, 6150, 6128, 6105, 6083, 6061, 6038, 6016, 5993, 5971, 5948, 5925, 5903, 5880, 5857, 5834, 5811, 5789, 5766, 5743, 5720, 5697, 5674, 5651, 5628, 5604, 5581, 5558, 5535, 5512, 5488, 5465, 5442, 5419, 5395, 5372, 5348, 5325, 5302, 5278, 5255, 5231, 5208, 5185, 5161, 5138, 5114, 5091, 5067, 5044, 5020, 4997, 4973, 4950, 4926, 4903, 4879, 4856, 4832, 4809, 4786, 4762, 4739, 4715, 4692, 4668, 4645, 4622, 4598, 4575, 4552, 4528, 4505, 4482, 4459, 4436, 4412, 4389, 4366, 4343, 4320, 4297, 4274, 4251, 4228, 4205, 4182, 4159, 4137, 4114, 4091, 4068, 4046, 4023, 4001, 3978, 3956, 3933, 3911, 3888, 3866, 3844, 3822, 3799, 3777, 3755, 3733, 3711, 3689, 3668, 3646, 3624, 3602, 3581, 3559, 3538, 3516, 3495, 3474, 3452, 3431, 3410, 3389, 3368, 3347, 3326, 3305, 3284, 3264, 3243, 3223, 3202, 3182, 3161, 3141, 3121, 3101, 3081, 3061, 3041, 3021, 3001, 2981, 2962, 2942, 2923, 2903, 2884, 2865, 2846, 2827, 2808, 2789, 2770, 2751, 2732, 2714, 2695, 2677, 2658, 2640, 2622, 2604, 2586, 2568, 2550, 2532, 2514, 2497, 2479, 2462, 2444, 2427, 2410, 2392, 2375, 2358, 2342, 2325, 2308, 2291, 2275, 2258, 2242, 2226, 2209, 2193, 2177, 2161, 2145, 2130, 2114, 2098, 2083, 2067, 2052, 2037, 2022, 2006, 1991, 1976, 1962, 1947, 1932, 1918, 1903, 1889, 1874, 1860, 1846, 1832, 1818, 1804, 1790, 1776, 1762, 1749, 1735, 1722, 1709, 1695, 1682, 1669, 1656, 1643, 1630, 1617, 1605, 1592, 1579, 1567, 1555, 1542, 1530, 1518, 1506, 1494, 1482, 1470, 1458, 1447, 1435, 1424, 1412, 1401, 1390, 1378, 1367, 1356, 1345, 1334, 1324, 1313, 1302, 1292, 1281, 1271, 1260, 1250, 1240, 1229, 1219, 1209, 1199, 1189, 1180, 1170, 1160, 1151, 1141, 1132, 1122, 1113, 1104, 1094, 1085, 1076, 1067, 1058, 1049, 1041, 1032, 1023, 1015, 1006, 998, 989, 981, 973, 964, 956, 948, 940, 932, 924, 916, 909]
DISCOUNT_GRANULARITY : constant(uint256) = 500
DISCOUNT_NUMERATOR: constant(uint256) = 10_000
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
def __init__(yfi: address, o_yfi: address, ve_yfi: address, owner: address, price_feed: address, curve_pool: address):
    YFI = ERC20(yfi)
    OYFI = ERC20(o_yfi)
    VEYFI = ve_yfi
    PRICE_FEED = AggregatorV3Interface(price_feed)
    CURVE_POOL = CurvePoolInterface(curve_pool)
    self._transfer_ownership(owner)
    self.payee = owner


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

    total_supply: uint256 = YFI.totalSupply()
    total_locked: uint256 = YFI.balanceOf(VEYFI)
    discount: uint256 = 0 
    if total_locked == 0:
        discount = convert(DISCOUNT_TABLE[0], uint256)
    else:
        discount = convert(DISCOUNT_TABLE[total_locked * DISCOUNT_GRANULARITY / total_supply], uint256)

    return amount * eth_per_yfi  * discount / PRICE_DENOMINATOR / DISCOUNT_NUMERATOR


@external
@view
def get_latest_price() -> uint256:
    """
    @dev get the latest price of YFI in ETH
    @return price of YFI in ETH
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
    return price


@external
def set_payee(new_payee: address):
    """
    @dev set the payee of the ETH used to exercise options
    @param new_payee the new payee
    """
    self._check_owner()
    self.payee = new_payee

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
    token.transfer(self.owner, amount, default_return_value=True)
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
