import pytest
from ape import convert, chain
from eth._utils.address import generate_contract_address
from eth_utils import to_checksum_address, to_canonical_address


@pytest.fixture(scope="session")
def yfi(accounts, project):
    dev = accounts[0]
    yield project.Token.deploy("YFI", sender=dev)


@pytest.fixture(scope="session")
def veyfi_and_reward_pool(accounts, project, yfi):
    # calculate the reward pool address to pass to veyfi
    reward_pool_address = to_checksum_address(
        generate_contract_address(
            to_canonical_address(str(accounts[0])), accounts[0].nonce + 1
        )
    )
    veyfi = project.VotingYFI.deploy(yfi, reward_pool_address, sender=accounts[0])
    start_time = (
        chain.pending_timestamp + 7 * 3600 * 24
    )  # MUST offset by a week otherwise token distributed are lost since no lock has been made yet.
    reward_pool = project.RewardPool.deploy(veyfi, start_time, sender=accounts[0])
    assert str(reward_pool) == reward_pool_address, "broken setup"
    yield veyfi, reward_pool


@pytest.fixture(scope="session")
def veyfi(veyfi_and_reward_pool):
    yield veyfi_and_reward_pool[0]


@pytest.fixture(scope="session")
def reward_pool(veyfi_and_reward_pool):
    yield veyfi_and_reward_pool[1]


DAY = 86400
WEEK = 7 * DAY


@pytest.fixture(autouse=True, scope="session")
def setup_time(chain):
    chain.pending_timestamp += WEEK - (
        chain.pending_timestamp - (chain.pending_timestamp // WEEK * WEEK)
    )
    chain.mine()
