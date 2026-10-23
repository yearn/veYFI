import pytest

DAY_LENGTH = 24 * 60 * 60
WEEK_LENGTH = 7 * DAY_LENGTH
EPOCH_LENGTH = 2 * WEEK_LENGTH
UNIT = 10**18
MAX = 2**256 - 1
ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'

@pytest.fixture
def locking_token(project, deployer):
    return project.MockToken.deploy(sender=deployer)

@pytest.fixture
def voting_escrow(project, deployer, locking_token):
    return project.VotingYFI.deploy(locking_token, ZERO_ADDRESS, sender=deployer)

@pytest.fixture
def genesis(chain):
    return chain.pending_timestamp // WEEK_LENGTH * WEEK_LENGTH

def test_measure(chain, project, deployer, alice, bob, locking_token, voting_escrow, genesis):
    locking_token.mint(alice, UNIT, sender=deployer)
    locking_token.mint(bob, 2 * UNIT, sender=deployer)
    locking_token.approve(voting_escrow, MAX, sender=alice)
    locking_token.approve(voting_escrow, MAX, sender=bob)
    voting_escrow.modify_lock(UNIT, chain.pending_timestamp + 50 * WEEK_LENGTH, sender=alice)
    voting_escrow.modify_lock(2 * UNIT, chain.pending_timestamp + 100 * WEEK_LENGTH, sender=bob)

    measure = project.Measure.deploy(genesis, voting_escrow, sender=deployer)

    chain.pending_timestamp += EPOCH_LENGTH
    chain.mine()

    total_weight = measure.total_vote_weight()
    weight = measure.vote_weight(alice)
    assert weight > 0 and total_weight > weight

    # forward to middle of epoch, when vote opens
    chain.pending_timestamp = genesis + EPOCH_LENGTH + WEEK_LENGTH
    chain.mine()
    assert voting_escrow.totalSupply() == total_weight
    assert voting_escrow.balanceOf(alice) == weight
    assert measure.total_vote_weight() == total_weight
    assert measure.vote_weight(alice) == weight
    
    # weights are constant throughout vote period
    chain.pending_timestamp += 2 * DAY_LENGTH
    chain.mine()
    assert voting_escrow.totalSupply() < total_weight
    assert voting_escrow.balanceOf(alice) < weight
    assert measure.total_vote_weight() == total_weight
    assert measure.vote_weight(alice) == weight

    # new epoch week after, meaning new weights
    chain.pending_timestamp += WEEK_LENGTH
    chain.mine()
    assert measure.total_vote_weight() < total_weight
    assert measure.vote_weight(alice) < weight

def test_decay(chain, project, deployer, alice, bob, locking_token, voting_escrow, genesis):
    locking_token.mint(alice, UNIT, sender=deployer)
    locking_token.approve(voting_escrow, MAX, sender=alice)
    voting_escrow.modify_lock(UNIT, chain.pending_timestamp + 50 * WEEK_LENGTH, sender=alice)
    chain.pending_timestamp += EPOCH_LENGTH

    measure = project.DecayMeasure.deploy(genesis, voting_escrow, sender=deployer)
    weight = measure.vote_weight(alice)
    assert weight > 0

    # 24h before end of epoch, voting power is full
    chain.pending_timestamp = genesis + 2 * EPOCH_LENGTH - DAY_LENGTH
    chain.mine()
    assert measure.vote_weight(alice) == weight

    # 12h before end of epoch, voting power is half
    chain.pending_timestamp = genesis + 2 * EPOCH_LENGTH - DAY_LENGTH // 2
    chain.mine()
    assert measure.vote_weight(alice) == weight // 2

    # 6h before end of epoch, voting power is a quarter
    chain.pending_timestamp = genesis + 2 * EPOCH_LENGTH - DAY_LENGTH // 4
    chain.mine()
    assert measure.vote_weight(alice) == weight // 4
