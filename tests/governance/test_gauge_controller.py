import ape
import pytest

WEEK_LENGTH = 7 * 24 * 60 * 60
EPOCH_LENGTH = 2 * WEEK_LENGTH
UNIT = 10**18
MAX = 2**256 - 1
ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'

@pytest.fixture
def gauge(accounts):
    return accounts[3]

@pytest.fixture
def gauge2(accounts):
    return accounts[4]

@pytest.fixture
def gauge3(accounts):
    return accounts[5]

@pytest.fixture
def epoch():
    return 4

@pytest.fixture
def genesis(chain, epoch):
    return chain.pending_timestamp - epoch * EPOCH_LENGTH

@pytest.fixture
def token(project, deployer):
    return project.dYFI.deploy(sender=deployer)

@pytest.fixture
def measure(project, deployer):
    return project.MockMeasure.deploy(sender=deployer)

@pytest.fixture
def minter(project, deployer, token):
    minter = project.MockMinter.deploy(token, sender=deployer)
    token.transferOwnership(minter, sender=deployer)
    return minter

@pytest.fixture
def burner(project, deployer, token):
    return project.Burner.deploy(token, sender=deployer)

@pytest.fixture
def controller(project, deployer, genesis, token, measure, minter, burner):
    controller = project.GaugeController.deploy(genesis, token, measure, minter, burner, sender=deployer)
    minter.set_controller(controller, sender=deployer)
    controller.update_emission(sender=deployer)
    return controller

def test_whitelist(chain, deployer, alice, bob, gauge, gauge2, controller):
    # whitelisting requires privileges
    controller.set_whitelister(alice, sender=deployer)
    with ape.reverts():
        controller.whitelist(gauge, True, sender=bob)

    assert not controller.gauge_whitelisted(gauge)
    controller.whitelist(gauge, True, sender=alice)
    assert controller.gauge_whitelisted(gauge)

    # cant whitelist during vote
    chain.pending_timestamp += WEEK_LENGTH
    with ape.reverts():
        controller.whitelist(gauge2, True, sender=alice)

def test_remove_whitelist_reserved(deployer, gauge, controller):
    controller.whitelist(gauge, True, sender=deployer)
    controller.set_reserved_points(gauge, 5_000, sender=deployer)
    assert controller.gauge_whitelisted(gauge)
    assert controller.reserved_points() == 5_000
    assert controller.gauge_reserved_points(gauge) == 5_000
    controller.whitelist(gauge, False, sender=deployer)
    assert not controller.gauge_whitelisted(gauge)
    assert controller.reserved_points() == 0
    assert controller.gauge_reserved_points(gauge) == 0

def test_vote(chain, deployer, alice, bob, gauge, gauge2, epoch, measure, controller):
    controller.whitelist(gauge, True, sender=deployer)
    measure.set_vote_weight(alice, 4 * UNIT, sender=deployer)
    measure.set_vote_weight(bob, 2 * UNIT, sender=deployer)

    # cant vote too early
    assert not controller.vote_open()
    with ape.reverts():
        controller.vote([gauge], [10_000], sender=alice)

    chain.pending_timestamp += WEEK_LENGTH
    chain.mine()

    assert controller.vote_open()
    assert controller.votes_available(alice) == 4 * UNIT
    assert controller.votes(epoch) == 0
    assert controller.votes_user(alice, epoch) == 0
    assert controller.gauge_votes(epoch, gauge) == 0
    assert controller.gauge_votes_user(alice, epoch, gauge) == 0
    controller.vote([gauge], [2_500], sender=alice)
    assert controller.votes_available(alice) == 3 * UNIT
    assert controller.votes(epoch) == UNIT
    assert controller.votes_user(alice, epoch) == UNIT
    assert controller.gauge_votes(epoch, gauge) == UNIT
    assert controller.gauge_votes_user(alice, epoch, gauge) == UNIT

    # cant vote more than weight
    with ape.reverts():
        controller.vote([gauge], [10_000], sender=alice)

    # cant vote on non-whitelisted gauge
    with ape.reverts():
        controller.vote([gauge2], [7_500], sender=alice)

    # votes on same gauge from same account are additive
    controller.vote([gauge], [7_500], sender=alice)
    assert controller.votes_available(alice) == 0
    assert controller.votes(epoch) == 4 * UNIT
    assert controller.votes_user(alice, epoch) == 4 * UNIT
    assert controller.gauge_votes(epoch, gauge) == 4 * UNIT
    assert controller.gauge_votes_user(alice, epoch, gauge) == 4 * UNIT

    # votes on same gauge from different account are additive
    controller.vote([gauge], [5_000], sender=bob)
    assert controller.votes_available(bob) == UNIT
    assert controller.votes(epoch) == 5 * UNIT
    assert controller.votes_user(bob, epoch) == UNIT
    assert controller.gauge_votes(epoch, gauge) == 5 * UNIT
    assert controller.gauge_votes_user(bob, epoch, gauge) == UNIT

