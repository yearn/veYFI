# @version 0.3.10
"""
@title YFI Buyback Auction
@author 0xkorin, Yearn Finance
@license GNU AGPLv3
@notice
    Contract to run permissionless dutch auctions, selling WETH for YFI.
    Anyone can kick off an auction.
    Auctions take up to 24 hours and can take place at most once a week.
    Auction price starts very high and halves every hour, until the auction 
    sells out or the 24 hour passes.
    Any unsold WETH rolls over to the next auction.
"""

from vyper.interfaces import ERC20

interface WETH:
    def deposit(): payable

interface Taker:
    def auctionTakeCallback(_id: bytes32, _sender: address, _taken: uint256, _needed: uint256, _data: Bytes[1024]): nonpayable

# https://hackmd.io/@D4Z1faeARKedWmEygMxDBA/Syxo_HJqp
interface Auction:
    def auctionLength() -> uint256: view
    def auctionCooldown() -> uint256: view
    def auctionInfo(_id: bytes32) -> AuctionInfo: view
    def getAmountNeeded(_id: bytes32, _take: uint256, _ts: uint256) -> uint256: view
    def price(_id: bytes32, _ts: uint256) -> uint256: view
    def kickable(_id: bytes32) -> uint256: view
    def kick(_id: bytes32) -> uint256: nonpayable
    def take(_id: bytes32, _max: uint256, _recipient: address, _data: Bytes[1024]): nonpayable

implements: Auction

struct AuctionInfo:
    sell: address
    want: address
    kicked: uint256
    available: uint256

sell: immutable(ERC20)
want: immutable(ERC20)
management: public(address)
pending_management: public(address)
treasury: public(address)
kick_threshold: public(uint256)

kicked: uint256
available: uint256
start_price: uint256

# keccak("YFI buyback")
AUCTION_ID: constant(bytes32) = 0xc3c33f920aa7747069e32346c4430a2bef834d3f1334109ef63d0a2d36e0c7fb
SCALE: constant(uint256) = 10**18
DECAY_SCALE: constant(uint256) = 10**27
START_PRICE: constant(uint256) = 40_000 * SCALE
MINUTE_FACTOR: constant(uint256) = 988_514_020_352_896_135_356_867_505
MINUTE: constant(uint256) = 60
HOUR: constant(uint256) = 60 * MINUTE
DAY: constant(uint256) = 24 * HOUR
AUCTION_LENGTH: constant(uint256) = DAY
KICK_COOLDOWN: constant(uint256) = 7 * DAY

event AuctionEnabled:
    auction_id: bytes32
    sell: indexed(address)
    want: indexed(address)
    auction: indexed(address)

event AuctionKicked:
    auction_id: indexed(bytes32)
    available: uint256

event AuctionTaken:
    auction_id: indexed(bytes32)
    taken: uint256
    left: uint256

event SetTreasury:
    treasury: indexed(address)

event SetKickThreshold:
    threshold: uint256

event PendingManagement:
    management: indexed(address)

event SetManagement:
    management: indexed(address)

@external
def __init__(_weth: address, _want: address, _treasury: address, _threshold: uint256):
    """
    @notice Constructor
    @param _weth WETH address
    @param _want Want token address
    @param _treasury Treasury address, recipient of want tokens
    @param _threshold Threshold ETH amount to automatically kick an auction
    """
    sell = ERC20(_weth)
    want = ERC20(_want)
    self.management = msg.sender
    self.treasury = _treasury
    self.kick_threshold = _threshold
    log AuctionEnabled(AUCTION_ID, _weth, _want, self)

@external
@payable
def __default__():
    """
    @notice Receive ETH to be sold at a future auction
    @dev May kick an auction
    """
    assert msg.value > 0
    WETH(sell.address).deposit(value=self.balance)

    amount: uint256 = sell.balanceOf(self)
    if amount >= self.kick_threshold and block.timestamp >= self.kicked + KICK_COOLDOWN:
        self._kick(amount)

@external
@view
def auctionLength() -> uint256:
    """
    @notice Get maximum duration of an auction
    @return Maximum duration (seconds)
    """
    return AUCTION_LENGTH

@external
@view
def auctionCooldown() -> uint256:
    """
    @notice Get cooldown in between auction kicks
    @return Kick cooldown (seconds)
    """
    return KICK_COOLDOWN

@external
@view
def auctionInfo(_id: bytes32) -> AuctionInfo:
    """
    @notice Get information of an auction
    @param _id Auction identifier
    @return sell token, want token, last kick time, sell tokens available
    """
    assert _id == AUCTION_ID

    available: uint256 = self.available
    if block.timestamp >= self.kicked + AUCTION_LENGTH:
        available = 0

    return AuctionInfo({
        sell: sell.address,
        want: want.address,
        kicked: self.kicked,
        available: available
    })

