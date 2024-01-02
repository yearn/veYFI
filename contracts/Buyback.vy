# @version 0.3.10
"""
@title YFI Buyer
@license MIT
@author banteg, 0xkorin
@notice
    Buy YFI for ETH at the current Chainlink price.
"""
from vyper.interfaces import ERC20

YFI: constant(address) = 0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e
YFI_ETH: constant(address) = 0x3EbEACa272Ce4f60E800f6C5EE678f50D2882fd4

STALE_AFTER: constant(uint256) = 3600
EPOCH_LENGTH: constant(uint256) = 14 * 24 * 60 * 60
PRICE_SCALE: constant(uint256) = 10**18

admin: public(address)
treasury: public(address)

available: public(uint256)
epoch_end: public(uint256)
last_update: public(uint256)
rate: public(uint256)

struct ChainlinkRound:
    roundId: uint80
    answer: int256
    startedAt: uint256
    updatedAt: uint256
    answeredInRound: uint80

interface Chainlink:
    def latestRoundData() -> ChainlinkRound: view

event Buyback:
    buyer: indexed(address)
    yfi: uint256
    eth: uint256

event UpdateAdmin:
    admin: indexed(address)

event UpdateTreasury:
    treasury: indexed(address)


@external
def __init__(_epoch_end: uint256):
    assert _epoch_end > block.timestamp

    self.admin = msg.sender
    self.treasury = msg.sender
    self.last_update = block.timestamp
    self.epoch_end = _epoch_end
    
    log UpdateAdmin(msg.sender)
    log UpdateTreasury(msg.sender)


@external
@payable
@nonreentrant("buy")
def __default__():
    self._update()


@external
@nonreentrant("buy")
def buy_eth(yfi_amount: uint256, receiver: address = msg.sender):
    self._update()

    oracle: ChainlinkRound = Chainlink(YFI_ETH).latestRoundData()
    assert oracle.updatedAt + STALE_AFTER > block.timestamp  # dev: stale oracle

    eth_amount: uint256 = convert(oracle.answer, uint256) * yfi_amount / PRICE_SCALE
    self.available -= eth_amount

    assert ERC20(YFI).transferFrom(msg.sender, self.treasury, yfi_amount, default_return_value=True) # dev: no allowance
    raw_call(receiver, b"", value=eth_amount)

    log Buyback(msg.sender, yfi_amount, eth_amount)


@view
@external
def price() -> uint256:
    oracle: ChainlinkRound = Chainlink(YFI_ETH).latestRoundData()
    return convert(oracle.answer, uint256)


@view
@external
def total_eth() -> uint256:
    return self._available(0)[0]


@view
@external
def max_amount() -> uint256:
    available: uint256 = self._available(0)[0]
    oracle: ChainlinkRound = Chainlink(YFI_ETH).latestRoundData()
    return available * PRICE_SCALE / convert(oracle.answer, uint256)


@internal
@payable
def _update():
    self.available, self.rate, self.epoch_end = self._available(msg.value)
    self.last_update = block.timestamp


@internal
@view
def _available(_value: uint256) -> (uint256, uint256, uint256):
    ts: uint256 = block.timestamp
    end: uint256 = self.epoch_end
    if block.timestamp > end:
        ts = end
    available: uint256 = self.available
    rate: uint256 = self.rate
    available += (ts - self.last_update) * rate

    if block.timestamp >= end:
        amount: uint256 = self.balance - _value - available
        epochs: uint256 = (end - block.timestamp) / EPOCH_LENGTH
        end += (epochs + 1) * EPOCH_LENGTH
        if epochs == 0:
            rate = amount / EPOCH_LENGTH
            available += (block.timestamp + EPOCH_LENGTH - end) * rate
        else:
            rate = 0
            available += amount

    return available, rate, end


@external
def sweep(token: address, amount: uint256 = max_value(uint256)):
    assert msg.sender == self.admin
    value: uint256 = amount
    if token == empty(address):
        if value == max_value(uint256):
            value = self.balance
        raw_call(self.admin, b"", value=value)
    else:
        if value == max_value(uint256):
            value = ERC20(token).balanceOf(self)
        assert ERC20(token).transfer(self.admin, value, default_return_value=True)


@external
def set_admin(proposed_admin: address):
    assert msg.sender == self.admin
    self.admin = proposed_admin

    log UpdateAdmin(proposed_admin)


@external
def set_treasury(new_treasury: address):
    assert msg.sender == self.admin
    self.treasury = new_treasury

    log UpdateTreasury(new_treasury)