def test_vote_multiple(chain, deployer, alice, gauge, gauge2, epoch, measure, controller):
    controller.whitelist(gauge, True, sender=deployer)
    controller.whitelist(gauge2, True, sender=deployer)
    measure.set_vote_weight(alice, 4 * UNIT, sender=deployer)
    
    chain.pending_timestamp += WEEK_LENGTH

    # cant vote more than weight
    with ape.reverts():
        controller.vote([gauge, gauge2], [7_500, 7_500], sender=alice)
    
    # vote for multiple gauges
    controller.vote([gauge, gauge2], [2_500, 7_500], sender=alice)
    assert controller.votes_available(alice) == 0
    assert controller.votes(epoch) == 4 * UNIT
    assert controller.votes_user(alice, epoch) == 4 * UNIT
    assert controller.gauge_votes(epoch, gauge) == UNIT
    assert controller.gauge_votes_user(alice, epoch, gauge) == UNIT
    assert controller.gauge_votes(epoch, gauge2) == 3 * UNIT
    assert controller.gauge_votes_user(alice, epoch, gauge2) == 3 * UNIT

def test_emission(chain, deployer, alice, gauge, gauge2, epoch, genesis, token, measure, minter, controller):
    controller.whitelist(gauge, True, sender=deployer)
    controller.whitelist(gauge2, True, sender=deployer)
    measure.set_vote_weight(alice, 4 * UNIT, sender=deployer)
    minter.set_mintable(epoch, 8 * UNIT, sender=deployer)

    chain.pending_timestamp += WEEK_LENGTH
    controller.vote([gauge, gauge2], [2_500, 7_500], sender=alice)
    chain.pending_timestamp += WEEK_LENGTH
    chain.mine()
    assert controller.epoch() == epoch + 1
    assert controller.emission() == (epoch - 1, 0, 0)
    assert controller.epoch_emission(epoch) == (0, 0)
    assert controller.gauge_emission(gauge) == (epoch - 1, 0, 0)
    assert controller.gauge_claimed(gauge) == 0
    assert token.balanceOf(gauge) == 0
    assert controller.claim(gauge, sender=deployer).return_value == \
        (2 * UNIT, 2 * UNIT, genesis + (epoch + 1) * EPOCH_LENGTH)
    assert controller.emission() == (epoch, 8 * UNIT, 8 * UNIT)
    assert controller.epoch_emission(epoch) == (8 * UNIT, 0)
    assert controller.gauge_emission(gauge) == (epoch, 2 * UNIT, 2 * UNIT)
    assert controller.gauge_claimed(gauge) == 2 * UNIT
    assert token.balanceOf(gauge) == 2 * UNIT

    # claiming again doesnt do anything
    assert controller.claim(gauge, sender=deployer).return_value == \
        (2 * UNIT, 2 * UNIT, genesis + (epoch + 1) * EPOCH_LENGTH)
    assert token.balanceOf(gauge) == 2 * UNIT

    # next epoch - amounts are properly updated
    chain.pending_timestamp += WEEK_LENGTH
    minter.set_mintable(epoch + 1, UNIT, sender=deployer)
    controller.vote([gauge], [10_000], sender=alice)
    chain.pending_timestamp += WEEK_LENGTH
    assert controller.claim(sender=gauge).return_value == \
        (3 * UNIT, UNIT, genesis + (epoch + 2) * EPOCH_LENGTH)
    assert controller.emission() == (epoch + 1, 9 * UNIT, UNIT)
    assert controller.epoch_emission(epoch + 1) == (UNIT, 0)
    assert controller.gauge_emission(gauge) == (epoch + 1, 3 * UNIT, UNIT)
    assert controller.gauge_claimed(gauge) == 3 * UNIT
    assert token.balanceOf(gauge) == 3 * UNIT

