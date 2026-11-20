import ape
import pytest

AUCTION_ID = '0xc3c33f920aa7747069e32346c4430a2bef834d3f1334109ef63d0a2d36e0c7fb'
WETH = '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'
HOUR_LENGTH = 60 * 60
AUCTION_LENGTH = 24 * HOUR_LENGTH
KICK_COOLDOWN = 7 * 24 * HOUR_LENGTH
UNIT = 10**18
MAX = 2**256 - 1
ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'

@pytest.fixture
def treasury(accounts):
    return accounts[3]

@pytest.fixture()
def weth():
    return ape.Contract(WETH)

@pytest.fixture
def token(project, deployer):
    return project.MockToken.deploy(sender=deployer)

@pytest.fixture
def auction(project, deployer, treasury, weth, token):
    return project.BuybackAuction.deploy(weth, token, treasury, 3 * UNIT, sender=deployer)

def test_transfer(chain, alice, weth, token, auction):
    assert auction.auctionInfo(AUCTION_ID) == (weth, token, 0, 0)
    assert auction.kickable(AUCTION_ID) == 0
    
    # transfer ETH, doesnt kick the auction
    alice.transfer(auction, UNIT)
    assert weth.balanceOf(auction) == UNIT
    assert auction.auctionInfo(AUCTION_ID) == (weth, token, 0, 0)
    assert auction.kickable(AUCTION_ID) == UNIT

    # transfer enough ETH to kick an auction
    ts = chain.pending_timestamp
    alice.transfer(auction, 2 * UNIT)
    assert weth.balanceOf(auction) == 3 * UNIT
    assert auction.auctionInfo(AUCTION_ID) == (weth, token, ts, 3 * UNIT)

def test_kick(chain, alice, weth, token, auction):
    # cant kick without any funds
    with ape.reverts():
        auction.kick(AUCTION_ID, sender=alice)

    alice.transfer(auction, UNIT)
    assert auction.auctionInfo(AUCTION_ID) == (weth, token, 0, 0)
    assert auction.kickable(AUCTION_ID) == UNIT
    assert auction.getAmountNeeded(AUCTION_ID, UNIT) == 0
    assert auction.price(AUCTION_ID) == 0

    # cant kick other auction
    with ape.reverts():
        auction.kick(AUCTION_ID[:-1]+'c', sender=alice)
    
    # kick
    ts = chain.pending_timestamp
    assert auction.kick(AUCTION_ID, sender=alice).return_value == UNIT
    assert auction.auctionInfo(AUCTION_ID) == (weth, token, ts, UNIT)
    assert auction.kickable(AUCTION_ID) == 0
    assert auction.getAmountNeeded(AUCTION_ID, UNIT) == 40_000 * UNIT
    assert auction.price(AUCTION_ID) == 40_000 * UNIT

    # cant kick during auction
    with ape.reverts():
        assert auction.kick(AUCTION_ID, sender=alice)

    chain.pending_timestamp += AUCTION_LENGTH
    chain.mine()

    # auction over, kick still on cooldown
    assert auction.auctionInfo(AUCTION_ID) == (weth, token, ts, 0)
    assert auction.kickable(AUCTION_ID) == 0
    with ape.reverts():
        assert auction.kick(AUCTION_ID, sender=alice)

    # kick after cooldown
    chain.pending_timestamp += KICK_COOLDOWN
    chain.mine()
    assert auction.kickable(AUCTION_ID) == UNIT
    ts = chain.pending_timestamp
    assert auction.kick(AUCTION_ID, sender=alice).return_value == UNIT
    assert auction.auctionInfo(AUCTION_ID) == (weth, token, ts, UNIT)

def test_price(chain, alice, auction):
    alice.transfer(auction, UNIT)
    ts = chain.pending_timestamp
    auction.kick(AUCTION_ID, sender=alice)

    # price halves every hour
    assert auction.price(AUCTION_ID) == 40_000 * UNIT
    chain.pending_timestamp = ts + HOUR_LENGTH
    chain.mine()
    assert auction.price(AUCTION_ID) == 20_000 * UNIT
    chain.pending_timestamp = ts + 2 * HOUR_LENGTH
    chain.mine()
    assert auction.price(AUCTION_ID) == 10_000 * UNIT

    # price is constant within the minute
    chain.pending_timestamp = ts + 2 * HOUR_LENGTH + 30
    chain.mine()
    assert auction.price(AUCTION_ID) == 10_000 * UNIT

    # price goes down by factor `(1/2)**(1/60)` every minute
    for i in range(1, 60):
        expected = 10_000 * 0.5**(i/60)
        chain.pending_timestamp = ts + 2 * HOUR_LENGTH + 60 * i
        chain.mine()
        actual = auction.price(AUCTION_ID)/UNIT
        assert abs(actual-expected) < actual / 10**12

