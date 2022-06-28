import pytest
from ape import convert, chain
from eth._utils.address import generate_contract_address
from eth_utils import to_checksum_address, to_canonical_address


@pytest.fixture(scope="session")
def yfi(accounts, project):
    dev = accounts[0]
    token = project.Token.deploy("YFI", sender=dev)
    supply = convert("36_666 ether", int)
    token.mint(dev, supply, sender=dev)
    assert token.balanceOf(dev) == supply
    return token


@pytest.fixture(scope="session")
def veyfi_and_reward_pool(accounts, project, yfi):
    # calculate the reward pool address to pass to veyfi
    reward_pool_address = to_checksum_address(
        generate_contract_address(
            to_canonical_address(str(accounts[0])), accounts[0].nonce + 1
        )
    )
    veyfi = project.VotingYFI.deploy(yfi, reward_pool_address, sender=accounts[0])
    start_time = chain.pending_timestamp
    reward_pool = project.RewardPool.deploy(veyfi, start_time, sender=accounts[0])
    assert str(reward_pool) == reward_pool_address, "broken setup"
    return veyfi, reward_pool


@pytest.fixture(scope="session")
def veyfi(veyfi_and_reward_pool):
    return veyfi_and_reward_pool[0]


@pytest.fixture(scope="session")
def reward_pool(veyfi_and_reward_pool):
    return veyfi_and_reward_pool[1]