def test_emission_vote_gap(chain, deployer, alice, gauge, gauge2, epoch, genesis, token, measure, minter, controller):
    # no votes and update for an epoch works as expected
    controller.whitelist(gauge, True, sender=deployer)
    controller.whitelist(gauge2, True, sender=deployer)
    measure.set_vote_weight(alice, UNIT, sender=deployer)
    minter.set_mintable(epoch, UNIT, sender=deployer)
    minter.set_mintable(epoch + 1, 2 * UNIT, sender=deployer)
    minter.set_mintable(epoch + 2, 3 * UNIT, sender=deployer)

    chain.pending_timestamp += WEEK_LENGTH
    controller.vote([gauge], [10_000], sender=alice)
    chain.pending_timestamp += EPOCH_LENGTH
    controller.vote([gauge2], [10_000], sender=alice)
    chain.pending_timestamp += EPOCH_LENGTH
    controller.vote([gauge], [10_000], sender=alice)

    # voting for the gauge updates the emission but does not claim it
    assert controller.gauge_emission(gauge) == (epoch + 1, UNIT, 0)
    assert controller.gauge_claimed(gauge) == 0
    chain.pending_timestamp += EPOCH_LENGTH

    assert controller.claim(gauge, sender=deployer).return_value == \
        (4 * UNIT, 3 * UNIT, genesis + (epoch + 3) * EPOCH_LENGTH)
    assert controller.gauge_emission(gauge) == (epoch + 2, 4 * UNIT, 3 * UNIT)
    assert controller.gauge_claimed(gauge) == 4 * UNIT
    assert token.balanceOf(gauge) == 4 * UNIT

def test_emission_reserved(chain, deployer, alice, gauge, gauge2, epoch, genesis, token, measure, minter, controller):
    controller.whitelist(gauge, True, sender=deployer)
    controller.whitelist(gauge2, True, sender=deployer)
    measure.set_vote_weight(alice, 2 * UNIT, sender=deployer)
    minter.set_mintable(epoch, 4 * UNIT, sender=deployer)
    minter.set_mintable(epoch + 1, 8 * UNIT, sender=deployer)
    
    # reserve 50%
    assert controller.reserved_points() == 0
    assert controller.gauge_reserved_points(gauge) == 0
    controller.set_reserved_points(gauge, 5_000, sender=deployer)
    assert controller.reserved_points() == 5_000
    assert controller.gauge_reserved_points(gauge) == 5_000

    # vote
    chain.pending_timestamp += WEEK_LENGTH
    controller.vote([gauge, gauge2], [5_000, 5_000], sender=alice)

    # amounts check out
    chain.pending_timestamp += WEEK_LENGTH
    assert controller.gauge_reserved_last_cumulative(gauge) == 0
    assert controller.claim(gauge, sender=deployer).return_value == \
        (3 * UNIT, 3 * UNIT, genesis + (epoch + 1) * EPOCH_LENGTH)
    assert controller.epoch_emission(epoch) == (4 * UNIT, 2 * UNIT)
    assert controller.gauge_reserved_last_cumulative(gauge) == 4 * UNIT
    assert controller.gauge_emission(gauge) == (epoch, 3 * UNIT, 3 * UNIT)
    assert token.balanceOf(gauge) == 3 * UNIT

    assert controller.claim(gauge2, sender=deployer).return_value == \
        (UNIT, UNIT, genesis + (epoch + 1) * EPOCH_LENGTH)
    assert controller.gauge_reserved_last_cumulative(gauge2) == 0
    assert controller.gauge_emission(gauge2) == (epoch, UNIT, UNIT)
    assert token.balanceOf(gauge2) == UNIT

    # next epoch - amounts are properly updated
    chain.pending_timestamp += WEEK_LENGTH
    controller.vote([gauge, gauge2], [7_500, 2_500], sender=alice)
    chain.pending_timestamp += WEEK_LENGTH

    assert controller.claim(gauge, sender=deployer).return_value == \
        (10 * UNIT, 7 * UNIT, genesis + (epoch + 2) * EPOCH_LENGTH)
    assert controller.epoch_emission(epoch + 1) == (8 * UNIT, 4 * UNIT)
    assert controller.gauge_reserved_last_cumulative(gauge) == 12 * UNIT
    assert controller.gauge_emission(gauge) == (epoch + 1, 10 * UNIT, 7 * UNIT)
    assert token.balanceOf(gauge) == 10 * UNIT

    assert controller.claim(gauge2, sender=deployer).return_value == \
        (2 * UNIT, UNIT, genesis + (epoch + 2) * EPOCH_LENGTH)
    assert controller.gauge_reserved_last_cumulative(gauge2) == 0
    assert controller.gauge_emission(gauge2) == (epoch + 1, 2 * UNIT, UNIT)
    assert token.balanceOf(gauge2) == 2 * UNIT

