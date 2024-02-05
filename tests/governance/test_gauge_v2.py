import ape
from ape import Contract
import pytest

WEEK_LENGTH = 7 * 24 * 60 * 60
EPOCH_LENGTH = 2 * WEEK_LENGTH
UNIT = 10**18
MAX = 2**256 - 1

@pytest.fixture
def ychad(accounts):
    return accounts['0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52']

@pytest.fixture
def locking_token():
    return Contract('0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e')

@pytest.fixture
def voting_escrow():
    return Contract('0x90c1f9220d90d3966FbeE24045EDd73E1d588aD5')

@pytest.fixture
def reward():
    return Contract('0x41252E8691e964f7DE35156B68493bAb6797a275')

@pytest.fixture
def epoch():
    return 1

@pytest.fixture
def genesis(chain, epoch):
    return chain.pending_timestamp - epoch * EPOCH_LENGTH

@pytest.fixture
def measure(project, deployer, voting_escrow, genesis):
    return project.Measure.deploy(genesis, voting_escrow, sender=deployer)

@pytest.fixture
def minter(project, accounts, deployer, voting_escrow, genesis, reward):
    minter = project.Minter.deploy(genesis, reward, voting_escrow, 0, sender=deployer)
    reward.transferOwnership(minter, sender=accounts[reward.owner()])
    return minter

@pytest.fixture
def burner(project, deployer, reward):
    return project.Burner.deploy(reward, sender=deployer)

@pytest.fixture
def controller(project, deployer, genesis, reward, measure, minter, burner):
    controller = project.GaugeController.deploy(genesis, reward, measure, minter, burner, sender=deployer)
    minter.set_controller(controller, sender=deployer)
    return controller
 
@pytest.fixture
def implementation(project, deployer):
    return project.GaugeV2.deploy(sender=deployer)

@pytest.fixture
def factory(project, deployer, controller, implementation):
    factory = project.GaugeFactory.deploy(controller, sender=deployer)
    factory.set_implementation(implementation, sender=deployer)
    return factory

@pytest.fixture
def vault(project, deployer):
    return project.MockToken.deploy(sender=deployer)

@pytest.fixture
def gauge(project, deployer, factory, vault):
    gauge = factory.deploy_gauge(vault, sender=deployer).return_value
    return project.GaugeV2.at(gauge)

def test_reinitialize(deployer, controller, implementation, vault, gauge):
    with ape.reverts():
        implementation.initialize(vault, deployer, controller, b"", sender=deployer)

    with ape.reverts():
        gauge.initialize(vault, deployer, controller, b"", sender=deployer)

def test_rewards(chain, deployer, alice, ychad, locking_token, voting_escrow, genesis, measure, controller, vault, gauge):
    locking_token.transfer(alice, UNIT, sender=ychad)
    locking_token.approve(voting_escrow, MAX, sender=alice)
    assert measure.vote_weight(alice) == 0
    voting_escrow.modify_lock(UNIT, chain.pending_timestamp + 200 * WEEK_LENGTH, sender=alice)
    assert measure.vote_weight(alice) > 0

    controller.whitelist(gauge, True, sender=deployer)

    vault.mint(alice, 2 * UNIT, sender=alice)
    vault.approve(gauge, 2 * UNIT, sender=alice)
    gauge.deposit(2 * UNIT, sender=alice)
    assert gauge.balanceOf(alice) == 2 * UNIT

    chain.pending_timestamp += WEEK_LENGTH
    controller.vote([gauge], [10_000], sender=alice)
    chain.pending_timestamp = genesis + 2 * EPOCH_LENGTH + WEEK_LENGTH
    gauge.getReward(alice, sender=alice)
    emission = controller.emission()[2]
    rate = emission * UNIT // EPOCH_LENGTH
    assert gauge.rewardRate() == rate
    assert abs(gauge.rewardPerTokenStored() - emission // 4) <= 1

    chain.pending_timestamp = genesis + 3 * EPOCH_LENGTH
    gauge.getReward(alice, sender=alice)
    assert gauge.rewardRate() == 0
    assert gauge.rewardPerTokenStored() == emission // 2