@external
@view
def getAmountNeeded(_id: bytes32, _amount: uint256, _ts: uint256 = block.timestamp) -> uint256:
    """
    @notice Get amount of `want` needed to buy `_amount` of `sell` at time `_ts`
    @param _id Auction identifier
    @param _amount Amount of `sell` tokens to sell to the caller
    @param _ts Timestamp
    @return Amount of `want` tokens needed
    """
    price: uint256 = self._price(_ts)
    if _id != AUCTION_ID or _amount == 0 or price == 0:
        return 0
    return (_amount * price + SCALE - 1) / SCALE

@external
@view
def price(_id: bytes32, _ts: uint256 = block.timestamp) -> uint256:
    """
    @notice Get price of `sell` in terms of `want` at time `_ts`
    @param _id Auction identifier
    @param _ts Timestamp
    @return Price
    """
    if _id != AUCTION_ID:
        return 0
    return self._price(_ts)

@external
@view
def kickable(_id: bytes32) -> uint256:
    """
    @notice Amount of `sell` tokens that can be kicked
    @param _id Auction identifier
    @return Amount of `sell` tokens
    """
    if _id != AUCTION_ID or block.timestamp < self.kicked + KICK_COOLDOWN:
        return 0
    return sell.balanceOf(self)

@external
def kick(_id: bytes32) -> uint256:
    """
    @notice Kick off an auction
    @param _id Auction identifier
    @return Amount of `sell` tokens available
    """
    assert _id == AUCTION_ID
    assert block.timestamp >= self.kicked + KICK_COOLDOWN
    amount: uint256 = sell.balanceOf(self)
    assert amount > 0
    self._kick(amount)
    return amount

@external
@nonreentrant("take")
def take(_id: bytes32, _max: uint256 = max_value(uint256), _recipient: address = msg.sender, _data: Bytes[1024] = b""):
    """
    @notice Take up to `_max` of `sell` tokens at current price
    @param _id Auction identifier
    @param _max Maximum amount of `sell` tokens to take
    @param _recipient Recipient of `sell` tokens
    """
    assert _id == AUCTION_ID
    price: uint256 = self._price(block.timestamp)
    assert price > 0
    available: uint256 = self.available
    taken: uint256 = min(_max, available)
    assert taken > 0
    available -= taken
    needed: uint256 = (taken * price + SCALE - 1) / SCALE
    self.available = available

    assert sell.transfer(_recipient, taken, default_return_value=True)
    if len(_data) > 0:
        # callback to recipient if there's any additional data
        Taker(_recipient).auctionTakeCallback(_id, msg.sender, taken, needed, _data)

    assert want.transferFrom(msg.sender, self.treasury, needed, default_return_value=True)
    log AuctionTaken(AUCTION_ID, taken, available)

@external
def set_treasury(_treasury: address):
    """
    @notice Set new treasury address
    @param _treasury New treasury address
    @dev Treasury is recipient of `want` tokens from auctions
    @dev Only callable by management
    """
    assert msg.sender == self.management
    assert _treasury != empty(address)
    self.treasury = _treasury
    log SetTreasury(_treasury)

@external
def set_kick_threshold(_threshold: uint256):
    """
    @notice Set new kick threshold
    @param _threshold New threshold (18 decimals)
    @dev If an ETH transfer puts the balance over the threshold, a new
        auction is automatically kicked
    @dev Only callable by management
    """
    assert msg.sender == self.management
    self.kick_threshold = _threshold
    log SetKickThreshold(_threshold)

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
def _kick(_amount: uint256):
    """
    @notice Kick an auction
    """
    self.kicked = block.timestamp
    self.available = _amount
    self.start_price = START_PRICE * SCALE / _amount
    log AuctionKicked(AUCTION_ID, _amount)

@internal
@view
def _price(_ts: uint256) -> uint256:
    """
    @notice
        Calculates price as `start * (1/2)**h * (1/2)**(m/60)`
        Where `h` is the amount of hours since the start of the auction
        and `m` is the amout of minutes past the hour
    """
    t: uint256 = self.kicked
    if _ts < t or _ts >= t + AUCTION_LENGTH:
        return 0
    t = _ts - t

    m: uint256 = (t % HOUR) / MINUTE

    # (1/2)**(m/60)
    f: uint256 = DECAY_SCALE
    x: uint256 = MINUTE_FACTOR
    if m % 2 != 0:
        f = MINUTE_FACTOR

    for _ in range(7):
        m /= 2
        if m == 0:
            break
        x = x * x / DECAY_SCALE
        if m % 2 != 0:
            f = f * x / DECAY_SCALE

    return self.start_price * (DECAY_SCALE >> (t / HOUR)) / DECAY_SCALE * f / DECAY_SCALE