def test_emission_multiple_reserved(chain, deployer, alice, gauge, gauge2, gauge3, epoch, genesis, token, measure, minter, controller):
    controller.whitelist(gauge, True, sender=deployer)
    controller.whitelist(gauge2, True, sender=deployer)
    controller.whitelist(gauge3, True, sender=deployer)
    measure.set_vote_weight(alice, UNIT, sender=deployer)
    minter.set_mintable(epoch, 8 * UNIT, sender=deployer)
    
    # reserve 50% + 25%
    controller.set_reserved_points(gauge, 5_000, sender=deployer)
    controller.set_reserved_points(gauge2, 2_500, sender=deployer)
    assert controller.reserved_points() == 7_500
    assert controller.gauge_reserved_points(gauge) == 5_000
    assert controller.gauge_reserved_points(gauge2) == 2_500

    chain.pending_timestamp += WEEK_LENGTH
    controller.vote([gauge, gauge3], [5_000, 5_000], sender=alice)

    # amounts check out
    chain.pending_timestamp += WEEK_LENGTH
    assert controller.claim(gauge, sender=deployer).return_value == \
        (5 * UNIT, 5 * UNIT, genesis + (epoch + 1) * EPOCH_LENGTH)
    assert controller.epoch_emission(epoch) == (8 * UNIT, 6 * UNIT)
    assert controller.gauge_reserved_last_cumulative(gauge) == 8 * UNIT
    assert controller.gauge_emission(gauge) == (epoch, 5 * UNIT, 5 * UNIT)
    assert token.balanceOf(gauge) == 5 * UNIT

    assert controller.claim(gauge2, sender=deployer).return_value == \
        (2 * UNIT, 2 * UNIT, genesis + (epoch + 1) * EPOCH_LENGTH)
    assert controller.gauge_reserved_last_cumulative(gauge2) == 8 * UNIT
    assert controller.gauge_emission(gauge2) == (epoch, 2 * UNIT, 2 * UNIT)
    assert token.balanceOf(gauge2) == 2 * UNIT

    assert controller.claim(gauge3, sender=deployer).return_value == \
        (UNIT, UNIT, genesis + (epoch + 1) * EPOCH_LENGTH)
    assert controller.gauge_reserved_last_cumulative(gauge3) == 0
    assert controller.gauge_emission(gauge3) == (epoch, UNIT, UNIT)
    assert token.balanceOf(gauge3) == UNIT

def test_emission_reserved_gap(chain, deployer, alice, gauge, gauge2, epoch, genesis, token, measure, minter, controller):
    # no votes and update for an epoch for a gauge with reserved points works as expected
    controller.whitelist(gauge, True, sender=deployer)
    controller.whitelist(gauge2, True, sender=deployer)
    measure.set_vote_weight(alice, UNIT, sender=deployer)
    minter.set_mintable(epoch, 8 * UNIT, sender=deployer)
    minter.set_mintable(epoch + 1, 4 * UNIT, sender=deployer)
    
    # reserve 25%
    controller.set_reserved_points(gauge, 2_500, sender=deployer)

    chain.pending_timestamp += WEEK_LENGTH
    controller.vote([gauge, gauge2], [5_000, 5_000], sender=alice)

    chain.pending_timestamp += EPOCH_LENGTH
    controller.vote([gauge2], [10_000], sender=alice)

    # amounts check out
    chain.pending_timestamp += WEEK_LENGTH
    assert controller.claim(gauge, sender=deployer).return_value == \
        (6 * UNIT, UNIT, genesis + (epoch + 2) * EPOCH_LENGTH)
    assert controller.epoch_emission(epoch) == (8 * UNIT, 2 * UNIT)
    assert controller.gauge_reserved_last_cumulative(gauge) == 12 * UNIT
    assert controller.gauge_emission(gauge) == (epoch + 1, 6 * UNIT, UNIT)
    assert token.balanceOf(gauge) == 6 * UNIT

    assert controller.claim(gauge2, sender=deployer).return_value == \
        (6 * UNIT, 3 * UNIT, genesis + (epoch + 2) * EPOCH_LENGTH)
    assert controller.gauge_emission(gauge2) == (epoch + 1, 6 * UNIT, 3 * UNIT)
    assert token.balanceOf(gauge2) == 6 * UNIT

