import pytest

from eth_utils import to_checksum_address


@pytest.fixture
def gov(accounts):
    yield accounts[0]


@pytest.fixture
def whale_amount():
    yield 10**22


@pytest.fixture
def whale(accounts, yfi, whale_amount):
    a = accounts[1]
    yfi.mint(a, whale_amount, sender=a)
    yield a


@pytest.fixture
def shark_amount():
    yield 10**20


@pytest.fixture
def shark(accounts, yfi, shark_amount):
    a = accounts[2]
    yfi.mint(a, shark_amount, sender=a)
    yield a


@pytest.fixture
def fish_amount():
    yield 10**18


@pytest.fixture
def fish(accounts, yfi, fish_amount):
    a = accounts[3]
    yfi.mint(a, fish_amount, sender=a)
    yield a


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
def yfi(project, gov):
    yield gov.deploy(project.Token, "YFI")


@pytest.fixture
def create_token(project, gov):
    def create_token(name):
        return gov.deploy(project.Token, name)

    yield create_token


@pytest.fixture
def ve_yfi(project, yfi, gov):
    yield gov.deploy(project.VotingEscrow, yfi, "veYFI", "veYFI", "1.0.0")


@pytest.fixture(autouse=True)
def ve_yfi_rewards(project, ve_yfi, yfi, gov):
    ve_yfi_rewards = gov.deploy(project.VeYfiRewards, ve_yfi, yfi, gov)
    ve_yfi.set_reward_pool(ve_yfi_rewards, sender=gov)
    yield ve_yfi_rewards


@pytest.fixture
def gauge_factory(project, gov):
    gauge = gov.deploy(project.Gauge)
    extra_reward = gov.deploy(project.ExtraReward)
    yield gov.deploy(project.GaugeFactory, gauge, extra_reward)


@pytest.fixture
def vote_delegation(project, gov, ve_yfi):
    yield gov.deploy(project.VoteDelegation, ve_yfi)


@pytest.fixture
def registry(project, gov, ve_yfi, yfi, gauge_factory, ve_yfi_rewards):
    yield gov.deploy(project.Registry, ve_yfi, yfi, gauge_factory, ve_yfi_rewards)


@pytest.fixture
def create_vault(project, gov):
    def create_vault():
        return gov.deploy(project.Token, "Yearn vault")

    return create_vault


@pytest.fixture
def create_gauge(registry, gauge_factory, gov, project):
    def create_gauge(vault):
        tx = registry.addVaultToRewards(vault, gov, gov, sender=gov)
        # TODO: Should be `tx.GaugeCreated[0].gauge`
        # https://github.com/ApeWorX/ape/issues/571
        gauge_address = to_checksum_address("0x" + tx.logs[0]["data"][26:])
        return project.Gauge.at(gauge_address)

    yield create_gauge


@pytest.fixture
def create_extra_reward(gauge_factory, gov, project):
    def create_extra_reward(gauge, token):
        tx = gauge_factory.createExtraReward(gauge, token, gov, sender=gov)
        # TODO: Should be `tx.ExtraRewardCreated[0].extraReward`
        # https://github.com/ApeWorX/ape/issues/571
        reward_address = to_checksum_address("0x" + tx.logs[0]["data"][26:])
        return project.ExtraReward.at(reward_address)

    yield create_extra_reward
