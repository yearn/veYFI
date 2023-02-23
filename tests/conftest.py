import pytest
from ape import convert, chain
from eth._utils.address import generate_contract_address
from eth_utils import to_checksum_address, to_canonical_address

DAY = 86400
WEEK = 7 * DAY


@pytest.fixture(scope="session")
def yfi(accounts, project):
    dev = accounts[0]
    yield project.Token.deploy("YFI", sender=dev)


@pytest.fixture(scope="session")
def ve_yfi_and_reward_pool(accounts, project, yfi):
    # calculate the reward pool address to pass to ve_yfi
    reward_pool_address = to_checksum_address(
        generate_contract_address(
            to_canonical_address(str(accounts[0])), accounts[0].nonce + 1
        )
    )
    ve_yfi = project.VotingYFI.deploy(yfi, reward_pool_address, sender=accounts[0])
    start_time = (
        chain.pending_timestamp + 7 * 3600 * 24
    )  # MUST offset by a week otherwise token distributed are lost since no lock has been made yet.
    reward_pool = project.RewardPool.deploy(ve_yfi, start_time, sender=accounts[0])
    assert str(reward_pool) == reward_pool_address, "broken setup"
    yield ve_yfi, reward_pool


@pytest.fixture(scope="session")
def ve_yfi(ve_yfi_and_reward_pool):
    yield ve_yfi_and_reward_pool[0]


@pytest.fixture(scope="session")
def reward_pool(ve_yfi_and_reward_pool):
    yield ve_yfi_and_reward_pool[1]


@pytest.fixture(scope="session")
def o_yfi(accounts, project):
    yield project.OYfi.deploy(sender=accounts[0])


@pytest.fixture(scope="session")
def options(accounts, project, yfi, o_yfi, ve_yfi):
    oft = project.OracleFakeTime.deploy(sender=accounts[0])

    yield project.Options.deploy(
        yfi,
        o_yfi,
        ve_yfi,
        accounts[0],
        oft,
        "0xc26b89a667578ec7b3f11b2f98d6fd15c07c54ba",
        sender=accounts[0],
    )


@pytest.fixture(scope="session")
def ve_yfi_o_yfi_pool(accounts, project, ve_yfi, o_yfi):
    start_time = chain.pending_timestamp + 7 * 3600 * 24
    yield project.OYfiRewardPool.deploy(ve_yfi, o_yfi, start_time, sender=accounts[0])


@pytest.fixture(autouse=True, scope="session")
def setup_time(chain):
    chain.pending_timestamp += WEEK - (
        chain.pending_timestamp - (chain.pending_timestamp // WEEK * WEEK)
    )
    chain.mine()