def test_blank_emission(chain, deployer, alice, gauge, epoch, token, measure, minter, burner, controller):
    controller.whitelist(gauge, True, sender=deployer)
    controller.set_blank_burn_points(2_500, sender=deployer)
    measure.set_vote_weight(alice, 4 * UNIT, sender=deployer)
    minter.set_mintable(epoch, 16 * UNIT, sender=deployer)
    minter.set_mintable(epoch + 1, UNIT, sender=deployer)

    # 75% blank vote
    chain.pending_timestamp += WEEK_LENGTH
    assert controller.blank_emission() == 0
    controller.vote([gauge, ZERO_ADDRESS], [2_500, 7_500], sender=alice)
    chain.pending_timestamp += WEEK_LENGTH

    controller.update_emission(sender=deployer)
    assert controller.epoch_emission(epoch) == (16 * UNIT, 0)
    assert controller.blank_emission() == 9 * UNIT
    assert burner.burned(controller) == 3 * UNIT
    assert token.balanceOf(controller) == 13 * UNIT

    # next epoch - blank emission is added
    chain.pending_timestamp += WEEK_LENGTH
    controller.vote([gauge], [10_000], sender=alice)
    chain.pending_timestamp += WEEK_LENGTH

    controller.update_emission(sender=deployer)
    assert controller.emission()[2] == 10 * UNIT
    assert controller.epoch_emission(epoch + 1) == (10 * UNIT, 0)
    assert controller.blank_emission() == 0

def test_no_votes(chain, deployer, alice, gauge, epoch, token, measure, minter, burner, controller):
    controller.whitelist(gauge, True, sender=deployer)
    controller.set_blank_burn_points(2_500, sender=deployer)
    measure.set_vote_weight(alice, 4 * UNIT, sender=deployer)
    minter.set_mintable(epoch, 4 * UNIT, sender=deployer)
    minter.set_mintable(epoch + 1, UNIT, sender=deployer)

    # no vote - everything counted as blank
    chain.pending_timestamp += EPOCH_LENGTH
    controller.update_emission(sender=deployer)
    assert controller.blank_emission() == 3 * UNIT
    assert burner.burned(controller) == UNIT
    assert token.balanceOf(controller) == 3 * UNIT

    # next epoch - blank emission is added
    chain.pending_timestamp += WEEK_LENGTH
    controller.vote([gauge], [10_000], sender=alice)
    chain.pending_timestamp += WEEK_LENGTH

    controller.update_emission(sender=deployer)
    assert controller.emission()[2] == 4 * UNIT
    assert controller.epoch_emission(epoch + 1) == (4 * UNIT, 0)
    assert controller.blank_emission() == 0

def test_set_reserved_points(chain, deployer, alice, gauge, gauge2, controller):
    # cant set points for a non-whitelisted gauge
    with ape.reverts():
        controller.set_reserved_points(gauge, 500, sender=deployer)

    controller.whitelist(gauge, True, sender=deployer)
    controller.whitelist(gauge2, True, sender=deployer)

    # only management can set reserved points
    with ape.reverts():
        controller.set_reserved_points(gauge, 5_000, sender=alice)

    assert controller.reserved_points() == 0
    assert controller.gauge_reserved_points(gauge) == 0
    controller.set_reserved_points(gauge, 5_000, sender=deployer)
    assert controller.reserved_points() == 5_000
    assert controller.gauge_reserved_points(gauge) == 5_000

    # total cant sum up to >100%
    with ape.reverts():
        controller.set_reserved_points(gauge2, 6_000, sender=deployer)

    # cant set reserved points while vote is open
    chain.pending_timestamp += WEEK_LENGTH
    with ape.reverts():
        controller.set_reserved_points(gauge, 4_000, sender=deployer)

