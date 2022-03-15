import pytest
from brownie import ZERO_ADDRESS


@pytest.fixture
def gov(accounts):
    yield accounts[0]


@pytest.fixture
def whale_amount():
    yield 10**22


@pytest.fixture
def whale(accounts, yfi, whale_amount):
    yfi.mint(accounts[1], whale_amount)
    yield accounts[1]


@pytest.fixture
def shark_amount():
    yield 10**20


@pytest.fixture
def shark(accounts, yfi, shark_amount):
    yfi.mint(accounts[2], shark_amount)
    yield accounts[2]


@pytest.fixture
def fish_amount():
    yield 10**18


@pytest.fixture
def fish(accounts, yfi, fish_amount):
    yfi.mint(accounts[3], fish_amount)
    yield accounts[3]


@pytest.fixture
def panda(accounts):
    yield accounts[4]


@pytest.fixture
def doggie(accounts):
    yield accounts[5]


@pytest.fixture
def bunny(accounts):
    yield accounts[6]


@pytest.fixture
def yfi(Token, gov):
    yield gov.deploy(Token, "YFI")


@pytest.fixture
def create_token(Token, gov):
    def create_token(name):
        return gov.deploy(Token, name)

    yield create_token


@pytest.fixture
def ve_yfi(VotingEscrow, yfi, gov):
    yield gov.deploy(VotingEscrow, yfi, "veYFI", "veYFI", "1.0.0")


@pytest.fixture
def ve_yfi_rewards(VeYfiRewards, ve_yfi, yfi, gov):
    ve_yfi_rewards = gov.deploy(VeYfiRewards, ve_yfi, yfi, gov)
    ve_yfi.set_reward_pool(ve_yfi_rewards)
    yield ve_yfi_rewards


@pytest.fixture
def gauge_factory(GaugeFactory, Gauge, ExtraReward, gov):
    gauge = gov.deploy(Gauge)
    extra_reward = gov.deploy(ExtraReward)
    yield gov.deploy(GaugeFactory, gauge, extra_reward)


@pytest.fixture
def vote_delegation(VoteDelegation, gov, ve_yfi):
    yield gov.deploy(VoteDelegation, ve_yfi)


@pytest.fixture
def registry(Registry, gov, ve_yfi, yfi, gauge_factory, ve_yfi_rewards):
    yield gov.deploy(Registry, ve_yfi, yfi, gauge_factory, ve_yfi_rewards)


@pytest.fixture
def create_vault(Token, gov):
    def create_vault():
        return gov.deploy(Token, "Yearn vault")

    return create_vault


@pytest.fixture
def create_gauge(registry, gov):
    def create_gauge(vault):
        return registry.addVaultToRewards(vault, gov, gov)

    yield create_gauge


@pytest.fixture
def create_extra_reward(gauge_factory, gov):
    def create_extra_reward(gauge, token):
        return gauge_factory.createExtraReward(gauge, token, gov)

    yield create_extra_reward


@pytest.fixture(scope="function", autouse=True)
def shared_setup(fn_isolation):
    pass