def test_take(chain, alice, bob, treasury, weth, token, auction):
    token.mint(alice, 100_000 * UNIT, sender=alice)
    token.approve(auction, MAX, sender=alice)

    kick = chain.pending_timestamp
    alice.transfer(auction, 5 * UNIT)
    
    ts = kick + 500
    chain.pending_timestamp = ts

    predict_price = auction.price(AUCTION_ID, ts)
    predict_cost = auction.getAmountNeeded(AUCTION_ID, 2 * UNIT, ts)
    
    # cant take from wrong auction
    with ape.reverts():
        auction.take(AUCTION_ID[:-1]+'c', 2 * UNIT, bob, sender=alice)

    # take
    cost = token.balanceOf(alice)
    auction.take(AUCTION_ID, 2 * UNIT, bob, sender=alice)
    cost -= token.balanceOf(alice)

    assert auction.auctionInfo(AUCTION_ID) == (weth, token, kick, 3 * UNIT)
    price = auction.price(AUCTION_ID)
    assert predict_price == price
    assert auction.getAmountNeeded(AUCTION_ID, 2 * UNIT) == cost
    assert predict_cost == cost
    assert cost == 2 * price
    assert token.balanceOf(treasury) == cost
    assert weth.balanceOf(bob) == 2 * UNIT

    # take all remaining
    chain.pending_timestamp += 5 * HOUR_LENGTH
    with chain.isolate():
        chain.mine()
        assert auction.price(AUCTION_ID) == price // 32

    cost2 = token.balanceOf(alice)
    auction.take(AUCTION_ID, MAX, sender=alice)
    cost2 -= token.balanceOf(alice)
    assert token.balanceOf(treasury) == cost + cost2
    assert weth.balanceOf(alice) == 3 * UNIT

def test_take_callback(chain, project, deployer, alice, treasury, weth, token, auction):
    token.mint(alice, 100_000 * UNIT, sender=alice)
    token.approve(auction, MAX, sender=alice)

    kick = chain.pending_timestamp
    alice.transfer(auction, 5 * UNIT)
    
    ts = kick + 12 * HOUR_LENGTH
    chain.pending_timestamp = ts

    cost = auction.getAmountNeeded(AUCTION_ID, 2 * UNIT, ts)
    data = b"123abc"

    callback = project.MockCallback.deploy(token, sender=deployer)
    callback.set_id(AUCTION_ID, sender=deployer)
    callback.set_sender(alice, sender=deployer)
    callback.set_taken(2 * UNIT, sender=deployer)
    callback.set_data(data, sender=deployer)

    # take
    auction.take(AUCTION_ID, 2 * UNIT, callback, sender=alice)
    assert token.balanceOf(treasury) == cost
    assert weth.balanceOf(callback) == 2 * UNIT

def test_set_treasury(deployer, alice, treasury, auction):
    # only management can set treasury
    with ape.reverts():
        auction.set_treasury(alice, sender=alice)

    assert auction.treasury() == treasury
    auction.set_treasury(alice, sender=deployer)
    assert auction.treasury() == alice

def test_set_kick_threshold(deployer, alice, auction):
    # only management can set kick threshold
    with ape.reverts():
        auction.set_kick_threshold(UNIT, sender=alice)

    assert auction.kick_threshold() == 3 * UNIT
    auction.set_kick_threshold(UNIT, sender=deployer)
    assert auction.kick_threshold() == UNIT


def test_transfer_management(deployer, alice, bob, auction):
    assert auction.management() == deployer
    assert auction.pending_management() == ZERO_ADDRESS
    with ape.reverts():
        auction.set_management(alice, sender=alice)
    
    auction.set_management(alice, sender=deployer)
    assert auction.pending_management() == alice

    with ape.reverts():
        auction.accept_management(sender=bob)

    auction.accept_management(sender=alice)
    assert auction.management() == alice
    assert auction.pending_management() == ZERO_ADDRESS