def test_set_blank_burn_points(chain, deployer, alice, gauge, gauge2, controller):
    # only management can set blank burn points
    with ape.reverts():
        controller.set_blank_burn_points(5_000, sender=alice)

    assert controller.blank_burn_points() == 0
    controller.set_blank_burn_points(5_000, sender=deployer)
    assert controller.blank_burn_points() == 5_000

    # cant burn >100%
    with ape.reverts():
        controller.set_blank_burn_points(11_000, sender=deployer)

    # cant set blank burn points while vote is open
    chain.pending_timestamp += WEEK_LENGTH
    with ape.reverts():
        controller.set_blank_burn_points(4_000, sender=deployer)

def test_set_legacy_gauge(chain, deployer, alice, bob, gauge, epoch, token, measure, minter, controller):
    # cant set legacy status of non-whitelisted gauge
    with ape.reverts():
        controller.set_legacy_gauge(gauge, True, sender=deployer)
    controller.whitelist(gauge, True, sender=deployer)

    # only manager can set legacy status
    with ape.reverts():
        controller.set_legacy_gauge(gauge, True, sender=alice)
    
    assert not controller.legacy_gauge(gauge)
    controller.set_legacy_gauge(gauge, True, sender=deployer)
    assert controller.legacy_gauge(gauge)
    
    measure.set_vote_weight(alice, 4 * UNIT, sender=deployer)
    minter.set_mintable(epoch, UNIT, sender=deployer)

    chain.pending_timestamp += WEEK_LENGTH
    controller.vote([gauge], [10_000], sender=alice)
    chain.pending_timestamp += WEEK_LENGTH
    
    # legacy gauges can only be claimed by operator
    controller.set_legacy_operator(alice, sender=deployer)
    with ape.reverts():
        controller.claim(gauge, bob, sender=bob)

    # claim
    controller.claim(gauge, bob, sender=alice)
    assert token.balanceOf(bob) == UNIT

def test_set_whitelister(deployer, alice, controller):
    # only management can set whitelister
    with ape.reverts():
        controller.set_whitelister(alice, sender=alice)

    assert controller.whitelister() == deployer
    controller.set_whitelister(alice, sender=deployer)
    assert controller.whitelister() == alice

def test_set_legacy_operator(deployer, alice, controller):
    # only management can set legacy operator
    with ape.reverts():
        controller.set_legacy_operator(alice, sender=alice)

    assert controller.legacy_operator() == deployer
    controller.set_legacy_operator(alice, sender=deployer)
    assert controller.legacy_operator() == alice

def test_set_measure(chain, deployer, alice, bob, measure, controller):
    # only management can set measure
    with ape.reverts():
        controller.set_measure(alice, sender=alice)

    assert controller.measure() == measure
    controller.set_measure(alice, sender=deployer)
    assert controller.measure() == alice

    # cant set measure while vote is open
    chain.pending_timestamp += WEEK_LENGTH
    with ape.reverts():
        controller.set_measure(bob, sender=deployer)

def test_set_minter(deployer, alice, minter, controller):
    # only management can set minter
    with ape.reverts():
        controller.set_minter(alice, sender=alice)

    assert controller.minter() == minter
    controller.set_minter(alice, sender=deployer)
    assert controller.minter() == alice

def test_set_burner(deployer, alice, burner, controller):
    # only management can set burner
    with ape.reverts():
        controller.set_burner(alice, sender=alice)

    assert controller.burner() == burner
    controller.set_burner(alice, sender=deployer)
    assert controller.burner() == alice

def test_transfer_management(deployer, alice, bob, controller):
    assert controller.management() == deployer
    assert controller.pending_management() == ZERO_ADDRESS
    with ape.reverts():
        controller.set_management(alice, sender=alice)
    
    controller.set_management(alice, sender=deployer)
    assert controller.pending_management() == alice

    with ape.reverts():
        controller.accept_management(sender=bob)

    controller.accept_management(sender=alice)
    assert controller.management() == alice
    assert controller.pending_management() == ZERO_ADDRESS
