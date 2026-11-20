import ape
from math import sqrt
import pytest

WEEK_LENGTH = 7 * 24 * 60 * 60
EPOCH_LENGTH = 2 * WEEK_LENGTH
UNIT = 10**18
MAX = 2**256 - 1
ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'

@pytest.fixture
def controller(accounts):
    return accounts[3]

@pytest.fixture
def locking_token(project, deployer):
    return project.MockToken.deploy(sender=deployer)

@pytest.fixture
def reward_token(project, deployer):
    return project.dYFI.deploy(sender=deployer)

@pytest.fixture
def voting_escrow(project, deployer, locking_token):
    return project.VotingYFI.deploy(locking_token, ZERO_ADDRESS, sender=deployer)

@pytest.fixture
def genesis(chain):
    return chain.pending_timestamp // WEEK_LENGTH * WEEK_LENGTH

@pytest.fixture
def minter(project, deployer, controller, reward_token, voting_escrow, genesis):
    minter = project.Minter.deploy(genesis, reward_token, voting_escrow, 0, sender=deployer)
    minter.set_controller(controller, sender=deployer)
    reward_token.transferOwnership(minter, sender=deployer)
    return minter

def test_minter(chain, deployer, alice, controller, locking_token, reward_token, voting_escrow, minter):
    locking_token.mint(alice, 2 * UNIT, sender=deployer)
    locking_token.approve(voting_escrow, MAX, sender=alice)
    voting_escrow.modify_lock(2 * UNIT, chain.pending_timestamp + 500 * WEEK_LENGTH, sender=alice)

    # epoch 2 - mint epoch 1 rewards
    chain.pending_timestamp += 2 * EPOCH_LENGTH
    chain.mine()
    supply = voting_escrow.totalSupply() / UNIT
    expected = sqrt(supply) * 12 * 14 / 365
    preview = minter.preview(1)
    assert abs(expected-preview / UNIT) <= preview / UNIT / 10**12

    # only controller can mint
    with ape.reverts():
        minter.mint(1, sender=alice)

    assert minter.last_epoch() == 0
    assert reward_token.balanceOf(controller) == 0
    assert minter.mint(1, sender=controller).return_value == preview
    assert minter.last_epoch() == 1
    assert reward_token.balanceOf(controller) == preview

    # cant mint more than once
    with ape.reverts():
        minter.mint(1, sender=controller)

    # cant mint future epoch
    with ape.reverts():
        minter.mint(2, sender=controller)

def test_minter_gap(chain, deployer, alice, controller, locking_token, reward_token, voting_escrow, minter):
    locking_token.mint(alice, 2 * UNIT, sender=deployer)
    locking_token.approve(voting_escrow, MAX, sender=alice)
    voting_escrow.modify_lock(2 * UNIT, chain.pending_timestamp + 500 * WEEK_LENGTH, sender=alice)

    chain.pending_timestamp += 3 * EPOCH_LENGTH
    chain.mine()

    # cant mint epoch 2 before minting 1
    with ape.reverts():
        minter.mint(2, sender=controller)

    mint1 = minter.mint(1, sender=controller).return_value
    mint2 = minter.mint(2, sender=controller).return_value
    assert mint1 > 0 and mint2 > 0
    assert reward_token.balanceOf(controller) == mint1 + mint2

def test_set_scaling_factor(chain, deployer, alice, controller, locking_token, voting_escrow, minter):
    locking_token.mint(alice, 2 * UNIT, sender=deployer)
    locking_token.approve(voting_escrow, MAX, sender=alice)
    voting_escrow.modify_lock(2 * UNIT, chain.pending_timestamp + 500 * WEEK_LENGTH, sender=alice)

    chain.pending_timestamp += 2 * EPOCH_LENGTH
    chain.mine()

    # cant set scaling factor if minting is behind
    with ape.reverts():
        minter.set_scaling_factor(240_000, sender=deployer)

    minter.mint(1, sender=controller)

    # only management can set scaling factor
    with ape.reverts():
        minter.set_scaling_factor(240_000, sender=alice)

    assert minter.scaling_factor() == 120_000
    expected = minter.preview(2) * 2
    minter.set_scaling_factor(240_000, sender=deployer)
    assert minter.scaling_factor() == 240_000
    assert minter.preview(2) == expected
    
    chain.pending_timestamp += EPOCH_LENGTH
    assert minter.mint(2, sender=controller).return_value == expected

def test_set_controller(deployer, alice, controller, minter):
    # only management can set controller
    with ape.reverts():
        minter.set_controller(alice, sender=alice)

    assert minter.controller() == controller
    minter.set_controller(alice, sender=deployer)
    assert minter.controller() == alice

def test_transfer_token_ownership(deployer, alice, minter, reward_token):
    # only management can transfer ownership
    with ape.reverts():
        minter.transfer_token_ownership(alice, sender=alice)
    with ape.reverts():
        reward_token.mint(alice, UNIT, sender=alice)

    assert reward_token.owner() == minter
    minter.transfer_token_ownership(alice, sender=deployer)
    assert reward_token.owner() == alice
    reward_token.mint(alice, UNIT, sender=alice)

def test_transfer_management(deployer, alice, bob, minter):
    assert minter.management() == deployer
    assert minter.pending_management() == ZERO_ADDRESS
    with ape.reverts():
        minter.set_management(alice, sender=alice)
    
    minter.set_management(alice, sender=deployer)
    assert minter.pending_management() == alice

    with ape.reverts():
        minter.accept_management(sender=bob)

    minter.accept_management(sender=alice)
    assert minter.management() == alice
    assert minter.pending_management() == ZERO_ADDRESS

def test_burner(project, deployer, alice):
    token = project.dYFI.deploy(sender=deployer)
    burner = project.Burner.deploy(token, sender=deployer)
    token.mint(alice, UNIT, sender=deployer)
    token.approve(burner, MAX, sender=alice)

    assert token.balanceOf(alice) == UNIT
    burner.burn(1, UNIT, sender=alice)
    assert token.balanceOf(alice) == 0
